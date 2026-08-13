"""
============================================================================
INTEGRATION STUB: proprietary PDF spatial parsing pipeline
============================================================================
This module is a MODULAR PLACEHOLDER. The owner will manually inject the
proprietary geometrical parsing scripts (PyMuPDF) and custom micrograd
anomaly-detection scripts here post-export.

CONTRACT (do not change the signature or the return shape):

    run_extraction_pipeline(directory_path: str) -> dict

    Input : path to a local directory containing downloaded PDF price lists
            (e.g. /tmp/processing/<task_id>/pdfs)
    Output: {
        "collections": [
            {
                "name": str,
                "designer_name": str | None,
                "release_year": int | None,
                "products": [
                    {
                        "model_name": str,
                        "category": str,
                        "dimensions_raw": str,
                        "base_price": float,
                        "variations_metadata": dict,   # price matrix / finishes
                        "source_file": str,            # relative pdf filename
                        "source_page": int             # page for QA deep link
                    }, ...
                ]
            }, ...
        ],
        "stats": {"files_processed": int, "pages_scanned": int}
    }
============================================================================
"""
import os
import random
import hashlib

CATEGORIES = ["Sofa", "Armchair", "Dining Table", "Coffee Table", "Chair", "Bed", "Sideboard", "Bookcase", "Wardrobe"]
DESIGNERS = ["Vincent Van Duysen", "Rodolfo Dordoni", "Jean-Marie Massaud", "Patricia Urquiola", "Nicola Gallizia", "Ron Gilad"]
MODEL_PREFIXES = ["Paul", "Gregor", "Octave", "Turner", "Camden", "Marteen", "Augusto", "Gliss", "Heritage", "Azul", "D.154", "Half"]
FABRIC_CATS = ["Cat. A", "Cat. B", "Cat. C", "Cat. D", "Leather Extra", "Leather Nabuk"]
FINISHES = ["Eucalyptus", "Graphite Oak", "Glossy Lacquer", "Matt Lacquer", "Canaletto Walnut", "Black Elm"]


def _rng_for(name: str) -> random.Random:
    seed = int.from_bytes(hashlib.sha256(name.encode()).digest()[:8], "big")
    return random.Random(seed)


def run_extraction_pipeline(directory_path: str) -> dict:
    """
    PLACEHOLDER implementation. Generates deterministic dummy catalog data
    from PDF filenames found in `directory_path`. Replace the body of this
    function with the proprietary PyMuPDF + micrograd extraction logic.
    """
    pdf_files = []
    for root, _dirs, files in os.walk(directory_path):
        for f in files:
            if f.lower().endswith(".pdf"):
                rel = os.path.relpath(os.path.join(root, f), directory_path)
                pdf_files.append(rel)
    pdf_files.sort()

    collections = []
    total_pages = 0
    for pdf in pdf_files:
        stem = os.path.splitext(os.path.basename(pdf))[0]
        rng = _rng_for(stem)
        n_products = rng.randint(4, 9)
        products = []
        for i in range(n_products):
            category = rng.choice(CATEGORIES)
            model = f"{rng.choice(MODEL_PREFIXES)} {rng.randint(10, 99)}"
            w, d, h = rng.randint(80, 320), rng.randint(60, 120), rng.randint(40, 210)
            base = round(rng.uniform(650, 18500), 2)
            page = rng.randint(2, 48)
            total_pages = max(total_pages, page)
            variations = {
                "price_matrix": {
                    cat: round(base * (1 + 0.12 * j), 2)
                    for j, cat in enumerate(rng.sample(FABRIC_CATS, k=3))
                },
                "finishes": rng.sample(FINISHES, k=2),
                "modules": rng.randint(1, 6),
            }
            products.append({
                "model_name": model,
                "category": category,
                "dimensions_raw": f"W{w} x D{d} x H{h} cm",
                "base_price": base,
                "variations_metadata": variations,
                "source_file": pdf,
                "source_page": page,
            })
        collections.append({
            "name": stem.replace("_", " ").replace("-", " ").title()[:250],
            "designer_name": rng.choice(DESIGNERS),
            "release_year": rng.randint(2015, 2025),
            "products": products,
        })

    return {
        "collections": collections,
        "stats": {"files_processed": len(pdf_files), "pages_scanned": total_pages},
    }
