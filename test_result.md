#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

# THIS SECTION CONTAINS CRITICAL TESTING INSTRUCTIONS FOR BOTH AGENTS
# BOTH MAIN_AGENT AND TESTING_AGENT MUST PRESERVE THIS ENTIRE BLOCK

# Communication Protocol:
# If the `testing_agent` is available, main agent should delegate all testing tasks to it.
#
# You have access to a file called `test_result.md`. This file contains the complete testing state
# and history, and is the primary means of communication between main and the testing agent.
#
# Main and testing agents must follow this exact format to maintain testing data. 
# The testing data must be entered in yaml format Below is the data structure:
# 
## user_problem_statement: {problem_statement}
## backend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.py"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## frontend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.js"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 0
##   run_ui: false
##
## test_plan:
##   current_focus:
##     - "Task name 1"
##     - "Task name 2"
##   stuck_tasks:
##     - "Task name with persistent issues"
##   test_all: false
##   test_priority: "high_first"  # or "sequential" or "stuck_first"
##
## agent_communication:
##     -agent: "main"  # or "testing" or "user"
##     -message: "Communication message between agents"

# Protocol Guidelines for Main agent
#
# 1. Update Test Result File Before Testing:
#    - Main agent must always update the `test_result.md` file before calling the testing agent
#    - Add implementation details to the status_history
#    - Set `needs_retesting` to true for tasks that need testing
#    - Update the `test_plan` section to guide testing priorities
#    - Add a message to `agent_communication` explaining what you've done
#
# 2. Incorporate User Feedback:
#    - When a user provides feedback that something is or isn't working, add this information to the relevant task's status_history
#    - Update the working status based on user feedback
#    - If a user reports an issue with a task that was marked as working, increment the stuck_count
#    - Whenever user reports issue in the app, if we have testing agent and task_result.md file so find the appropriate task for that and append in status_history of that task to contain the user concern and problem as well 
#
# 3. Track Stuck Tasks:
#    - Monitor which tasks have high stuck_count values or where you are fixing same issue again and again, analyze that when you read task_result.md
#    - For persistent issues, use websearch tool to find solutions
#    - Pay special attention to tasks in the stuck_tasks list
#    - When you fix an issue with a stuck task, don't reset the stuck_count until the testing agent confirms it's working
#
# 4. Provide Context to Testing Agent:
#    - When calling the testing agent, provide clear instructions about:
#      - Which tasks need testing (reference the test_plan)
#      - Any authentication details or configuration needed
#      - Specific test scenarios to focus on
#      - Any known issues or edge cases to verify
#
# 5. Call the testing agent with specific instructions referring to test_result.md
#
# IMPORTANT: Main agent must ALWAYS update test_result.md BEFORE calling the testing agent, as it relies on this file to understand what to test next.

#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================



#====================================================================================================
# Testing Data - Main Agent and testing sub agent both should log testing data below this section
#====================================================================================================

user_problem_statement: |
  B2B SaaS Data Hub for luxury furniture brands (Molteni & C). Slice 1 scope:
  REAL PyMuPDF spatial parsing of PDF price lists (no mocks, no OCR) + micrograd
  autograd anomaly classification -> MongoDB -> live Task Monitor -> QA split-screen
  showing the source PDF page next to the extracted product matrix (model, category,
  dimension, variant code, min-max price range across finish variations, reviewer notes).
  Architecture: Next.js UI + /api routes, MongoDB storage, and a supervisor-managed
  Python DS sidecar (FastAPI, port 8001) holding the real PyMuPDF / sentence-transformers
  CLIP / micrograd code. Redis+Celery replaced by an in-worker asyncio queue with task
  documents in MongoDB. Login gated by a single MASTER_PASSWORD from .env.

backend:
  - task: "Auth login with MASTER_PASSWORD"
    implemented: true
    working: true
    file: "app/api/[[...path]]/route.js"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "POST /api/auth/login accepts {password}. Correct key is 'homeart2025' (MASTER_PASSWORD in /app/.env) and returns {token,user}. Wrong/missing key must return 401 with {error}."
        -working: true
        -agent: "testing"
        -comment: "✅ TESTED - All auth scenarios working correctly: (1) Correct password returns 200 with token and user object. (2) Wrong password returns 401 with error message. (3) Missing password returns 401 with error message."

  - task: "Health + stats aggregation"
    implemented: true
    working: true
    file: "app/api/[[...path]]/route.js"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "GET /api/health proxies the DS sidecar (expects worker.ok true). GET /api/stats returns products/approved/pending/rejected/documents/factories/embeddings/avg_confidence/flagged."
        -working: true
        -agent: "testing"
        -comment: "✅ TESTED - Health check returns ok=true with worker reachable (queue=0, 6121 products in worker, 3 docs). Stats returns all required fields: 20,499 products (0 approved, 20,499 pending, 0 rejected), 5 documents, 1 factory, 0 embeddings, avg_confidence=0.799, 4,169 flagged."

  - task: "Dropbox folder traversal (scan)"
    implemented: true
    working: "NA"
    file: "backend/dropbox_fetch.py"
    stuck_count: 0
    priority: "medium"
    needs_retesting: false
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "POST /api/scan {url} enqueues a scan task and returns {task_id}. The 2.5GB archive is already cached on disk so the task should reach status=done within ~30s and result.files should list 394 PDFs, several flagged is_price_list=true. Do NOT use a different Dropbox URL or it will trigger a fresh 2.5GB download."
        -working: "NA"
        -agent: "testing"
        -comment: "NOT TESTED - Skipped as per instructions to avoid triggering 2.5GB download. This is a medium priority task and the archive is already cached. The endpoint structure was verified through code review."

  - task: "Real PyMuPDF spatial parsing + micrograd ingestion pipeline"
    implemented: true
    working: true
    file: "backend/pipeline.py, backend/assemble.py, backend/anomaly.py, backend/worker.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "Already executed a full clean run: 5 Molteni price lists, 2186 pages -> 20499 products, 19797 anomalous cells rejected, micrograd MLP(8,[8,8,1]) trained to ~100% weak-label accuracy. Verified ground truth: model '505 UP System', category 'Structural elements D 320', dimension '3 modules', variant_code 'SP3/12', price 175-373 EUR over 4 finishes on page 38. For a cheap re-test use POST /api/ingest {source:'local', paths:['/app/data/pdfs/2026_PL_Gliss-Master-Smart-Configuration_EN_EUR.pdf'], factory:'Molteni & C', max_pages:24} (24 pages, ~10s) and poll /api/tasks/{id} until done. Re-ingesting the same path MUST NOT duplicate products (documents.id is stable via $setOnInsert)."
        -working: true
        -agent: "testing"
        -comment: "✅ TESTED - Micrograd autograd verified: a.grad=4.0, b.grad=2.0 (correct gradient propagation). Idempotent re-ingest test PASSED: ingested Gliss-Master-Smart-Configuration PDF (24 pages), task completed in ~12s with status=done, progress=100%. Events array contains expected keywords (PyMuPDF, micrograd, products assembled). Product count stable at 665 before and after re-ingest, confirming deduplication works correctly. No product duplication detected."

  - task: "Task monitor endpoints"
    implemented: true
    working: true
    file: "app/api/[[...path]]/route.js"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "GET /api/tasks returns up to 25 newest tasks WITHOUT the events array. GET /api/tasks/{id} returns the full doc including events[] (live parser stream), progress, stats, result. 404 for unknown id."
        -working: true
        -agent: "testing"
        -comment: "✅ TESTED - GET /api/tasks returns list of tasks correctly WITHOUT events array (verified). GET /api/tasks/{id} returns full task with events array (64 events), progress=100, status=done. GET /api/tasks/{bogus_id} returns 404 as expected."

  - task: "Products query, filters, sorting, facets"
    implemented: true
    working: true
    file: "app/api/[[...path]]/route.js"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "GET /api/products supports doc_id, status, model, flagged, min_conf, min_var, q (regex over model/category/dimension/variant_code), sort=best|page|price, limit (max 300), skip. Returns {items,total,skip,limit}. Verify sort=best returns descending confidence, min_var=3 only returns n_variations>=3, and q='505 UP' matches. GET /api/products/models returns per-model counts and price extremes. Every product must expose price_min, price_max, variations[], bbox, bbox_cells, bbox_col_header, page_width, page_height and NO _id field."
        -working: true
        -agent: "testing"
        -comment: "✅ TESTED - All product query features working: (1) Basic query returns {items,total,skip,limit} with all required fields (id, model_name, category, dimension, variant_code, price_min, price_max, n_variations, variations[], bbox, bbox_cells, bbox_col_header, page, page_width, page_height, status, reviewer_notes, confidence). NO _id field present ✓. (2) sort=best returns confidence descending [0.9987, 0.9987, 0.9985...] ✓. (3) min_var=3 filter returns only n_variations>=3 ✓. (4) min_conf=0.7 filter returns only confidence>=0.7 ✓. (5) q='505 UP' search returns 874 matches ✓. (6) doc_id filter returns 3,141 products ✓. (7) status=pending filter works ✓. (8) Pagination (limit/skip) works ✓. (9) GET /api/products/models returns 200 model facets with {model,n,min,max} ✓. Variations array structure verified with price, bbox, confidence fields."

  - task: "QA review: PATCH product status / reviewer_notes / price range edit"
    implemented: true
    working: true
    file: "app/api/[[...path]]/route.js"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "PATCH /api/products/{id} whitelists status, reviewer_notes, model_name, category, dimension, variant_code, price_min, price_max, currency, collection and returns the fresh document. POST /api/products/bulk {ids,status} bulk-updates. Verify approving a product moves the /api/stats approved counter and that reviewer_notes persists across a subsequent GET."
        -working: true
        -agent: "testing"
        -comment: "✅ TESTED - PATCH /api/products/{id} working correctly: updated status=approved, reviewer_notes='QA test note', price_min=123, price_max=456. All fields reflected in response and persisted in database (verified with subsequent GET). Stats approved counter increased to 1 after approval. Product restored to original state after test. POST /api/products/bulk updated 2 products successfully (modified=2), then restored to pending."

  - task: "PDF page raster proxy for QA split-screen"
    implemented: true
    working: true
    file: "app/api/[[...path]]/route.js, backend/pipeline.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "GET /api/page-image?doc_id=..&page=..&dpi=150 must return Content-Type image/png rendered on demand by PyMuPDF and cached on disk. Pick a real doc_id from /api/documents and a page from a product. Unknown doc_id should return an error status, not a crash."
        -working: true
        -agent: "testing"
        -comment: "✅ TESTED - GET /api/page-image returns valid PNG image (162.2 KB) with correct Content-Type: image/png and PNG magic bytes (\\x89PNG) verified. Tested with real doc_id and page number from products. GET /api/page-image with bogus doc_id returns 404 error status (no crash)."

  - task: "Slice 2: dual CLIP embedding job (/api/embed)"
    implemented: true
    working: true
    file: "backend/worker.py, backend/embeddings.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "POST /api/embed {} enqueues an embed task -> {task_id}. Real sentence-transformers models on CPU: text = clip-ViT-B-32-multilingual-v1, image = clip-ViT-B-32, both 512-d. The index is ALREADY BUILT (16,309 vectors of 20,499 products - only confidence>=0.6 rows are indexed on purpose, information-poor rows whose text has <3 components are skipped as hubs). So a fresh POST /api/embed should finish almost immediately reporting embedded=0 or a very small number, because products are already flagged embedded=true. Verify: task reaches status done, result.embedded is a number, and /api/stats embeddings count does NOT drop. DO NOT wipe product_embeddings - rebuilding costs ~8 minutes of CPU."
        -working: true
        -agent: "testing"
        -comment: "✅ TESTED - POST /api/embed working correctly: (1) Task created successfully with task_id. (2) Task completed with status='done' and result.embedded=0 (as expected, all products already embedded). (3) CRITICAL: Embeddings count remained stable at 16,309 before and after (no decrease). (4) Vector index integrity preserved. Embed job completes almost immediately since products are already flagged embedded=true."

  - task: "Slice 2: Spotlight vector search (/api/search) text + image"
    implemented: true
    working: true
    file: "backend/worker.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "POST /api/search with JSON {q, top_k} does TEXT search: the query is encoded by the multilingual CLIP text encoder, then compared in a MEAN-CENTRED 512-d space (centering is required - raw cosine sat at ~0.9 for everything and ranking collapsed). POST /api/search as multipart/form-data with field 'file' (an image) does IMAGE search using the CLIP image encoder against the RAW (uncentered) space. Expected response {results:[...with score...], mode:'text'|'image', searched:<int>}. Verify: (1) {'q':'диван из кожи','top_k':8} returns 8 results whose model_name/category are sofas (GREGOR/LUCIO/CLEO/AUGUSTO) with score>0.7; (2) {'q':'кухонный модуль с ящиками'} returns KITCHEN BOX DRAWERS first; (3) {'q':'dining table oak'} returns table-ish rows; (4) empty q returns {results:[],mode:'text'} and not a 500; (5) results are de-duplicated - no two results share the same (model_name, category) pair; (6) each result carries score, price_min, price_max, doc_id, page so the UI can render a page thumbnail; (7) an image upload (generate/download any small JPEG, e.g. via PIL) returns mode='image' with 8 results and scores in the 0.2-0.35 CLIP image-text band. Latency should be well under 3s for text queries after the first call (the vector matrix is cached in memory)."
        -working: true
        -agent: "testing"
        -comment: "✅ TESTED - POST /api/search working correctly for both TEXT and IMAGE modes: TEXT MODE: (1) Russian query 'диван из кожи' returns 8 sofa/pouf results (TURNER, GREGOR, LUCIO, CLEO, AUGUSTO found) with top score=0.7964 (>0.7 ✓). (2) Russian query 'кухонный модуль с ящиками' returns KITCHEN BOX DRAWERS as first result ✓. (3) Russian query 'кровать' returns bed-related rows (BED ACCESSORIES, daybed) ✓. (4) English query 'dining table oak' returns table rows (WOODY, MONK found) ✓. (5) Empty query returns {results:[], mode:'text'} with HTTP 200 (not 500) ✓. (6) De-duplication PASSED: no duplicate (model_name, category) pairs in any query ✓. (7) All required fields present in results: score, price_min, price_max, doc_id, page, model_name, n_variations ✓. (8) Searched count: 16309 (matches embeddings count) ✓. IMAGE MODE: (9) PIL-generated 400x300 JPEG uploaded successfully ✓. (10) Returns mode='image' with 8 results ✓. (11) Scores in expected CLIP image-text band: 0.29-0.30 (within 0.1-0.45 range) ✓. (12) All required fields present: score, doc_id, page ✓. LATENCY: Warm text query latency measured at 0.241s (well under 3s threshold) ✓. SEMANTIC CORRECTNESS: Russian-language queries return semantically correct furniture types ✓. EMBEDDING TEXT BUILDER: Product texts are clean semantic strings with format 'MODEL. category. finishes. Collection, Section' - no price text (EUR/€) and no variant codes found ✓."


frontend:
  - task: "Login screen, shell, Ingest, Task Monitor, QA split-screen"
    implemented: true
    working: "NA"
    file: "app/page.js, components/hub/*.jsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "Manually verified via screenshots: login with homeart2025, live parser stream with micrograd loss chart, and the QA split-screen rendering PDF page 38 with amber price-cell boxes, blue column-header boxes and green row-label boxes aligned to the real glyphs. NOT yet handed to the frontend testing agent - awaiting explicit user permission."

metadata:
  created_by: "main_agent"
  version: "1.0"
  test_sequence: 0
  run_ui: false

test_plan:
  current_focus:
    - "Slice 2: Spotlight vector search (/api/search) text + image"
    - "Slice 2: dual CLIP embedding job (/api/embed)"
  stuck_tasks: []
  test_all: false
  test_priority: "high_first"

agent_communication:
    -agent: "main"
    -message: |
      Slice 1 is implemented and a real full pipeline run has already completed (20,499
      products from 2,186 real Molteni PDF pages). Please test the BACKEND only.
      Key facts you need:
        * Master password: homeart2025
        * The DS sidecar is a separate supervisor program named 'dsworker' on port 8001;
          Next.js proxies to it via PY_WORKER_URL. Do not restart dsworker while a task runs.
        * Database already has 5 documents and ~20.5k products, so read-only endpoints can
          be tested immediately without ingesting anything.
        * For an ingestion re-test use the SMALL doc:
          POST /api/ingest {"source":"local","paths":["/app/data/pdfs/2026_PL_Gliss-Master-Smart-Configuration_EN_EUR.pdf"],"factory":"Molteni & C","max_pages":24}
          then poll GET /api/tasks/{task_id} until status done (~10-20s). Confirm the
          products count for that doc_id does NOT double (idempotent re-ingest).
        * Do NOT call /api/scan with any URL other than the one already cached, and do not
          delete anything under /app/data.
      Please report any endpoint returning 500, any missing field needed by the QA UI
      (price_min, price_max, variations[].bbox, bbox_col_header, page_width/height), and
      whether page-image returns real PNG bytes.
    -agent: "testing"
    -message: |
      ✅ BACKEND TESTING COMPLETE - ALL 26 TESTS PASSED (100%)
      
      Comprehensive backend test suite executed successfully. All high-priority endpoints
      are working correctly with no critical issues found.
      
      KEY FINDINGS:
      • Auth: All scenarios working (correct/wrong/missing password)
      • Health & Stats: Worker reachable, all aggregation fields present
      • Products API: All filters, sorting, pagination, facets working correctly
      • Product fields: All required fields present (price_min, price_max, variations[].bbox,
        bbox_col_header, page_width, page_height). NO MongoDB _id field in responses ✓
      • QA Review: PATCH and bulk updates working, changes persist, stats counter updates
      • Page Image: Returns valid PNG with correct magic bytes (162 KB), 404 for bogus doc_id
      • Tasks: List endpoint excludes events, detail endpoint includes events, 404 for bogus ID
      • Ingestion Pipeline: Idempotent re-ingest verified - no product duplication (665→665)
      • Micrograd: Gradient propagation working correctly (a.grad=4.0, b.grad=2.0)
      
      Database state: 20,499 products, 5 documents, 1 factory, avg_confidence=0.799, 4,169 flagged
      
      NO CRITICAL ISSUES FOUND. Backend is production-ready.
    -agent: "main"
    -message: |
      SLICE 2 (Spotlight Search) is now implemented - please test ONLY the two new
      Slice 2 backend tasks (/api/embed and /api/search). Everything else already
      passed 26/26 and does not need retesting.

      CRITICAL - things that will waste a lot of time if you break them:
        * The vector index is ALREADY BUILT: 16,309 embeddings. DO NOT delete or wipe
          the `product_embeddings` collection and do not set products.embedded=false.
          Rebuilding costs ~8 minutes of CPU inference.
        * Do NOT restart the `dsworker` supervisor program while a task is running.
        * Do NOT call /api/scan (2.5 GB Dropbox archive).
        * Do NOT modify /app/.env.

      Implementation notes you need to test correctly:
        * TEXT search compares in a MEAN-CENTRED space; IMAGE search compares in the raw
          space. This asymmetry is intentional (documented in worker.py::_load_vectors).
        * Text-mode cosine scores land roughly in 0.35-0.85; image-mode scores land
          roughly in 0.2-0.35. Do not assert image scores > 0.7.
        * Results are de-duplicated by (model_name, category), drawn from a deep
          candidate pool, so `len(results)` should equal top_k for common queries.
        * For the image test, create a small JPEG locally with PIL (do not download
          anything large) and POST it as multipart field name 'file'.

      Report: any 500s, whether Russian queries return semantically correct furniture,
      whether de-duplication holds, whether every result carries score/price_min/
      price_max/doc_id/page, and the measured latency of a warm text query.
    -agent: "testing"
    -message: |
      ✅ SLICE 2 BACKEND TESTING COMPLETE - ALL 6 TESTS PASSED (100%)
      
      Tested ONLY the two new Slice 2 backend tasks as requested. All tests passed with no critical issues.
      
      TEST RESULTS:
      
      A) POST /api/embed ✅
         • Task created and completed successfully (status=done)
         • Result: embedded=0 (expected - all products already embedded)
         • CRITICAL: Embeddings count stable at 16,309 (no decrease) ✓
         • Vector index integrity preserved ✓
      
      B) POST /api/search - TEXT MODE ✅
         • Russian query "диван из кожи" (leather sofa): Returns 8 sofa/pouf results (TURNER, GREGOR, LUCIO, CLEO, AUGUSTO), top score=0.7964 (>0.7) ✓
         • Russian query "кухонный модуль с ящиками" (kitchen module): Returns KITCHEN BOX DRAWERS as first result ✓
         • Russian query "кровать" (bed): Returns bed-related rows (BED ACCESSORIES, daybed) ✓
         • English query "dining table oak": Returns table rows (WOODY, MONK) ✓
         • Mode: "text" ✓
         • Searched: 16,309 (matches embeddings count) ✓
         • De-duplication: PASSED - no duplicate (model_name, category) pairs ✓
         • All required fields present: score, price_min, price_max, doc_id, page, model_name, n_variations ✓
         • Semantic correctness: Russian queries return correct furniture types ✓
      
      C) POST /api/search - EMPTY QUERY ✅
         • Returns {results:[], mode:"text"} with HTTP 200 (not 500) ✓
      
      D) POST /api/search - IMAGE MODE ✅
         • PIL-generated 400x300 JPEG uploaded successfully ✓
         • Mode: "image" ✓
         • Returns 8 results ✓
         • Scores in expected CLIP image-text band: 0.29-0.30 (within 0.1-0.45 range) ✓
         • All required fields present: score, doc_id, page ✓
      
      E) LATENCY ✅
         • Warm text query latency: 0.241s (well under 3s threshold) ✓
      
      F) EMBEDDING TEXT BUILDER ✅
         • Product texts are clean semantic strings ✓
         • Format: "MODEL. category. finishes. Collection, Section" ✓
         • No price text (EUR/€) ✓
         • No variant codes ✓
      
      SUMMARY: Both Slice 2 endpoints (/api/embed and /api/search) are working correctly.
      NO CRITICAL ISSUES FOUND. Vector search is production-ready.

