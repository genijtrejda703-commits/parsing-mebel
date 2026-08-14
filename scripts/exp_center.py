"""Experiment: is the poor retrieval quality caused by embedding anisotropy?

Hypothesis: all product sentences share a huge common component (template
boilerplate + the narrow cone of the distilled multilingual encoder), so cosine
similarity is dominated by that shared mass. Mean-centering the space before
comparing should restore discrimination.
"""
import sys

sys.path.insert(0, "/app/backend")
import numpy as np

import db
import embeddings as E

rows = list(db.embeddings_col.find({}, {"product_id": 1, "vector": 1}).limit(12000))
ids = [r["product_id"] for r in rows]
M = np.asarray([r["vector"] for r in rows], dtype=np.float32)
print("index:", M.shape)

mu = M.mean(axis=0, keepdims=True)
print("mean vector norm:", float(np.linalg.norm(mu)))
sample = M[np.random.choice(len(M), 400, replace=False)]
print("avg pairwise cos RAW      :", float((sample @ sample.T).mean()))
Mc = M - mu
Mc /= np.clip(np.linalg.norm(Mc, axis=1, keepdims=True), 1e-8, None)
sc = Mc[np.random.choice(len(Mc), 400, replace=False)]
print("avg pairwise cos CENTERED :", float((sc @ sc.T).mean()))

prod = {p["id"]: p for p in db.products.find(
    {"id": {"$in": ids}}, {"_id": 0, "id": 1, "model_name": 1, "category": 1,
                           "collection": 1, "price_min": 1, "price_max": 1})}


def show(title, scores):
    order = np.argsort(-scores)[:6]
    print("   " + title)
    for i in order:
        p = prod.get(ids[i], {})
        print(f"     {scores[i]:.3f}  {str(p.get('model_name'))[:30]:32} | "
              f"{str(p.get('category'))[:24]:26} | {str(p.get('collection'))[:24]}")


for q in ["диван из кожи", "комод с ящиками", "обеденный стол дуб", "кухня с ящиками"]:
    qv = E.encode_text([q])[0]
    print(f"\n=== {q!r}")
    show("RAW", M @ qv)
    qc = qv - mu[0]
    qc = qc / max(float(np.linalg.norm(qc)), 1e-8)
    show("CENTERED", Mc @ qc)
