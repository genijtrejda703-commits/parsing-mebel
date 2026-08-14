"""Real PyMuPDF spatial parsing for furniture price lists.

No OCR, no LLM guessing: we reconstruct the price matrix from raw glyph
geometry, exactly the way a human reads the page.

Verified against the live Molteni & C 2026 price lists, e.g.
`2026_PL_Living-Systems-Dining_EN_EUR.pdf` page 37, whose real layout is:

                    1 module   2 modules  3 modules ...   <- dimension header
                    SP3/04     SP3/08     SP3/12  ...     <- variant code
    matt lacquer BC     96        120        175  ...     <- finish row + prices
    matt lacquer col   112        147        208  ...
    woods*             115        149        230  ...
    glossy lacquer     152        228        373  ...

So a PRODUCT is one *column* (dimension / variant code) and its VARIATIONS are
the finishes down that column -> which is precisely where the min-max price
range comes from.

Rules implemented per spec:
  * headers/footers: blocks with y0 < 5% or y1 > 95% of page height are removed
    from matrix assembly (they are kept aside because on this brand the running
    header carries the model name - see `resolve_model`).
  * model name: blocks with font_size >= 14.0pt, minus the ignore list.
  * price regex: ^\\d{1,3}(?:[.\\s]\\d{3})*(?:,\\d{2})?$
  * matrix assembly: for a price block, the closest block directly ABOVE
    (same x0 +/- 10px) and the closest block to the LEFT (same y0 +/- 10px).
"""
import io
import os
import re
import statistics
import uuid

import pymupdf as fitz

PRICE_RE = re.compile(r"^\d{1,3}(?:[.\s]\d{3})*(?:,\d{2})?$")

IGNORE_MODEL_NAMES = ["MOLTENI", "MOLTENI & C", "LIVING SYSTEMS", "KITCHENS",
                      "DADA", "GLISS MASTER", "Gio Ponti", "Vincent Van Duysen"]

STOP_PHRASES = ["GENERAL TERMS", "CONDITIONS OF SALE", "PRICE LIST", "CONTENTS",
                "GUIDE TO CONSULTATION", "INTERACTIVE DIGITAL", "INSTRUCTIONS FOR",
                "USER FRIENDLY", "DIGITAL ECOSYSTEM", "3D CONFIGURATOR", "GUARANTEE",
                "MOLTENI GROUP", "PRODUCT INFORMATION", "MADE IN ITALY", "OUR DESIGN",
                "PIGRECO", "NEW ENTRY", "INDEX", "SUMMARY",
                "MEASUREMENTS IN", "CONVERSION", "SYMBOLS", "LEGEND", "HOW TO",
                "PACKAGING", "TRANSPORT", "PAYMENT", "DELIVERY", "WARRANTY",
                "IN CLIENT FABRIC", "ORDERS IN CLIENT", "COMPOSITION EXAMPLE",
                "NOTES", "IMPORTANT", "SURCHARGE FOR", "PLEASE NOTE"]

DIM_RE = re.compile(r"(\b[WHDL]\s?\d{2,4}\b)|(\b\d{2,4}\b)|(\d+\s*modul)|(\bth\s?\d+\b)"
                    r"|(\bcm\b)|(\d+\s*[xX]\s*\d+)|(\bdepth\b)|(\bwidth\b)|(\bheight\b)",
                    re.IGNORECASE)
CODE_RE = re.compile(r"^[A-Z]{1,4}\d{0,2}[./\-]\d{1,3}(?:[./\-]\d{1,3})?[A-Z]?$")
HAS_LETTER = re.compile(r"[A-Za-zÀ-ÿ]")

DATA_DIR = os.environ.get("DATA_DIR", "/app/data")


def norm(text):
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9 ]", " ", (text or "").upper())).strip()


_IGNORE_NORM = {norm(x) for x in IGNORE_MODEL_NAMES}
_IGNORE_TOKENS = {t for x in _IGNORE_NORM for t in x.split()}


def parse_price(raw):
    s = (raw or "").strip()
    try:
        if "," in s:
            whole, dec = s.split(",", 1)
            whole = re.sub(r"[.\s]", "", whole)
            return float(f"{whole or 0}.{dec}")
        return float(re.sub(r"[.\s]", "", s))
    except Exception:
        return None


def doc_title_tokens(filename):
    base = os.path.splitext(os.path.basename(filename))[0]
    base = re.sub(r"[_\-]+", " ", base)
    drop = {"PL", "EN", "EUR", "IT", "CL", "TD", "FN", "EXPORT", "UPDATE", "NEWS"}
    toks = set()
    for t in norm(base).split():
        if t.isdigit() or t in drop or len(t) < 3:
            continue
        toks.add(t)
    return toks


# --------------------------------------------------------------------------- #
# block extraction
# --------------------------------------------------------------------------- #
def extract_blocks(page):
    """Line-level blocks with [x0, y0, x1, y1, font_size]. Splits header/footer
    and rotated running labels out of the matrix body."""
    W, H = float(page.rect.width), float(page.rect.height)
    top_cut, bot_cut = 0.05 * H, 0.95 * H
    body, headers, side = [], [], []
    d = page.get_text("dict")
    for b in d.get("blocks", []):
        if b.get("type") != 0:
            continue
        for ln in b.get("lines", []):
            spans = ln.get("spans", [])
            text = "".join(s.get("text", "") for s in spans).strip()
            if not text:
                continue
            size = max((s.get("size", 0.0) for s in spans), default=0.0)
            font = spans[0].get("font", "") if spans else ""
            x0, y0, x1, y1 = [float(v) for v in ln["bbox"]]
            direction = tuple(round(v) for v in ln.get("dir", (1, 0)))
            blk = {"text": text, "x0": round(x0, 2), "y0": round(y0, 2),
                   "x1": round(x1, 2), "y1": round(y1, 2),
                   "size": round(size, 2), "font": font}
            if direction != (1, 0):
                side.append(blk)                     # rotated section labels
            elif y0 < top_cut or y1 > bot_cut:
                headers.append(blk)                  # stripped per spec
            else:
                body.append(blk)
    body.sort(key=lambda b: (b["y0"], b["x0"]))
    return body, headers, side, W, H


MODEL_TAIL_RE = re.compile(r"\s+(depth|width|height|prof\.?|larg\.?)\s*\.?\s*\d+.*$", re.I)
MODEL_TAIL2_RE = re.compile(r"\s+[WHDL]\s*\d{2,4}.*$")
DIM_WORDS = {"DEPTH", "WIDTH", "HEIGHT", "D", "W", "H", "TH", "MM", "CM", "PROF", "LARG"}


def clean_model(text):
    """Normalise a raw title/running header into a stable model name.

    Running headers on this brand look like `505 UP System depth 400` or
    `505 UP System    Composition examples`; the stable model is the prefix.
    """
    if not text:
        return None
    t = re.split(r"\s{2,}", text.strip())[0].strip()
    t = MODEL_TAIL_RE.sub("", t)
    t = MODEL_TAIL2_RE.sub("", t)
    t = t.strip(" -\u2013\u2014*\u00b7").strip()
    if len(t) < 3 or not HAS_LETTER.search(t):
        return None
    first = HAS_LETTER.search(t)
    if not t[first.start()].isupper():          # footnote prose starts lowercase
        return None
    n = norm(t)
    if n in _IGNORE_NORM or any(p in n for p in STOP_PHRASES):
        return None
    toks = n.split()
    if toks and all(x.isdigit() or x in DIM_WORDS for x in toks):
        return None
    return t


def resolve_model(headers, body, title_tokens, page_h=842.0, med_size=7.0):
    """Model name = biggest >=14pt block that is not brand boilerplate."""
    cands = []
    for b in body + headers:
        if b["size"] < 14.0:
            continue
        t = b["text"].strip()
        if len(t) < 3 or not HAS_LETTER.search(t) or PRICE_RE.match(t):
            continue
        if t.endswith("*"):                      # footnote annotation, not a title
            continue
        if b["size"] < 1.6 * med_size:
            continue
        if b["y0"] > 0.6 * page_h:
            continue
        n = norm(t)
        if n in _IGNORE_NORM:
            continue
        toks = set(n.split())
        if toks and (toks <= _IGNORE_TOKENS or toks <= title_tokens):
            continue
        if any(p in n for p in STOP_PHRASES):
            continue
        if n.startswith("DESIGN "):
            continue
        cands.append(b)
    if not cands:
        return None
    cands.sort(key=lambda b: (-b["size"], b["y0"]))
    return cands[0]["text"].strip()


def page_context(headers):
    """running_header (largest, carries model) + section_title (small, category)."""
    hs = sorted(headers, key=lambda b: (-b["size"], b["y0"]))
    running = hs[0]["text"].strip() if hs and hs[0]["size"] >= 9.5 else None
    section = None
    for h in sorted(headers, key=lambda b: b["y0"]):
        if h["size"] < 9.5 and HAS_LETTER.search(h["text"]) and len(h["text"].strip()) > 3:
            section = h["text"].strip()
            break
    return running, section


# --------------------------------------------------------------------------- #
# matrix assembly
# --------------------------------------------------------------------------- #
def _nearest_above(block, others, tol=10.0):
    """Closest non-price block directly above, same x0 +/- tol (center fallback)."""
    best, best_gap = None, 1e9
    cx = (block["x0"] + block["x1"]) / 2
    for o in others:
        if o["y1"] > block["y0"] + 1.0:
            continue
        aligned = abs(o["x0"] - block["x0"]) <= tol
        if not aligned:
            ox = (o["x0"] + o["x1"]) / 2
            aligned = abs(ox - cx) <= tol + 2
        if not aligned:
            continue
        gap = block["y0"] - o["y1"]
        if 0 <= gap < best_gap:
            best, best_gap = o, gap
    return best, best_gap


def _chain_above(block, others, limit=3, tol=10.0):
    chain, cur = [], dict(block)
    pool = list(others)
    for _ in range(limit):
        nxt, gap = _nearest_above(cur, pool, tol)
        if not nxt or gap > 40:
            break
        chain.append(nxt)
        pool = [o for o in pool if o is not nxt]
        cur = nxt
    return chain


def _nearest_left(block, others, tol=10.0):
    best, best_gap = None, 1e9
    for o in others:
        if o["x1"] > block["x0"] + 1.0:
            continue
        if abs(o["y0"] - block["y0"]) > tol:
            continue
        gap = block["x0"] - o["x1"]
        if 0 <= gap < best_gap:
            best, best_gap = o, gap
    return best


def page_matrix(body, W, H):
    """Find price candidates and their spatial neighbours, then group into tables."""
    prices, plain = [], []
    for b in body:
        (prices if PRICE_RE.match(b["text"]) else plain).append(b)
    if not prices:
        return [], []

    med_size = statistics.median([b["size"] for b in body]) if body else 7.0

    for p in prices:
        p["row_peers"] = sum(1 for q in prices if abs(q["y0"] - p["y0"]) <= 3.0)
        p["col_peers"] = sum(1 for q in prices if abs(q["x0"] - p["x0"]) <= 10.0)
        chain = _chain_above(p, plain)
        p["above"] = chain[0] if chain else None
        p["above_chain"] = chain
        p["left"] = _nearest_left(p, plain)
        p["value"] = parse_price(p["text"])
        p["median_size"] = med_size

    # ---- rows -> tables -> columns ----
    rows = []
    for p in sorted(prices, key=lambda b: (b["y0"], b["x0"])):
        if rows and abs(rows[-1]["y"] - p["y0"]) <= 3.0:
            rows[-1]["cells"].append(p)
        else:
            rows.append({"y": p["y0"], "cells": [p]})

    tables, cur = [], None
    for r in rows:
        xs = {round(c["x0"] / 8) for c in r["cells"]}
        if cur is None:
            cur = {"rows": [r], "xs": xs}
            continue
        gap = r["y"] - cur["rows"][-1]["y"]
        inter = len(xs & cur["xs"]) / max(len(xs | cur["xs"]), 1)
        if gap <= 30 and (inter >= 0.4 or len(xs) == 1):
            cur["rows"].append(r)
            cur["xs"] |= xs
        else:
            tables.append(cur)
            cur = {"rows": [r], "xs": xs}
    if cur:
        tables.append(cur)

    out = []
    for t in tables:
        cols = {}
        for r in t["rows"]:
            for c in r["cells"]:
                key = None
                for k in cols:
                    if abs(k - c["x0"]) <= 10.0:
                        key = k
                        break
                cols.setdefault(key if key is not None else c["x0"], []).append(c)
        out.append({"rows": t["rows"], "cols": cols})
    return prices, out


def describe_column(cells):
    """Resolve dimension / variant code / raw headers for one matrix column."""
    top = min(cells, key=lambda c: c["y0"])
    chain = top.get("above_chain") or []
    dimension, code, raw = None, None, []
    for blk in chain:
        t = blk["text"].strip()
        raw.append(t)
        if code is None and CODE_RE.match(t):
            code = t
        elif dimension is None and DIM_RE.search(t) and not PRICE_RE.match(t):
            dimension = t
    if dimension is None and code is None and raw:
        dimension = raw[0]
    return dimension, code, raw, chain


# --------------------------------------------------------------------------- #
# document level
# --------------------------------------------------------------------------- #
def parse_pdf(path, max_pages=None, on_page=None):
    """Pass 1: real geometric parse of every page. Returns pages + candidates."""
    doc = fitz.open(path)
    tokens = doc_title_tokens(path)
    total = len(doc) if max_pages is None else min(len(doc), max_pages)
    pages, carried = [], None
    for pno in range(total):
        page = doc[pno]
        body, headers, side, W, H = extract_blocks(page)
        running, section = page_context(headers)
        med = statistics.median([b["size"] for b in body]) if body else 7.0
        found = clean_model(resolve_model(headers, body, tokens, H, med))
        if found:
            carried = found
        model = found
        if not model:
            rc = clean_model(running)
            if rc:
                if carried and norm(carried) in norm(rc):
                    model = carried
                else:
                    model = rc
                    carried = rc
            else:
                model = carried
        prices, tables = page_matrix(body, W, H)
        pages.append({
            "page": pno, "width": W, "height": H,
            "model_name": model, "running_header": running, "section_title": section,
            "side_labels": [s["text"] for s in side][:6],
            "n_blocks": len(body), "n_headers": len(headers),
            "header_prices": [{"text": b["text"],
                               "bbox": [b["x0"], b["y0"], b["x1"], b["y1"]],
                               "zone": "header" if b["y0"] < 0.05 * H else "footer"}
                              for b in headers if PRICE_RE.match(b["text"])],
            "prices": prices, "tables": tables,
        })
        if on_page and (pno % 10 == 0 or pno == total - 1):
            on_page(pno + 1, total, len(prices))
    doc.close()
    return pages


def render_page_png(pdf_path, page_no, dpi=120):
    """On-demand page raster for the QA split-screen (disk cached)."""
    key = f"{os.path.basename(pdf_path)}__{page_no}__{dpi}.png"
    cache_dir = os.path.join(DATA_DIR, "pages")
    os.makedirs(cache_dir, exist_ok=True)
    dest = os.path.join(cache_dir, key)
    if os.path.exists(dest):
        with open(dest, "rb") as f:
            return f.read()
    doc = fitz.open(pdf_path)
    pix = doc[page_no].get_pixmap(dpi=dpi)
    data = pix.tobytes("png")
    doc.close()
    with open(dest, "wb") as f:
        f.write(data)
    return data
