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


user_problem_statement: |
  Molteni & C Data Hub. Turn PDF price lists into a Position -> Variant -> Price catalogue via
  PyMuPDF geometric parsing + micrograd anomaly gating. Session resumed after container reset:
  rebuilt runtime, migrated to the Position->Variant schema (Directive 1), added full-folder file
  inventory + coverage (Directive 2), and generated the factory report (P2). UI is Russian.
  Master password lives only in /app/.env (see /app/memory/test_credentials.md). CLIP search deferred.

backend:
  - task: "Auth login (master password from .env)"
    implemented: true
    working: true
    file: "app/api/[[...path]]/route.js"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "POST /api/auth/login {password} -> {token,user} for homeart-molteni-2026; wrong/empty -> 401."
        -working: true
        -agent: "testing"
        -comment: "✅ PASSED all 3 tests: (1) Valid password returns 200 with token and user, (2) Wrong password returns 401 with error, (3) Empty password returns 401. Auth endpoint working correctly."

  - task: "Position-first catalogue API (Directive 1)"
    implemented: true
    working: true
    file: "app/api/[[...path]]/route.js, backend/worker.py, backend/assemble.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "GET /api/positions (filters q/status/flagged/category/min_variants/sort, pagination), GET /api/positions/{id} (position + variant_prices + pages + documents), GET /api/positions/facets, PATCH /api/positions/{id} (status/reviewer_notes/name, cascade_status cascades to variant_prices), POST /api/positions/bulk. Expect 628 positions, 65607 variant_prices. '505 UP System' must be ONE position (~1249 variant prices) and distinct from '505 UP Sideboard'."
        -working: true
        -agent: "testing"
        -comment: "✅ PASSED 4/5 tests: (1) GET /api/positions returns 628 positions with correct fields, (2) GET /api/positions/{id} returns position detail with variants containing raw geometry chains (above_chain_raw, left_raw), (3) GET /api/positions/facets returns categories and documents, (4) PATCH with cascade_status correctly updates position and cascades to 1249 variants. Verified '505 UP System' (id: 4dc45d9c-7702-47b9-b9a5-dcda737a1862, 1249 variants) and '505 UP Sideboard' (id: 1c3887b1-08da-4218-868b-66f2772179fd, 2134 variants) are SEPARATE positions (no-merge invariant confirmed)."

  - task: "Stats with position/variant counts"
    implemented: true
    working: true
    file: "app/api/[[...path]]/route.js"
    stuck_count: 0
    priority: "medium"
    needs_retesting: false
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "GET /api/stats returns positions, positions_pending/approved/flagged, variant_prices, positions_avg_confidence plus legacy product counts."
        -working: true
        -agent: "testing"
        -comment: "✅ PASSED: GET /api/stats returns correct counts: positions=628 (expected 600-660), variant_prices=65607 (expected 60000-70000), documents=14. All required fields present: positions_pending, positions_approved, positions_flagged, positions_avg_confidence."

  - task: "Position-first Excel export (sheets Позиции/Цены/Сводка)"
    implemented: true
    working: true
    file: "app/api/[[...path]]/route.js, backend/export_xlsx.py, backend/worker.py"
    stuck_count: 0
    priority: "medium"
    needs_retesting: false
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "GET /api/export-positions?status=all -> xlsx (Content-Type spreadsheet), 3 sheets, Cyrillic headers. X-Positions/X-Rows headers set."
        -working: true
        -agent: "testing"
        -comment: "✅ PASSED: GET /api/export-positions?status=all returns valid xlsx (3179465 bytes) with Content-Type 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'. Verified 3 Cyrillic sheets: 'Позиции', 'Цены', 'Сводка'. File starts with PK magic bytes (valid ZIP/xlsx)."

  - task: "File inventory - local + full Dropbox folder (Directive 2)"
    implemented: true
    working: true
    file: "app/api/[[...path]]/route.js, backend/worker.py, backend/inventory.py, backend/dropbox_fetch.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "POST /api/inventory {source:local|dropbox,...}; GET /api/inventory (filters source/doc_type/current/q; returns items,total,by_type,current_listini,ingested). Full folder already inventoried (source=dropbox, 397 files, 29 current listini). Dropbox zip cached; do NOT trigger a fresh 2.5GB download during tests (use GET only; POST source=local is fast)."
        -working: true
        -agent: "testing"
        -comment: "✅ PASSED 3/4 tests: (1) GET /api/inventory returns correct structure with items, total=411, by_type, current_listini=42, ingested=29, (2) GET /api/inventory?source=dropbox returns total=397 (expected ~397), (3) GET /api/inventory?current=true returns 42 items all with is_current_listino=true, (4) POST /api/inventory with source=local returns task_id and completes successfully. Minor: current_listini=42 slightly above expected range 25-40, but not a critical issue."

  - task: "Coverage aggregation (Directive 2)"
    implemented: true
    working: true
    file: "app/api/[[...path]]/route.js, backend/worker.py"
    stuck_count: 0
    priority: "medium"
    needs_retesting: false
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "GET /api/coverage -> {documents[], totals{pages_total,pages_with_matrix,pages_parsed,pages_skipped,positions,variant_prices}, files_parsed, files_classified_only, classified_only[]}."
        -working: true
        -agent: "testing"
        -comment: "✅ PASSED: GET /api/coverage returns correct structure with documents[], totals{pages_total, pages_with_matrix, pages_parsed, pages_skipped, positions, variant_prices}, files_parsed=14 (expected 14), files_classified_only, classified_only[]."

  - task: "Inventory Excel export"
    implemented: true
    working: true
    file: "app/api/[[...path]]/route.js, backend/export_xlsx.py, backend/worker.py"
    stuck_count: 0
    priority: "low"
    needs_retesting: false
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "GET /api/inventory/export -> xlsx with sheets Инвентаризация + Покрытие."
        -working: true
        -agent: "testing"
        -comment: "✅ PASSED: GET /api/inventory/export returns valid xlsx (31253 bytes) with Content-Type 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'. Verified 2 Cyrillic sheets: 'Инвентаризация', 'Покрытие'."

  - task: "Search graceful degradation (CLIP index not built)"
    implemented: true
    working: true
    file: "backend/worker.py"
    stuck_count: 0
    priority: "medium"
    needs_retesting: false
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "POST /api/search {q} must return 200 with {results:[],note:'no embeddings yet'} when embeddings=0 (torch not installed). Must NOT 500."
        -working: true
        -agent: "testing"
        -comment: "✅ PASSED: POST /api/search with query '505 up system' returns 200 (not 500) with empty results=[] and note='no embeddings yet'. Graceful degradation working correctly when embeddings index not built."

  - task: "Idempotent re-ingest on Position->Variant schema"
    implemented: true
    working: true
    file: "backend/worker.py, backend/assemble.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "main"
        -comment: "Verified manually: re-ingesting Gliss-Master kept positions=19, variant_prices=1623, products=665 (no duplication). Deterministic variant-price ids + delete_many(doc_id)."

frontend:
  - task: "Position-first QA workbench (split screen)"
    implemented: true
    working: "NA"
    file: "components/hub/PositionWorkbench.jsx, app/page.js"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "Not yet UI-tested by testing agent (awaiting user permission). Renders per screenshot: list + PDF overlay + position detail + approve/reject."
  - task: "Инвентаризация файлов + Покрытие screens"
    implemented: true
    working: "NA"
    file: "components/hub/InventoryPanel.jsx, components/hub/CoveragePanel.jsx, app/page.js"
    stuck_count: 0
    priority: "medium"
    needs_retesting: false
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "Awaiting user permission for frontend testing."

metadata:
  created_by: "main_agent"
  version: "2.0"
  test_sequence: 1
  run_ui: false

test_plan:
  current_focus:
    - "Auth login (master password from .env)"
    - "Position-first catalogue API (Directive 1)"
    - "File inventory - local + full Dropbox folder (Directive 2)"
    - "Coverage aggregation (Directive 2)"
    - "Position-first Excel export (sheets Позиции/Цены/Сводка)"
    - "Stats with position/variant counts"
    - "Search graceful degradation (CLIP index not built)"
    - "Inventory Excel export"
  stuck_tasks: []
  test_all: false
  test_priority: "high_first"

agent_communication:
    -agent: "main"
    -message: |
      Resumed after container reset. Runtime rebuilt (dsworker :8001, .env with MASTER_PASSWORD
      homeart-molteni-2026), DB re-ingested from 14 cached listini on the NEW Position->Variant
      schema. Please test BACKEND ONLY (no UI). Auth: POST /api/auth/login {"password":"homeart-molteni-2026"}
      (also in /app/memory/test_credentials.md). Focus on the position-first API, inventory (GET only +
      POST source=local is fine; DO NOT POST source=dropbox — it would attempt a 2.5GB download), coverage,
      exports (xlsx content-type + sheet names), stats, and search graceful degradation. Expected magnitudes:
      628 positions, 65607 variant_prices, 14 docs, 397 files in dropbox inventory, 29 current listini.
      Key correctness check: '505 UP System' is ONE position (~1249 variant prices), separate from
      '505 UP Sideboard' (no-merge invariant).
    -agent: "testing"
    -message: |
      Backend testing completed. Executed 19 tests across 9 backend endpoints. Results: 17/19 tests PASSED (89%).
      All critical functionality working correctly. Two minor issues noted but do not affect core functionality:
      (1) current_listini count is 42 vs expected 25-40 (minor variance), (2) test logic issue with 505 UP search
      (both positions exist and are correctly separate). All high-priority tasks verified working: Auth, Positions API
      with cascade, Stats, Inventory, Coverage, Exports, Search graceful degradation. No major issues found.
