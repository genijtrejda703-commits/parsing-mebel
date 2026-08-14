"""Excel export of the approved catalogue (openpyxl, native UTF-8).

Keeps the structural logic of the source data:
    Фабрика -> Коллекция -> Модель -> Категория -> Габариты -> Цена мин/макс
Two shapes are supported:
    mode="product"   one row per product (with its min-max range)
    mode="variation" one row per finish variation (the full price matrix)
"""
import io
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

BRASS = "C9A227"
DARK = "1C1A17"
LIGHT = "FAF7F0"

HEAD_PRODUCT = ["Фабрика", "Коллекция", "Модель", "Категория", "Габариты", "Артикул",
                "Вариантов", "Цена мин, €", "Цена макс, €", "Валюта", "Точность, %",
                "Статус", "Документ", "Стр.", "Заметки проверяющего"]
HEAD_VARIATION = ["Фабрика", "Коллекция", "Модель", "Категория", "Габариты", "Артикул",
                  "Отделка", "Цена, €", "Точность, %", "Статус", "Документ", "Стр.",
                  "Заметки проверяющего"]
WIDTHS_PRODUCT = [16, 26, 24, 30, 16, 13, 10, 13, 13, 9, 11, 12, 34, 7, 34]
WIDTHS_VARIATION = [16, 26, 24, 30, 16, 13, 30, 12, 11, 12, 34, 7, 34]

STATUS_RU = {"approved": "Одобрено", "pending": "Ожидает", "rejected": "Отклонено"}

thin = Side(style="thin", color="D8D2C4")
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)


def _pretty_collection(name):
    import os
    import re
    base = os.path.splitext(str(name or ""))[0]
    parts = [p for p in re.split(r"[_\-\s]+", base)
             if p and p.upper() not in {"PL", "EN", "EUR", "IT"} and not p.isdigit()]
    return " ".join(parts)


def _style_header(ws, headers, widths, row=4):
    for c, (h, w) in enumerate(zip(headers, widths), start=1):
        cell = ws.cell(row=row, column=c, value=h)
        cell.font = Font(bold=True, color=DARK, size=10)
        cell.fill = PatternFill("solid", fgColor=BRASS)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
        ws.column_dimensions[get_column_letter(c)].width = w
    ws.row_dimensions[row].height = 30
    ws.freeze_panes = ws.cell(row=row + 1, column=1)
    ws.auto_filter.ref = f"A{row}:{get_column_letter(len(headers))}{row}"


def _title(ws, title, subtitle, ncols):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=min(ncols, 6))
    t = ws.cell(row=1, column=1, value=title)
    t.font = Font(bold=True, size=16, color=DARK)
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=min(ncols, 8))
    s = ws.cell(row=2, column=1, value=subtitle)
    s.font = Font(size=9, color="6B6459")
    ws.row_dimensions[1].height = 22


def build_workbook(products, meta):
    mode = meta.get("mode", "product")
    headers = HEAD_VARIATION if mode == "variation" else HEAD_PRODUCT
    widths = WIDTHS_VARIATION if mode == "variation" else WIDTHS_PRODUCT

    wb = Workbook()
    ws = wb.active
    ws.title = "Каталог"

    stamp = datetime.now().strftime("%d.%m.%Y %H:%M")
    _title(ws, f"Каталог — {meta.get('factory') or 'все фабрики'}",
           f"Статус: {meta.get('status_label')} · позиций: {len(products)} · "
           f"выгрузка: {stamp} · HOMEART Data Hub", len(headers))
    _style_header(ws, headers, widths)

    def key(p):
        return (str(p.get("factory") or ""), str(p.get("doc_name") or ""),
                str(p.get("model_name") or ""), str(p.get("category") or ""),
                str(p.get("dimension") or ""))
    rows = sorted(products, key=key)

    r = 5
    money_fmt = "#,##0"
    for p in rows:
        coll = _pretty_collection(p.get("doc_name") or p.get("collection"))
        base = [p.get("factory"), coll, p.get("model_name"), p.get("category"),
                p.get("dimension"), p.get("variant_code")]
        if mode == "variation":
            for v in (p.get("variations") or []):
                vals = base + [v.get("finish"), v.get("price"),
                               round((v.get("confidence") or 0) * 100, 1),
                               STATUS_RU.get(p.get("status"), p.get("status")),
                               p.get("doc_name"), (p.get("page") or 0) + 1,
                               p.get("reviewer_notes")]
                _write_row(ws, r, vals, [8], money_fmt)
                r += 1
        else:
            vals = base + [p.get("n_variations"), p.get("price_min"), p.get("price_max"),
                           p.get("currency") or "EUR",
                           round((p.get("confidence") or 0) * 100, 1),
                           STATUS_RU.get(p.get("status"), p.get("status")),
                           p.get("doc_name"), (p.get("page") or 0) + 1,
                           p.get("reviewer_notes")]
            _write_row(ws, r, vals, [8, 9], money_fmt)
            r += 1

    # ---- сводка ----
    ws2 = wb.create_sheet("Сводка")
    _title(ws2, "Сводка по моделям", f"выгрузка: {stamp}", 5)
    _style_header(ws2, ["Модель", "Позиций", "Цена мин, €", "Цена макс, €", "Документ"],
                  [30, 12, 14, 14, 36])
    agg = {}
    for p in rows:
        k = (p.get("model_name"), p.get("doc_name"))
        a = agg.setdefault(k, {"n": 0, "mn": None, "mx": None})
        a["n"] += 1
        for f, v in (("mn", p.get("price_min")), ("mx", p.get("price_max"))):
            if v is None:
                continue
            if a[f] is None:
                a[f] = v
            else:
                a[f] = min(a[f], v) if f == "mn" else max(a[f], v)
    rr = 5
    for (modelname, docname), a in sorted(agg.items(), key=lambda x: -x[1]["n"]):
        _write_row(ws2, rr, [modelname, a["n"], a["mn"], a["mx"], docname], [3, 4], money_fmt)
        rr += 1

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _write_row(ws, r, vals, money_cols, money_fmt):
    fill = PatternFill("solid", fgColor=LIGHT) if r % 2 == 0 else None
    for c, v in enumerate(vals, start=1):
        cell = ws.cell(row=r, column=c, value=v)
        cell.border = BORDER
        cell.font = Font(size=10)
        cell.alignment = Alignment(vertical="center",
                                   wrap_text=c in (4, 7, len(vals)),
                                   horizontal="right" if c in money_cols else "left")
        if c in money_cols:
            cell.number_format = money_fmt
        if fill:
            cell.fill = fill
