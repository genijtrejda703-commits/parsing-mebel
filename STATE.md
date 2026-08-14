# STATE — Molteni & C Data Hub (resume without archaeology)

_Last updated: STEP 0 baseline restore in progress._

## What this is
B2B data hub that turns Molteni & C PDF price lists into a structured
**Position → Variant → Price** catalogue via real PyMuPDF geometric parsing +
micrograd anomaly gating. Next.js UI (Russian) + `/api` proxy + Python DS sidecar
(`dsworker`, FastAPI, :8001) + local MongoDB (`datahub`). No external APIs; master
password from `/app/.env` only.

## Reset-resilience (run after any container reset)
```
MASTER_PASSWORD='homeart-molteni-2026' bash scripts/bootstrap.sh   # deps, .env, dsworker, start
python3 scripts/reingest.py                                        # wipe + rebuild DB from /app/data
```
`.env`, MongoDB data, HF/torch model cache and downloaded PDFs are **never** in git.
The 14 current listini under `data/molteni/` **are** committed, so re-ingest is fully
reproducible offline.

## Architecture / key files
- `backend/pipeline.py` — PyMuPDF geometric parse (UNCHANGED invariants: single >=14pt
  headline, no concatenation, above=dimension/code, left=finish).
- `backend/engine.py` / `nn.py` — micrograd (indentation trap fixed; sanity a.grad=4,b.grad=2).
- `backend/assemble.py` — column->product; **+ positions/variant_prices derivation (P0)**.
- `backend/worker.py` — asyncio queue jobs (ingest/embed/photos/anomalies/inventory).
- `app/api/[[...path]]/route.js` — `/api/*` proxy + Mongo reads.

## Progress log
- [x] STEP 0 baseline: `.env` (+`.env.example`, gitignored `.env`), core deps
  (pymupdf/openpyxl/uvicorn), `dsworker` supervisor conf via bootstrap, password rotated to
  `homeart-molteni-2026` and old value scrubbed from repo.
- [x] BASELINE GATES: dsworker :8001 ✓, nextjs serving ✓, login ✓, micrograd sanity ✓ (a.grad=4,b.grad=2).
- [x] P0 Directive 1: positions/variant_prices schema + position-first API/QA/Excel.
      Gates met: 628 positions, 65 607 variant-prices, «505 UP System» = 1 position (1249 vp),
      idempotent re-ingest verified (19/1623 stable), sheets «Позиции»/«Цены»/«Сводка».
- [x] P1 Directive 2: content-based file classifier + coverage. Local 14 listini + FULL
      394-PDF Dropbox folder inventoried (via curl download; urllib couldn't follow the 302).
      29 current listini identified; «Инвентаризация файлов» + «Покрытие» screens + xlsx.
      Dada Kitchens + Gliss Master ingested (mandatory). Extra folder listini classified but
      NOT auto-ingested (duplicate/other-language/older — dedup safety); listed in report.
- [x] P2: /app/reports/Molteni_C_report.md (real numbers, methodology, coverage, limitations,
      empty «Результаты ручной приёмки»). Regenerate: `python3 scripts/build_report.py`.
- [ ] P3 «Приёмка» / P4 «Не сошлось» / CLIP search — deferred (budget permitting).

## Current counts
- positions: 628 · variant_prices: 65 607 · docs ingested: 14 · files inventoried (full folder): 397

## Notes for next session
- Full Dropbox zip cached at data/tmp/dropbox_8c3fd69399fb.zip (2.5 GB, gitignored). Delete to reclaim disk.
- To ingest additional current listini found in the folder, run inventory with `ingest_new:true`
  (review dedup/price-conflict implications first — Directive 4 territory).
- CLIP search is deferred: «Умный поиск» should show "индекс не построен" and offer on-demand build.
