"""One-off exploration: extract Molteni price-list PDFs and dump real PyMuPDF geometry."""
import os, re, sys, zipfile, json

ZIP = "/app/data/tmp/molteni.zip"
OUT = "/app/data/molteni"
os.makedirs(OUT, exist_ok=True)

zf = zipfile.ZipFile(ZIP)
targets = [n for n in zf.namelist()
           if n.lower().endswith(".pdf") and "прайс" in n.lower() and "_PL_" in n]
print(f"price-list PDFs: {len(targets)}")
for n in targets:
    flat = os.path.basename(n)
    dest = os.path.join(OUT, flat)
    if not os.path.exists(dest):
        with zf.open(n) as src, open(dest, "wb") as dst:
            dst.write(src.read())
    print(f"  {flat}  {os.path.getsize(dest)/1e6:.1f}MB")
zf.close()

# ---- geometry dump ----
import fitz
PRICE_RE = re.compile(r"^\d{1,3}(?:[.\s]\d{3})*(?:,\d{2})?$")
path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(OUT, "2026_PL_Living-Systems-Dining_EN_EUR.pdf")
doc = fitz.open(path)
print(f"\n=== {os.path.basename(path)} pages={len(doc)} ===")

# find first pages that contain price-looking tokens
hits = []
for pno in range(min(len(doc), 40)):
    page = doc[pno]
    d = page.get_text("dict")
    n_price = 0
    for b in d["blocks"]:
        if b.get("type") != 0:
            continue
        for ln in b["lines"]:
            t = "".join(s["text"] for s in ln["spans"]).strip()
            if PRICE_RE.match(t):
                n_price += 1
    if n_price > 5:
        hits.append((pno, n_price))
print("pages with >5 price tokens:", hits[:12])

pno = hits[0][0] if hits else 0
page = doc[pno]
W, H = page.rect.width, page.rect.height
print(f"\n--- PAGE {pno} size={W:.1f}x{H:.1f} ---")
d = page.get_text("dict")
rows = []
for b in d["blocks"]:
    if b.get("type") != 0:
        continue
    for ln in b["lines"]:
        txt = "".join(s["text"] for s in ln["spans"]).strip()
        if not txt:
            continue
        size = max(s["size"] for s in ln["spans"])
        x0, y0, x1, y1 = ln["bbox"]
        rows.append((round(y0, 1), round(x0, 1), round(x1, 1), round(y1, 1), round(size, 1), txt))
rows.sort()
print(f"{len(rows)} line-blocks")
for r in rows[:130]:
    tag = "PRICE" if PRICE_RE.match(r[5]) else ("BIG" if r[4] >= 14.0 else "")
    print(f"y0={r[0]:7} x0={r[1]:7} x1={r[2]:7} sz={r[4]:5} {tag:5} | {r[5][:70]}")
