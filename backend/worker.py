"""Celery application + ingestion pipeline task."""
import os
import json
import shutil
from datetime import datetime, timezone

from celery import Celery
from dotenv import load_dotenv

from db import query, jsonb
from dropbox_client import download_shared_link, DropboxLinkError
from pipeline import run_extraction_pipeline
from embeddings import generate_text_embedding, generate_image_embedding, vector_literal

load_dotenv("/app/.env")

REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
PROCESSING_DIR = os.environ.get("PROCESSING_DIR", "/tmp/processing")

celery_app = Celery("datahub", broker=REDIS_URL, backend=REDIS_URL)
celery_app.conf.update(
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    worker_prefetch_multiplier=1,
)


def _update_task(task_id, **fields):
    sets, params = ["updated_at = now()"], []
    for k, v in fields.items():
        sets.append(f"{k} = %s")
        params.append(jsonb(v) if isinstance(v, (dict, list)) else v)
    params.append(task_id)
    query(f"UPDATE ingest_tasks SET {', '.join(sets)} WHERE id = %s", params, fetch=None)


def _update_factory(factory_id, **fields):
    sets, params = [], []
    for k, v in fields.items():
        sets.append(f"{k} = %s")
        params.append(v)
    params.append(factory_id)
    query(f"UPDATE factories SET {', '.join(sets)} WHERE id = %s", params, fetch=None)


@celery_app.task(bind=True, name="ingest.process")
def process_ingest(self, task_id: str, factory_id: str, dropbox_url: str = None, local_dir: str = None):
    """Full ingestion pipeline: download -> extract -> parse -> embed -> persist."""
    work_dir = os.path.join(PROCESSING_DIR, task_id)
    pdf_dir = os.path.join(work_dir, "pdfs")
    try:
        _update_factory(factory_id, status="syncing")

        # STAGE 1: acquire files
        if dropbox_url:
            _update_task(task_id, status="downloading", progress=10, message="Downloading from Dropbox...")
            os.makedirs(work_dir, exist_ok=True)

            def cb(nbytes):
                mb = nbytes / (1024 * 1024)
                _update_task(task_id, message=f"Downloading from Dropbox... {mb:.1f} MB")

            files = download_shared_link(dropbox_url, work_dir, progress_cb=cb)
        else:
            pdf_dir = local_dir or pdf_dir
            files = []
            for root, _d, fs in os.walk(pdf_dir):
                for f in fs:
                    if f.lower().endswith(".pdf"):
                        p = os.path.join(root, f)
                        files.append({"name": os.path.relpath(p, pdf_dir), "path": p, "bytes": os.path.getsize(p)})
            if not files:
                raise ValueError("No PDF files found in the uploaded batch")

        _update_task(task_id, progress=40, files=[{"name": f["name"], "bytes": f["bytes"]} for f in files],
                     message=f"Downloaded {len(files)} PDF file(s)")

        # STAGE 2: proprietary spatial parsing (stub)
        _update_task(task_id, status="parsing", progress=55, message="Parsing Geometry...")
        extraction = run_extraction_pipeline(pdf_dir if not dropbox_url else os.path.join(work_dir, "pdfs"))

        # STAGE 3: embeddings + persist
        _update_task(task_id, status="embedding", progress=75, message="Generating Embeddings...")
        n_products = 0
        for coll in extraction.get("collections", []):
            row = query(
                "INSERT INTO collections (factory_id, name, designer_name, release_year) VALUES (%s,%s,%s,%s) RETURNING id",
                (factory_id, coll["name"], coll.get("designer_name"), coll.get("release_year")), fetch="one")
            coll_id = row["id"]
            for p in coll.get("products", []):
                prow = query(
                    """INSERT INTO products (collection_id, model_name, category, dimensions_raw, base_price,
                       variations_metadata, review_status, source_file, source_page)
                       VALUES (%s,%s,%s,%s,%s,%s,'pending',%s,%s) RETURNING id""",
                    (coll_id, p["model_name"], p.get("category"), p.get("dimensions_raw"), p.get("base_price"),
                     jsonb(p.get("variations_metadata") or {}), p.get("source_file"), p.get("source_page")),
                    fetch="one")
                text_repr = f"{p['model_name']} {p.get('category','')} {coll.get('designer_name','')} {coll['name']}"
                tvec = vector_literal(generate_text_embedding(text_repr))
                ivec = vector_literal(generate_image_embedding(text_repr.encode()))
                query("INSERT INTO product_embeddings (product_id, text_embedding, image_embedding) VALUES (%s, %s::vector, %s::vector)",
                      (prow["id"], tvec, ivec), fetch=None)
                n_products += 1

        # STAGE 4: finalize
        stats = extraction.get("stats", {})
        stats["products_created"] = n_products
        _update_task(task_id, status="completed", progress=100, message="Completed", stats=stats)
        query("UPDATE factories SET status='active', total_items = total_items + %s, last_synced = now() WHERE id = %s",
              (n_products, factory_id), fetch=None)
        return {"ok": True, "products": n_products}

    except (DropboxLinkError, ValueError) as e:
        _update_task(task_id, status="failed", message="Failed", error=str(e))
        _update_factory(factory_id, status="error")
        shutil.rmtree(work_dir, ignore_errors=True)
        return {"ok": False, "error": str(e)}
    except Exception as e:
        _update_task(task_id, status="failed", message="Failed", error=f"Internal error: {e}")
        _update_factory(factory_id, status="error")
        shutil.rmtree(work_dir, ignore_errors=True)
        raise
