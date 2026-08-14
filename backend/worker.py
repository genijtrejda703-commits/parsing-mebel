"""DS sidecar: FastAPI + in-worker async queue, tracked in MongoDB.

Replaces Redis/Celery with a single asyncio queue draining into a 1-thread
executor (CPU-bound PyMuPDF / torch work is serialised on purpose). Every job
streams its progress into the `tasks` collection, which the Next.js Task Monitor
polls - so the UI sees live parsing status without a broker.
"""
import asyncio
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import numpy as np
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from pymongo import UpdateOne

import db
from assemble import build_products, run_micrograd
from dropbox_fetch import (cleanup_archive, download_folder, extract, list_pdfs,
                           zip_path_for)
from pipeline import parse_pdf, render_page_png

app = FastAPI(title="DataHub DS Worker")
JOBQ: asyncio.Queue = asyncio.Queue()
EXEC = ThreadPoolExecutor(max_workers=1)
VEC_CACHE = {"stamp": None, "ids": [], "M": None}


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
    L(f"{name}: {len(prods)} products assembled, {stats['rejected_cells']} cells "
      f"rejected as spatial anomalies, {n_flag} flagged for review")
    db.documents.update_one({"id": doc_id}, {"$set": {
        "status": "parsed", "pages": len(pages), "products": len(prods),
        "rejected_cells": stats["rejected_cells"],
        "micrograd": {k: v for k, v in mg.items() if k != "acc_curve"},
        "anomaly_samples": stats["anomaly_samples"], "parsed_at": now()}})
    return len(prods), stats["rejected_cells"], mg


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
    total_prod = total_rej = 0
    last_mg = {}
    base = 10.0
    span = 88.0 / len(files)
    for i, f in enumerate(files):
        try:
            np_, nr_, mg = _ingest_one(tid, f["path"], f["name"], factory, factory_id,
                                       max_pages, base + i * span, span)
            total_prod += np_
            total_rej += nr_
            last_mg = mg
            progress(tid, base + (i + 1) * span,
                     {"products": total_prod, "rejected": total_rej,
                      "docs_done": i + 1, "docs_total": len(files),
                      "micrograd_loss": mg.get("loss_curve", [])[-20:],
                      "micrograd_acc": mg.get("acc_curve", [])[-20:]})
        except Exception as e:
            log(tid, f"{f['name']} failed: {type(e).__name__}: {e}", "error")
    if zp and payload.get("cleanup"):
        cleanup_archive(zp, L)
    finish(tid, "done", {"products": total_prod, "rejected": total_rej,
                         "micrograd": last_mg},
           f"extraction complete - {total_prod} products, {total_rej} anomalies rejected")


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


JOBS = {"scan": job_scan, "ingest": job_ingest, "embed": job_embed}


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
    """Load the vector index, plus a mean-centred copy.

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
    VEC_CACHE.update({"stamp": stamp, "ids": ids, "M": M, "Mc": Mc, "mu": mu})
    return VEC_CACHE


@app.post("/search")
async def search(req: Request):
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

    # deep candidate pool, then one row per (model, category) so the grid is not
    # 24 near-identical columns of the same product family
    pool = int(min(max(top_k * 40, 400), M.shape[0]))
    order = np.argsort(-sims)[:pool]
    picked = [(ids[i], float(sims[i])) for i in order]
    pmap = {p["id"]: p for p in db.products.find(
        {"id": {"$in": [pid for pid, _ in picked]}}, {"_id": 0})}
    seen, out = set(), []
    for pid, s in picked:
        p = pmap.get(pid)
        if not p:
            continue
        key = (p.get("model_name"), p.get("category"))
        if key in seen:
            continue
        seen.add(key)
        p["score"] = s
        out.append(p)
        if len(out) >= top_k:
            break
    return {"results": out, "mode": mode, "searched": int(M.shape[0])}
