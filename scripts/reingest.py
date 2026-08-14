#!/usr/bin/env python3
"""Wipe-and-rebuild the Mongo catalogue from the PDFs cached in /app/data.

All catalogue data derives from the source PDFs, so this script is the canonical
way to restore state after a container reset (models/DB/.env are never committed).
It drops the derived collections, then drives the running dsworker /ingest job on
the cached current listini and waits for completion. Idempotent re-ingest is
guaranteed by stable documents.id keyed on file path.

Usage:
  python3 scripts/reingest.py                 # all price lists under data/molteni
  python3 scripts/reingest.py a.pdf b.pdf      # explicit files (basename or path)
"""
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
import db  # noqa: E402

WORKER = os.environ.get("PY_WORKER_URL", "http://localhost:8001")
MOLTENI = "/app/data/molteni"
WIPE = ["documents", "products", "positions", "variant_prices", "tasks",
        "anomalies", "product_embeddings", "file_inventory"]


def post(route, payload):
    req = urllib.request.Request(
        WORKER + route, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def get(route):
    with urllib.request.urlopen(WORKER + route, timeout=60) as r:
        return json.loads(r.read())


def resolve_paths(args):
    if args:
        out = []
        for a in args:
            p = a if os.path.isabs(a) else os.path.join(MOLTENI, a)
            if os.path.exists(p):
                out.append(p)
            else:
                print(f"  skip (missing): {a}")
        return out
    return sorted(os.path.join(MOLTENI, f) for f in os.listdir(MOLTENI)
                 if f.lower().endswith(".pdf"))


def main():
    paths = resolve_paths(sys.argv[1:])
    if not paths:
        print("no PDFs to ingest"); return 1
    print(f"dropping derived collections: {', '.join(WIPE)}")
    for c in WIPE:
        db.db[c].drop()
    print(f"enqueuing ingest of {len(paths)} document(s)")
    for p in paths:
        print("  -", os.path.basename(p))
    res = post("/ingest", {"source": "local", "paths": paths,
                            "factory": "Molteni & C"})
    tid = res["task_id"]
    print("task:", tid)
    last = None
    while True:
        time.sleep(5)
        t = get(f"/tasks/{tid}") if False else None
        doc = db.tasks.find_one({"id": tid}, {"_id": 0, "status": 1,
                                              "progress": 1, "stats": 1})
        if not doc:
            continue
        line = f"  {doc.get('progress', 0):5.1f}%  {doc.get('status')}  {doc.get('stats', {})}"
        if line != last:
            print(line); last = line
        if doc.get("status") in ("done", "error"):
            break
    print("positions:", db.db["positions"].count_documents({}))
    print("variant_prices:", db.db["variant_prices"].count_documents({}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
