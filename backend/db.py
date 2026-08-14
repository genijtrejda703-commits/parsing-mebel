"""Mongo access for the DS sidecar. Reads the same protected env as Next.js."""
import os

from pymongo import MongoClient


def _load_env(path="/app/.env"):
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    except FileNotFoundError:
        pass


_load_env()

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "datahub")
DATA_DIR = os.environ.get("DATA_DIR", "/app/data")

client = MongoClient(MONGO_URL)
db = client[DB_NAME]

factories = db["factories"]
documents = db["documents"]
tasks = db["tasks"]
products = db["products"]
embeddings_col = db["product_embeddings"]


def ensure_indexes():
    try:
        products.create_index("factory_id")
        products.create_index("doc_id")
        products.create_index("status")
        products.create_index([("model_name", 1)])
        products.create_index("page")
        tasks.create_index("created_at")
        documents.create_index("id", unique=True)
        embeddings_col.create_index("product_id")
    except Exception:
        pass


for _d in ("tmp", "pages", "uploads", "pdfs"):
    os.makedirs(os.path.join(DATA_DIR, _d), exist_ok=True)
