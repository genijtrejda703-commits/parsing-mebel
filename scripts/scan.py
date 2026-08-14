"""Scan: where do >=14pt blocks live, what are running headers, how many price candidates."""
import os, re, sys, collections
import fitz

PRICE_RE = re.compile(r"^\d{1,3}(?:[.\s]\d{3})*(?:,\d{2})?$")
path = sys.argv[1]
lim = int(sys.argv[2]) if len(sys.argv) > 2 else 60
doc = fitz.open(path)
print(f"=== {os.path.basename(path)} pages={len(doc)} ===")
sizehist = collections.Counter()
big_texts = collections.Counter()
for pno in range(min(len(doc), lim)):
    page = doc[pno]
    H = page.rect.height
    d = page.get_text("dict")
    maxsz = 0.0
    npr = 0
    hdr = []
    big = []
    for b in d["blocks"]:
        if b.get("type") != 0:
            continue
        for ln in b["lines"]:
            t = "".join(s["text"] for s in ln["spans"]).strip()
            if not t:
                continue
            sz = max(s["size"] for s in ln["spans"])
            sizehist[round(sz)] += 1
            dirv = tuple(round(v) for v in ln["dir"])
            if dirv != (1, 0):
                continue
            y0, y1 = ln["bbox"][1], ln["bbox"][3]
            maxsz = max(maxsz, sz)
            if PRICE_RE.match(t):
                npr += 1
            if y0 < 0.05 * H:
                hdr.append(f"{t[:42]}({sz:.0f})")
            if sz >= 14.0:
                big.append(f"{t[:36]}({sz:.0f})")
                big_texts[t[:40]] += 1
    if pno < lim:
        print(f"p{pno:>3} maxsz={maxsz:5.1f} prices={npr:>4} hdr={hdr[:2]} big={big[:3]}")
print("\nfont size histogram:", dict(sorted(sizehist.items())))
print("\nmost common >=14pt texts:", big_texts.most_common(12))
