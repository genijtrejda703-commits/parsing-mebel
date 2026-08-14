"""Turn parsed page geometry into QA-ready product records.

A product = one column of a reconstructed price matrix (its dimension / variant
code). Its variations = the finish rows down that column, which yields the
min-max price range.
"""
import uuid
from datetime import datetime, timezone

from anomaly import MicrogradAnomalyModel, featurize, weak_label
from pipeline import describe_column

ACCEPT_CONF = 0.45
FLAG_CONF = 0.60


def collect_training_set(pages):
    X, Y = [], []
    for pg in pages:
        for c in pg["prices"]:
            f = featurize(c, pg["width"], pg["height"], c.get("median_size", 7.0))
            lab = weak_label(c)
            if lab is not None:
                X.append(f)
                Y.append(lab)
    return X, Y


def score_pages(pages, model):
    feats, refs = [], []
    for pg in pages:
        for c in pg["prices"]:
            feats.append(featurize(c, pg["width"], pg["height"], c.get("median_size", 7.0)))
            refs.append(c)
    if not feats:
        return 0
    conf, margin = model.score(feats)
    for c, cf, mg in zip(refs, conf, margin):
        c["confidence"] = float(round(cf, 4))
        c["margin"] = float(round(mg, 4))
    return len(refs)


def _bbox_union(boxes):
    xs0 = min(b[0] for b in boxes)
    ys0 = min(b[1] for b in boxes)
    xs1 = max(b[2] for b in boxes)
    ys1 = max(b[3] for b in boxes)
    return [round(xs0, 2), round(ys0, 2), round(xs1, 2), round(ys1, 2)]


def build_products(pages, doc_meta):
    """Assemble products + return (products, stats)."""
    products = []
    rejected = 0
    anomaly_samples = []
    for pg in pages:
        category = pg.get("section_title") or pg.get("running_header")
        section = pg["side_labels"][0] if pg.get("side_labels") else None
        for table in pg["tables"]:
            for col_x, cells in table["cols"].items():
                cells = sorted(cells, key=lambda c: c["y0"])
                dimension, code, raw_chain, chain = describe_column(cells)
                variations, boxes, confs = [], [], []
                for c in cells:
                    val = c.get("value")
                    if val is None:
                        continue
                    finish = c["left"]["text"].strip() if c.get("left") else None
                    variations.append({
                        "finish": finish,
                        "price": val,
                        "raw": c["text"],
                        "bbox": [c["x0"], c["y0"], c["x1"], c["y1"]],
                        "bbox_row_label": ([c["left"]["x0"], c["left"]["y0"],
                                            c["left"]["x1"], c["left"]["y1"]]
                                           if c.get("left") else None),
                        "confidence": c.get("confidence", 0.5),
                        "row_peers": c.get("row_peers", 0),
                        "col_peers": c.get("col_peers", 0),
                    })
                    boxes.append([c["x0"], c["y0"], c["x1"], c["y1"]])
                    confs.append(c.get("confidence", 0.5))
                if not variations:
                    continue
                mean_conf = sum(confs) / len(confs)
                if mean_conf < ACCEPT_CONF:
                    rejected += len(variations)
                    if len(anomaly_samples) < 25:
                        anomaly_samples.append({
                            "page": pg["page"], "text": variations[0]["raw"],
                            "confidence": round(mean_conf, 3),
                            "reason": "low micrograd score (isolated / no column header)",
                            "row_peers": variations[0]["row_peers"],
                        })
                    continue
                prices = [v["price"] for v in variations]
                header_boxes = [[b["x0"], b["y0"], b["x1"], b["y1"]] for b in chain]
                products.append({
                    "id": str(uuid.uuid4()),
                    "factory_id": doc_meta["factory_id"],
                    "factory": doc_meta["factory"],
                    "doc_id": doc_meta["doc_id"],
                    "doc_name": doc_meta["doc_name"],
                    "collection": doc_meta.get("collection"),
                    "section": section,
                    "page": pg["page"],
                    "page_width": pg["width"],
                    "page_height": pg["height"],
                    "model_name": pg.get("model_name") or "Unassigned",
                    "category": category,
                    "dimension": dimension,
                    "variant_code": code,
                    "col_header_raw": raw_chain,
                    "currency": "EUR",
                    "price_min": min(prices),
                    "price_max": max(prices),
                    "n_variations": len(variations),
                    "variations": variations,
                    "bbox": _bbox_union(boxes + (header_boxes or boxes)),
                    "bbox_cells": boxes,
                    "bbox_col_header": header_boxes,
                    "confidence": round(mean_conf, 4),
                    "anomaly": mean_conf < FLAG_CONF,
                    "status": "pending",
                    "reviewer_notes": "",
                    "embedded": False,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
    stats = {"products": len(products), "rejected_cells": rejected,
             "anomaly_samples": anomaly_samples}
    return products, stats


def run_micrograd(pages, log=None):
    """Train the micrograd anomaly net on this document's own geometry."""
    X, Y = collect_training_set(pages)
    model = MicrogradAnomalyModel()
    pos = sum(1 for y in Y if y > 0)
    neg = len(Y) - pos
    if log:
        log(f"micrograd training set: {len(X)} weakly-labelled cells "
            f"({pos} valid / {neg} anomalous), 8 spatial features")
    ok = model.train(X, Y, log=log)
    if not ok and log:
        log("micrograd: not enough labelled geometry, falling back to margin=0 prior")
    n = score_pages(pages, model)
    if log:
        log(f"micrograd scored {n} price candidates")
    return model, {"trained": ok, "n_labelled": len(X), "pos": pos, "neg": neg,
                   "loss_curve": model.loss_curve, "acc_curve": model.acc_curve}
