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
user_problem_statement: "B2B SaaS Data Hub для обработки PDF-прайсов мебельных фабрик (HOMEART): Next.js UI + Python FastAPI backend (порт 8001, проксируется через Next.js /api) + PostgreSQL с pgvector + Redis + Celery. Инжест из публичных Dropbox-ссылок (без OAuth, dl=1 ZIP), заглушка run_extraction_pipeline, 512-d эмбеддинги-заглушки, семантический (<=>) и визуальный поиск, QA-интерфейс, SSE прогресс, JWT-auth по единому паролю."

backend:
  - task: "Infrastructure: PostgreSQL+pgvector, Redis, FastAPI (8001), Celery via supervisor"
    implemented: true
    working: true
    file: "/app/scripts/setup_infra.sh, /app/scripts/datahub_supervisor.conf"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: true
          agent: "main"
          comment: "All services RUNNING. pgvector v0.8.0 built from source. Migrations applied (001_init.sql with CREATE EXTENSION vector, HNSW indexes)."
  - task: "Next.js /api proxy -> FastAPI (streaming, SSE passthrough)"
    implemented: true
    working: true
    file: "/app/app/api/[[...path]]/route.js"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: true
          agent: "main"
          comment: "Verified /api/health and login through port 3000."
        - working: true
          agent: "testing"
          comment: "Comprehensive test: all 11 API endpoints tested through Next.js proxy at https://sofa-search-1.preview.emergentagent.com/api. Health, auth, upload, tasks, SSE stream, search (fulltext/semantic/visual), QA, and file serving all work correctly. SSE streaming verified with proper event delivery."
  - task: "Auth: POST /api/auth/login (password from .env ADMIN_PASSWORD=homeart2025) -> JWT"
    implemented: true
    working: true
    file: "/app/backend/auth.py, /app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: true
          agent: "main"
          comment: "JWT issued, protected routes require Bearer token."
        - working: true
          agent: "testing"
          comment: "Auth fully tested: (1) Login with correct password 'homeart2025' returns JWT token (200), (2) Login with incorrect password correctly rejected (401), (3) Protected endpoint /api/stats without token correctly rejected (401). All auth flows working as expected."
  - task: "Dropbox ingest: POST /api/ingest/dropbox (public shared link, dl=1 ZIP, no OAuth) + Celery pipeline"
    implemented: true
    working: true
    file: "/app/backend/worker.py, /app/backend/dropbox_client.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: true
          agent: "main"
          comment: "E2E verified with REAL user Dropbox folder (~2.4GB, 394 PDFs -> 2616 products with embeddings). Statuses: queued->downloading->parsing->embedding->completed. Factory updated to active with total_items and last_synced. Failure path verified (size limit -> failed + factory error). MAX_DOWNLOAD_MB=8192."
        - working: true
          agent: "testing"
          comment: "Dropbox URL validation tested: invalid URL (https://evil.com/file.zip) correctly rejected with 400 error. Real Dropbox ingest not re-tested per instructions (existing data preserved). Validation logic working correctly."
  - task: "Manual upload fallback: POST /api/ingest/upload (multipart PDFs)"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: "Implemented, not yet tested."
        - working: true
          agent: "testing"
          comment: "Manual upload fully tested: Created 2 minimal valid PDF files, uploaded via multipart form with factory_name='Test Factory QA'. Task created (task_id: 369a6e28-0fcb-422e-a4ca-9591e6b2329f), files saved (2 PDFs), Celery worker processed task to completion. Task status progressed queued->completed, created 17 products with embeddings. All products have source_file and source_page metadata. Upload, processing, and persistence all working correctly."
  - task: "Task tracking: GET /api/ingest/tasks, GET /api/ingest/tasks/{id}, SSE /api/ingest/tasks/{id}/stream?token="
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: true
          agent: "main"
          comment: "Polling verified. SSE stream not yet tested through proxy."
        - working: true
          agent: "testing"
          comment: "Task tracking fully tested: (1) GET /api/ingest/tasks returns list of 3 tasks with factory_name joined, (2) GET /api/ingest/tasks/{id} returns individual task details, (3) SSE stream /api/ingest/tasks/{id}/stream?token=JWT successfully delivers events with proper text/event-stream content-type, tested with completed task, received data events with task status. Token authentication via query param working. All task tracking endpoints operational."
  - task: "Full-text search: GET /api/search?q=&factory_id=&designer=&category="
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: "Implemented (ILIKE across model/collection/factory), not yet tested."
        - working: true
          agent: "testing"
          comment: "Full-text search fully tested with real Molteni & C data (2616 products): (1) Search q='Paul' returned 30 results including 'Paul 27', 'Paul 42' models, (2) Search designer='Dordoni' returned 30 results with designer_name='Rodolfo Dordoni', (3) Search factory_id filter returned 17 products from Test Factory QA. ILIKE pattern matching working across model_name, collection name, and factory name. All filters operational."
  - task: "Semantic search: POST /api/search/semantic (pgvector <=> cosine)"
    implemented: true
    working: true
    file: "/app/backend/server.py, /app/backend/embeddings.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: true
          agent: "main"
          comment: "Verified: returns ranked products with distance/similarity."
        - working: true
          agent: "testing"
          comment: "Semantic search fully tested: Query 'modular corner sofa scandinavian style' with limit=5 returned 5 results. Each result includes distance and similarity fields (similarity = 1 - distance). Results correctly sorted by distance ascending (best matches first). pgvector <=> operator working correctly with 512-d embeddings. Sample result: 'Half 64' with similarity=0.1324, distance=0.8676."
  - task: "Visual search: POST /api/search/visual (multipart image -> image_embedding <=>)"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: "Implemented, not yet tested."
        - working: true
          agent: "testing"
          comment: "Visual search fully tested: Uploaded minimal valid PNG image (1x1 pixel) via multipart form with limit=5. Endpoint accepted image, generated embedding, queried pgvector with <=> operator, returned 5 results with similarity scores. Sample result: 'Turner 66' with similarity=0.1319. Image upload, embedding generation, and vector search all working correctly."
  - task: "QA: GET /api/qa/products?status=, POST /api/qa/products/{id}/review, PDF deep link GET /api/files/{task_id}/{path}?token="
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: "qa/products verified returns pending items with task_id/source_file/source_page. review + file serving not yet tested."
        - working: true
          agent: "testing"
          comment: "QA workflow fully tested: (1) GET /api/qa/products?status=pending returned 5 products with required fields (task_id, source_file, source_page), (2) POST review with action='approve' changed review_status to 'approved' (200), (3) Approved product verified in GET /api/qa/products?status=approved list, (4) POST review with action='reject' changed status to 'rejected' (200), (5) POST review with invalid action correctly rejected (400). PDF deep link GET /api/files/{task_id}/{source_file}?token=JWT returned PDF file with Content-Type: application/pdf (584 bytes). Token auth via query param working. All QA endpoints operational."

frontend:
  - task: "Login + App shell (sidebar) + Dashboard (stats, factories)"
    implemented: true
    working: true
    file: "/app/app/page.js"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: true
          agent: "main"
          comment: "Screenshot verified: login works, dashboard shows real data (Molteni & C, 2616 products)."
  - task: "Ingest view (dropbox form, manual upload, SSE/polling progress, task history)"
    implemented: true
    working: "NA"
    file: "/app/app/page.js"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: "Implemented, not UI-tested yet."
  - task: "Search view (fulltext/semantic/visual tabs)"
    implemented: true
    working: "NA"
    file: "/app/app/page.js"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: "Implemented, not UI-tested yet."
  - task: "QA view (pending table, approve/reject, PDF deep link)"
    implemented: true
    working: "NA"
    file: "/app/app/page.js"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: "Implemented, not UI-tested yet."

metadata:
  created_by: "main_agent"
  version: "1.0"
  test_sequence: 2
  run_ui: false

test_plan:
  current_focus: []
  stuck_tasks: []
  test_all: false
  test_priority: "high_first"

agent_communication:
    - agent: "main"
      message: "Backend is Python FastAPI on 127.0.0.1:8001, proxied through Next.js /api. Test ONLY through the external URL /api prefix. Auth: POST /api/auth/login {password: homeart2025} -> {token}; all other routes need Authorization: Bearer <token>. SSE and /api/files accept ?token= query param. DB already contains real ingested data (factory Molteni & C, 2616 products). DO NOT run another Dropbox ingest with the real link (2.4GB download) - for ingest testing use the manual upload endpoint with small generated PDFs. Do not delete existing data."
    - agent: "testing"
      message: "Backend testing COMPLETE - ALL 11 TESTS PASSED ✅. Tested: (1) Health check, (2) Auth (login correct/incorrect, protected endpoints), (3) Manual upload (2 PDFs -> 17 products created via Celery), (4) Task list, (5) SSE stream through Next.js proxy, (6) Full-text search (query, designer, factory filters), (7) Semantic search (pgvector <=> with 512-d embeddings), (8) Visual search (image upload), (9) QA workflow (get pending/approved, approve/reject actions, invalid action validation), (10) PDF deep link (file serving with token auth), (11) Dropbox URL validation. All endpoints working correctly through Next.js proxy at https://sofa-search-1.preview.emergentagent.com/api. No critical issues found. Existing Molteni & C data (2616 products) preserved. Test Factory QA created with 17 products from manual upload."

frontend_redesign_v2:
  - agent: "main"
    message: "Frontend redesigned per user spec: Login 'System Access' (Enter .env password / Authenticate); sidebar nav Ingestion/QA Review/Vector Search/Settings; Ingestion = big dropbox input + 'Run Parsing Pipeline' + live Task Monitor cards with emoji status badges and progress bars (SSE + polling fallback) + manual upload fallback (collapsible); QA Review = split-screen (left: PDF iframe autoscrolled via #page=N, right: product card with price matrix HTML table, Approve & Publish / Edit / Reject, prev/next navigation); Vector Search = single Spotlight-style smart field (Enter=semantic, drag-drop image=visual, collapsible classic filters), result cards with category photos and 'Match XX%' badges ((2-distance)/2). Settings = service health + stack + factories registry. Screenshots verified: ingestion, vector search, QA. Note: PDF iframe appears empty in headless screenshot browser (no PDF plugin) but /api/files serves 200 application/pdf correctly. Pod restart recovery verified via /app/scripts/setup_infra.sh (single command, data survived in /app/data/postgres)."
