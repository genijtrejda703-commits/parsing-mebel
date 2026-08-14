"""Turn parsed page geometry into QA-ready product records.

A product = one column of a reconstructed price matrix (its dimension / variant
code). Its variations = the finish rows down that column, which yields the
min-max price range.
"""
import hashlib
import uuid
from datetime import datetime, timezone

from anomaly import MicrogradAnomalyModel, NUM_RE, featurize, weak_label
from pipeline import describe_column, norm

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


def rejection_reason(cand):
    """Human-readable Russian explanation for why a price cell was discarded."""
    above = cand.get("above")
    if (cand.get("row_peers") or 0) <= 1:
        return "Изолированная ячейка — нет соседей в строке"
    if not cand.get("left"):
        return "Нет подписи строки слева"
    if not above:
        return "Нет заголовка столбца сверху"
    if NUM_RE.match(str(above.get("text", "")).strip()):
        return "Заголовок столбца — тоже число (признак оглавления)"
    return "Ниже порога уверенности micrograd"


def build_products(pages, doc_meta, collect_rejected=False):
    """Assemble products + return (products, stats)."""
    products = []
    rejected = 0
    anomaly_samples = []
    rejected_records = []
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
                    if collect_rejected:
                        for c in cells:
                            if c.get("value") is None:
                                continue
                            above = c.get("above")
                            left = c.get("left")
                            rejected_records.append({
                                "page": pg["page"],
                                "text": c["text"],
                                "value": c.get("value"),
                                "bbox": [c["x0"], c["y0"], c["x1"], c["y1"]],
                                "confidence": round(float(c.get("confidence", 0.5)), 4),
                                "margin": c.get("margin"),
                                "row_peers": c.get("row_peers", 0),
                                "col_peers": c.get("col_peers", 0),
                                "above_text": (above or {}).get("text"),
                                "left_text": (left or {}).get("text"),
                                "model_name": pg.get("model_name"),
                                "category": category,
                                "reason": rejection_reason(c),
                                "zone": "matrix",
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
             "anomaly_samples": anomaly_samples,
             "rejected_records": rejected_records}
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



# --------------------------------------------------------------------------- #
# Directive 1: Position -> Variant -> Price
# --------------------------------------------------------------------------- #
# A POSITION is one model exactly as printed (e.g. "505 UP System"), deduped by
# normalised name within a factory. A VARIANT-PRICE is a single cell of the
# reconstructed matrix: one (variant_code, dimension, finish) -> one price, with
# BOTH raw geometry chains kept (above-chain = dimension/variant code, left block
# = finish, per the Molteni-inverted semantics). One position expands into its
# whole variant list across all listini it appears in.

def _vp_id(doc_id, page, bbox):
    """Deterministic id for a price cell so re-ingest is idempotent."""
    key = f"{doc_id}|{page}|{bbox}"
    return hashlib.sha1(key.encode()).hexdigest()[:20]


def flatten_variants(products):
    """Explode column-level products into variant-price rows + position seeds.

    Returns (variant_prices, position_seeds) where position_seeds is keyed by
    normalised model name and carries the provenance needed to upsert a position.
    """
    vps = []
    seeds = {}
    ts = datetime.now(timezone.utc).isoformat()
    for p in products:
        printed = (p.get("model_name") or "Unassigned").strip()
        nkey = norm(printed) or "UNASSIGNED"
        seed = seeds.setdefault(nkey, {
            "norm_name": nkey, "names": {}, "categories": set(),
            "sections": set(), "collections": set(),
            "docs": {}, "n_variants": 0, "prices": [], "confs": [],
        })
        seed["names"][printed] = seed["names"].get(printed, 0) + 1
        if p.get("category"):
            seed["categories"].add(p["category"])
        if p.get("section"):
            seed["sections"].add(p["section"])
        if p.get("collection"):
            seed["collections"].add(p["collection"])
        seed["docs"].setdefault(p["doc_id"], p.get("doc_name"))
        for v in (p.get("variations") or []):
            if v.get("price") is None:
                continue
            vid = _vp_id(p["doc_id"], p["page"], v.get("bbox"))
            vps.append({
                "id": vid,
                "norm_name": nkey,
                "position_name": printed,
                "factory_id": p["factory_id"],
                "factory": p["factory"],
                "doc_id": p["doc_id"],
                "doc_name": p["doc_name"],
                "collection": p.get("collection"),
                "page": p["page"],
                "page_width": p.get("page_width"),
                "page_height": p.get("page_height"),
                "variant_code": p.get("variant_code"),
                "dimension": p.get("dimension"),
                "finish": v.get("finish"),
                "price": v.get("price"),
                "currency": p.get("currency", "EUR"),
                "raw": v.get("raw"),
                "bbox": v.get("bbox"),
                "bbox_row_label": v.get("bbox_row_label"),
                "bbox_col_header": p.get("bbox_col_header"),
                # both raw chains stored, per invariant
                "above_chain_raw": p.get("col_header_raw"),
                "left_raw": v.get("finish"),
                "confidence": float(v.get("confidence", p.get("confidence", 0.5))),
                "status": "pending",
                "created_at": ts,
            })
            seed["n_variants"] += 1
            seed["prices"].append(v.get("price"))
            seed["confs"].append(float(v.get("confidence", p.get("confidence", 0.5))))
    return vps, seeds
