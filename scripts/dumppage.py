"""Dump one page's real geometry: line-level blocks with bbox, size, rotation."""
import os, re, sys
import fitz

PRICE_RE = re.compile(r"^\d{1,3}(?:[.\s]\d{3})*(?:,\d{2})?$")
path = sys.argv[1]
pno = int(sys.argv[2])
doc = fitz.open(path)
page = doc[pno]
W, H = page.rect.width, page.rect.height
print(f"=== {os.path.basename(path)} page {pno} size={W:.1f}x{H:.1f} rot={page.rotation} ===")
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
        font = ln["spans"][0].get("font", "")
        x0, y0, x1, y1 = ln["bbox"]
        rows.append((round(y0, 1), round(x0, 1), round(x1, 1), round(size, 1), tuple(round(v) for v in ln["dir"]), font, txt))
rows.sort()
print(f"{len(rows)} line-blocks")
for r in rows:
    tag = "PRICE" if PRICE_RE.match(r[6]) else ("BIG" if r[3] >= 14.0 else "")
    print(f"y0={r[0]:7} x0={r[1]:7} x1={r[2]:7} sz={r[3]:5} dir={r[4]} {tag:5} {r[5][:14]:16}| {r[6][:60]}")
