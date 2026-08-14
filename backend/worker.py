"""DS sidecar: FastAPI + in-worker async queue, tracked in MongoDB.

Replaces Redis/Celery with a single asyncio queue draining into a 1-thread
executor (CPU-bound PyMuPDF / torch work is serialised on purpose). Every job
streams its progress into the `tasks` collection, which the Next.js Task Monitor
polls - so the UI sees live parsing status without a broker.
"""
import asyncio
import os
import shutil
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import numpy as np
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from pymongo import UpdateOne

import db
import inventory
from assemble import build_products, run_micrograd
from dropbox_fetch import (cleanup_archive, download_folder, extract, list_pdfs,
                           list_spreadsheets, zip_path_for)
from pipeline import parse_pdf, render_page_png

app = FastAPI(title="DataHub DS Worker")
JOBQ: asyncio.Queue = asyncio.Queue()
EXEC = ThreadPoolExecutor(max_workers=1)
VEC_CACHE = {"stamp": None, "ids": [], "M": None}
LOOP = None  # captured at startup for thread -> queue hand-off


def now():
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# task bookkeeping
# --------------------------------------------------------------------------- #
def new_task(kind, title, meta=None):
    tid = str(uuid.uuid4())
    db.tasks.insert_one({
        "id": tid, "type": kind, "title": title, "status": "queued",
        "progress": 0, "events": [{"ts": now(), "msg": "queued", "level": "info"}],
        "stats": {}, "meta": meta or {}, "result": {},
        "created_at": now(), "updated_at": now(),
    })
    return tid


def log(tid, msg, level="info"):
    db.tasks.update_one({"id": tid}, {
        "$push": {"events": {"$each": [{"ts": now(), "msg": msg, "level": level}],
                             "$slice": -500}},
        "$set": {"updated_at": now()},
    })


def progress(tid, pct, stats=None):
    upd = {"progress": round(min(max(pct, 0), 100), 1), "updated_at": now()}
    if stats:
        for k, v in stats.items():
            upd[f"stats.{k}"] = v
    db.tasks.update_one({"id": tid}, {"$set": upd})


def finish(tid, status, result=None, msg=None):
    upd = {"status": status, "updated_at": now(),
           "progress": 100 if status == "done" else None}
    upd = {k: v for k, v in upd.items() if v is not None}
    if result is not None:
        upd["result"] = result
    db.tasks.update_one({"id": tid}, {"$set": upd})
    if msg:
        log(tid, msg, "success" if status == "done" else "error")


def start(tid):
    db.tasks.update_one({"id": tid}, {"$set": {"status": "running", "updated_at": now()}})


# --------------------------------------------------------------------------- #
# jobs
# --------------------------------------------------------------------------- #
def job_scan(tid, payload):
    start(tid)
    url = payload["url"]
    L = lambda m: log(tid, m)
    L("connecting to Dropbox shared folder")
    zp = download_folder(url, L)
    progress(tid, 70)
    files = list_pdfs(zp)
    pl = [f for f in files if f["is_price_list"]]
    L(f"archive traversed: {len(files)} PDFs found, {len(pl)} look like price lists")
    finish(tid, "done", {"files": files, "zip": zp},
           f"scan complete - {len(files)} PDFs available for ingestion")


def _ingest_one(tid, path, name, factory, factory_id, max_pages, base_pct, span_pct):
    L = lambda m: log(tid, m)
    doc_id = str(uuid.uuid4())
    collection = os.path.splitext(name)[0].replace("_", " ")
    L(f"opening {name}")
    # id must be STABLE across re-ingests, otherwise old products get orphaned
    db.documents.update_one({"path": path}, {
        "$setOnInsert": {"id": doc_id, "created_at": now()},
        "$set": {"name": name, "path": path, "factory": factory,
                 "factory_id": factory_id, "collection": collection,
                 "status": "parsing"}}, upsert=True)
    doc_rec = db.documents.find_one({"path": path})
    doc_id = doc_rec["id"]

    def on_page(i, total, npr):
        progress(tid, base_pct + span_pct * 0.7 * i / max(total, 1))
        if i % 40 == 0 or i == total:
            log(tid, f"{name}: spatial parse {i}/{total} pages, {npr} price blocks on page")

    t0 = time.time()
    pages = parse_pdf(path, max_pages=max_pages, on_page=on_page)
    L(f"{name}: PyMuPDF geometry extracted from {len(pages)} pages in {time.time() - t0:.1f}s")
    progress(tid, base_pct + span_pct * 0.72)

    model, mg = run_micrograd(pages, log=L)
    progress(tid, base_pct + span_pct * 0.88)

    prods, stats = build_products(pages, {
        "factory_id": factory_id, "factory": factory, "doc_id": doc_id,
        "doc_name": name, "collection": collection})
    db.products.delete_many({"doc_id": doc_id})
    for i in range(0, len(prods), 500):
        db.products.insert_many(prods[i:i + 500])
    n_flag = sum(1 for p in prods if p["anomaly"])

    # ---- Directive 1: derive positions + variant-prices ----
    from assemble import flatten_variants
    vps, seeds = flatten_variants(prods)
    db.variant_prices.delete_many({"doc_id": doc_id})
    _upsert_positions(factory_id, factory, seeds)
    pos_map = {p["norm_name"]: p["id"] for p in
               db.positions.find({"factory_id": factory_id}, {"norm_name": 1, "id": 1})}
    for v in vps:
        v["position_id"] = pos_map.get(v["norm_name"])
    for i in range(0, len(vps), 1000):
        db.variant_prices.insert_many(vps[i:i + 1000])
    L(f"{name}: {len(prods)} matrix columns -> {len(vps)} variant-prices across "
      f"{len(seeds)} positions, {stats['rejected_cells']} cells rejected, "
      f"{n_flag} flagged for review")

    # ---- coverage for Directive 2 (captured in this single parse) ----
    pages_with_prices = sum(1 for pg in pages if pg["prices"])
    pages_with_matrix = sum(1 for pg in pages if pg["tables"])
    parsed_pages = {p["page"] for p in prods}
    coverage = {
        "pages_total": len(pages),
        "pages_with_prices": pages_with_prices,
        "pages_with_matrix": pages_with_matrix,
        "pages_parsed": len(parsed_pages),
        "pages_skipped": max(pages_with_matrix - len(parsed_pages), 0),
        "positions": len(seeds),
        "variant_prices": len(vps),
        "rejected_cells": stats["rejected_cells"],
    }
    db.documents.update_one({"id": doc_id}, {"$set": {
        "status": "parsed", "pages": len(pages), "products": len(prods),
        "positions": len(seeds), "variant_prices": len(vps),
        "rejected_cells": stats["rejected_cells"], "coverage": coverage,
        "micrograd": {k: v for k, v in mg.items() if k != "acc_curve"},
        "anomaly_samples": stats["anomaly_samples"], "parsed_at": now()}})
    return len(prods), len(vps), stats["rejected_cells"], mg


def _upsert_positions(factory_id, factory, seeds):
    """Upsert one position per normalised model name within the factory.

    Dedupe invariant: the same model across different listini is ONE position.
    The exact printed name is resolved in the rollup (most frequent printed form).
    """
    for nkey, seed in seeds.items():
        db.positions.update_one(
            {"factory_id": factory_id, "norm_name": nkey},
            {"$setOnInsert": {"id": str(uuid.uuid4()), "factory_id": factory_id,
                              "factory": factory, "norm_name": nkey,
                              "status": "pending", "reviewer_notes": "",
                              "created_at": now()},
             "$set": {"updated_at": now()},
             "$addToSet": {
                 "categories": {"$each": list(seed["categories"])},
                 "sections": {"$each": list(seed["sections"])},
                 "collections": {"$each": list(seed["collections"])},
                 "name_variants": {"$each": list(seed["names"].keys())},
                 "doc_ids": {"$each": list(seed["docs"].keys())}}},
            upsert=True)


def _rollup_positions(factory_id, log=None):
    """Recompute per-position rollups from variant_prices; prune empty positions."""
    agg = db.variant_prices.aggregate([
        {"$match": {"factory_id": factory_id}},
        {"$group": {"_id": "$position_id",
                    "n": {"$sum": 1},
                    "pmin": {"$min": "$price"},
                    "pmax": {"$max": "$price"},
                    "conf": {"$avg": "$confidence"},
                    "names": {"$push": "$position_name"},
                    "docs": {"$addToSet": "$doc_id"},
                    "pages": {"$addToSet": "$page"}}}],
        allowDiskUse=True)
    live = set()
    for g in agg:
        pid = g["_id"]
        if not pid:
            continue
        live.add(pid)
        # canonical printed name = most frequent among this position's cells
        counts = {}
        for nm in g["names"]:
            counts[nm] = counts.get(nm, 0) + 1
        canonical = max(counts.items(), key=lambda kv: kv[1])[0] if counts else None
        conf = float(g.get("conf") or 0.0)
        db.positions.update_one({"id": pid}, {"$set": {
            "name": canonical,
            "n_variants": int(g["n"]),
            "price_min": g.get("pmin"),
            "price_max": g.get("pmax"),
            "avg_confidence": round(conf, 4),
            "flagged": conf < 0.60,
            "n_docs": len(g.get("docs") or []),
            "n_pages": len(g.get("pages") or []),
            "updated_at": now()}})
    # drop positions that no longer have any variant-prices
    removed = db.positions.delete_many(
        {"factory_id": factory_id, "id": {"$nin": list(live)}}).deleted_count
    if log:
        log(f"каталог позиций пересчитан: {len(live)} позиций активно, "
            f"{removed} пустых удалено")
    return len(live)


def job_ingest(tid, payload):
    start(tid)
    L = lambda m: log(tid, m)
    factory = payload.get("factory") or "Molteni & C"
    max_pages = payload.get("max_pages") or None
    db.factories.update_one({"name": factory}, {"$setOnInsert": {
        "id": str(uuid.uuid4()), "name": factory, "created_at": now()}}, upsert=True)
    factory_id = db.factories.find_one({"name": factory})["id"]

    files = []
    zp = None
    if payload.get("source") == "dropbox":
        zp = download_folder(payload["url"], L)
        progress(tid, 8)
        files = extract(zp, payload.get("rels") or [], L)
    else:
        for p in payload.get("paths") or []:
            if os.path.exists(p):
                files.append({"path": p, "name": os.path.basename(p)})
    if not files:
        finish(tid, "error", {}, "no PDFs resolved from the request")
        return

    L(f"ingestion queue: {len(files)} document(s) for {factory}")
    total_prod = total_var = total_rej = 0
    last_mg = {}
    base = 10.0
    span = 84.0 / len(files)
    for i, f in enumerate(files):
        try:
            np_, nv_, nr_, mg = _ingest_one(tid, f["path"], f["name"], factory,
                                            factory_id, max_pages,
                                            base + i * span, span)
            total_prod += np_
            total_var += nv_
            total_rej += nr_
            last_mg = mg
            progress(tid, base + (i + 1) * span,
                     {"products": total_prod, "variant_prices": total_var,
                      "rejected": total_rej,
                      "docs_done": i + 1, "docs_total": len(files),
                      "micrograd_loss": mg.get("loss_curve", [])[-20:],
                      "micrograd_acc": mg.get("acc_curve", [])[-20:]})
        except Exception as e:
            log(tid, f"{f['name']} failed: {type(e).__name__}: {e}", "error")
    n_positions = _rollup_positions(factory_id, L)
    progress(tid, 98, {"positions": n_positions, "variant_prices": total_var})
    if zp and payload.get("cleanup"):
        cleanup_archive(zp, L)
    finish(tid, "done", {"products": total_prod, "positions": n_positions,
                         "variant_prices": total_var, "rejected": total_rej,
                         "micrograd": last_mg},
           f"готово — {n_positions} позиций, {total_var} вариантов-цен, "
           f"{total_rej} аномалий отсеяно")


def job_embed(tid, payload):
    start(tid)
    L = lambda m: log(tid, m)
    import embeddings as E
    L("warming dual CLIP encoders (first run downloads nothing - cached)")
    E.warm(L)
    q = {"embedded": {"$ne": True}}
    if payload.get("factory_id"):
        q["factory_id"] = payload["factory_id"]
    # only index trustworthy extractions - front-matter prose would otherwise
    # pollute the vector space and outrank real products
    min_conf = payload.get("min_conf", 0.6)
    if min_conf:
        q["confidence"] = {"$gte": float(min_conf)}
    total = db.products.count_documents(q)
    if not total:
        finish(tid, "done", {"embedded": 0}, "nothing to embed - all products already vectorised")
        return
    L(f"embedding {total} products into the 512-d CLIP space")
    done = 0
    B = 128
    while True:
        batch = list(db.products.find(q, limit=B))
        if not batch:
            break
        # information-poor rows (e.g. "TURNER. Sofas") become hubs that rank high
        # for every query, so they are excluded from the vector index
        texts, keep = [], []
        for p in batch:
            t = E.product_text(p)
            if t.count(".") >= 2 or len(t) >= 40:
                keep.append(p)
                texts.append(t)
        if texts:
            vecs = E.encode_text(texts)
            ops = []
            for p, v, t in zip(keep, vecs, texts):
                ops.append(UpdateOne({"product_id": p["id"]}, {"$set": {
                    "id": str(uuid.uuid4()), "product_id": p["id"],
                    "factory_id": p.get("factory_id"), "doc_id": p.get("doc_id"),
                    "kind": "text", "dim": int(v.shape[0]), "text": t,
                    "vector": [float(x) for x in v], "created_at": now()}}, upsert=True))
            db.embeddings_col.bulk_write(ops, ordered=False)
        db.products.update_many({"id": {"$in": [p["id"] for p in batch]}},
                                {"$set": {"embedded": True}})
        done += len(batch)
        progress(tid, 100.0 * done / total, {"embedded": done})
        if done % 1024 < B:
            L(f"vectorised {done}/{total}")
    VEC_CACHE["stamp"] = None
    try:
        C = _load_vectors()
        M = C["M"]
        L(f"vector index warm: {M.shape[0]} x {M.shape[1] if M.ndim > 1 else 0} float32, mean-centred copy ready")
    except Exception as e:
        L(f"vector cache warm skipped: {e}")
    finish(tid, "done", {"embedded": done}, f"{done} products embedded (512-d, CPU)")


def job_photos(tid, payload):
    """Map every product to the vector illustration sitting above its matrix."""
    start(tid)
    L = lambda m: log(tid, m)
    from photos import map_document
    docs = list(db.documents.find({}, {"_id": 0}))
    if not docs:
        finish(tid, "done", {"photos": 0}, "нет документов для обработки")
        return
    L(f"сканирование векторной графики: {len(docs)} документ(ов)")
    total = 0
    for n, d in enumerate(docs):
        if not os.path.exists(d.get("path", "")):
            L(f"{d.get('name')}: файл недоступен, пропуск")
            continue
        prods = list(db.products.find({"doc_id": d["id"]},
                                      {"_id": 0, "id": 1, "page": 1, "bbox": 1}))
        by_page = {}
        for p in prods:
            by_page.setdefault(p.get("page", 0), []).append((p["id"], p.get("bbox")))
        L(f"{d['name']}: {len(prods)} позиций на {len(by_page)} страницах")

        def on_page(i, t, k, _n=n, _name=d["name"]):
            progress(tid, 100.0 * (_n + i / max(t, 1)) / len(docs))
            if i % 100 == 0:
                log(tid, f"{_name}: страница {i}/{t}, найдено иллюстраций {k}")

        photos = map_document(d["path"], by_page, on_page)
        ops = [UpdateOne({"id": pid}, {"$set": {"photo": ph}})
               for pid, ph in photos.items()]
        for i in range(0, len(ops), 1000):
            db.products.bulk_write(ops[i:i + 1000], ordered=False)
        total += len(photos)
        L(f"{d['name']}: {len(photos)} позиций связано с иллюстрацией")
        progress(tid, 100.0 * (n + 1) / len(docs), {"photos": total})
    finish(tid, "done", {"photos": total},
           f"готово — {total} иллюстраций сопоставлено с матрицами цен")


def job_anomalies(tid, payload):
    """Re-parse geometry and persist every discarded price cell with its reason.

    Deliberately does NOT touch products or embeddings: it only rebuilds the
    audit trail of what micrograd threw away.
    """
    start(tid)
    L = lambda m: log(tid, m)
    from assemble import build_products, run_micrograd
    from pipeline import parse_pdf
    docs = list(db.documents.find({}, {"_id": 0}))
    if not docs:
        finish(tid, "done", {"anomalies": 0}, "нет документов для обработки")
        return
    db.anomalies.delete_many({})
    L(f"журнал аномалий: пересчёт по {len(docs)} документам")
    total = 0
    for n, d in enumerate(docs):
        if not os.path.exists(d.get("path", "")):
            continue
        base = 100.0 * n / len(docs)
        span = 100.0 / len(docs)

        def on_page(i, t, npr, _b=base, _s=span, _name=d["name"]):
            progress(tid, _b + _s * 0.6 * i / max(t, 1))
            if i % 150 == 0:
                log(tid, f"{_name}: геометрия {i}/{t} страниц")

        pages = parse_pdf(d["path"], on_page=on_page)
        run_micrograd(pages, log=L)
        _, stats = build_products(pages, {
            "factory_id": d.get("factory_id"), "factory": d.get("factory"),
            "doc_id": d["id"], "doc_name": d["name"],
            "collection": d.get("collection")}, collect_rejected=True)

        recs = []
        for r in stats.get("rejected_records", []):
            r = dict(r)
            r.update({"id": str(uuid.uuid4()), "doc_id": d["id"],
                      "doc_name": d["name"], "factory": d.get("factory"),
                      "created_at": now()})
            recs.append(r)
        for pg in pages:
            for hp in pg.get("header_prices", []):
                recs.append({
                    "id": str(uuid.uuid4()), "doc_id": d["id"], "doc_name": d["name"],
                    "factory": d.get("factory"), "page": pg["page"],
                    "text": hp["text"], "bbox": hp["bbox"], "confidence": 0.0,
                    "row_peers": 0, "col_peers": 0, "above_text": None,
                    "left_text": None, "model_name": pg.get("model_name"),
                    "category": pg.get("section_title"),
                    "reason": "Колонтитул страницы (верхние/нижние 5%)",
                    "zone": hp["zone"], "created_at": now()})
        for i in range(0, len(recs), 1000):
            db.anomalies.insert_many(recs[i:i + 1000])
        total += len(recs)
        L(f"{d['name']}: записано {len(recs)} отсеянных блоков")
        progress(tid, base + span, {"anomalies": total})
    finish(tid, "done", {"anomalies": total},
           f"журнал готов — {total} отсеянных блоков задокументировано")


def _join_ingested(records):
    docmap = {d["name"]: d for d in db.documents.find(
        {}, {"_id": 0, "id": 1, "name": 1, "coverage": 1, "positions": 1,
             "variant_prices": 1, "pages": 1})}
    for r in records:
        d = docmap.get(r["name"])
        if d:
            r.update({"ingested": True, "doc_id": d["id"], "coverage": d.get("coverage"),
                      "positions": d.get("positions"), "variant_prices": d.get("variant_prices")})
        else:
            r["ingested"] = False
    return records


def _persist_inventory(records, source):
    ops = [UpdateOne({"rel": r["rel"], "source": source}, {"$set": r}, upsert=True)
           for r in records]
    if ops:
        db.file_inventory.bulk_write(ops)


def _enqueue(kind, title, payload, meta=None):
    tid = new_task(kind, title, meta)
    if LOOP is not None:
        asyncio.run_coroutine_threadsafe(JOBQ.put((tid, kind, payload)), LOOP)
    return tid


def job_inventory(tid, payload):
    start(tid)
    L = lambda m: log(tid, m)
    data_dir = os.environ.get("DATA_DIR", "/app/data")
    molteni = os.path.join(data_dir, "molteni")
    source = payload.get("source", "local")

    if source == "local":
        folder = payload.get("folder", molteni)
        pdfs = sorted(f for f in os.listdir(folder) if f.lower().endswith(".pdf"))
        L(f"инвентаризация {len(pdfs)} файлов в {folder} (по содержимому)")
        records = []
        for i, name in enumerate(pdfs):
            rec = inventory.make_record(os.path.join(folder, name), "local", name)
            records.append(rec)
            L(f"  {name}: {rec['doc_type']} · {rec.get('year')} · "
              f"{rec.get('currency')} · {rec['pages']} стр.")
            progress(tid, 5 + 85 * (i + 1) / max(len(pdfs), 1),
                     {"classified": i + 1, "total": len(pdfs)})
        inventory.supersede_pass(records)
        _join_ingested(records)
        # decisive content signal from the actual parse: many matrix cells => price list
        for r in records:
            if (r.get("variant_prices") or 0) >= 200:
                r["doc_type"] = "прайс-лист"
        inventory.supersede_pass(records)  # re-run with corrected types
        _join_ingested(records)
        db.file_inventory.delete_many({"source": "local"})
        _persist_inventory(records, "local")
        cur = sum(1 for r in records if r["is_current_listino"])
        finish(tid, "done", {"files": len(records), "current_listini": cur},
               f"инвентаризация завершена — {len(records)} файлов, "
               f"{cur} актуальных прайс-листов")
        return

    # ---- full Dropbox folder pass (strict read-only transit) ----
    url = payload["url"]
    st = os.statvfs(data_dir)
    free_gb = st.f_bavail * st.f_frsize / 1e9
    L(f"свободно на диске: {free_gb:.1f} ГБ")
    if free_gb < 3.5:
        finish(tid, "error", {}, f"мало места ({free_gb:.1f} ГБ) для транзита архива")
        return
    L("загрузка архива общей папки Dropbox (dl=1) во временное хранилище")
    zp = download_folder(url, L)
    entries = list_pdfs(zp)
    L(f"в архиве {len(entries)} PDF; классификация entry-by-entry, "
      f"каждый файл удаляется сразу после разбора")
    tmpdir = os.path.join(data_dir, "tmp", "inv")
    os.makedirs(tmpdir, exist_ok=True)
    os.makedirs(molteni, exist_ok=True)
    have = set(os.listdir(molteni))
    records = []
    with zipfile.ZipFile(zp) as zf:
        for i, e in enumerate(entries):
            tmp = os.path.join(tmpdir, e["name"])
            try:
                with zf.open(e["rel"]) as src, open(tmp, "wb") as dst:
                    shutil.copyfileobj(src, dst, 1 << 20)
                rec = inventory.make_record(tmp, "dropbox", e["rel"])
                rec["folder"] = e.get("folder")
                rec["size"] = e.get("size", rec.get("size"))
                records.append(rec)
            except Exception as ex:
                L(f"  пропуск {e['name']}: {type(ex).__name__}: {ex}")
            finally:
                if os.path.exists(tmp):
                    os.remove(tmp)  # strict transit: payload removed immediately
            if (i + 1) % 25 == 0 or i + 1 == len(entries):
                progress(tid, 30 + 55 * (i + 1) / max(len(entries), 1),
                         {"classified": i + 1, "total": len(entries)})
                L(f"  классифицировано {i + 1}/{len(entries)}")
    inventory.supersede_pass(records)

    # flag spreadsheet price files (never parsed by the geometric engine)
    for e in list_spreadsheets(zp):
        records.append({
            "id": str(uuid.uuid4()), "source": "dropbox", "rel": e["rel"],
            "name": e["name"], "folder": e.get("folder"), "size": e.get("size"),
            "pages": None, "doc_type": "таблица (не разбирается)",
            "year": None, "currency": None, "is_current_listino": False,
            "superseded_by": None, "ingested": False,
            "sample_title": "электронная таблица — геометрический разбор не применим",
            "classified_at": now()})

    # keep + ingest current listini not already cached ONLY when requested
    keepers = [r for r in records
               if r.get("is_current_listino") and r["name"] not in have]
    new_paths = []
    ingest_tid = None
    if keepers and payload.get("ingest_new", False):
        with zipfile.ZipFile(zp) as zf:
            for r in keepers:
                dest = os.path.join(molteni, r["name"])
                try:
                    with zf.open(r["rel"]) as src, open(dest, "wb") as dst:
                        shutil.copyfileobj(src, dst, 1 << 20)
                    new_paths.append(dest)
                except Exception as ex:
                    L(f"  не удалось сохранить {r['name']}: {ex}")
        L(f"сохранено {len(new_paths)} новых актуальных прайс-листов для разбора")

    _join_ingested(records)
    _persist_inventory(records, "dropbox")
    if payload.get("cleanup", False):
        cleanup_archive(zp, L)

    if new_paths and payload.get("ingest_new", False):
        ingest_tid = _enqueue("ingest", f"Разбор {len(new_paths)} новых прайс-листов",
                              {"source": "local", "paths": new_paths,
                               "factory": "Molteni & C"}, {"n": len(new_paths)})
        L(f"поставлена задача разбора новых прайс-листов: {ingest_tid}")

    cur = sum(1 for r in records if r.get("is_current_listino"))
    kept = [r for r in records if r.get("is_current_listino") and r["name"] not in have]
    msg = (f"полная инвентаризация — {len(records)} файлов, {cur} актуальных прайс-листов, "
           + (f"{len(new_paths)} новых поставлено на разбор" if new_paths
              else f"{len(kept)} новых доступно к разбору (авторазбор не запрошен)"))
    finish(tid, "done",
           {"files": len(records), "current_listini": cur,
            "new_available": len(kept), "new_ingested": len(new_paths),
            "ingest_task": ingest_tid}, msg)


JOBS = {"scan": job_scan, "ingest": job_ingest, "embed": job_embed,
        "photos": job_photos, "anomalies": job_anomalies,
        "inventory": job_inventory}


async def consumer():
    while True:
        tid, kind, payload = await JOBQ.get()
        try:
            await asyncio.get_running_loop().run_in_executor(EXEC, JOBS[kind], tid, payload)
        except Exception as e:
            finish(tid, "error", {}, f"{type(e).__name__}: {e}")
        finally:
            JOBQ.task_done()


@app.on_event("startup")
async def _startup():
    global LOOP
    LOOP = asyncio.get_running_loop()
    db.ensure_indexes()
    asyncio.create_task(consumer())


# --------------------------------------------------------------------------- #
# http
# --------------------------------------------------------------------------- #
@app.get("/health")
def health():
    return {"ok": True, "queue": JOBQ.qsize(),
            "products": db.products.estimated_document_count(),
            "docs": db.documents.estimated_document_count()}


@app.post("/scan")
async def scan(req: Request):
    body = await req.json()
    tid = new_task("scan", "Dropbox folder traversal", {"url": body.get("url")})
    await JOBQ.put((tid, "scan", body))
    return {"task_id": tid}


@app.post("/ingest")
async def ingest(req: Request):
    body = await req.json()
    n = len(body.get("rels") or body.get("paths") or [])
    tid = new_task("ingest", f"Ingest {n} document(s)", {"n": n})
    await JOBQ.put((tid, "ingest", body))
    return {"task_id": tid}


@app.post("/embed")
async def embed(req: Request):
    body = await req.json() if await req.body() else {}
    tid = new_task("embed", "Generate 512-d CLIP embeddings")
    await JOBQ.put((tid, "embed", body))
    return {"task_id": tid}


@app.post("/photos")
async def photos_job(req: Request):
    body = await req.json() if await req.body() else {}
    tid = new_task("photos", "Сопоставление иллюстраций товаров")
    await JOBQ.put((tid, "photos", body))
    return {"task_id": tid}


@app.post("/anomalies")
async def anomalies_job(req: Request):
    body = await req.json() if await req.body() else {}
    tid = new_task("anomalies", "Журнал отсеянных аномалий")
    await JOBQ.put((tid, "anomalies", body))
    return {"task_id": tid}


@app.post("/inventory")
async def inventory_job(req: Request):
    body = await req.json() if await req.body() else {}
    src = body.get("source", "local")
    title = ("Полная инвентаризация папки Dropbox" if src == "dropbox"
             else "Инвентаризация локальных прайс-листов")
    tid = new_task("inventory", title, {"source": src})
    await JOBQ.put((tid, "inventory", body))
    return {"task_id": tid}


@app.get("/photo")
def photo(product_id: str, dpi: int = 130):
    from photos import render_crop
    p = db.products.find_one({"id": product_id}, {"_id": 0, "photo": 1, "doc_id": 1})
    if not p or not p.get("photo"):
        return JSONResponse({"error": "no illustration for this product"}, status_code=404)
    doc = db.documents.find_one({"id": p["doc_id"]})
    if not doc or not os.path.exists(doc.get("path", "")):
        return JSONResponse({"error": "document not found"}, status_code=404)
    try:
        png = render_crop(doc["path"], p["photo"]["page"], p["photo"]["bbox"], dpi=dpi)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    return Response(content=png, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=604800"})


@app.get("/page-image")
def page_image(doc_id: str, page: int, dpi: int = 120):
    doc = db.documents.find_one({"id": doc_id})
    if not doc or not os.path.exists(doc["path"]):
        return JSONResponse({"error": "document not found"}, status_code=404)
    try:
        png = render_page_png(doc["path"], page, dpi=dpi)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    return Response(content=png, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=86400"})


def _load_vectors():
    """Load the vector index, plus a mean-centred copy and an id->row map.

    The distilled multilingual CLIP text encoder is strongly anisotropic: every
    product sentence shares a dominant direction, so raw cosine sits around 0.9
    for everything and ranking collapses. Subtracting the dataset mean ('all but
    the top') restores discrimination for text->text retrieval. Image->text
    queries keep the raw space, because CLIP was trained for exactly that
    alignment and the modality mean differs.
    """
    stamp = db.embeddings_col.count_documents({})
    if VEC_CACHE["stamp"] == stamp and VEC_CACHE.get("M") is not None:
        return VEC_CACHE
    ids, rows = [], []
    for e in db.embeddings_col.find({}, {"product_id": 1, "vector": 1}):
        ids.append(e["product_id"])
        rows.append(e["vector"])
    if rows:
        M = np.asarray(rows, dtype=np.float32)
        mu = M.mean(axis=0)
        Mc = M - mu
        Mc /= np.clip(np.linalg.norm(Mc, axis=1, keepdims=True), 1e-8, None)
    else:
        M = np.zeros((0, 512), dtype=np.float32)
        mu = np.zeros((512,), dtype=np.float32)
        Mc = M
    VEC_CACHE.update({"stamp": stamp, "ids": ids, "M": M, "Mc": Mc, "mu": mu,
                      "pos": {pid: i for i, pid in enumerate(ids)}})
    return VEC_CACHE


# cosine bands differ wildly per modality, so the 0..1 match score is calibrated
CALIBRATION = {"text": (0.30, 0.92), "image": (0.08, 0.38)}


def _calibrate(v, mode):
    lo, hi = CALIBRATION[mode]
    return float(min(max((v - lo) / (hi - lo), 0.0), 1.0))


def _lexical_scores(q, limit=500):
    """MongoDB text-index half of hybrid search, with RU->EN query translation."""
    from lexicon import translate_query
    terms, matched = translate_query(q)
    if not terms:
        return {}, terms, matched
    try:
        cur = db.products.find(
            {"$text": {"$search": " ".join(terms)},
             "confidence": {"$gte": 0.65}, "n_variations": {"$gte": 2}},
            {"_id": 0, "id": 1, "s": {"$meta": "textScore"}},
        ).sort([("s", {"$meta": "textScore"})]).limit(limit)
        raw = [(d["id"], float(d["s"])) for d in cur]
    except Exception:
        return {}, terms, matched
    if not raw:
        return {}, terms, matched
    mx = max(s for _, s in raw) or 1.0
    return {pid: s / mx for pid, s in raw}, terms, matched


@app.post("/search")
async def search(req: Request):
    # graceful degradation (Directive: CLIP deferred): if the vector index is not
    # built, return a clean "no embeddings yet" state without loading torch/CLIP.
    if db.embeddings_col.estimated_document_count() == 0:
        ct0 = req.headers.get("content-type", "")
        mode0 = "image" if ct0.startswith("multipart/form-data") else "text"
        return {"results": [], "mode": mode0, "note": "no embeddings yet"}
    import embeddings as E
    ct = req.headers.get("content-type", "")
    top_k = 24
    if ct.startswith("multipart/form-data"):
        form = await req.form()
        raw = await form["file"].read()
        qv = E.encode_image_bytes(raw)
        mode = "image"
        top_k = int(form.get("top_k") or 24)
    else:
        body = await req.json()
        q = (body.get("q") or "").strip()
        if not q:
            return {"results": [], "mode": "text"}
        qv = E.encode_text([q])[0]
        mode = "text"
        top_k = int(body.get("top_k") or 24)

    C = _load_vectors()
    ids, M, Mc, mu = C["ids"], C["M"], C["Mc"], C["mu"]
    if M.shape[0] == 0:
        return {"results": [], "mode": mode, "note": "no embeddings yet"}

    qv = np.asarray(qv, dtype=np.float32)
    if mode == "text":
        qc = qv - mu
        n = float(np.linalg.norm(qc))
        sims = Mc @ (qc / (n if n > 1e-8 else 1.0))
    else:
        sims = M @ qv

    # ---- hybrid ranking: Reciprocal Rank Fusion of the vector and lexical lists ----
    # RRF is scale-free, which matters because a mean-centred cosine and a MongoDB
    # textScore are not comparable numbers. A naive weighted sum let pure keyword
    # hits with a NEGATIVE cosine outrank genuine semantic matches.
    pos = C["pos"]
    pool = int(min(max(top_k * 40, 500), M.shape[0]))
    order = list(np.argsort(-sims)[:pool])
    vec_rank = {ids[i]: r for r, i in enumerate(order)}
    cand = set(vec_rank.keys())

    lex, terms, matched = ({}, [], [])
    if mode == "text":
        lex, terms, matched = _lexical_scores(q)
        cand |= set(lex.keys())
    lex_rank = {pid: r for r, (pid, _) in
                enumerate(sorted(lex.items(), key=lambda kv: -kv[1]))}

    K = 60.0
    scored = []
    for pid in cand:
        rrf = 0.0
        if pid in vec_rank:
            rrf += 1.0 / (K + vec_rank[pid] + 1)
        if pid in lex_rank:
            rrf += 1.0 / (K + lex_rank[pid] + 1)
        i = pos.get(pid)
        cos = float(sims[i]) if i is not None else None
        vec = _calibrate(cos, mode) if cos is not None else 0.0
        lx = lex.get(pid, 0.0)
        match = (0.60 * vec + 0.40 * lx) if mode == "text" else vec
        scored.append((pid, rrf, match, cos, lx))
    scored.sort(key=lambda x: -x[1])

    head = scored[:max(top_k * 40, 800)]
    pmap = {p["id"]: p for p in db.products.find(
        {"id": {"$in": [row[0] for row in head]}}, {"_id": 0})}
    BAD_CATEGORY = {"", "note", "notes", "features", "surcharges", "attention",
                    "attention:", "important", "measurements", "general"}
    seen, out = set(), []
    for pid, rrf, match, cos, lx in head:
        p = pmap.get(pid)
        if not p:
            continue
        # search surfaces real price matrices, not stray cells or note blocks
        if (p.get("n_variations") or 0) < 2:
            continue
        cat = str(p.get("category") or "").strip().lower()
        if cat in BAD_CATEGORY:
            continue
        key = (p.get("model_name"), p.get("category"))
        if key in seen:
            continue
        seen.add(key)
        p["score"] = cos if cos is not None else 0.0
        p["match"] = round(match, 4)
        p["lex"] = round(lx, 4)
        p["rrf"] = round(rrf, 5)
        out.append(p)
        if len(out) >= top_k:
            break
    # RRF chose *which* rows; display order follows the calibrated match so the
    # % badges in the UI read monotonically top-to-bottom
    out.sort(key=lambda p: -p["match"])
    return {"results": out, "mode": mode, "searched": int(M.shape[0]),
            "lexical_terms": terms, "translated_from": matched,
            "lexical_hits": len(lex)}


@app.get("/export")
def export(status: str = "approved", doc_id: str = "", factory: str = "",
           mode: str = "product"):
    from export_xlsx import build_workbook
    q = {}
    if status and status != "all":
        q["status"] = status
    if doc_id:
        q["doc_id"] = doc_id
    if factory:
        q["factory"] = factory
    prods = list(db.products.find(q, {"_id": 0}).limit(60000))
    labels = {"approved": "только одобренные", "pending": "ожидают проверки",
              "rejected": "отклонённые", "all": "все статусы"}
    data = build_workbook(prods, {
        "factory": factory or (prods[0].get("factory") if prods else None),
        "status_label": labels.get(status, status), "mode": mode})
    n_rows = (sum(len(p.get("variations") or []) for p in prods)
              if mode == "variation" else len(prods))
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="homeart_catalog.xlsx"',
                 "X-Rows": str(n_rows), "X-Products": str(len(prods))})


@app.get("/export-inventory")
def export_inventory():
    from export_xlsx import build_inventory_workbook
    records = list(db.file_inventory.find({}, {"_id": 0}).limit(5000))
    docs = list(db.documents.find({}, {"_id": 0}))
    data = build_inventory_workbook(records, docs)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="homeart_inventory.xlsx"',
                 "X-Files": str(len(records))})


@app.get("/export-positions")
def export_positions(status: str = "all", doc_id: str = "", factory: str = ""):
    """Position-first workbook: sheets «Позиции», «Цены», «Сводка»."""
    from export_xlsx import build_position_workbook
    pq, vq = {}, {}
    if status and status != "all":
        pq["status"] = status
        vq["status"] = status
    if factory:
        pq["factory"] = factory
        vq["factory"] = factory
    if doc_id:
        vq["doc_id"] = doc_id
    variants = list(db.variant_prices.find(vq, {"_id": 0}).limit(200000))
    if doc_id:
        pids = {v.get("position_id") for v in variants}
        pq["id"] = {"$in": list(pids)}
    positions = list(db.positions.find(pq, {"_id": 0}).limit(20000))
    labels = {"approved": "только одобренные", "pending": "ожидают проверки",
              "rejected": "отклонённые", "all": "все статусы"}
    data = build_position_workbook(positions, variants, {
        "factory": factory or (positions[0].get("factory") if positions else None),
        "status_label": labels.get(status, status)})
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="homeart_positions.xlsx"',
                 "X-Rows": str(len(variants)), "X-Positions": str(len(positions))})
