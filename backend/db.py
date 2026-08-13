"""PostgreSQL connection helpers (psycopg2 pool)."""
import os
import json
import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv("/app/.env")

POSTGRES_URL = os.environ.get("POSTGRES_URL", "postgresql://datahub:datahub_secret@127.0.0.1:5432/furniture_hub")

psycopg2.extras.register_uuid()

_pool = None


def get_pool():
    global _pool
    if _pool is None:
        _pool = ThreadedConnectionPool(minconn=1, maxconn=10, dsn=POSTGRES_URL)
    return _pool


@contextmanager
def get_conn():
    pool = get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def query(sql, params=None, fetch="all"):
    """Execute SQL. fetch: 'all' | 'one' | None."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or ())
            if fetch == "all":
                return [dict(r) for r in cur.fetchall()]
            if fetch == "one":
                row = cur.fetchone()
                return dict(row) if row else None
            return None


def jsonb(value):
    return psycopg2.extras.Json(value)
