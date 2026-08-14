"""Experiment: does hubness correction fix the residual 'TURNER for everything' bias?

Centering fixed anisotropy, but short/low-information texts can become 'hubs'
that sit close to every query. The standard remedy is to subtract each item's
average similarity to a random reference sample (CSLS-style local scaling).
"""
import sys

sys.path.insert(0, "/app/backend")
import numpy as np

import db
import embeddings as E

rows = list(db.embeddings_col.find({}, {"product_id": 1, "vector": 1, "text": 1}))
ids = [r["product_id"] for r in rows]
txt = {r["product_id"]: r.get("text", "") for r in rows}
M = np.asarray([r["vector"] for r in rows], dtype=np.float32)
mu = M.mean(axis=0)
Mc = M - mu
Mc /= np.clip(np.linalg.norm(Mc, axis=1, keepdims=True), 1e-8, None)
print("index", Mc.shape)

rng = np.random.default_rng(0)
ref = Mc[rng.choice(len(Mc), 2000, replace=False)]
hub = (Mc @ ref.T).mean(axis=1)
print("hubness stats: min %.3f max %.3f mean %.3f" % (hub.min(), hub.max(), hub.mean()))
worst = np.argsort(-hub)[:5]
print("biggest hubs:")
for i in worst:
    print(f"   hub={hub[i]:.3f}  {txt.get(ids[i], '')[:70]!r}")

prod = {p["id"]: p for p in db.products.find(
    {}, {"_id": 0, "id": 1, "model_name": 1, "category": 1, "doc_name": 1})}


def show(tag, s):
    print("  " + tag)
    for i in np.argsort(-s)[:5]:
        p = prod.get(ids[i], {})
        print(f"    {s[i]:.3f} {str(p.get('model_name'))[:24]:26} | "
              f"{str(p.get('category'))[:22]:24} | {str(p.get('doc_name'))[8:28]}")


QUERIES = ["стеллаж 505 глянцевый лак", "обеденный стол", "диван из кожи",
           "кухонный модуль с ящиками", "шкаф для одежды"]
for q in QUERIES:
    qv = E.encode_text([q])[0]
    qc = qv - mu
    qc /= max(float(np.linalg.norm(qc)), 1e-8)
    s = Mc @ qc
    print(f"\n=== {q!r}")
    show("CENTERED", s)
    show("CENTERED - HUB", s - hub)

print("\n--- does the corpus even contain table/wardrobe vocabulary? ---")
for kw in ["table", "dining", "wardrobe", "sofa", "bed", "shelf", "shelving"]:
    n = db.products.count_documents({"$or": [
        {"category": {"$regex": kw, "$options": "i"}},
        {"model_name": {"$regex": kw, "$options": "i"}}]})
    print(f"   {kw:10} {n}")
