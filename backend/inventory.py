"""Directive 2: content-based file inventory + coverage.

Classifies each PDF by what is *inside* it (filenames lie): document type,
year/version, currency, multi-volume grouping and supersede relationships.
Coverage numbers are read back from the ingest pass stored on `documents`.
"""
import os
import re
import uuid
from datetime import datetime, timezone

import fitz  # PyMuPDF

YEAR_RE = re.compile(r"\b(20[12]\d)\b")
VOL_RE = re.compile(r"\b(?:vol(?:ume)?\.?|part|tomo)\s*\.?\s*(\d+)\b", re.I)

# content keyword signals (filenames lie, so we read the pages)
FABRIC_KW = ["categoria tessuti", "fabric category", "fabrics category",
             "leather category", "covering category", "campionario",
             "swatch book", "sample book"]
TECH_KW = ["scheda tecnica", "technical sheet", "assembly instruction",
           "installation manual", "maintenance manual", "istruzioni di montaggio"]
MKT_KW = ["marketing tools", "brochure", "lookbook", "press kit",
          "press release", "moodboard", "communication kit"]
CAT_KW = ["general catalogue", "collection book", "catalogo generale",
          "general catalog"]
PRICE_KW = ["listino", "price list", "price-list", "prezzi di listino",
            "recommended retail price", "net price list", "listino prezzi"]

CUR_RULES = [("EUR", ["€", " eur", "euro"]), ("USD", ["us$", "usd", " $"]),
             ("GBP", ["£", "gbp"]), ("CHF", ["chf"])]


def _norm_group(name):
    """Collapse a filename to a collection key (drop year/lang/currency/vol)."""
    s = re.sub(r"\.pdf$", "", name, flags=re.I)
    s = re.sub(r"20[12]\d", "", s)
    s = re.sub(r"\b(EN|IT|FR|DE|ES|EUR|USD|GBP|CHF|PL|Vol\.?\d+|Part\d+)\b", "",
               s, flags=re.I)
    s = re.sub(r"[_\-]+", " ", s)
    s = re.sub(r"[^A-Za-z ]", " ", s)
    return re.sub(r"\s+", " ", s).strip().upper()


def classify_pdf(path):
    """Return a content-derived classification dict for one PDF."""
    name = os.path.basename(path)
    info = {"name": name, "size": os.path.getsize(path) if os.path.exists(path) else 0,
            "pages": 0, "doc_type": "прочее", "year": None, "currency": None,
            "currency_valid": False, "volume": None, "group_key": _norm_group(name),
            "sample_title": "", "error": None}
    try:
        doc = fitz.open(path)
    except Exception as e:  # unreadable / not a pdf
        info["error"] = f"{type(e).__name__}: {e}"
        return info
    try:
        info["pages"] = doc.page_count
        n = min(6, doc.page_count)
        text = ""
        for i in range(n):
            text += doc.load_page(i).get_text("text") + "\n"
        # also last page (indexes/legends often there)
        if doc.page_count > n:
            text += doc.load_page(doc.page_count - 1).get_text("text")
        low = text.lower()

        # title = first non-trivial line of page 1
        for line in text.splitlines():
            t = line.strip()
            if len(t) >= 4 and not t.isdigit():
                info["sample_title"] = t[:120]
                break

        # doc type: content signals + Molteni filename type-codes (strong prior).
        # euro symbols alone are NOT enough (catalogues/finishes guides show prices).
        nl = name.lower()
        pl_name = any(t in nl for t in ("_pl_", "listino", "price-list", "price list",
                                        "price-lists", "pricelist"))
        cat_name = ("catalog" in nl or "catalogo" in nl or "collection book" in nl
                    or "art of living" in nl)
        # any "finishes/_FN_" file is a finishes/fabric doc, never a price list
        finishes_doc = ("_fn_" in nl or "finishes" in nl or "finish-guide" in nl
                        or "отделки" in nl)
        fn_name = finishes_doc
        mkt_name = any(t in nl for t in ("_ae_", "_cl_", "brochure", "leaflet",
                                         "styling-book", "magazine", "circular"))
        td_name = ("_td_" in nl or "product-sheet" in nl or "product sheet" in nl
                   or "_fr_" in nl)

        content_price = any(k in low for k in PRICE_KW)
        # content-only price signal must be a real multi-page listino, not a leaflet
        price = pl_name or (content_price and (info["pages"] or 0) >= 8)
        fabric = any(k in low for k in FABRIC_KW) or fn_name
        mkt = any(k in low for k in MKT_KW) or mkt_name
        tech = any(k in low for k in TECH_KW) or td_name
        cat = any(k in low for k in CAT_KW) or cat_name

        if finishes_doc:
            info["doc_type"] = "ткани и отделки"
        elif price and not (cat_name and not pl_name):
            info["doc_type"] = "прайс-лист"
        elif cat:
            info["doc_type"] = "каталог"
        elif fabric:
            info["doc_type"] = "ткани и отделки"
        elif mkt:
            info["doc_type"] = "маркетинг"
        elif tech:
            info["doc_type"] = "технический"
        else:
            info["doc_type"] = "прочее"

        # year from content + pdf metadata; take the most plausible (max)
        years = [int(y) for y in YEAR_RE.findall(text) if 2015 <= int(y) <= 2027]
        meta = doc.metadata or {}
        for key in ("creationDate", "modDate"):
            m = re.search(r"20[12]\d", meta.get(key, "") or "")
            if m:
                years.append(int(m.group(0)))
        if years:
            info["year"] = max(set(years), key=years.count) if len(years) < 4 else max(years)

        # currency
        for cur, kws in CUR_RULES:
            if any(k in low for k in kws):
                info["currency"] = cur
                info["currency_valid"] = True
                break

        vm = VOL_RE.search(text) or VOL_RE.search(name)
        if vm:
            info["volume"] = int(vm.group(1))
    finally:
        doc.close()
    return info


def supersede_pass(records):
    """Within each group, the newest price list is current; older ones superseded."""
    groups = {}
    for r in records:
        if r["doc_type"] == "прайс-лист":
            groups.setdefault(r["group_key"], []).append(r)
    for key, items in groups.items():
        yrs = [i["year"] for i in items if i["year"]]
        newest = max(yrs) if yrs else None
        for i in items:
            if newest and i["year"] and i["year"] < newest:
                i["is_current_listino"] = False
                i["superseded_by"] = f"{key} {newest}"
            else:
                i["is_current_listino"] = True
                i["superseded_by"] = None
    # non price lists are never "current listini"
    for r in records:
        r.setdefault("is_current_listino", False)
        r.setdefault("superseded_by", None)
    return records


def make_record(path, source="local", rel=None):
    c = classify_pdf(path)
    c["id"] = str(uuid.uuid4())
    c["source"] = source
    c["rel"] = rel or os.path.basename(path)
    c["classified_at"] = datetime.now(timezone.utc).isoformat()
    return c
