"""Probe: are the visuals on Molteni price-list pages raster images or vector art?

This decides how product photo crops must be produced:
  * raster images present -> map via page.get_image_info() bboxes
  * vector drawings only  -> fall back to a geometric 'visual region' crop
"""
import sys

import pymupdf as fitz

path = sys.argv[1]
pages = [int(x) for x in sys.argv[2].split(",")]
doc = fitz.open(path)
for pno in pages:
    page = doc[pno]
    W, H = page.rect.width, page.rect.height
    try:
        info = page.get_image_info(xrefs=True)
    except Exception as e:
        info = []
        print("get_image_info failed:", e)
    big = [i for i in info
           if (i["bbox"][2] - i["bbox"][0]) > 60 and (i["bbox"][3] - i["bbox"][1]) > 60]
    drawings = page.get_drawings()
    print(f"\npage {pno}: {W:.0f}x{H:.0f}  raster_images={len(info)} (big={len(big)})  vector_paths={len(drawings)}")
    for i in big[:6]:
        b = i["bbox"]
        print(f"   raster bbox=({b[0]:.0f},{b[1]:.0f},{b[2]:.0f},{b[3]:.0f}) "
              f"{b[2]-b[0]:.0f}x{b[3]-b[1]:.0f} xref={i.get('xref')}")
    if drawings:
        xs0 = min(d["rect"][0] for d in drawings)
        ys0 = min(d["rect"][1] for d in drawings)
        xs1 = max(d["rect"][2] for d in drawings)
        ys1 = max(d["rect"][3] for d in drawings)
        print(f"   vector envelope=({xs0:.0f},{ys0:.0f},{xs1:.0f},{ys1:.0f})")
