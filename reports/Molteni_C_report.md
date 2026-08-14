# Отчёт по фабрике Molteni & C

_Сформировано автоматически: 14.08.2026 23:22 · HOMEART Data Hub_

> Все числа получены из живой базы каталога (геометрический разбор исходных PDF-прайс-листов). Отчёт воспроизводим командой `python3 scripts/build_report.py`.

## 1. Итоги каталога

| Метрика | Значение |
|---|---:|
| Позиций (модели, дедуп по фабрике) | **628** |
| Вариантов-цен (ячейки матриц) | **65 607** |
| Разобрано документов | 14 |
| Файлов в инвентаре | 397 |
| Актуальных прайс-листов | 29 |
| Позиций помечено на проверку | 46 |

## 2. Инвентаризация файлов

_Источник инвентаря: полная папка Dropbox · всего файлов: 397_

**По типу документа (из содержимого, не по имени файла):**

| Тип | Файлов |
|---|---:|
| прочее | 279 |
| каталог | 55 |
| прайс-лист | 29 |
| маркетинг | 16 |
| ткани и отделки | 11 |
| технический | 4 |
| таблица (не разбирается) | 3 |

**По году (определён из содержимого):**

| Год | Файлов |
|---|---:|
| — | 238 |
| 2026 | 44 |
| 2025 | 37 |
| 2024 | 27 |
| 2023 | 14 |
| 2022 | 2 |
| 2021 | 2 |
| 2020 | 4 |
| 2019 | 6 |
| 2018 | 2 |
| 2015 | 8 |
| 2013 | 13 |

**Актуальные прайс-листы (текущие листини):**

| Прайс-лист | Год | Валюта | Страниц | Вариантов-цен |
|---|---:|:--:|---:|---:|
| 2026_PL_Kitchens_EN.pdf | 2026 | EUR | 1 060 | 17 908 |
| 2026_PL_Sofas_EN_EUR.pdf | 2026 | EUR | 321 | 15 282 |
| 2026_PL_Night-Systems-Sleeping_EN_EUR.pdf | 2026 | EUR | 330 | 9 514 |
| 2026_PL_Living-Systems-Dining_EN_EUR.pdf | 2026 | EUR | 451 | 7 407 |
| 2026_PL_Bathrooms_EN.pdf | 2026 | EUR | 270 | 7 039 |
| 2026_PL_New-Collection_EN_EUR.pdf | 2026 | EUR | 160 | 2 966 |
| 2026_PL_New-Collection_EN_EUR.pdf | 2026 | EUR | 162 | 2 966 |
| 2026_PL_Kitchens-News_EN.pdf | 2026 | — | 100 | 1 706 |
| 2026_PL_Gliss-Master-Smart-Configuration_EN_EUR.pdf | 2026 | EUR | 24 | 1 623 |
| 2026_PL_Outdoor_EN_EUR.pdf | 2026 | EUR | 180 | 1 397 |
| 2026_PL_Landscapes_EN_EUR.pdf | 2026 | EUR | 109 | 668 |
| 2026_PL_Heritage-Collection_EN_EUR.pdf | 2026 | EUR | 62 | 97 |
| new-kitchen-price-list-2026.pdf | 2026 | EUR | 1 060 | 0 |
| 2026_PL_Marketing-Tools_EN_EUR.pdf | 2026 | EUR | 77 | 0 |
| 2026_PL_Bathrooms-Fantini_EN_Export.pdf | 2026 | EUR | 74 | 0 |
| 2026_PL_Outdoor_New-collection_EN_EUR.pdf | 2026 | EUR | 37 | 0 |
| 2025_PL_Monk-Cabana_EN_EUR.pdf | 2025 | — | 2 | 0 |
| 2025_PL_Gio-Ponti-Objects_IT-EN_EUR.pdf | 2025 | EUR | 9 | 0 |
| 2026_PL_Bathroom-Solutions_EN.pdf | 2026 | — | 5 | 0 |
| 2026_CL_Price-Lists-Kitchen-News_Update_EN.pdf | 2026 | — | 2 | 0 |
| 2026_CL_Price-Lists_Kitchen-News_EN (1).pdf | 2026 | — | 1 | 0 |
| Listino Armani_Dada_ENG_01_2022.pdf | 2023 | EUR | 272 | 0 |
| Listino Armani_Dada_ITA_01_2022.pdf | 2023 | EUR | 272 | 0 |
| 2025 LISTINO New-collection_EN_EUR.pdf | 2025 | EUR | 162 | 0 |
| new-collection-2025-eur.pdf | 2025 | EUR | 164 | 0 |
| размеры.pdf | 2025 | — | 72 | 0 |
| gliss-master-product-sheet.pdf | 2023 | — | 64 | 0 |
| колонны Atelier.pdf | 2025 | — | 14 | 0 |
| file_modifiche_listino_post_31_05_2024_it_it_en_gb_ir_c.pdf | 2024 | — | 1 | 0 |

## 3. Методология

- **Геометрический разбор (PyMuPDF).** Матрицы восстанавливаются по координатам, а не OCR: каждая цена привязывается к заголовку своего столбца (сверху — габариты/артикул) и подписи строки (слева — отделка), с учётом инвертированной семантики Molteni. Обе исходные цепочки сохраняются для аудита.

- **Имя позиции — ровно как напечатано.** Первичное имя — заголовок секции ≥14 pt (с игнор-листом брендовых строк), вторичное — перенос бегущего колонтитула. Соседние заголовки никогда не склеиваются (ловушка «Rose Martin»); одна модель через разные листини = ОДНА позиция (дедуп по нормализованному имени внутри фабрики).

- **Гейтинг аномалий micrograd.** Собственный autograd-движок обучается на пространственных признаках ячейки (соседи в строке/столбце, кегль, выравнивание) и отсеивает ложные «цены»: номера страниц, циклы Мартиндейла (~30 000), метраж ткани, индексы категорий отделки. Проверка градиента: `a.grad=4.0, b.grad=2.0` (санити-тест).

## 4. Покрытие

| Метрика | Страниц |
|---|---:|
| Всего страниц (разобранные документы) | 3 220 |
| Страниц с матрицами | 2 235 |
| Страниц разобрано | 1 777 |
| Страниц пропущено (матрица есть, разбор не дал ячеек) | 458 |
| Ячеек отсеяно нейросетью (аномалии) | 33 354 |

**Покрытие по фабрике:** 79.5% страниц с матрицами разобрано.

**Покрытие по документам:**

| Документ | Стр. | С матрицами | Разобрано | Пропущено | Позиций | Вариантов-цен |
|---|---:|---:|---:|---:|---:|---:|
| 2026_PL_Kitchens_EN.pdf | 1 060 | 874 | 680 | 194 | 352 | 17 908 |
| 2026_PL_Sofas_EN_EUR.pdf | 321 | 184 | 177 | 7 | 57 | 15 282 |
| 2026_PL_Night-Systems-Sleeping_EN_EUR.pdf | 330 | 230 | 203 | 27 | 54 | 9 514 |
| 2026_PL_Living-Systems-Dining_EN_EUR.pdf | 451 | 283 | 224 | 59 | 60 | 7 407 |
| 2026_PL_Bathrooms_EN.pdf | 270 | 226 | 206 | 20 | 59 | 7 039 |
| 2026_PL_New-Collection_EN_EUR.pdf | 160 | 96 | 83 | 13 | 35 | 2 966 |
| 2026_PL_Kitchens-News_EN.pdf | 100 | 77 | 69 | 8 | 40 | 1 706 |
| 2026_PL_Gliss-Master-Smart-Configuration_EN_EUR.pdf | 24 | 20 | 20 | 0 | 19 | 1 623 |
| 2026_PL_Outdoor_EN_EUR.pdf | 180 | 81 | 67 | 14 | 29 | 1 397 |
| 2026_PL_Landscapes_EN_EUR.pdf | 109 | 58 | 36 | 22 | 4 | 668 |
| 2026_PL_Heritage-Collection_EN_EUR.pdf | 62 | 25 | 12 | 13 | 6 | 97 |
| 2025_PL_Monk-Cabana_EN_EUR.pdf | 2 | 1 | 0 | 1 | 0 | 0 |
| 2026_PL_Bathrooms-Fantini_EN_Export.pdf | 74 | 59 | 0 | 59 | 0 | 0 |
| 2026_PL_Marketing-Tools_EN_EUR.pdf | 77 | 21 | 0 | 21 | 0 | 0 |

**Классифицировано без разбора (382):** new-kitchen-price-list-2026.pdf (прайс-лист), 2025_TD_Arial-Manual-Doors_IT_EN.pdf (технический), 2026_PL_Outdoor_New-collection_EN_EUR.pdf (прайс-лист), 2025_PL_Gio-Ponti-Objects_IT-EN_EUR.pdf (прайс-лист), 2026_PL_Bathroom-Solutions_EN.pdf (прайс-лист), 2026_CL_Price-Lists-Kitchen-News_Update_EN.pdf (прайс-лист), 2026_CL_Discontinued-Fabrics-Newsletter_EN.pdf (маркетинг), 2026_CL_Price-Lists_Kitchen-News_EN (1).pdf (прайс-лист), 2025_TD_505-UP_IT-EN.pdf (технический), 2024_Catalog_Inspiring solutions for living spaces.pdf (каталог), new-gliss-master-manual-2023-avp-updates.pdf (маркетинг), 2025 КАТАЛОГ New-Collection_IT-EN.pdf (маркетинг), 2025_Catalogo_ Home Full IT-EN.pdf (каталог), 2026_FN_Finishes-Guideline_IT-EN.pdf (ткани и отделки), 2026_FN_Finishes-Guideline_IT-EN.pdf (ткани и отделки), 2024_Catalog_outdoor.pdf (каталог), 2024_Catalog_outdoor.pdf (каталог), new-new-collection-2026-catalog.pdf (каталог), new-new-collection-2026-catalog.pdf (каталог), 2026_new-new-collection-catalog.pdf (каталог), 2026_CT_New-Collection_IT-EN.pdf (маркетинг), 2026_CT_Outdoor_Digital_IT-EN.pdf (прочее), 2024_Catalog_Heritage Collection.pdf (каталог), finishes-guideline-2026-avp-updates.pdf (ткани и отделки), 2026_CT_Home_IT-EN.pdf (прочее), kitchen-collection-2025-full-catalog.pdf (каталог), kitchen-collection-2025-full-catalog (1).pdf (каталог), 2025_AE_Mdw_Styling-Book_IT-EN.pdf (маркетинг), new-kitchen-manual-2025-avp-updates.pdf (прочее), 2024_Catalog_ Molteni Landscapes.pdf (каталог), 2025_Catalogo_Home Short  IT-EN.pdf (каталог), 2025_AE_Brochure_Palazzo-Molteni_MDW_EN.pdf (маркетинг), 2025_AE_Brochure_Palazzo-Molteni_MDW_EN.pdf (маркетинг), 2025_AE_Products-Presentation_Confidential_EN-1.pdf (маркетинг), Listino Armani_Dada_ENG_01_2022.pdf (прайс-лист), kitchen-collection-2023-catalog.pdf (каталог), Listino Armani_Dada_ITA_01_2022.pdf (прайс-лист), new-upholstery-manual-2025-avp-updates.pdf (прочее), 2025_Manual_new-upholstery-avp-updates.pdf (прочее), 2024_Catalo_Collection.pdf (маркетинг), new-gliss-master-manual-2025-avp-updates.pdf (прочее), 2025_Manual_gliss-master-manual-2025-avp-updates.pdf (прочее), 2024_Catalog_Home Short.pdf (каталог), 3. Kitchen Collection.pdf (прочее), 2024_Project Collection.pdf (прочее), 2025 LISTINO New-collection_EN_EUR.pdf (прайс-лист), new-collection-2025-eur.pdf (прайс-лист), new-kitchen-manual-2023-avp-updates.pdf (прочее), kitchen-design-manual-2023-avp-updates.pdf (прочее), 1. Kitchen Design Manual 2023.pdf (прочее), new-505-up-manual-2023-avp-updates.pdf (маркетинг), dining-catalog.pdf (каталог), home-2025-full-catalog.pdf (каталог), new-outdoor-2026-catalog.pdf (каталог), 2026 new-outdoor-catalog.pdf (каталог), 2026 new-outdoor-catalog.pdf (каталог), 2026_CT_Outdoor_IT-EN.pdf (прочее), sofas-catalog.pdf (каталог), 2. Molteni_C Outdoor Catalogue 2022.pdf (каталог), home-2024-full-catalog.pdf (каталог)

## 5. Известные ограничения

- **Нулевые/микро-цены (кандидаты «Не сошлось»).** 2 вариантов с ценой ≤ 0 и 3 997 с ценой < 5 € — вероятно номера/индексы, ошибочно принятые за цену. Они помечаются, а не исправляются вслепую.

- **Неразрешённые имена моделей.** 1 позиций без надёжного печатного имени (сложные раскладки без заголовка ≥14 pt).

- **Сложные раскладки.** Часть страниц Outdoor/каталожного типа даёт дюймовые размеры в позиции цены — такие страницы помечаются «раскладка пока не поддержана», вывод не форсируется.

- **xlsx-прайсы** (если встречаются в папке) в инвентаре отмечаются отдельно и не разбираются геометрическим движком.

## 6. Результаты ручной приёмки

_Раздел для оператора: заполняется по итогам модуля «Приёмка» (стратифицированная выборка страниц-матриц, повизуальная сверка ячеек). Ниже — таблица для фиксации итогов._

| Дата | Проверяющий | Документов в выборке | Ячеек проверено | Ошибок | Доля ошибок | Комментарий |
|---|---|---:|---:|---:|---:|---|
|  |  |  |  |  |  |  |
