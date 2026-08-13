"""FastAPI backend: HOMEART Furniture Data Hub."""
import os
import json
import uuid
import asyncio
from pathlib import Path

from fastapi import FastAPI, APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from db import query, jsonb
from auth import create_token, verify_password, require_auth
from embeddings import generate_text_embedding, generate_image_embedding, vector_literal
from dropbox_client import dropbox_download_url, DropboxLinkError
from worker import process_ingest

load_dotenv("/app/.env")

PROCESSING_DIR = os.environ.get("PROCESSING_DIR", "/tmp/processing")

app = FastAPI(title="HOMEART Furniture Data Hub")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
api = APIRouter(prefix="/api")


def _json_safe(rows):
    def conv(v):
        if isinstance(v, (dict, list)):
            return v
        if hasattr(v, "isoformat"):
            return v.isoformat()
        if isinstance(v, uuid.UUID):
            return str(v)
        if v.__class__.__name__ == "Decimal":
            return float(v)
        return v
    if isinstance(rows, dict):
        return {k: conv(v) for k, v in rows.items()}
    return [{k: conv(v) for k, v in r.items()} for r in rows]


# ---------- health / auth ----------
@api.get("/health")
def health():
    try:
        query("SELECT 1 AS ok", fetch="one")
        db_ok = True
    except Exception:
        db_ok = False
    return {"status": "ok", "service": "fastapi", "database": "up" if db_ok else "down"}


class LoginBody(BaseModel):
    password: str


@api.post("/auth/login")
def login(body: LoginBody):
    if not verify_password(body.password):
        raise HTTPException(status_code=401, detail="Неверный пароль")
    return {"token": create_token()}


# ---------- stats / factories ----------
@api.get("/stats", dependencies=[Depends(require_auth)])
def stats():
    row = query("""SELECT
        (SELECT COUNT(*) FROM factories) AS factories,
        (SELECT COUNT(*) FROM collections) AS collections,
        (SELECT COUNT(*) FROM products) AS products,
        (SELECT COUNT(*) FROM products WHERE review_status='pending') AS pending_qa,
        (SELECT COUNT(*) FROM products WHERE review_status='approved') AS approved,
        (SELECT COUNT(*) FROM ingest_tasks WHERE status NOT IN ('completed','failed')) AS active_tasks""", fetch="one")
    return _json_safe(row)


@api.get("/factories", dependencies=[Depends(require_auth)])
def list_factories():
    rows = query("SELECT * FROM factories ORDER BY created_at DESC")
    return _json_safe(rows)


# ---------- ingestion ----------
class IngestBody(BaseModel):
    factory_name: str
    dropbox_url: str


@api.post("/ingest/dropbox", dependencies=[Depends(require_auth)])
def ingest_dropbox(body: IngestBody):
    if not body.factory_name.strip():
        raise HTTPException(400, "Укажите название фабрики")
    try:
        dropbox_download_url(body.dropbox_url)  # validate link early
    except DropboxLinkError as e:
        raise HTTPException(400, str(e))

    factory = query("SELECT id FROM factories WHERE lower(name)=lower(%s)", (body.factory_name.strip(),), fetch="one")
    if factory:
        factory_id = factory["id"]
        query("UPDATE factories SET dropbox_url=%s, status='pending' WHERE id=%s", (body.dropbox_url, factory_id), fetch=None)
    else:
        factory_id = query("INSERT INTO factories (name, dropbox_url, status) VALUES (%s,%s,'pending') RETURNING id",
                           (body.factory_name.strip(), body.dropbox_url), fetch="one")["id"]

    task = query("INSERT INTO ingest_tasks (factory_id, source, status, message) VALUES (%s,'dropbox','queued','Queued') RETURNING id",
                 (factory_id,), fetch="one")
    task_id = str(task["id"])
    async_res = process_ingest.delay(task_id, str(factory_id), dropbox_url=body.dropbox_url)
    query("UPDATE ingest_tasks SET celery_task_id=%s WHERE id=%s", (async_res.id, task_id), fetch=None)
    return {"task_id": task_id, "factory_id": str(factory_id), "status": "queued"}


@api.post("/ingest/upload", dependencies=[Depends(require_auth)])
async def ingest_upload(factory_name: str = Form(...), files: list[UploadFile] = File(...)):
    """Graceful fallback: manual local PDF upload."""
    if not files:
        raise HTTPException(400, "Файлы не переданы")
    factory = query("SELECT id FROM factories WHERE lower(name)=lower(%s)", (factory_name.strip(),), fetch="one")
    if factory:
        factory_id = factory["id"]
        query("UPDATE factories SET status='pending' WHERE id=%s", (factory_id,), fetch=None)
    else:
        factory_id = query("INSERT INTO factories (name, status) VALUES (%s,'pending') RETURNING id",
                           (factory_name.strip(),), fetch="one")["id"]

    task = query("INSERT INTO ingest_tasks (factory_id, source, status, message) VALUES (%s,'manual','queued','Queued') RETURNING id",
                 (factory_id,), fetch="one")
    task_id = str(task["id"])
    pdf_dir = Path(PROCESSING_DIR) / task_id / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    saved = 0
    for uf in files:
        if not (uf.filename or "").lower().endswith(".pdf"):
            continue
        safe_name = os.path.basename(uf.filename)
        with open(pdf_dir / safe_name, "wb") as out:
            while True:
                chunk = await uf.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
        saved += 1
    if saved == 0:
        raise HTTPException(400, "Ни одного PDF-файла не загружено")
    async_res = process_ingest.delay(task_id, str(factory_id), local_dir=str(pdf_dir))
    query("UPDATE ingest_tasks SET celery_task_id=%s WHERE id=%s", (async_res.id, task_id), fetch=None)
    return {"task_id": task_id, "factory_id": str(factory_id), "files_saved": saved, "status": "queued"}


@api.get("/ingest/tasks", dependencies=[Depends(require_auth)])
def list_tasks():
    rows = query("""SELECT t.*, f.name AS factory_name FROM ingest_tasks t
                    LEFT JOIN factories f ON f.id = t.factory_id
                    ORDER BY t.created_at DESC LIMIT 50""")
    return _json_safe(rows)


@api.get("/ingest/tasks/{task_id}", dependencies=[Depends(require_auth)])
def get_task(task_id: str):
    row = query("""SELECT t.*, f.name AS factory_name FROM ingest_tasks t
                   LEFT JOIN factories f ON f.id = t.factory_id WHERE t.id = %s""", (task_id,), fetch="one")
    if not row:
        raise HTTPException(404, "Task not found")
    return _json_safe(row)


@api.get("/ingest/tasks/{task_id}/stream")
async def stream_task(task_id: str, token: str = Query(default="")):
    """SSE progress stream (token passed as query param because EventSource can't set headers)."""
    import jwt as pyjwt
    from auth import JWT_SECRET
    try:
        pyjwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")

    async def gen():
        last = None
        for _ in range(600):  # max 10 min
            row = query("SELECT id, status, progress, message, error, stats FROM ingest_tasks WHERE id=%s", (task_id,), fetch="one")
            if not row:
                yield f"data: {json.dumps({'error': 'not_found'})}\n\n"
                return
            payload = json.dumps(_json_safe(row), default=str)
            if payload != last:
                yield f"data: {payload}\n\n"
                last = payload
            if row["status"] in ("completed", "failed"):
                return
            await asyncio.sleep(1.0)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------- search ----------
@api.get("/search", dependencies=[Depends(require_auth)])
def search(q: str = "", factory_id: str = "", designer: str = "", category: str = "", limit: int = 30):
    where, params = ["1=1"], []
    if q.strip():
        where.append("(p.model_name ILIKE %s OR c.name ILIKE %s OR f.name ILIKE %s)")
        like = f"%{q.strip()}%"
        params += [like, like, like]
    if factory_id.strip():
        where.append("f.id = %s")
        params.append(factory_id)
    if designer.strip():
        where.append("c.designer_name ILIKE %s")
        params.append(f"%{designer.strip()}%")
    if category.strip():
        where.append("p.category ILIKE %s")
        params.append(f"%{category.strip()}%")
    params.append(min(limit, 100))
    rows = query(f"""SELECT p.id, p.model_name, p.category, p.dimensions_raw, p.base_price,
                     p.variations_metadata, p.review_status, p.source_file, p.source_page,
                     c.name AS collection_name, c.designer_name, c.release_year, f.name AS factory_name
                     FROM products p JOIN collections c ON c.id=p.collection_id JOIN factories f ON f.id=c.factory_id
                     WHERE {' AND '.join(where)} ORDER BY p.created_at DESC LIMIT %s""", params)
    return _json_safe(rows)


class SemanticBody(BaseModel):
    query: str
    limit: int = 12


@api.post("/search/semantic", dependencies=[Depends(require_auth)])
def semantic_search(body: SemanticBody):
    if not body.query.strip():
        raise HTTPException(400, "Пустой запрос")
    vec = vector_literal(generate_text_embedding(body.query))
    rows = query("""SELECT p.id, p.model_name, p.category, p.dimensions_raw, p.base_price,
                    c.name AS collection_name, c.designer_name, f.name AS factory_name,
                    (e.text_embedding <=> %s::vector) AS distance
                    FROM product_embeddings e
                    JOIN products p ON p.id = e.product_id
                    JOIN collections c ON c.id = p.collection_id
                    JOIN factories f ON f.id = c.factory_id
                    WHERE e.text_embedding IS NOT NULL
                    ORDER BY e.text_embedding <=> %s::vector
                    LIMIT %s""", (vec, vec, min(body.limit, 50)))
    out = _json_safe(rows)
    for r in out:
        r["similarity"] = round(1 - float(r["distance"]), 4)
    return out


@api.post("/search/visual", dependencies=[Depends(require_auth)])
async def visual_search(image: UploadFile = File(...), limit: int = Form(default=12)):
    data = await image.read()
    if not data:
        raise HTTPException(400, "Пустой файл")
    vec = vector_literal(generate_image_embedding(data))
    rows = query("""SELECT p.id, p.model_name, p.category, p.dimensions_raw, p.base_price,
                    c.name AS collection_name, c.designer_name, f.name AS factory_name,
                    (e.image_embedding <=> %s::vector) AS distance
                    FROM product_embeddings e
                    JOIN products p ON p.id = e.product_id
                    JOIN collections c ON c.id = p.collection_id
                    JOIN factories f ON f.id = c.factory_id
                    WHERE e.image_embedding IS NOT NULL
                    ORDER BY e.image_embedding <=> %s::vector
                    LIMIT %s""", (vec, vec, min(int(limit), 50)))
    out = _json_safe(rows)
    for r in out:
        r["similarity"] = round(1 - float(r["distance"]), 4)
    return out


# ---------- QA ----------
@api.get("/qa/products", dependencies=[Depends(require_auth)])
def qa_products(status: str = "pending", limit: int = 100):
    rows = query("""SELECT p.*, c.name AS collection_name, c.designer_name, f.name AS factory_name, f.id AS factory_id,
                    t.id AS task_id
                    FROM products p
                    JOIN collections c ON c.id = p.collection_id
                    JOIN factories f ON f.id = c.factory_id
                    LEFT JOIN LATERAL (
                        SELECT id FROM ingest_tasks it WHERE it.factory_id = f.id ORDER BY it.created_at DESC LIMIT 1
                    ) t ON true
                    WHERE p.review_status = %s ORDER BY p.created_at DESC LIMIT %s""",
                 (status, min(limit, 300)))
    return _json_safe(rows)


class ReviewBody(BaseModel):
    action: str  # approve | reject


@api.post("/qa/products/{product_id}/review", dependencies=[Depends(require_auth)])
def review_product(product_id: str, body: ReviewBody):
    if body.action not in ("approve", "reject"):
        raise HTTPException(400, "action must be approve|reject")
    new_status = "approved" if body.action == "approve" else "rejected"
    row = query("UPDATE products SET review_status=%s WHERE id=%s RETURNING id", (new_status, product_id), fetch="one")
    if not row:
        raise HTTPException(404, "Product not found")
    return {"id": str(row["id"]), "review_status": new_status}


# ---------- source PDF serving (QA deep links) ----------
@api.get("/files/{task_id}/{file_path:path}")
def serve_pdf(task_id: str, file_path: str, token: str = Query(default="")):
    import jwt as pyjwt
    from auth import JWT_SECRET
    try:
        pyjwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")
    base = Path(PROCESSING_DIR) / task_id / "pdfs"
    target = (base / file_path).resolve()
    if not str(target).startswith(str(base.resolve())) or not target.exists():
        raise HTTPException(404, "Файл не найден (временное хранилище могло быть очищено)")
    return FileResponse(str(target), media_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="{target.name}"'})


app.include_router(api)
