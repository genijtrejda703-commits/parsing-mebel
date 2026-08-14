#!/usr/bin/env python3
"""Backend API test suite for Molteni Data Hub - Position->Variant schema.

Tests backend endpoints for:
1. Auth (master password)
2. Stats (positions, variant_prices counts)
3. Positions API (list, detail, facets, PATCH with cascade)
4. Inventory (GET with filters, POST local only)
5. Coverage aggregation
6. Excel exports (positions, inventory)
7. Search graceful degradation
8. Tasks
"""
import io
import os
import sys
import time
import requests

# Use internal localhost URL for testing
BASE_URL = "http://localhost:3000"
API_BASE = f"{BASE_URL}/api"
MASTER_PASSWORD = "homeart-molteni-2026"
TIMEOUT = 60


def test_auth():
    """Test 1: Auth login with master password"""
    print("\n" + "="*80)
    print("TEST 1: Auth login (POST /api/auth/login)")
    print("="*80)
    
    results = {"passed": 0, "failed": 0, "tests": []}
    
    # Test 1.1: Valid password
    try:
        print("\n[1.1] Testing valid password...")
        url = f"{API_BASE}/auth/login"
        payload = {"password": MASTER_PASSWORD}
        resp = requests.post(url, json=payload, timeout=TIMEOUT)
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        print(f"   Response keys: {data.keys()}")
        
        assert "token" in data, "Missing 'token' in response"
        assert "user" in data, "Missing 'user' in response"
        assert data["token"], "Token is empty"
        assert data["user"], "User is empty"
        
        print(f"   ✅ PASSED - Valid password returns token and user")
        results["passed"] += 1
        results["tests"].append(("1.1: valid password", True, None))
    except Exception as e:
        print(f"   ❌ FAILED - {e}")
        results["failed"] += 1
        results["tests"].append(("1.1: valid password", False, str(e)))
    
    # Test 1.2: Wrong password
    try:
        print("\n[1.2] Testing wrong password...")
        url = f"{API_BASE}/auth/login"
        payload = {"password": "wrong-password"}
        resp = requests.post(url, json=payload, timeout=TIMEOUT)
        
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        
        data = resp.json()
        assert "error" in data, "Missing 'error' in response"
        
        print(f"   ✅ PASSED - Wrong password returns 401")
        results["passed"] += 1
        results["tests"].append(("1.2: wrong password", True, None))
    except Exception as e:
        print(f"   ❌ FAILED - {e}")
        results["failed"] += 1
        results["tests"].append(("1.2: wrong password", False, str(e)))
    
    # Test 1.3: Empty password
    try:
        print("\n[1.3] Testing empty password...")
        url = f"{API_BASE}/auth/login"
        payload = {"password": ""}
        resp = requests.post(url, json=payload, timeout=TIMEOUT)
        
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        
        print(f"   ✅ PASSED - Empty password returns 401")
        results["passed"] += 1
        results["tests"].append(("1.3: empty password", True, None))
    except Exception as e:
        print(f"   ❌ FAILED - {e}")
        results["failed"] += 1
        results["tests"].append(("1.3: empty password", False, str(e)))
    
    print(f"\n{'='*80}")
    print(f"TEST 1 SUMMARY: {results['passed']}/3 passed, {results['failed']}/3 failed")
    print(f"{'='*80}")
    
    return results


def test_stats():
    """Test 2: Stats endpoint"""
    print("\n" + "="*80)
    print("TEST 2: Stats (GET /api/stats)")
    print("="*80)
    
    results = {"passed": 0, "failed": 0, "tests": []}
    
    try:
        print("\n[2.1] Testing GET /api/stats...")
        url = f"{API_BASE}/stats"
        resp = requests.get(url, timeout=TIMEOUT)
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        print(f"   Response keys: {data.keys()}")
        
        # Check required fields
        required_fields = [
            "positions", "positions_pending", "positions_approved", 
            "positions_flagged", "variant_prices", "positions_avg_confidence",
            "documents"
        ]
        for field in required_fields:
            assert field in data, f"Missing field '{field}'"
        
        # Check expected counts
        positions = data["positions"]
        variant_prices = data["variant_prices"]
        documents = data["documents"]
        
        print(f"   positions: {positions} (expected 600-660)")
        print(f"   variant_prices: {variant_prices} (expected 60000-70000)")
        print(f"   documents: {documents} (expected 14)")
        
        assert 600 <= positions <= 660, f"positions out of range: {positions}"
        assert 60000 <= variant_prices <= 70000, f"variant_prices out of range: {variant_prices}"
        assert documents == 14, f"documents should be 14, got {documents}"
        
        print(f"   ✅ PASSED - Stats correct")
        results["passed"] += 1
        results["tests"].append(("2.1: stats counts", True, None))
    except Exception as e:
        print(f"   ❌ FAILED - {e}")
        results["failed"] += 1
        results["tests"].append(("2.1: stats counts", False, str(e)))
    
    print(f"\n{'='*80}")
    print(f"TEST 2 SUMMARY: {results['passed']}/1 passed, {results['failed']}/1 failed")
    print(f"{'='*80}")
    
    return results


def test_positions():
    """Test 3: Positions API"""
    print("\n" + "="*80)
    print("TEST 3: Positions API")
    print("="*80)
    
    results = {"passed": 0, "failed": 0, "tests": []}
    
    # Test 3.1: GET /api/positions with limit and sort
    try:
        print("\n[3.1] Testing GET /api/positions?limit=5&sort=variants...")
        url = f"{API_BASE}/positions?limit=5&sort=variants"
        resp = requests.get(url, timeout=TIMEOUT)
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        assert "items" in data, "Missing 'items'"
        assert "total" in data, "Missing 'total'"
        
        total = data["total"]
        items = data["items"]
        
        print(f"   total: {total} (expected ~628)")
        print(f"   items count: {len(items)}")
        
        assert 600 <= total <= 660, f"total out of range: {total}"
        assert len(items) == 5, f"Expected 5 items, got {len(items)}"
        
        # Check required fields in items
        for item in items:
            assert "name" in item, "Missing 'name'"
            assert "n_variants" in item, "Missing 'n_variants'"
            assert "price_min" in item, "Missing 'price_min'"
            assert "price_max" in item, "Missing 'price_max'"
            assert "avg_confidence" in item, "Missing 'avg_confidence'"
            assert "status" in item, "Missing 'status'"
            assert "categories" in item, "Missing 'categories'"
        
        print(f"   ✅ PASSED - Positions list correct")
        results["passed"] += 1
        results["tests"].append(("3.1: positions list", True, None))
    except Exception as e:
        print(f"   ❌ FAILED - {e}")
        results["failed"] += 1
        results["tests"].append(("3.1: positions list", False, str(e)))
    
    # Test 3.2: Search for "505 UP System"
    position_505_id = None
    try:
        print("\n[3.2] Testing search for '505 UP System'...")
        url = f"{API_BASE}/positions?q=505%20UP%20System"
        resp = requests.get(url, timeout=TIMEOUT)
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        items = data["items"]
        
        # Find exact match for "505 UP System"
        pos_505 = None
        for item in items:
            if item["name"] == "505 UP System":
                pos_505 = item
                position_505_id = item["id"]
                break
        
        assert pos_505 is not None, "Could not find position '505 UP System'"
        
        n_variants = pos_505["n_variants"]
        print(f"   Found '505 UP System' with {n_variants} variants (expected 1000-1400)")
        
        assert 1000 <= n_variants <= 1400, f"n_variants out of range: {n_variants}"
        
        # Check that "505 UP Sideboard" is a SEPARATE position
        pos_sideboard = None
        for item in items:
            if item["name"] == "505 UP Sideboard":
                pos_sideboard = item
                break
        
        assert pos_sideboard is not None, "Could not find position '505 UP Sideboard'"
        assert pos_sideboard["id"] != pos_505["id"], "505 UP System and Sideboard should be separate positions"
        
        print(f"   ✅ PASSED - '505 UP System' and '505 UP Sideboard' are separate positions")
        results["passed"] += 1
        results["tests"].append(("3.2: 505 UP System search", True, None))
    except Exception as e:
        print(f"   ❌ FAILED - {e}")
        results["failed"] += 1
        results["tests"].append(("3.2: 505 UP System search", False, str(e)))
    
    # Test 3.3: GET /api/positions/{id} for 505 UP System
    try:
        print("\n[3.3] Testing GET /api/positions/{id} for 505 UP System...")
        
        if position_505_id is None:
            raise Exception("position_505_id not found in previous test")
        
        url = f"{API_BASE}/positions/{position_505_id}"
        resp = requests.get(url, timeout=TIMEOUT)
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        assert "position" in data, "Missing 'position'"
        assert "variants" in data, "Missing 'variants'"
        assert "pages" in data, "Missing 'pages'"
        assert "documents" in data, "Missing 'documents'"
        
        variants = data["variants"]
        pages = data["pages"]
        
        print(f"   variants count: {len(variants)}")
        print(f"   pages count: {len(pages)}")
        
        # Check variant structure
        if len(variants) > 0:
            v = variants[0]
            required_variant_fields = [
                "variant_code", "dimension", "finish", "price",
                "bbox", "bbox_row_label", "page",
                "above_chain_raw", "left_raw"
            ]
            for field in required_variant_fields:
                assert field in v, f"Missing field '{field}' in variant"
            
            print(f"   Sample variant: code={v.get('variant_code')}, price={v.get('price')}")
        
        # Check pages structure
        if len(pages) > 0:
            p = pages[0]
            assert "doc_id" in p, "Missing 'doc_id' in page"
            assert "page" in p, "Missing 'page' in page"
            assert "page_width" in p, "Missing 'page_width' in page"
            assert "page_height" in p, "Missing 'page_height' in page"
            assert "variants" in p, "Missing 'variants' in page"
        
        print(f"   ✅ PASSED - Position detail correct with raw geometry chains")
        results["passed"] += 1
        results["tests"].append(("3.3: position detail", True, None))
    except Exception as e:
        print(f"   ❌ FAILED - {e}")
        results["failed"] += 1
        results["tests"].append(("3.3: position detail", False, str(e)))
    
    # Test 3.4: GET /api/positions/facets
    try:
        print("\n[3.4] Testing GET /api/positions/facets...")
        url = f"{API_BASE}/positions/facets"
        resp = requests.get(url, timeout=TIMEOUT)
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        assert "categories" in data, "Missing 'categories'"
        assert "documents" in data, "Missing 'documents'"
        
        categories = data["categories"]
        documents = data["documents"]
        
        print(f"   categories count: {len(categories)}")
        print(f"   documents count: {len(documents)}")
        
        assert len(categories) > 0, "categories should not be empty"
        assert len(documents) > 0, "documents should not be empty"
        
        print(f"   ✅ PASSED - Facets correct")
        results["passed"] += 1
        results["tests"].append(("3.4: facets", True, None))
    except Exception as e:
        print(f"   ❌ FAILED - {e}")
        results["failed"] += 1
        results["tests"].append(("3.4: facets", False, str(e)))
    
    # Test 3.5: PATCH /api/positions/{id} with cascade_status
    try:
        print("\n[3.5] Testing PATCH /api/positions/{id} with cascade_status...")
        
        if position_505_id is None:
            raise Exception("position_505_id not found in previous test")
        
        # First, approve the position
        url = f"{API_BASE}/positions/{position_505_id}"
        payload = {
            "status": "approved",
            "reviewer_notes": "qa test",
            "cascade_status": True
        }
        resp = requests.patch(url, json=payload, timeout=TIMEOUT)
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        assert data["status"] == "approved", f"Status should be 'approved', got {data['status']}"
        
        # Get the position again to confirm persisted
        resp2 = requests.get(url, timeout=TIMEOUT)
        data2 = resp2.json()
        assert data2["position"]["status"] == "approved", "Status not persisted"
        
        # Check that at least one variant has status approved
        variants = data2["variants"]
        approved_variants = [v for v in variants if v.get("status") == "approved"]
        assert len(approved_variants) > 0, "No variants have status 'approved' after cascade"
        
        print(f"   Approved {len(approved_variants)} variants via cascade")
        
        # Restore to pending
        payload2 = {
            "status": "pending",
            "cascade_status": True
        }
        resp3 = requests.patch(url, json=payload2, timeout=TIMEOUT)
        assert resp3.status_code == 200, "Failed to restore to pending"
        
        print(f"   ✅ PASSED - PATCH with cascade_status works")
        results["passed"] += 1
        results["tests"].append(("3.5: PATCH cascade", True, None))
    except Exception as e:
        print(f"   ❌ FAILED - {e}")
        results["failed"] += 1
        results["tests"].append(("3.5: PATCH cascade", False, str(e)))
    
    print(f"\n{'='*80}")
    print(f"TEST 3 SUMMARY: {results['passed']}/5 passed, {results['failed']}/5 failed")
    print(f"{'='*80}")
    
    return results


def test_inventory():
    """Test 4: Inventory API"""
    print("\n" + "="*80)
    print("TEST 4: Inventory API")
    print("="*80)
    
    results = {"passed": 0, "failed": 0, "tests": []}
    
    # Test 4.1: GET /api/inventory
    try:
        print("\n[4.1] Testing GET /api/inventory...")
        url = f"{API_BASE}/inventory"
        resp = requests.get(url, timeout=TIMEOUT)
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        assert "items" in data, "Missing 'items'"
        assert "total" in data, "Missing 'total'"
        assert "by_type" in data, "Missing 'by_type'"
        assert "current_listini" in data, "Missing 'current_listini'"
        assert "ingested" in data, "Missing 'ingested'"
        
        print(f"   total: {data['total']}")
        print(f"   current_listini: {data['current_listini']}")
        print(f"   ingested: {data['ingested']}")
        
        print(f"   ✅ PASSED - Inventory basic query works")
        results["passed"] += 1
        results["tests"].append(("4.1: inventory basic", True, None))
    except Exception as e:
        print(f"   ❌ FAILED - {e}")
        results["failed"] += 1
        results["tests"].append(("4.1: inventory basic", False, str(e)))
    
    # Test 4.2: GET /api/inventory?source=dropbox
    try:
        print("\n[4.2] Testing GET /api/inventory?source=dropbox...")
        url = f"{API_BASE}/inventory?source=dropbox"
        resp = requests.get(url, timeout=TIMEOUT)
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        total = data["total"]
        current_listini = data["current_listini"]
        
        print(f"   total: {total} (expected ~397)")
        print(f"   current_listini: {current_listini} (expected 25-40)")
        
        assert 350 <= total <= 450, f"total out of range: {total}"
        assert 25 <= current_listini <= 40, f"current_listini out of range: {current_listini}"
        
        print(f"   ✅ PASSED - Dropbox inventory correct")
        results["passed"] += 1
        results["tests"].append(("4.2: inventory dropbox", True, None))
    except Exception as e:
        print(f"   ❌ FAILED - {e}")
        results["failed"] += 1
        results["tests"].append(("4.2: inventory dropbox", False, str(e)))
    
    # Test 4.3: GET /api/inventory?current=true
    try:
        print("\n[4.3] Testing GET /api/inventory?current=true...")
        url = f"{API_BASE}/inventory?current=true"
        resp = requests.get(url, timeout=TIMEOUT)
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        items = data["items"]
        
        # Check all items have is_current_listino=true
        for item in items:
            assert item.get("is_current_listino") == True, \
                f"Item {item.get('name')} has is_current_listino={item.get('is_current_listino')}"
        
        print(f"   All {len(items)} items have is_current_listino=true")
        print(f"   ✅ PASSED - Current filter works")
        results["passed"] += 1
        results["tests"].append(("4.3: inventory current", True, None))
    except Exception as e:
        print(f"   ❌ FAILED - {e}")
        results["failed"] += 1
        results["tests"].append(("4.3: inventory current", False, str(e)))
    
    # Test 4.4: POST /api/inventory with source=local
    try:
        print("\n[4.4] Testing POST /api/inventory with source=local...")
        url = f"{API_BASE}/inventory"
        payload = {"source": "local"}
        resp = requests.post(url, json=payload, timeout=TIMEOUT)
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        assert "task_id" in data, "Missing 'task_id'"
        
        task_id = data["task_id"]
        print(f"   task_id: {task_id}")
        
        # Poll task status
        max_polls = 60
        for i in range(max_polls):
            task_url = f"{API_BASE}/tasks/{task_id}"
            task_resp = requests.get(task_url, timeout=TIMEOUT)
            
            if task_resp.status_code == 200:
                task_data = task_resp.json()
                status = task_data.get("status")
                print(f"   Poll {i+1}: status={status}")
                
                if status == "done":
                    print(f"   ✅ PASSED - Inventory task completed")
                    results["passed"] += 1
                    results["tests"].append(("4.4: inventory POST local", True, None))
                    break
                elif status == "error":
                    raise Exception(f"Task failed: {task_data.get('error')}")
            
            time.sleep(1)
        else:
            raise Exception(f"Task did not complete in {max_polls} seconds")
    except Exception as e:
        print(f"   ❌ FAILED - {e}")
        results["failed"] += 1
        results["tests"].append(("4.4: inventory POST local", False, str(e)))
    
    print(f"\n{'='*80}")
    print(f"TEST 4 SUMMARY: {results['passed']}/4 passed, {results['failed']}/4 failed")
    print(f"{'='*80}")
    
    return results


def test_coverage():
    """Test 5: Coverage API"""
    print("\n" + "="*80)
    print("TEST 5: Coverage API")
    print("="*80)
    
    results = {"passed": 0, "failed": 0, "tests": []}
    
    try:
        print("\n[5.1] Testing GET /api/coverage...")
        url = f"{API_BASE}/coverage"
        resp = requests.get(url, timeout=TIMEOUT)
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        assert "documents" in data, "Missing 'documents'"
        assert "totals" in data, "Missing 'totals'"
        assert "files_parsed" in data, "Missing 'files_parsed'"
        assert "files_classified_only" in data, "Missing 'files_classified_only'"
        assert "classified_only" in data, "Missing 'classified_only'"
        
        totals = data["totals"]
        assert "pages_total" in totals, "Missing 'pages_total'"
        assert "pages_with_matrix" in totals, "Missing 'pages_with_matrix'"
        assert "pages_parsed" in totals, "Missing 'pages_parsed'"
        assert "pages_skipped" in totals, "Missing 'pages_skipped'"
        assert "positions" in totals, "Missing 'positions'"
        assert "variant_prices" in totals, "Missing 'variant_prices'"
        
        files_parsed = data["files_parsed"]
        print(f"   files_parsed: {files_parsed} (expected 14)")
        
        assert files_parsed == 14, f"files_parsed should be 14, got {files_parsed}"
        
        print(f"   ✅ PASSED - Coverage correct")
        results["passed"] += 1
        results["tests"].append(("5.1: coverage", True, None))
    except Exception as e:
        print(f"   ❌ FAILED - {e}")
        results["failed"] += 1
        results["tests"].append(("5.1: coverage", False, str(e)))
    
    print(f"\n{'='*80}")
    print(f"TEST 5 SUMMARY: {results['passed']}/1 passed, {results['failed']}/1 failed")
    print(f"{'='*80}")
    
    return results


def test_exports():
    """Test 6: Excel exports"""
    print("\n" + "="*80)
    print("TEST 6: Excel exports")
    print("="*80)
    
    results = {"passed": 0, "failed": 0, "tests": []}
    
    # Test 6.1: GET /api/export-positions?status=all
    try:
        print("\n[6.1] Testing GET /api/export-positions?status=all...")
        url = f"{API_BASE}/export-positions?status=all"
        resp = requests.get(url, timeout=TIMEOUT)
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        # Check Content-Type
        ct = resp.headers.get("Content-Type", "")
        assert "spreadsheetml.sheet" in ct, f"Wrong Content-Type: {ct}"
        
        # Check body is valid xlsx (starts with PK)
        body = resp.content
        assert len(body) > 5000, f"Body too small: {len(body)} bytes"
        assert body[:2] == b'PK', f"Missing ZIP magic bytes, got: {body[:4].hex()}"
        
        print(f"   Body size: {len(body)} bytes")
        
        # Try to open with openpyxl to check sheets
        try:
            from openpyxl import load_workbook
            wb = load_workbook(io.BytesIO(body))
            sheet_names = wb.sheetnames
            print(f"   Sheet names: {sheet_names}")
            
            # Check for expected Cyrillic sheet names
            expected_sheets = ["Позиции", "Цены", "Сводка"]
            for sheet in expected_sheets:
                assert sheet in sheet_names, f"Missing sheet '{sheet}'"
            
            print(f"   ✅ PASSED - Export positions xlsx correct with Cyrillic sheets")
            results["passed"] += 1
            results["tests"].append(("6.1: export positions", True, None))
        except ImportError:
            print(f"   ⚠️  openpyxl not available, skipping sheet validation")
            print(f"   ✅ PASSED - Export positions xlsx valid (basic check)")
            results["passed"] += 1
            results["tests"].append(("6.1: export positions", True, None))
    except Exception as e:
        print(f"   ❌ FAILED - {e}")
        results["failed"] += 1
        results["tests"].append(("6.1: export positions", False, str(e)))
    
    # Test 6.2: GET /api/inventory/export
    try:
        print("\n[6.2] Testing GET /api/inventory/export...")
        url = f"{API_BASE}/inventory/export"
        resp = requests.get(url, timeout=TIMEOUT)
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        # Check Content-Type
        ct = resp.headers.get("Content-Type", "")
        assert "spreadsheetml.sheet" in ct, f"Wrong Content-Type: {ct}"
        
        # Check body is valid xlsx
        body = resp.content
        assert len(body) > 5000, f"Body too small: {len(body)} bytes"
        assert body[:2] == b'PK', f"Missing ZIP magic bytes"
        
        print(f"   Body size: {len(body)} bytes")
        
        # Try to open with openpyxl to check sheets
        try:
            from openpyxl import load_workbook
            wb = load_workbook(io.BytesIO(body))
            sheet_names = wb.sheetnames
            print(f"   Sheet names: {sheet_names}")
            
            # Check for expected Cyrillic sheet names
            expected_sheets = ["Инвентаризация", "Покрытие"]
            for sheet in expected_sheets:
                assert sheet in sheet_names, f"Missing sheet '{sheet}'"
            
            print(f"   ✅ PASSED - Export inventory xlsx correct with Cyrillic sheets")
            results["passed"] += 1
            results["tests"].append(("6.2: export inventory", True, None))
        except ImportError:
            print(f"   ⚠️  openpyxl not available, skipping sheet validation")
            print(f"   ✅ PASSED - Export inventory xlsx valid (basic check)")
            results["passed"] += 1
            results["tests"].append(("6.2: export inventory", True, None))
    except Exception as e:
        print(f"   ❌ FAILED - {e}")
        results["failed"] += 1
        results["tests"].append(("6.2: export inventory", False, str(e)))
    
    print(f"\n{'='*80}")
    print(f"TEST 6 SUMMARY: {results['passed']}/2 passed, {results['failed']}/2 failed")
    print(f"{'='*80}")
    
    return results


def test_search():
    """Test 7: Search graceful degradation"""
    print("\n" + "="*80)
    print("TEST 7: Search graceful degradation")
    print("="*80)
    
    results = {"passed": 0, "failed": 0, "tests": []}
    
    try:
        print("\n[7.1] Testing POST /api/search (no embeddings)...")
        url = f"{API_BASE}/search"
        payload = {"q": "505 up system"}
        resp = requests.post(url, json=payload, timeout=TIMEOUT)
        
        # MUST be 200, not 500
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        assert "results" in data, "Missing 'results'"
        assert "note" in data, "Missing 'note'"
        
        results_list = data["results"]
        note = data["note"]
        
        print(f"   results: {results_list}")
        print(f"   note: {note}")
        
        # Should return empty results with note about no embeddings
        assert results_list == [], f"Expected empty results, got {len(results_list)}"
        assert "no embeddings" in note.lower() or "not built" in note.lower(), \
            f"Note should mention no embeddings: {note}"
        
        print(f"   ✅ PASSED - Search returns 200 with graceful degradation")
        results["passed"] += 1
        results["tests"].append(("7.1: search graceful", True, None))
    except Exception as e:
        print(f"   ❌ FAILED - {e}")
        results["failed"] += 1
        results["tests"].append(("7.1: search graceful", False, str(e)))
    
    print(f"\n{'='*80}")
    print(f"TEST 7 SUMMARY: {results['passed']}/1 passed, {results['failed']}/1 failed")
    print(f"{'='*80}")
    
    return results


def test_tasks():
    """Test 8: Tasks endpoint"""
    print("\n" + "="*80)
    print("TEST 8: Tasks endpoint")
    print("="*80)
    
    results = {"passed": 0, "failed": 0, "tests": []}
    
    try:
        print("\n[8.1] Testing GET /api/tasks...")
        url = f"{API_BASE}/tasks"
        resp = requests.get(url, timeout=TIMEOUT)
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        print(f"   Response type: {type(data)}")
        
        # Should be a list or dict with items
        if isinstance(data, list):
            print(f"   Tasks count: {len(data)}")
        elif isinstance(data, dict) and "items" in data:
            print(f"   Tasks count: {len(data['items'])}")
        else:
            print(f"   Response: {data}")
        
        print(f"   ✅ PASSED - Tasks endpoint works")
        results["passed"] += 1
        results["tests"].append(("8.1: tasks", True, None))
    except Exception as e:
        print(f"   ❌ FAILED - {e}")
        results["failed"] += 1
        results["tests"].append(("8.1: tasks", False, str(e)))
    
    print(f"\n{'='*80}")
    print(f"TEST 8 SUMMARY: {results['passed']}/1 passed, {results['failed']}/1 failed")
    print(f"{'='*80}")
    
    return results


def test_documents():
    """Test 9: Documents endpoint"""
    print("\n" + "="*80)
    print("TEST 9: Documents endpoint")
    print("="*80)
    
    results = {"passed": 0, "failed": 0, "tests": []}
    
    try:
        print("\n[9.1] Testing GET /api/documents...")
        url = f"{API_BASE}/documents"
        resp = requests.get(url, timeout=TIMEOUT)
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        print(f"   Response type: {type(data)}")
        
        # Should be a list or dict with items
        if isinstance(data, list):
            print(f"   Documents count: {len(data)}")
            assert len(data) > 0, "Documents list should not be empty"
        elif isinstance(data, dict) and "items" in data:
            print(f"   Documents count: {len(data['items'])}")
            assert len(data['items']) > 0, "Documents list should not be empty"
        
        print(f"   ✅ PASSED - Documents endpoint works")
        results["passed"] += 1
        results["tests"].append(("9.1: documents", True, None))
    except Exception as e:
        print(f"   ❌ FAILED - {e}")
        results["failed"] += 1
        results["tests"].append(("9.1: documents", False, str(e)))
    
    print(f"\n{'='*80}")
    print(f"TEST 9 SUMMARY: {results['passed']}/1 passed, {results['failed']}/1 failed")
    print(f"{'='*80}")
    
    return results


def main():
    """Run all backend tests"""
    print("\n" + "="*80)
    print("MOLTENI DATA HUB - BACKEND TEST SUITE")
    print("Position->Variant Schema")
    print("="*80)
    print(f"Backend URL: {API_BASE}")
    print(f"Timeout: {TIMEOUT}s")
    print("="*80)
    
    all_results = {
        "1_Auth": test_auth(),
        "2_Stats": test_stats(),
        "3_Positions": test_positions(),
        "4_Inventory": test_inventory(),
        "5_Coverage": test_coverage(),
        "6_Exports": test_exports(),
        "7_Search": test_search(),
        "8_Tasks": test_tasks(),
        "9_Documents": test_documents(),
    }
    
    # Summary
    print("\n" + "="*80)
    print("FINAL SUMMARY")
    print("="*80)
    
    total_passed = sum(r["passed"] for r in all_results.values())
    total_failed = sum(r["failed"] for r in all_results.values())
    total_tests = total_passed + total_failed
    
    for section, result in all_results.items():
        status = "✅ PASS" if result["failed"] == 0 else "❌ FAIL"
        print(f"  {section}: {result['passed']}/{result['passed'] + result['failed']} passed {status}")
    
    print(f"\n{'='*80}")
    print(f"OVERALL: {total_passed}/{total_tests} tests passed ({100*total_passed//total_tests if total_tests > 0 else 0}%)")
    print(f"{'='*80}")
    
    # Detailed failures
    if total_failed > 0:
        print("\n" + "="*80)
        print("FAILED TESTS DETAILS")
        print("="*80)
        for section, result in all_results.items():
            for test_name, passed, error in result["tests"]:
                if not passed:
                    print(f"\n❌ {section} - {test_name}")
                    print(f"   Error: {error}")
    
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
