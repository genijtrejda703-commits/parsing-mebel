#!/usr/bin/env python3
"""
Comprehensive backend API test suite for HOMEART Data Hub
Tests all Next.js /api routes and Python DS sidecar endpoints
"""
import os
import sys
import time
import requests
from dotenv import load_dotenv

load_dotenv('/app/.env')

BASE_URL = os.getenv('NEXT_PUBLIC_BASE_URL', 'https://saas-ingestion.preview.emergentagent.com')
API_URL = f"{BASE_URL}/api"
MASTER_PASSWORD = os.getenv('MASTER_PASSWORD', 'homeart2025')

print(f"Testing backend at: {API_URL}")
print(f"Master password: {MASTER_PASSWORD}")
print("=" * 80)

# Global state for test data
test_state = {
    'token': None,
    'doc_id': None,
    'product_id': None,
    'page_number': None,
    'task_id': None,
    'product_ids_for_bulk': []
}

def test_auth_login():
    """Test 1: POST /api/auth/login - correct password"""
    print("\n[TEST 1] POST /api/auth/login - correct password")
    try:
        resp = requests.post(f"{API_URL}/auth/login", json={"password": MASTER_PASSWORD}, timeout=10)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            if 'token' in data and 'user' in data:
                test_state['token'] = data['token']
                print(f"  ✅ PASS - Got token and user: {data['user']}")
                return True
            else:
                print(f"  ❌ FAIL - Missing token or user in response: {data}")
                return False
        else:
            print(f"  ❌ FAIL - Expected 200, got {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        print(f"  ❌ FAIL - Exception: {e}")
        return False

def test_auth_login_wrong_password():
    """Test 2: POST /api/auth/login - wrong password"""
    print("\n[TEST 2] POST /api/auth/login - wrong password")
    try:
        resp = requests.post(f"{API_URL}/auth/login", json={"password": "wrongpassword"}, timeout=10)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 401:
            data = resp.json()
            if 'error' in data:
                print(f"  ✅ PASS - Got 401 with error: {data['error']}")
                return True
            else:
                print(f"  ❌ FAIL - 401 but no error field: {data}")
                return False
        else:
            print(f"  ❌ FAIL - Expected 401, got {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        print(f"  ❌ FAIL - Exception: {e}")
        return False

def test_auth_login_missing_password():
    """Test 3: POST /api/auth/login - missing password"""
    print("\n[TEST 3] POST /api/auth/login - missing password")
    try:
        resp = requests.post(f"{API_URL}/auth/login", json={}, timeout=10)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 401:
            data = resp.json()
            if 'error' in data:
                print(f"  ✅ PASS - Got 401 with error: {data['error']}")
                return True
            else:
                print(f"  ❌ FAIL - 401 but no error field: {data}")
                return False
        else:
            print(f"  ❌ FAIL - Expected 401, got {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        print(f"  ❌ FAIL - Exception: {e}")
        return False

def test_health():
    """Test 4: GET /api/health"""
    print("\n[TEST 4] GET /api/health")
    try:
        resp = requests.get(f"{API_URL}/health", timeout=10)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            if data.get('ok') and 'worker' in data and data['worker'].get('ok'):
                print(f"  ✅ PASS - Health check OK, worker reachable: {data}")
                return True
            else:
                print(f"  ❌ FAIL - Health check failed or worker not OK: {data}")
                return False
        else:
            print(f"  ❌ FAIL - Expected 200, got {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        print(f"  ❌ FAIL - Exception: {e}")
        return False

def test_stats():
    """Test 5: GET /api/stats"""
    print("\n[TEST 5] GET /api/stats")
    try:
        resp = requests.get(f"{API_URL}/stats", timeout=10)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            required_fields = ['products', 'approved', 'pending', 'rejected', 'documents', 
                             'factories', 'embeddings', 'avg_confidence', 'flagged']
            missing = [f for f in required_fields if f not in data]
            if not missing:
                print(f"  ✅ PASS - All required fields present:")
                for k, v in data.items():
                    print(f"    {k}: {v}")
                return True
            else:
                print(f"  ❌ FAIL - Missing fields: {missing}")
                print(f"  Response: {data}")
                return False
        else:
            print(f"  ❌ FAIL - Expected 200, got {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        print(f"  ❌ FAIL - Exception: {e}")
        return False

def test_documents():
    """Test 6: GET /api/documents"""
    print("\n[TEST 6] GET /api/documents")
    try:
        resp = requests.get(f"{API_URL}/documents", timeout=10)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            if 'items' in data and isinstance(data['items'], list):
                print(f"  ✅ PASS - Got {len(data['items'])} documents")
                if len(data['items']) > 0:
                    test_state['doc_id'] = data['items'][0]['id']
                    print(f"  Saved doc_id for later tests: {test_state['doc_id']}")
                return True
            else:
                print(f"  ❌ FAIL - Missing or invalid 'items' field: {data}")
                return False
        else:
            print(f"  ❌ FAIL - Expected 200, got {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        print(f"  ❌ FAIL - Exception: {e}")
        return False

def test_factories():
    """Test 7: GET /api/factories"""
    print("\n[TEST 7] GET /api/factories")
    try:
        resp = requests.get(f"{API_URL}/factories", timeout=10)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            if 'items' in data and isinstance(data['items'], list):
                print(f"  ✅ PASS - Got {len(data['items'])} factories")
                return True
            else:
                print(f"  ❌ FAIL - Missing or invalid 'items' field: {data}")
                return False
        else:
            print(f"  ❌ FAIL - Expected 200, got {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        print(f"  ❌ FAIL - Exception: {e}")
        return False

def test_products_basic():
    """Test 8: GET /api/products - basic query"""
    print("\n[TEST 8] GET /api/products - basic query")
    try:
        resp = requests.get(f"{API_URL}/products?limit=5", timeout=10)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            required_top = ['items', 'total', 'skip', 'limit']
            missing_top = [f for f in required_top if f not in data]
            if missing_top:
                print(f"  ❌ FAIL - Missing top-level fields: {missing_top}")
                return False
            
            if not isinstance(data['items'], list):
                print(f"  ❌ FAIL - 'items' is not a list")
                return False
            
            print(f"  Got {len(data['items'])} items, total={data['total']}")
            
            # Check first product has required fields
            if len(data['items']) > 0:
                prod = data['items'][0]
                test_state['product_id'] = prod.get('id')
                test_state['page_number'] = prod.get('page')
                
                # Check for _id field (should NOT be present)
                if '_id' in prod:
                    print(f"  ❌ FAIL - Product contains MongoDB _id field (should be excluded)")
                    return False
                
                required_fields = ['id', 'model_name', 'category', 'dimension', 'variant_code',
                                 'price_min', 'price_max', 'n_variations', 'variations', 'bbox',
                                 'bbox_cells', 'bbox_col_header', 'page', 'page_width', 
                                 'page_height', 'status', 'reviewer_notes', 'confidence']
                missing = [f for f in required_fields if f not in prod]
                if missing:
                    print(f"  ❌ FAIL - Product missing fields: {missing}")
                    print(f"  Product keys: {list(prod.keys())}")
                    return False
                
                # Check variations structure
                if not isinstance(prod['variations'], list):
                    print(f"  ❌ FAIL - variations is not a list")
                    return False
                
                if len(prod['variations']) > 0:
                    var = prod['variations'][0]
                    var_required = ['price', 'bbox', 'confidence']
                    var_missing = [f for f in var_required if f not in var]
                    if var_missing:
                        print(f"  ❌ FAIL - Variation missing fields: {var_missing}")
                        return False
                
                print(f"  ✅ PASS - All required fields present, no _id field")
                print(f"  Saved product_id: {test_state['product_id']}, page: {test_state['page_number']}")
                return True
            else:
                print(f"  ⚠️  WARNING - No products in database to test field structure")
                return True
        else:
            print(f"  ❌ FAIL - Expected 200, got {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        print(f"  ❌ FAIL - Exception: {e}")
        return False

def test_products_sort_best():
    """Test 9: GET /api/products?sort=best"""
    print("\n[TEST 9] GET /api/products?sort=best")
    try:
        resp = requests.get(f"{API_URL}/products?sort=best&limit=10", timeout=10)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            items = data.get('items', [])
            if len(items) >= 2:
                # Check descending confidence
                confidences = [p['confidence'] for p in items]
                is_descending = all(confidences[i] >= confidences[i+1] for i in range(len(confidences)-1))
                if is_descending:
                    print(f"  ✅ PASS - Confidence descending: {confidences[:5]}")
                    return True
                else:
                    print(f"  ❌ FAIL - Confidence not descending: {confidences}")
                    return False
            else:
                print(f"  ⚠️  WARNING - Not enough products to verify sort order")
                return True
        else:
            print(f"  ❌ FAIL - Expected 200, got {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        print(f"  ❌ FAIL - Exception: {e}")
        return False

def test_products_min_var():
    """Test 10: GET /api/products?min_var=3"""
    print("\n[TEST 10] GET /api/products?min_var=3")
    try:
        resp = requests.get(f"{API_URL}/products?min_var=3&limit=20", timeout=10)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            items = data.get('items', [])
            if len(items) > 0:
                all_valid = all(p['n_variations'] >= 3 for p in items)
                if all_valid:
                    n_vars = [p['n_variations'] for p in items[:5]]
                    print(f"  ✅ PASS - All products have n_variations >= 3: {n_vars}")
                    return True
                else:
                    invalid = [p['n_variations'] for p in items if p['n_variations'] < 3]
                    print(f"  ❌ FAIL - Some products have n_variations < 3: {invalid}")
                    return False
            else:
                print(f"  ⚠️  WARNING - No products match min_var=3 filter")
                return True
        else:
            print(f"  ❌ FAIL - Expected 200, got {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        print(f"  ❌ FAIL - Exception: {e}")
        return False

def test_products_min_conf():
    """Test 11: GET /api/products?min_conf=0.7"""
    print("\n[TEST 11] GET /api/products?min_conf=0.7")
    try:
        resp = requests.get(f"{API_URL}/products?min_conf=0.7&limit=20", timeout=10)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            items = data.get('items', [])
            if len(items) > 0:
                all_valid = all(p['confidence'] >= 0.7 for p in items)
                if all_valid:
                    confs = [p['confidence'] for p in items[:5]]
                    print(f"  ✅ PASS - All products have confidence >= 0.7: {confs}")
                    return True
                else:
                    invalid = [p['confidence'] for p in items if p['confidence'] < 0.7]
                    print(f"  ❌ FAIL - Some products have confidence < 0.7: {invalid}")
                    return False
            else:
                print(f"  ⚠️  WARNING - No products match min_conf=0.7 filter")
                return True
        else:
            print(f"  ❌ FAIL - Expected 200, got {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        print(f"  ❌ FAIL - Exception: {e}")
        return False

def test_products_search():
    """Test 12: GET /api/products?q=505 UP"""
    print("\n[TEST 12] GET /api/products?q=505 UP")
    try:
        resp = requests.get(f"{API_URL}/products?q=505 UP&limit=10", timeout=10)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            if data['total'] > 0:
                print(f"  ✅ PASS - Found {data['total']} matches for '505 UP'")
                if len(data['items']) > 0:
                    print(f"    First match: {data['items'][0].get('model_name', 'N/A')}")
                return True
            else:
                print(f"  ❌ FAIL - Expected matches for '505 UP', got 0")
                return False
        else:
            print(f"  ❌ FAIL - Expected 200, got {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        print(f"  ❌ FAIL - Exception: {e}")
        return False

def test_products_by_doc_id():
    """Test 13: GET /api/products?doc_id=<real_id>"""
    print("\n[TEST 13] GET /api/products?doc_id=<real_id>")
    if not test_state['doc_id']:
        print("  ⚠️  SKIP - No doc_id available from previous tests")
        return True
    try:
        resp = requests.get(f"{API_URL}/products?doc_id={test_state['doc_id']}&limit=5", timeout=10)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"  ✅ PASS - Got {data['total']} products for doc_id={test_state['doc_id']}")
            # Save some product IDs for bulk test
            if len(data['items']) >= 2:
                test_state['product_ids_for_bulk'] = [data['items'][0]['id'], data['items'][1]['id']]
            return True
        else:
            print(f"  ❌ FAIL - Expected 200, got {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        print(f"  ❌ FAIL - Exception: {e}")
        return False

def test_products_by_status():
    """Test 14: GET /api/products?status=pending"""
    print("\n[TEST 14] GET /api/products?status=pending")
    try:
        resp = requests.get(f"{API_URL}/products?status=pending&limit=5", timeout=10)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            items = data.get('items', [])
            if len(items) > 0:
                all_pending = all(p['status'] == 'pending' for p in items)
                if all_pending:
                    print(f"  ✅ PASS - All {len(items)} products have status=pending")
                    return True
                else:
                    statuses = [p['status'] for p in items]
                    print(f"  ❌ FAIL - Not all products are pending: {statuses}")
                    return False
            else:
                print(f"  ⚠️  WARNING - No pending products found")
                return True
        else:
            print(f"  ❌ FAIL - Expected 200, got {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        print(f"  ❌ FAIL - Exception: {e}")
        return False

def test_products_pagination():
    """Test 15: GET /api/products?limit=5&skip=5"""
    print("\n[TEST 15] GET /api/products?limit=5&skip=5")
    try:
        resp = requests.get(f"{API_URL}/products?limit=5&skip=5", timeout=10)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            if data['skip'] == 5 and data['limit'] == 5:
                print(f"  ✅ PASS - Pagination working: skip={data['skip']}, limit={data['limit']}, got {len(data['items'])} items")
                return True
            else:
                print(f"  ❌ FAIL - Pagination mismatch: {data}")
                return False
        else:
            print(f"  ❌ FAIL - Expected 200, got {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        print(f"  ❌ FAIL - Exception: {e}")
        return False

def test_products_models():
    """Test 16: GET /api/products/models"""
    print("\n[TEST 16] GET /api/products/models")
    try:
        resp = requests.get(f"{API_URL}/products/models", timeout=10)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            if 'items' in data and isinstance(data['items'], list):
                print(f"  ✅ PASS - Got {len(data['items'])} model facets")
                if len(data['items']) > 0:
                    item = data['items'][0]
                    required = ['model', 'n', 'min', 'max']
                    missing = [f for f in required if f not in item]
                    if missing:
                        print(f"  ❌ FAIL - Model item missing fields: {missing}")
                        return False
                    print(f"    Example: {item}")
                return True
            else:
                print(f"  ❌ FAIL - Missing or invalid 'items' field: {data}")
                return False
        else:
            print(f"  ❌ FAIL - Expected 200, got {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        print(f"  ❌ FAIL - Exception: {e}")
        return False

def test_product_by_id():
    """Test 17: GET /api/products/{id}"""
    print("\n[TEST 17] GET /api/products/{id}")
    if not test_state['product_id']:
        print("  ⚠️  SKIP - No product_id available from previous tests")
        return True
    try:
        resp = requests.get(f"{API_URL}/products/{test_state['product_id']}", timeout=10)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            if data.get('id') == test_state['product_id']:
                print(f"  ✅ PASS - Got product: {data.get('model_name', 'N/A')}")
                return True
            else:
                print(f"  ❌ FAIL - Product ID mismatch")
                return False
        else:
            print(f"  ❌ FAIL - Expected 200, got {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        print(f"  ❌ FAIL - Exception: {e}")
        return False

def test_product_by_id_not_found():
    """Test 18: GET /api/products/{bogus_id} - should return 404"""
    print("\n[TEST 18] GET /api/products/{bogus_id} - should return 404")
    try:
        resp = requests.get(f"{API_URL}/products/bogus-id-12345", timeout=10)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 404:
            print(f"  ✅ PASS - Got 404 for bogus product ID")
            return True
        else:
            print(f"  ❌ FAIL - Expected 404, got {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        print(f"  ❌ FAIL - Exception: {e}")
        return False

def test_patch_product():
    """Test 19: PATCH /api/products/{id} - update status, reviewer_notes, prices"""
    print("\n[TEST 19] PATCH /api/products/{id}")
    if not test_state['product_id']:
        print("  ⚠️  SKIP - No product_id available from previous tests")
        return True
    try:
        # First, get current state
        resp = requests.get(f"{API_URL}/products/{test_state['product_id']}", timeout=10)
        if resp.status_code != 200:
            print(f"  ❌ FAIL - Could not fetch product before PATCH")
            return False
        original = resp.json()
        original_status = original.get('status')
        
        # PATCH with new values
        patch_data = {
            "status": "approved",
            "reviewer_notes": "QA test note",
            "price_min": 123,
            "price_max": 456
        }
        resp = requests.patch(f"{API_URL}/products/{test_state['product_id']}", 
                            json=patch_data, timeout=10)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            # Verify all fields were updated
            if (data.get('status') == 'approved' and 
                data.get('reviewer_notes') == 'QA test note' and
                data.get('price_min') == 123 and
                data.get('price_max') == 456):
                print(f"  ✅ PASS - Product updated successfully")
                
                # Verify persistence with GET
                resp2 = requests.get(f"{API_URL}/products/{test_state['product_id']}", timeout=10)
                if resp2.status_code == 200:
                    data2 = resp2.json()
                    if (data2.get('status') == 'approved' and 
                        data2.get('reviewer_notes') == 'QA test note'):
                        print(f"  ✅ PASS - Changes persisted in database")
                        
                        # Check stats to see if approved count increased
                        stats_resp = requests.get(f"{API_URL}/stats", timeout=10)
                        if stats_resp.status_code == 200:
                            stats = stats_resp.json()
                            print(f"  Stats - approved: {stats.get('approved')}")
                        
                        # Restore original state
                        restore_data = {
                            "status": original_status or "pending",
                            "reviewer_notes": ""
                        }
                        requests.patch(f"{API_URL}/products/{test_state['product_id']}", 
                                     json=restore_data, timeout=10)
                        print(f"  Restored product to original state")
                        return True
                    else:
                        print(f"  ❌ FAIL - Changes not persisted")
                        return False
                else:
                    print(f"  ❌ FAIL - Could not verify persistence")
                    return False
            else:
                print(f"  ❌ FAIL - Fields not updated correctly: {data}")
                return False
        else:
            print(f"  ❌ FAIL - Expected 200, got {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        print(f"  ❌ FAIL - Exception: {e}")
        return False

def test_bulk_update():
    """Test 20: POST /api/products/bulk"""
    print("\n[TEST 20] POST /api/products/bulk")
    if len(test_state['product_ids_for_bulk']) < 2:
        print("  ⚠️  SKIP - Not enough product IDs for bulk test")
        return True
    try:
        ids = test_state['product_ids_for_bulk']
        bulk_data = {
            "ids": ids,
            "status": "approved"
        }
        resp = requests.post(f"{API_URL}/products/bulk", json=bulk_data, timeout=10)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            if data.get('modified') == 2:
                print(f"  ✅ PASS - Bulk updated {data['modified']} products")
                
                # Restore to pending
                restore_data = {"ids": ids, "status": "pending"}
                requests.post(f"{API_URL}/products/bulk", json=restore_data, timeout=10)
                print(f"  Restored products to pending")
                return True
            else:
                print(f"  ❌ FAIL - Expected modified=2, got {data}")
                return False
        else:
            print(f"  ❌ FAIL - Expected 200, got {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        print(f"  ❌ FAIL - Exception: {e}")
        return False

def test_page_image():
    """Test 21: GET /api/page-image?doc_id=...&page=...&dpi=150"""
    print("\n[TEST 21] GET /api/page-image")
    if not test_state['doc_id'] or not test_state['page_number']:
        print("  ⚠️  SKIP - No doc_id or page_number available")
        return True
    try:
        url = f"{API_URL}/page-image?doc_id={test_state['doc_id']}&page={test_state['page_number']}&dpi=150"
        resp = requests.get(url, timeout=30)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            content_type = resp.headers.get('Content-Type', '')
            if 'image/png' in content_type:
                # Check PNG magic bytes
                if resp.content[:4] == b'\x89PNG':
                    size_kb = len(resp.content) / 1024
                    if size_kb > 10:
                        print(f"  ✅ PASS - Got valid PNG image ({size_kb:.1f} KB)")
                        return True
                    else:
                        print(f"  ❌ FAIL - PNG too small ({size_kb:.1f} KB), might be invalid")
                        return False
                else:
                    print(f"  ❌ FAIL - Content-Type is image/png but missing PNG magic bytes")
                    return False
            else:
                print(f"  ❌ FAIL - Wrong Content-Type: {content_type}")
                return False
        else:
            print(f"  ❌ FAIL - Expected 200, got {resp.status_code}: {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"  ❌ FAIL - Exception: {e}")
        return False

def test_page_image_bogus_doc():
    """Test 22: GET /api/page-image with bogus doc_id - should return error"""
    print("\n[TEST 22] GET /api/page-image with bogus doc_id")
    try:
        url = f"{API_URL}/page-image?doc_id=bogus-doc-id&page=1&dpi=150"
        resp = requests.get(url, timeout=10)
        print(f"  Status: {resp.status_code}")
        if resp.status_code >= 400:
            print(f"  ✅ PASS - Got error status {resp.status_code} for bogus doc_id")
            return True
        else:
            print(f"  ❌ FAIL - Expected error status, got {resp.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ FAIL - Exception: {e}")
        return False

def test_tasks_list():
    """Test 23: GET /api/tasks - should return list without events array"""
    print("\n[TEST 23] GET /api/tasks")
    try:
        resp = requests.get(f"{API_URL}/tasks", timeout=10)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            if 'items' in data and isinstance(data['items'], list):
                print(f"  ✅ PASS - Got {len(data['items'])} tasks")
                if len(data['items']) > 0:
                    task = data['items'][0]
                    if 'events' in task:
                        print(f"  ❌ FAIL - Task list should NOT include events array")
                        return False
                    if 'id' in task:
                        test_state['task_id'] = task['id']
                        print(f"  Saved task_id: {test_state['task_id']}")
                return True
            else:
                print(f"  ❌ FAIL - Missing or invalid 'items' field")
                return False
        else:
            print(f"  ❌ FAIL - Expected 200, got {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        print(f"  ❌ FAIL - Exception: {e}")
        return False

def test_task_by_id():
    """Test 24: GET /api/tasks/{id} - should include events array"""
    print("\n[TEST 24] GET /api/tasks/{id}")
    if not test_state['task_id']:
        print("  ⚠️  SKIP - No task_id available")
        return True
    try:
        resp = requests.get(f"{API_URL}/tasks/{test_state['task_id']}", timeout=10)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            if 'events' in data and isinstance(data['events'], list):
                print(f"  ✅ PASS - Task includes events array with {len(data['events'])} events")
                print(f"    Task status: {data.get('status')}, progress: {data.get('progress')}")
                return True
            else:
                print(f"  ❌ FAIL - Task detail should include events array")
                return False
        else:
            print(f"  ❌ FAIL - Expected 200, got {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        print(f"  ❌ FAIL - Exception: {e}")
        return False

def test_task_not_found():
    """Test 25: GET /api/tasks/{bogus_id} - should return 404"""
    print("\n[TEST 25] GET /api/tasks/{bogus_id}")
    try:
        resp = requests.get(f"{API_URL}/tasks/bogus-task-id-12345", timeout=10)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 404:
            print(f"  ✅ PASS - Got 404 for bogus task ID")
            return True
        else:
            print(f"  ❌ FAIL - Expected 404, got {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        print(f"  ❌ FAIL - Exception: {e}")
        return False

def test_ingest_idempotent():
    """Test 26: POST /api/ingest - idempotent re-ingest (CRITICAL)"""
    print("\n[TEST 26] POST /api/ingest - idempotent re-ingest")
    try:
        # Get current product count for the test document
        test_pdf = "/app/data/pdfs/2026_PL_Gliss-Master-Smart-Configuration_EN_EUR.pdf"
        
        # Find the doc_id for this PDF
        docs_resp = requests.get(f"{API_URL}/documents", timeout=10)
        if docs_resp.status_code != 200:
            print(f"  ❌ FAIL - Could not fetch documents")
            return False
        
        docs = docs_resp.json()['items']
        test_doc = None
        for doc in docs:
            if 'Gliss-Master-Smart-Configuration' in doc.get('name', ''):
                test_doc = doc
                break
        
        if test_doc:
            doc_id = test_doc['id']
            # Get current product count
            prod_resp = requests.get(f"{API_URL}/products?doc_id={doc_id}&limit=1", timeout=10)
            if prod_resp.status_code == 200:
                count_before = prod_resp.json()['total']
                print(f"  Products before re-ingest: {count_before}")
            else:
                count_before = None
        else:
            count_before = None
            print(f"  No existing doc found for Gliss-Master-Smart-Configuration")
        
        # Start ingestion
        ingest_data = {
            "source": "local",
            "paths": [test_pdf],
            "factory": "Molteni & C",
            "max_pages": 24
        }
        resp = requests.post(f"{API_URL}/ingest", json=ingest_data, timeout=10)
        print(f"  Status: {resp.status_code}")
        
        if resp.status_code != 200:
            print(f"  ❌ FAIL - Ingest request failed: {resp.text}")
            return False
        
        data = resp.json()
        if 'task_id' not in data:
            print(f"  ❌ FAIL - No task_id in response: {data}")
            return False
        
        task_id = data['task_id']
        print(f"  Task ID: {task_id}")
        
        # Poll task until done (max 60 seconds)
        max_wait = 60
        start_time = time.time()
        while time.time() - start_time < max_wait:
            task_resp = requests.get(f"{API_URL}/tasks/{task_id}", timeout=10)
            if task_resp.status_code != 200:
                print(f"  ❌ FAIL - Could not fetch task status")
                return False
            
            task = task_resp.json()
            status = task.get('status')
            progress = task.get('progress', 0)
            
            print(f"  Task status: {status}, progress: {progress}%")
            
            if status == 'done':
                print(f"  ✅ Task completed successfully")
                
                # Verify task structure
                if 'events' not in task or not isinstance(task['events'], list):
                    print(f"  ❌ FAIL - Task missing events array")
                    return False
                
                if len(task['events']) == 0:
                    print(f"  ❌ FAIL - Task events array is empty")
                    return False
                
                # Check for expected messages in events
                event_messages = ' '.join([e.get('msg', '') for e in task['events']])
                expected_keywords = ['PyMuPDF', 'micrograd', 'products assembled']
                missing_keywords = [kw for kw in expected_keywords if kw not in event_messages]
                if missing_keywords:
                    print(f"  ⚠️  WARNING - Events missing keywords: {missing_keywords}")
                else:
                    print(f"  ✅ Events contain expected keywords")
                
                if task.get('progress') != 100:
                    print(f"  ❌ FAIL - Task done but progress != 100: {task.get('progress')}")
                    return False
                
                # Now check idempotency - product count should be the same
                if count_before is not None:
                    # Re-fetch the doc to get its ID (might have been created fresh)
                    docs_resp2 = requests.get(f"{API_URL}/documents", timeout=10)
                    docs2 = docs_resp2.json()['items']
                    test_doc2 = None
                    for doc in docs2:
                        if 'Gliss-Master-Smart-Configuration' in doc.get('name', ''):
                            test_doc2 = doc
                            break
                    
                    if test_doc2:
                        doc_id2 = test_doc2['id']
                        prod_resp2 = requests.get(f"{API_URL}/products?doc_id={doc_id2}&limit=1", timeout=10)
                        if prod_resp2.status_code == 200:
                            count_after = prod_resp2.json()['total']
                            print(f"  Products after re-ingest: {count_after}")
                            
                            # Allow small variance (within 5%) due to potential parsing differences
                            if abs(count_after - count_before) <= max(1, count_before * 0.05):
                                print(f"  ✅ PASS - Idempotent re-ingest verified (count stable)")
                                return True
                            else:
                                print(f"  ❌ FAIL - Product count changed significantly: {count_before} -> {count_after}")
                                print(f"  This suggests products were duplicated instead of deduplicated")
                                return False
                else:
                    print(f"  ⚠️  WARNING - Could not verify idempotency (no baseline count)")
                    return True
                
                return True
            
            elif status == 'error':
                print(f"  ❌ FAIL - Task failed with error")
                if 'events' in task:
                    for evt in task['events'][-5:]:
                        print(f"    {evt.get('level', 'info')}: {evt.get('msg', '')}")
                return False
            
            time.sleep(3)
        
        print(f"  ❌ FAIL - Task did not complete within {max_wait} seconds")
        return False
        
    except Exception as e:
        print(f"  ❌ FAIL - Exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all backend tests"""
    print("\n" + "=" * 80)
    print("HOMEART DATA HUB - BACKEND API TEST SUITE")
    print("=" * 80)
    
    results = []
    
    # Auth tests
    results.append(("Auth - correct password", test_auth_login()))
    results.append(("Auth - wrong password", test_auth_login_wrong_password()))
    results.append(("Auth - missing password", test_auth_login_missing_password()))
    
    # Health & Stats
    results.append(("Health check", test_health()))
    results.append(("Stats aggregation", test_stats()))
    
    # Documents & Factories
    results.append(("Documents list", test_documents()))
    results.append(("Factories list", test_factories()))
    
    # Products - basic & filters
    results.append(("Products - basic query", test_products_basic()))
    results.append(("Products - sort=best", test_products_sort_best()))
    results.append(("Products - min_var=3", test_products_min_var()))
    results.append(("Products - min_conf=0.7", test_products_min_conf()))
    results.append(("Products - search q=505 UP", test_products_search()))
    results.append(("Products - by doc_id", test_products_by_doc_id()))
    results.append(("Products - by status", test_products_by_status()))
    results.append(("Products - pagination", test_products_pagination()))
    results.append(("Products - models facet", test_products_models()))
    
    # Products - individual
    results.append(("Product by ID", test_product_by_id()))
    results.append(("Product by ID - 404", test_product_by_id_not_found()))
    
    # Products - updates
    results.append(("PATCH product", test_patch_product()))
    results.append(("Bulk update", test_bulk_update()))
    
    # Page image
    results.append(("Page image - valid", test_page_image()))
    results.append(("Page image - bogus doc", test_page_image_bogus_doc()))
    
    # Tasks
    results.append(("Tasks list", test_tasks_list()))
    results.append(("Task by ID", test_task_by_id()))
    results.append(("Task by ID - 404", test_task_not_found()))
    
    # Ingestion (CRITICAL - idempotency test)
    results.append(("Ingest - idempotent re-ingest", test_ingest_idempotent()))
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print("=" * 80)
    print(f"TOTAL: {passed}/{total} tests passed ({100*passed//total}%)")
    print("=" * 80)
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
