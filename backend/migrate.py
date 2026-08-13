"""Simple SQL migration runner. Tracks applied migrations in schema_migrations."""
import os
import sys
import psycopg2
from dotenv import load_dotenv

load_dotenv("/app/.env")

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "migrations")
POSTGRES_URL = os.environ.get("POSTGRES_URL", "postgresql://datahub:datahub_secret@127.0.0.1:5432/furniture_hub")


def run_migrations():
    conn = psycopg2.connect(POSTGRES_URL)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version VARCHAR(64) PRIMARY KEY, applied_at TIMESTAMPTZ DEFAULT now())")
    cur.execute("SELECT version FROM schema_migrations")
    applied = {r[0] for r in cur.fetchall()}
    files = sorted(f for f in os.listdir(MIGRATIONS_DIR) if f.endswith(".sql"))
    for fname in files:
        version = fname.split("_")[0]
        if version in applied:
            print(f"skip {fname}")
            continue
        with open(os.path.join(MIGRATIONS_DIR, fname)) as f:
            sql = f.read()
        print(f"applying {fname} ...")
        cur.execute(sql)
        cur.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
        print(f"applied {fname}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    try:
        run_migrations()
        print("migrations OK")
    except Exception as e:
        print(f"migration failed: {e}", file=sys.stderr)
        sys.exit(1)
