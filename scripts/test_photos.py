"""Verify the vector-coverage crop actually lands on the furniture drawing."""
import sys

sys.path.insert(0, "/app/backend")
import db
from photos import map_document, render_crop

doc = db.documents.find_one({"name": {"$regex": "Living-Systems-Dining"}})
print("doc:", doc["name"], doc["path"])

prods = list(db.products.find(
    {"doc_id": doc["id"], "page": {"$in": [37, 39, 41, 43]}, "n_variations": {"$gte": 3}},
    {"_id": 0, "id": 1, "page": 1, "bbox": 1, "model_name": 1, "category": 1,
     "variant_code": 1}).limit(40))
print("products:", len(prods))

by_page = {}
for p in prods:
    by_page.setdefault(p["page"], []).append((p["id"], p["bbox"]))

photos = map_document(doc["path"], by_page)
print("mapped:", len(photos), "of", len(prods))

shown = 0
for p in prods:
    ph = photos.get(p["id"])
    if not ph:
        continue
    w = ph["bbox"][2] - ph["bbox"][0]
    h = ph["bbox"][3] - ph["bbox"][1]
    print(f"  p{p['page']+1} {p['model_name'][:22]:24} {str(p['variant_code'])[:8]:10} "
          f"matrix_top={p['bbox'][1]:.0f} crop={ph['bbox']} ({w:.0f}x{h:.0f})")
    if shown < 3:
        data = render_crop(doc["path"], ph["page"], ph["bbox"], dpi=110)
        out = f"/app/data/_crop_test_{shown}.png"
        open(out, "wb").write(data)
        print("     wrote", out, len(data), "bytes")
        shown += 1
