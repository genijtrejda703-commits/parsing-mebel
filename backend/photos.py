"""Product illustration crops from Molteni price-list pages.

`page.get_images()` is useless on these files: every embedded raster is a tiny
logo (verified - the largest is under 60x60pt), because the furniture drawings are
VECTOR artwork (200-1700 vector paths per page).

So instead of hunting raster xrefs we reconstruct the illustration geometrically:

1. Rasterise the *coverage* of all vector paths onto a coarse 4pt occupancy grid
   (one pass per page, cheap even for 1700 paths).
2. For each extracted price matrix, walk UPWARD from the top of its bounding box
   inside a horizontal window around the matrix, and take the contiguous band of
   covered rows - that band is the drawing that belongs to this product.
3. Tighten the band horizontally to the columns that are actually covered, then
   render just that clip with PyMuPDF at request time (disk cached).

This is the same "closest visual above the matrix" rule that was asked for, only
driven by vector coverage instead of raster bboxes.
"""
import hashlib
import os

import numpy as np
import pymupdf as fitz

CELL = 4.0
DATA_DIR = os.environ.get("DATA_DIR", "/app/data")
PHOTO_DIR = os.path.join(DATA_DIR, "photos")


def occupancy(page):
    """Boolean grid of vector-drawing coverage, CELL points per cell."""
    W, H = float(page.rect.width), float(page.rect.height)
    nx, ny = int(W / CELL) + 1, int(H / CELL) + 1
    g = np.zeros((ny, nx), dtype=bool)
    try:
        drawings = page.get_drawings()
    except Exception:
        return g, W, H
    for d in drawings:
        r = d.get("rect")
        if r is None:
            continue
        x0, y0, x1, y1 = float(r[0]), float(r[1]), float(r[2]), float(r[3])
        if x1 < x0:
            x0, x1 = x1, x0
        if y1 < y0:
            y0, y1 = y1, y0
        w, h = x1 - x0, y1 - y0
        if w > 0.95 * W and h > 0.95 * H:
            continue                      # page frame
        if w < 0.8 and h < 0.8:
            continue                      # dots
        i0, i1 = max(int(y0 / CELL), 0), min(int(y1 / CELL) + 1, ny)
        j0, j1 = max(int(x0 / CELL), 0), min(int(x1 / CELL) + 1, nx)
        if i1 <= i0 or j1 <= j0:
            continue
        g[i0:i1, j0:j1] = True
    return g, W, H


def visual_above(g, bbox, x_pad=30.0, min_h=38.0, min_w=52.0,
                 max_search=170.0, max_gap=13):
    """Contiguous covered band directly above `bbox` -> clip rect, or None."""
    ny, nx = g.shape
    j0 = max(int((bbox[0] - x_pad) / CELL), 0)
    j1 = min(int((bbox[2] + x_pad) / CELL) + 1, nx)
    top = min(max(int(bbox[1] / CELL), 0), ny)
    if j1 <= j0 or top <= 1:
        return None
    rows = g[:top, j0:j1].any(axis=1)

    end, gap, i = None, 0, top - 1
    limit = int(max_search / CELL)
    while i >= 0:
        if rows[i]:
            end = i
            break
        gap += 1
        if gap > limit:
            return None
        i -= 1
    if end is None:
        return None

    start, gap, i = end, 0, end - 1
    while i >= 0:
        if rows[i]:
            start, gap = i, 0
        else:
            gap += 1
            if gap > max_gap:
                break
        i -= 1

    y0, y1 = start * CELL, (end + 1) * CELL
    if y1 - y0 < min_h:
        return None
    band = g[start:end + 1, j0:j1]
    nz = np.nonzero(band.any(axis=0))[0]
    if not len(nz):
        return None
    x0 = (j0 + int(nz[0])) * CELL
    x1 = (j0 + int(nz[-1]) + 1) * CELL
    if x1 - x0 < min_w:
        return None
    return [round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)]


def map_document(pdf_path, products_by_page, on_page=None):
    """{page: [(product_id, bbox)...]} -> {product_id: photo dict}.

    Products belonging to the same table (same matrix top edge) share one crop
    spanning the whole table width: a single column's slice is a meaningless
    sliver, whereas the band above the full table is the coherent drawing of that
    product family - which is exactly the granularity search results dedupe to.
    """
    doc = fitz.open(pdf_path)
    out = {}
    pages = sorted(products_by_page.keys())
    for n, pno in enumerate(pages):
        if pno >= len(doc):
            continue
        try:
            g, W, H = occupancy(doc[pno])
        except Exception:
            continue
        groups = {}
        for pid, bbox in products_by_page[pno]:
            if not bbox or len(bbox) != 4:
                continue
            groups.setdefault(round(float(bbox[1]) / 6) * 6, []).append((pid, bbox))
        for _, members in groups.items():
            xs0 = min(b[0] for _, b in members)
            ys0 = min(b[1] for _, b in members)
            xs1 = max(b[2] for _, b in members)
            union = [xs0, ys0, xs1, max(b[3] for _, b in members)]
            try:
                clip = visual_above(g, union)
            except Exception:
                clip = None
            if not clip:
                continue
            photo = {"page": pno, "bbox": clip, "page_width": W, "page_height": H}
            for pid, _ in members:
                out[pid] = photo
        if on_page and (n % 25 == 0 or n == len(pages) - 1):
            on_page(n + 1, len(pages), len(out))
    doc.close()
    return out


def render_crop(pdf_path, page_no, bbox, dpi=120):
    os.makedirs(PHOTO_DIR, exist_ok=True)
    key = hashlib.sha1(
        f"{os.path.basename(pdf_path)}|{page_no}|{bbox}|{dpi}".encode()).hexdigest()[:20]
    dest = os.path.join(PHOTO_DIR, key + ".png")
    if os.path.exists(dest):
        with open(dest, "rb") as f:
            return f.read()
    doc = fitz.open(pdf_path)
    page = doc[page_no]
    rect = fitz.Rect(*bbox) & page.rect
    pix = page.get_pixmap(clip=rect, dpi=dpi)
    data = pix.tobytes("png")
    doc.close()
    with open(dest, "wb") as f:
        f.write(data)
    return data
