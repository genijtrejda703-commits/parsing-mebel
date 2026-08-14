#!/usr/bin/env python3
"""Generate «Отчёт по фабрике Molteni & C» (markdown) with REAL numbers.

Reads the live Mongo catalogue and writes /app/reports/Molteni_C_report.md.
Run any time after ingest: python3 scripts/build_report.py
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
import db  # noqa: E402

OUT_DIR = "/app/reports"
OUT = os.path.join(OUT_DIR, "Molteni_C_report.md")


def fmt(n):
    return f"{n:,}".replace(",", " ") if isinstance(n, (int, float)) else (n or "—")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    positions = db.positions.count_documents({})
    variants = db.variant_prices.count_documents({})
    docs = list(db.documents.find({}, {"_id": 0}).sort("variant_prices", -1))
    # prefer the full-folder (dropbox) inventory when present, else local
    inv = list(db.file_inventory.find({"source": "dropbox"}, {"_id": 0}))
    inv_source = "полная папка Dropbox"
    if not inv:
        inv = list(db.file_inventory.find({}, {"_id": 0}))
        inv_source = "локальные файлы"
    flagged = db.positions.count_documents({"flagged": True})
    zero_price = db.variant_prices.count_documents({"price": {"$lte": 0}})
    low_price = db.variant_prices.count_documents({"price": {"$gt": 0, "$lt": 5}})
    unnamed = db.positions.count_documents({"norm_name": "UNASSIGNED"})

    # coverage totals
    T = {"pages_total": 0, "pages_with_matrix": 0, "pages_parsed": 0,
         "pages_skipped": 0, "rejected_cells": 0}
    for d in docs:
        c = d.get("coverage") or {}
        for k in T:
            T[k] += c.get(k, 0)

    # inventory rollups
    by_type = {}
    by_year = {}
    for r in inv:
        by_type[r.get("doc_type")] = by_type.get(r.get("doc_type"), 0) + 1
        by_year[r.get("year")] = by_year.get(r.get("year"), 0) + 1
    current = [r for r in inv if r.get("is_current_listino")]
    classified_only = [r for r in inv if not r.get("ingested")]

    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    L = []
    L.append("# Отчёт по фабрике Molteni & C\n")
    L.append(f"_Сформировано автоматически: {now} · HOMEART Data Hub_\n")
    L.append("> Все числа получены из живой базы каталога (геометрический разбор "
             "исходных PDF-прайс-листов). Отчёт воспроизводим командой "
             "`python3 scripts/build_report.py`.\n")

    L.append("## 1. Итоги каталога\n")
    L.append("| Метрика | Значение |")
    L.append("|---|---:|")
    L.append(f"| Позиций (модели, дедуп по фабрике) | **{fmt(positions)}** |")
    L.append(f"| Вариантов-цен (ячейки матриц) | **{fmt(variants)}** |")
    L.append(f"| Разобрано документов | {fmt(len(docs))} |")
    L.append(f"| Файлов в инвентаре | {fmt(len(inv))} |")
    L.append(f"| Актуальных прайс-листов | {fmt(len(current))} |")
    L.append(f"| Позиций помечено на проверку | {fmt(flagged)} |")
    L.append("")

    L.append("## 2. Инвентаризация файлов\n")
    L.append(f"_Источник инвентаря: {inv_source} · всего файлов: {len(inv)}_\n")
    L.append("**По типу документа (из содержимого, не по имени файла):**\n")
    L.append("| Тип | Файлов |")
    L.append("|---|---:|")
    for k, v in sorted(by_type.items(), key=lambda x: -x[1]):
        L.append(f"| {k} | {fmt(v)} |")
    L.append("")
    L.append("**По году (определён из содержимого):**\n")
    L.append("| Год | Файлов |")
    L.append("|---|---:|")
    for k, v in sorted(by_year.items(), key=lambda x: (x[0] is None, x[0]), reverse=True):
        L.append(f"| {k or '—'} | {fmt(v)} |")
    L.append("")
    L.append("**Актуальные прайс-листы (текущие листини):**\n")
    L.append("| Прайс-лист | Год | Валюта | Страниц | Вариантов-цен |")
    L.append("|---|---:|:--:|---:|---:|")
    for r in sorted(current, key=lambda x: -(x.get("variant_prices") or 0)):
        L.append(f"| {r.get('name')} | {r.get('year') or '—'} | "
                 f"{r.get('currency') or '—'} | {fmt(r.get('pages'))} | "
                 f"{fmt(r.get('variant_prices') or 0)} |")
    L.append("")

    L.append("## 3. Методология\n")
    L.append("- **Геометрический разбор (PyMuPDF).** Матрицы восстанавливаются по "
             "координатам, а не OCR: каждая цена привязывается к заголовку своего "
             "столбца (сверху — габариты/артикул) и подписи строки (слева — отделка), "
             "с учётом инвертированной семантики Molteni. Обе исходные цепочки "
             "сохраняются для аудита.\n")
    L.append("- **Имя позиции — ровно как напечатано.** Первичное имя — заголовок "
             "секции ≥14 pt (с игнор-листом брендовых строк), вторичное — перенос "
             "бегущего колонтитула. Соседние заголовки никогда не склеиваются "
             "(ловушка «Rose Martin»); одна модель через разные листини = ОДНА позиция "
             "(дедуп по нормализованному имени внутри фабрики).\n")
    L.append("- **Гейтинг аномалий micrograd.** Собственный autograd-движок обучается "
             "на пространственных признаках ячейки (соседи в строке/столбце, кегль, "
             "выравнивание) и отсеивает ложные «цены»: номера страниц, циклы "
             "Мартиндейла (~30 000), метраж ткани, индексы категорий отделки. "
             "Проверка градиента: `a.grad=4.0, b.grad=2.0` (санити-тест).\n")

    L.append("## 4. Покрытие\n")
    L.append("| Метрика | Страниц |")
    L.append("|---|---:|")
    L.append(f"| Всего страниц (разобранные документы) | {fmt(T['pages_total'])} |")
    L.append(f"| Страниц с матрицами | {fmt(T['pages_with_matrix'])} |")
    L.append(f"| Страниц разобрано | {fmt(T['pages_parsed'])} |")
    L.append(f"| Страниц пропущено (матрица есть, разбор не дал ячеек) | {fmt(T['pages_skipped'])} |")
    L.append(f"| Ячеек отсеяно нейросетью (аномалии) | {fmt(T['rejected_cells'])} |")
    cov = round(100 * T["pages_parsed"] / T["pages_with_matrix"], 1) if T["pages_with_matrix"] else 0
    L.append(f"\n**Покрытие по фабрике:** {cov}% страниц с матрицами разобрано.\n")
    L.append("**Покрытие по документам:**\n")
    L.append("| Документ | Стр. | С матрицами | Разобрано | Пропущено | Позиций | Вариантов-цен |")
    L.append("|---|---:|---:|---:|---:|---:|---:|")
    for d in docs:
        c = d.get("coverage") or {}
        L.append(f"| {d.get('name')} | {fmt(c.get('pages_total') or d.get('pages'))} | "
                 f"{fmt(c.get('pages_with_matrix'))} | {fmt(c.get('pages_parsed'))} | "
                 f"{fmt(c.get('pages_skipped'))} | {fmt(d.get('positions'))} | "
                 f"{fmt(d.get('variant_prices'))} |")
    L.append("")
    if classified_only:
        L.append(f"**Классифицировано без разбора ({len(classified_only)}):** "
                 + ", ".join(f"{r.get('name')} ({r.get('doc_type')})"
                             for r in classified_only[:60]) + "\n")

    L.append("## 5. Известные ограничения\n")
    L.append(f"- **Нулевые/микро-цены (кандидаты «Не сошлось»).** {fmt(zero_price)} "
             f"вариантов с ценой ≤ 0 и {fmt(low_price)} с ценой < 5 € — вероятно "
             "номера/индексы, ошибочно принятые за цену. Они помечаются, а не "
             "исправляются вслепую.\n")
    L.append(f"- **Неразрешённые имена моделей.** {fmt(unnamed)} позиций без "
             "надёжного печатного имени (сложные раскладки без заголовка ≥14 pt).\n")
    L.append("- **Сложные раскладки.** Часть страниц Outdoor/каталожного типа даёт "
             "дюймовые размеры в позиции цены — такие страницы помечаются "
             "«раскладка пока не поддержана», вывод не форсируется.\n")
    L.append("- **xlsx-прайсы** (если встречаются в папке) в инвентаре отмечаются "
             "отдельно и не разбираются геометрическим движком.\n")

    L.append("## 6. Результаты ручной приёмки\n")
    L.append("_Раздел для оператора: заполняется по итогам модуля «Приёмка» "
             "(стратифицированная выборка страниц-матриц, повизуальная сверка ячеек). "
             "Ниже — таблица для фиксации итогов._\n")
    L.append("| Дата | Проверяющий | Документов в выборке | Ячеек проверено | "
             "Ошибок | Доля ошибок | Комментарий |")
    L.append("|---|---|---:|---:|---:|---:|---|")
    L.append("|  |  |  |  |  |  |  |")
    L.append("")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print("wrote", OUT, f"({os.path.getsize(OUT)} bytes)")
    print(f"positions={positions} variant_prices={variants} docs={len(docs)} "
          f"current_listini={len(current)}")


if __name__ == "__main__":
    main()
