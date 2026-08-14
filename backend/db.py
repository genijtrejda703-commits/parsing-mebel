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
positions = db["positions"]
variant_prices = db["variant_prices"]
file_inventory = db["file_inventory"]
embeddings_col = db["product_embeddings"]
anomalies = db["anomalies"]


def ensure_indexes():
    try:
        products.create_index("factory_id")
        products.create_index("doc_id")
        products.create_index("status")
        products.create_index([("model_name", 1)])
        products.create_index("page")
        products.create_index("confidence")
        positions.create_index([("factory_id", 1), ("norm_name", 1)], unique=True)
        positions.create_index("id", unique=True)
        positions.create_index("status")
        positions.create_index("flagged")
        positions.create_index([("name", 1)])
        variant_prices.create_index("id", unique=True)
        variant_prices.create_index("position_id")
        variant_prices.create_index("doc_id")
        variant_prices.create_index("norm_name")
        variant_prices.create_index("page")
        file_inventory.create_index("id", unique=True)
        file_inventory.create_index("rel")
        file_inventory.create_index("doc_type")
        tasks.create_index("created_at")
        documents.create_index("id", unique=True)
        embeddings_col.create_index("product_id")
        anomalies.create_index("doc_id")
        anomalies.create_index("confidence")
        anomalies.create_index("reason")
    except Exception:
        pass
    try:
        # lexical half of hybrid search
        products.create_index(
            [("model_name", "text"), ("category", "text"), ("collection", "text"),
             ("section", "text"), ("doc_name", "text"), ("variations.finish", "text")],
            name="prod_text",
            weights={"model_name": 6, "category": 5, "variations.finish": 2,
                     "section": 2, "doc_name": 3, "collection": 1},
            default_language="english")
    except Exception:
        pass


for _d in ("tmp", "pages", "uploads", "pdfs"):
    os.makedirs(os.path.join(DATA_DIR, _d), exist_ok=True)
