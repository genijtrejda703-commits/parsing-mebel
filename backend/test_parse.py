"""Dev harness: prove the real parser + micrograd on live Molteni pages."""
import sys

from assemble import build_products, run_micrograd
from pipeline import parse_pdf

path = sys.argv[1]
mx = int(sys.argv[2]) if len(sys.argv) > 2 else 46

pages = parse_pdf(path, max_pages=mx, on_page=lambda i, t, n: print(f"  page {i}/{t} prices={n}"))
print(f"\nparsed {len(pages)} pages")

model, meta = run_micrograd(pages, log=lambda m: print("  [mg]", m))
print("micrograd meta:", {k: v for k, v in meta.items() if k not in ("loss_curve", "acc_curve")})
print("loss curve:", meta["loss_curve"][:8], "...", meta["loss_curve"][-4:])
print("acc  curve:", meta["acc_curve"][:8], "...", meta["acc_curve"][-4:])

prods, stats = build_products(pages, {"factory_id": "f1", "factory": "Molteni & C",
                                      "doc_id": "d1", "doc_name": path.split("/")[-1],
                                      "collection": "Living Systems - Dining"})
print("\nSTATS:", {k: v for k, v in stats.items() if k != "anomaly_samples"})

# page 15 = table of contents -> must be rejected
p15 = [p for p in prods if p["page"] == 15]
print(f"\npage 15 (table of contents) products kept: {len(p15)}  <-- want ~0")

for pageno in (37, 39, 41):
    sub = [p for p in prods if p["page"] == pageno]
    print(f"\n===== PAGE {pageno}: {len(sub)} products =====")
    for p in sub[:6]:
        print(f"  model={p['model_name']!r}")
        print(f"    category={p['category']!r} dim={p['dimension']!r} code={p['variant_code']!r}")
        print(f"    range={p['price_min']}-{p['price_max']} EUR  n_var={p['n_variations']} "
              f"conf={p['confidence']} anomaly={p['anomaly']}")
        for v in p["variations"][:5]:
            print(f"       {str(v['finish'])[:38]:40} {v['price']:>9}  conf={v['confidence']}")

print("\nANOMALY SAMPLES (rejected by micrograd):")
for a in stats["anomaly_samples"][:8]:
    print("  ", a)

print("\nmodel-name coverage:")
from collections import Counter
c = Counter(p["model_name"] for p in prods)
for k, v in c.most_common(10):
    print(f"   {v:>5}  {k}")
