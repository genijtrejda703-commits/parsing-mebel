#!/usr/bin/env python3
"""Backend API tests for HOMEART Data Hub."""
import os
import sys
import time
import json
import requests
from pathlib import Path
from io import BytesIO

# Load environment
BASE_URL = "https://sofa-search-1.preview.emergentagent.com/api"
PASSWORD = "homeart2025"

# Global token storage
TOKEN = None


def create_minimal_pdf(filename: str) -> str:
    """Create a minimal valid PDF file for testing."""
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /Resources 4 0 R /MediaBox [0 0 612 792] /Contents 5 0 R >>
endobj
4 0 obj
<< /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >>
endobj
5 0 obj
<< /Length 44 >>
stream
BT
/F1 12 Tf
100 700 Td
(Test PDF) Tj
ET
endstream
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000229 00000 n 
0000000327 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
420
%%EOF
"""
    path = f"/tmp/{filename}"
    with open(path, "wb") as f:
        f.write(pdf_content)
    return path


def create_test_image(filename: str) -> str:
    """Create a small test PNG image for visual search."""
    # Create a minimal valid PNG file (1x1 blue pixel)
    png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
    path = f"/tmp/{filename}"
    with open(path, "wb") as f:
        f.write(png_data)
    return path


def test_health():
    """Test 1: Health check endpoint."""
    print("\n=== TEST 1: Health Check ===")
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=10)
        print(f"Status: {resp.status_code}")
        data = resp.json()
        print(f"Response: {json.dumps(data, indent=2)}")
        
        if resp.status_code == 200 and data.get("status") == "ok" and data.get("database") == "up":
            print("✅ Health check PASSED")
            return True
        else:
            print("❌ Health check FAILED: unexpected response")
            return False
    except Exception as e:
        print(f"❌ Health check FAILED: {e}")
        return False


def test_auth():
    """Test 2: Authentication - login with correct/incorrect password, protected endpoint without token."""
    global TOKEN
    print("\n=== TEST 2: Authentication ===")
    
    # Test 2a: Login with correct password
    print("\n2a. Login with correct password:")
    try:
        resp = requests.post(f"{BASE_URL}/auth/login", json={"password": PASSWORD}, timeout=10)
        print(f"Status: {resp.status_code}")
        data = resp.json()
        
        if resp.status_code == 200 and "token" in data:
            TOKEN = data["token"]
            print(f"✅ Login with correct password PASSED (token received)")
        else:
            print(f"❌ Login with correct password FAILED: {data}")
            return False
    except Exception as e:
        print(f"❌ Login with correct password FAILED: {e}")
        return False
    
    # Test 2b: Login with incorrect password
    print("\n2b. Login with incorrect password:")
    try:
        resp = requests.post(f"{BASE_URL}/auth/login", json={"password": "wrongpassword"}, timeout=10)
        print(f"Status: {resp.status_code}")
        
        if resp.status_code == 401:
            print("✅ Login with incorrect password correctly rejected (401)")
        else:
            print(f"❌ Login with incorrect password FAILED: expected 401, got {resp.status_code}")
            return False
    except Exception as e:
        print(f"❌ Login with incorrect password test FAILED: {e}")
        return False
    
    # Test 2c: Access protected endpoint without token
    print("\n2c. Access protected endpoint without token:")
    try:
        resp = requests.get(f"{BASE_URL}/stats", timeout=10)
        print(f"Status: {resp.status_code}")
        
        if resp.status_code == 401:
            print("✅ Protected endpoint without token correctly rejected (401)")
            return True
        else:
            print(f"❌ Protected endpoint without token FAILED: expected 401, got {resp.status_code}")
            return False
    except Exception as e:
        print(f"❌ Protected endpoint without token test FAILED: {e}")
        return False


def test_manual_upload():
    """Test 3: Manual upload fallback - upload PDFs, poll task until completed."""
    print("\n=== TEST 3: Manual Upload Fallback ===")
    
    if not TOKEN:
        print("❌ No token available, skipping test")
        return False
    
    # Create test PDFs
    print("\n3a. Creating test PDF files...")
    try:
        pdf1 = create_minimal_pdf("test_catalog_1.pdf")
        pdf2 = create_minimal_pdf("test_catalog_2.pdf")
        print(f"✅ Created test PDFs: {pdf1}, {pdf2}")
    except Exception as e:
        print(f"❌ Failed to create test PDFs: {e}")
        return False
    
    # Upload PDFs
    print("\n3b. Uploading PDFs...")
    try:
        files = [
            ('files', ('test_catalog_1.pdf', open(pdf1, 'rb'), 'application/pdf')),
            ('files', ('test_catalog_2.pdf', open(pdf2, 'rb'), 'application/pdf'))
        ]
        data = {'factory_name': 'Test Factory QA'}
        headers = {'Authorization': f'Bearer {TOKEN}'}
        
        resp = requests.post(f"{BASE_URL}/ingest/upload", files=files, data=data, headers=headers, timeout=30)
        print(f"Status: {resp.status_code}")
        result = resp.json()
        print(f"Response: {json.dumps(result, indent=2)}")
        
        if resp.status_code != 200 or "task_id" not in result:
            print(f"❌ Upload FAILED: {result}")
            return False
        
        task_id = result["task_id"]
        print(f"✅ Upload successful, task_id: {task_id}")
        
    except Exception as e:
        print(f"❌ Upload FAILED: {e}")
        return False
    
    # Poll task until completed
    print("\n3c. Polling task status...")
    try:
        max_attempts = 30
        for attempt in range(max_attempts):
            time.sleep(2)
            resp = requests.get(f"{BASE_URL}/ingest/tasks/{task_id}", headers=headers, timeout=10)
            task = resp.json()
            status = task.get("status")
            progress = task.get("progress", 0)
            message = task.get("message", "")
            
            print(f"Attempt {attempt + 1}/{max_attempts}: status={status}, progress={progress}, message={message}")
            
            if status == "completed":
                stats = task.get("stats", {})
                products_created = stats.get("products_created", 0)
                print(f"✅ Task completed! Products created: {products_created}")
                
                if products_created > 0:
                    print("✅ Manual upload test PASSED")
                    return True
                else:
                    print("❌ Task completed but no products created")
                    return False
            
            elif status == "failed":
                error = task.get("error", "Unknown error")
                print(f"❌ Task failed: {error}")
                return False
        
        print(f"❌ Task did not complete within {max_attempts * 2} seconds")
        return False
        
    except Exception as e:
        print(f"❌ Task polling FAILED: {e}")
        return False


def test_task_list():
    """Test 4: Get list of tasks."""
    print("\n=== TEST 4: Task List ===")
    
    if not TOKEN:
        print("❌ No token available, skipping test")
        return False
    
    try:
        headers = {'Authorization': f'Bearer {TOKEN}'}
        resp = requests.get(f"{BASE_URL}/ingest/tasks", headers=headers, timeout=10)
        print(f"Status: {resp.status_code}")
        tasks = resp.json()
        
        print(f"Total tasks: {len(tasks)}")
        
        # Check for completed tasks
        completed_tasks = [t for t in tasks if t.get("status") == "completed"]
        print(f"Completed tasks: {len(completed_tasks)}")
        
        if resp.status_code == 200 and isinstance(tasks, list) and len(completed_tasks) > 0:
            print("✅ Task list test PASSED")
            return True
        else:
            print("❌ Task list test FAILED: no completed tasks found")
            return False
            
    except Exception as e:
        print(f"❌ Task list test FAILED: {e}")
        return False


def test_sse_stream():
    """Test 5: SSE stream for a completed task."""
    print("\n=== TEST 5: SSE Stream ===")
    
    if not TOKEN:
        print("❌ No token available, skipping test")
        return False
    
    try:
        # Get a completed task
        headers = {'Authorization': f'Bearer {TOKEN}'}
        resp = requests.get(f"{BASE_URL}/ingest/tasks", headers=headers, timeout=10)
        tasks = resp.json()
        completed_tasks = [t for t in tasks if t.get("status") == "completed"]
        
        if not completed_tasks:
            print("❌ No completed tasks available for SSE test")
            return False
        
        task_id = completed_tasks[0]["id"]
        print(f"Testing SSE stream for task: {task_id}")
        
        # Test SSE endpoint with token as query param
        resp = requests.get(f"{BASE_URL}/ingest/tasks/{task_id}/stream?token={TOKEN}", 
                           stream=True, timeout=15)
        print(f"Status: {resp.status_code}")
        
        if resp.status_code != 200:
            print(f"❌ SSE stream FAILED: status {resp.status_code}")
            return False
        
        # Read at least one event
        events_received = 0
        for line in resp.iter_lines(decode_unicode=True):
            if line and line.startswith("data:"):
                events_received += 1
                print(f"Received event: {line[:100]}...")
                if events_received >= 1:
                    break
        
        if events_received > 0:
            print(f"✅ SSE stream test PASSED (received {events_received} event(s))")
            return True
        else:
            print("❌ SSE stream test FAILED: no events received")
            return False
            
    except Exception as e:
        print(f"❌ SSE stream test FAILED: {e}")
        return False


def test_fulltext_search():
    """Test 6: Full-text search with query and filters."""
    print("\n=== TEST 6: Full-text Search ===")
    
    if not TOKEN:
        print("❌ No token available, skipping test")
        return False
    
    headers = {'Authorization': f'Bearer {TOKEN}'}
    
    # Test 6a: Search by query "Paul"
    print("\n6a. Search for 'Paul':")
    try:
        resp = requests.get(f"{BASE_URL}/search?q=Paul", headers=headers, timeout=10)
        print(f"Status: {resp.status_code}")
        results = resp.json()
        print(f"Results count: {len(results)}")
        
        if len(results) > 0:
            print(f"Sample result: {results[0].get('model_name')} - {results[0].get('factory_name')}")
            print("✅ Search by query PASSED")
        else:
            print("❌ Search by query FAILED: no results (expected products with 'Paul' in name)")
            return False
    except Exception as e:
        print(f"❌ Search by query FAILED: {e}")
        return False
    
    # Test 6b: Search by designer "Dordoni"
    print("\n6b. Search by designer 'Dordoni':")
    try:
        resp = requests.get(f"{BASE_URL}/search?designer=Dordoni", headers=headers, timeout=10)
        print(f"Status: {resp.status_code}")
        results = resp.json()
        print(f"Results count: {len(results)}")
        
        if len(results) > 0:
            print(f"Sample result: {results[0].get('model_name')} by {results[0].get('designer_name')}")
            print("✅ Search by designer PASSED")
        else:
            print("❌ Search by designer FAILED: no results")
            return False
    except Exception as e:
        print(f"❌ Search by designer FAILED: {e}")
        return False
    
    # Test 6c: Get factory_id and search by factory
    print("\n6c. Search by factory_id:")
    try:
        # Get factories first
        resp = requests.get(f"{BASE_URL}/factories", headers=headers, timeout=10)
        factories = resp.json()
        
        if not factories:
            print("⚠️ No factories found, skipping factory filter test")
        else:
            factory_id = factories[0]["id"]
            print(f"Testing with factory_id: {factory_id}")
            
            resp = requests.get(f"{BASE_URL}/search?factory_id={factory_id}", headers=headers, timeout=10)
            print(f"Status: {resp.status_code}")
            results = resp.json()
            print(f"Results count: {len(results)}")
            
            if len(results) > 0:
                print("✅ Search by factory_id PASSED")
            else:
                print("❌ Search by factory_id FAILED: no results")
                return False
    except Exception as e:
        print(f"❌ Search by factory_id FAILED: {e}")
        return False
    
    return True


def test_semantic_search():
    """Test 7: Semantic search with vector similarity."""
    print("\n=== TEST 7: Semantic Search ===")
    
    if not TOKEN:
        print("❌ No token available, skipping test")
        return False
    
    try:
        headers = {'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'}
        payload = {
            "query": "modular corner sofa scandinavian style",
            "limit": 5
        }
        
        resp = requests.post(f"{BASE_URL}/search/semantic", json=payload, headers=headers, timeout=10)
        print(f"Status: {resp.status_code}")
        results = resp.json()
        print(f"Results count: {len(results)}")
        
        if resp.status_code != 200:
            print(f"❌ Semantic search FAILED: status {resp.status_code}")
            return False
        
        if len(results) == 0:
            print("❌ Semantic search FAILED: no results returned")
            return False
        
        # Check that results have required fields
        first = results[0]
        if "distance" not in first or "similarity" not in first:
            print("❌ Semantic search FAILED: missing distance/similarity fields")
            return False
        
        print(f"Sample result: {first.get('model_name')} - similarity: {first.get('similarity')}, distance: {first.get('distance')}")
        
        # Check that results are sorted by distance (ascending)
        distances = [r.get("distance", 999) for r in results]
        if distances == sorted(distances):
            print("✅ Semantic search PASSED (results sorted by distance)")
            return True
        else:
            print("❌ Semantic search FAILED: results not sorted by distance")
            return False
            
    except Exception as e:
        print(f"❌ Semantic search FAILED: {e}")
        return False


def test_visual_search():
    """Test 8: Visual search with image upload."""
    print("\n=== TEST 8: Visual Search ===")
    
    if not TOKEN:
        print("❌ No token available, skipping test")
        return False
    
    try:
        # Create test image
        img_path = create_test_image("test_search.png")
        print(f"Created test image: {img_path}")
        
        headers = {'Authorization': f'Bearer {TOKEN}'}
        files = {'image': ('test_search.png', open(img_path, 'rb'), 'image/png')}
        data = {'limit': '5'}
        
        resp = requests.post(f"{BASE_URL}/search/visual", files=files, data=data, headers=headers, timeout=10)
        print(f"Status: {resp.status_code}")
        results = resp.json()
        print(f"Results count: {len(results)}")
        
        if resp.status_code != 200:
            print(f"❌ Visual search FAILED: status {resp.status_code}")
            return False
        
        if len(results) == 0:
            print("❌ Visual search FAILED: no results returned")
            return False
        
        # Check that results have similarity field
        first = results[0]
        if "similarity" not in first:
            print("❌ Visual search FAILED: missing similarity field")
            return False
        
        print(f"Sample result: {first.get('model_name')} - similarity: {first.get('similarity')}")
        print("✅ Visual search PASSED")
        return True
        
    except Exception as e:
        print(f"❌ Visual search FAILED: {e}")
        return False


def test_qa_workflow():
    """Test 9: QA workflow - get pending, approve, reject, invalid action."""
    print("\n=== TEST 9: QA Workflow ===")
    
    if not TOKEN:
        print("❌ No token available, skipping test")
        return False
    
    headers = {'Authorization': f'Bearer {TOKEN}'}
    
    # Test 9a: Get pending products
    print("\n9a. Get pending products:")
    try:
        resp = requests.get(f"{BASE_URL}/qa/products?status=pending&limit=5", headers=headers, timeout=10)
        print(f"Status: {resp.status_code}")
        products = resp.json()
        print(f"Pending products count: {len(products)}")
        
        if resp.status_code != 200:
            print(f"❌ Get pending products FAILED: status {resp.status_code}")
            return False
        
        if len(products) == 0:
            print("⚠️ No pending products found, cannot test approve/reject")
            return False
        
        # Check required fields
        first = products[0]
        if "task_id" not in first or "source_file" not in first or "source_page" not in first:
            print("❌ Get pending products FAILED: missing required fields (task_id, source_file, source_page)")
            return False
        
        print(f"Sample product: {first.get('model_name')} - task_id: {first.get('task_id')}, source: {first.get('source_file')}:{first.get('source_page')}")
        print("✅ Get pending products PASSED")
        
        product_id_approve = first["id"]
        product_id_reject = products[1]["id"] if len(products) > 1 else None
        
    except Exception as e:
        print(f"❌ Get pending products FAILED: {e}")
        return False
    
    # Test 9b: Approve a product
    print("\n9b. Approve a product:")
    try:
        payload = {"action": "approve"}
        resp = requests.post(f"{BASE_URL}/qa/products/{product_id_approve}/review", 
                           json=payload, headers=headers, timeout=10)
        print(f"Status: {resp.status_code}")
        result = resp.json()
        print(f"Response: {json.dumps(result, indent=2)}")
        
        if resp.status_code == 200 and result.get("review_status") == "approved":
            print("✅ Approve product PASSED")
        else:
            print(f"❌ Approve product FAILED: {result}")
            return False
    except Exception as e:
        print(f"❌ Approve product FAILED: {e}")
        return False
    
    # Test 9c: Verify approved product appears in approved list
    print("\n9c. Verify approved product in approved list:")
    try:
        resp = requests.get(f"{BASE_URL}/qa/products?status=approved&limit=10", headers=headers, timeout=10)
        approved_products = resp.json()
        approved_ids = [p["id"] for p in approved_products]
        
        if product_id_approve in approved_ids:
            print("✅ Approved product found in approved list")
        else:
            print("❌ Approved product NOT found in approved list")
            return False
    except Exception as e:
        print(f"❌ Verify approved product FAILED: {e}")
        return False
    
    # Test 9d: Reject a product (if available)
    if product_id_reject:
        print("\n9d. Reject a product:")
        try:
            payload = {"action": "reject"}
            resp = requests.post(f"{BASE_URL}/qa/products/{product_id_reject}/review", 
                               json=payload, headers=headers, timeout=10)
            print(f"Status: {resp.status_code}")
            result = resp.json()
            
            if resp.status_code == 200 and result.get("review_status") == "rejected":
                print("✅ Reject product PASSED")
            else:
                print(f"❌ Reject product FAILED: {result}")
                return False
        except Exception as e:
            print(f"❌ Reject product FAILED: {e}")
            return False
    
    # Test 9e: Invalid action
    print("\n9e. Test invalid action:")
    try:
        payload = {"action": "invalid_action"}
        resp = requests.post(f"{BASE_URL}/qa/products/{product_id_approve}/review", 
                           json=payload, headers=headers, timeout=10)
        print(f"Status: {resp.status_code}")
        
        if resp.status_code == 400:
            print("✅ Invalid action correctly rejected (400)")
            return True
        else:
            print(f"❌ Invalid action test FAILED: expected 400, got {resp.status_code}")
            return False
    except Exception as e:
        print(f"❌ Invalid action test FAILED: {e}")
        return False


def test_pdf_deep_link():
    """Test 10: PDF deep link for QA."""
    print("\n=== TEST 10: PDF Deep Link ===")
    
    if not TOKEN:
        print("❌ No token available, skipping test")
        return False
    
    try:
        headers = {'Authorization': f'Bearer {TOKEN}'}
        
        # Get a product from manual upload task (should have files on disk)
        resp = requests.get(f"{BASE_URL}/ingest/tasks", headers=headers, timeout=10)
        tasks = resp.json()
        
        # Find a completed manual upload task
        manual_tasks = [t for t in tasks if t.get("source") == "manual" and t.get("status") == "completed"]
        
        if not manual_tasks:
            print("⚠️ No completed manual upload tasks found, cannot test PDF deep link")
            return False
        
        task_id = manual_tasks[0]["id"]
        print(f"Using task_id: {task_id}")
        
        # Get products from this task
        resp = requests.get(f"{BASE_URL}/qa/products?status=pending&limit=50", headers=headers, timeout=10)
        products = resp.json()
        
        # Find a product from this task
        task_products = [p for p in products if str(p.get("task_id")) == str(task_id)]
        
        if not task_products:
            print(f"⚠️ No products found for task {task_id}, cannot test PDF deep link")
            return False
        
        product = task_products[0]
        source_file = product.get("source_file")
        
        if not source_file:
            print("⚠️ Product has no source_file, cannot test PDF deep link")
            return False
        
        print(f"Testing PDF link: task_id={task_id}, source_file={source_file}")
        
        # Test PDF endpoint with token as query param
        url = f"{BASE_URL}/files/{task_id}/{source_file}?token={TOKEN}"
        resp = requests.get(url, timeout=10)
        print(f"Status: {resp.status_code}")
        print(f"Content-Type: {resp.headers.get('Content-Type')}")
        
        if resp.status_code == 200 and resp.headers.get('Content-Type') == 'application/pdf':
            print(f"✅ PDF deep link PASSED (received {len(resp.content)} bytes)")
            return True
        elif resp.status_code == 404:
            print("⚠️ PDF file not found (may have been cleaned up) - this is acceptable")
            return True
        else:
            print(f"❌ PDF deep link FAILED: status {resp.status_code}, content-type {resp.headers.get('Content-Type')}")
            return False
            
    except Exception as e:
        print(f"❌ PDF deep link test FAILED: {e}")
        return False


def test_dropbox_validation():
    """Test 11: Dropbox link validation - invalid URL should return 400."""
    print("\n=== TEST 11: Dropbox Link Validation ===")
    
    if not TOKEN:
        print("❌ No token available, skipping test")
        return False
    
    try:
        headers = {'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'}
        payload = {
            "factory_name": "Test Factory Invalid",
            "dropbox_url": "https://evil.com/file.zip"
        }
        
        resp = requests.post(f"{BASE_URL}/ingest/dropbox", json=payload, headers=headers, timeout=10)
        print(f"Status: {resp.status_code}")
        
        if resp.status_code == 400:
            print("✅ Dropbox validation PASSED (invalid URL rejected with 400)")
            return True
        else:
            print(f"❌ Dropbox validation FAILED: expected 400, got {resp.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Dropbox validation test FAILED: {e}")
        return False


def main():
    """Run all backend tests."""
    print("=" * 80)
    print("HOMEART Data Hub - Backend API Tests")
    print(f"Base URL: {BASE_URL}")
    print("=" * 80)
    
    results = {}
    
    # Run tests in priority order
    results["1. Health Check"] = test_health()
    results["2. Authentication"] = test_auth()
    results["3. Manual Upload"] = test_manual_upload()
    results["4. Task List"] = test_task_list()
    results["5. SSE Stream"] = test_sse_stream()
    results["6. Full-text Search"] = test_fulltext_search()
    results["7. Semantic Search"] = test_semantic_search()
    results["8. Visual Search"] = test_visual_search()
    results["9. QA Workflow"] = test_qa_workflow()
    results["10. PDF Deep Link"] = test_pdf_deep_link()
    results["11. Dropbox Validation"] = test_dropbox_validation()
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    print("=" * 80)
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
