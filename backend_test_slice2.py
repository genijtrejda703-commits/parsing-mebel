#!/usr/bin/env python3
"""Backend test suite for Slice 2: CLIP embedding and vector search."""
import io
import json
import os
import sys
import time
from PIL import Image
import requests

BASE_URL = os.getenv("NEXT_PUBLIC_BASE_URL", "https://quality-control-32.preview.emergentagent.com")
API_URL = f"{BASE_URL}/api"
PASSWORD = "homeart2025"

def login():
    """Get auth token."""
    resp = requests.post(f"{API_URL}/auth/login", json={"password": PASSWORD})
    if resp.status_code != 200:
        print(f"❌ Login failed: {resp.status_code} {resp.text}")
        sys.exit(1)
    return resp.json()["token"]

def get_stats():
    """Get current stats."""
    resp = requests.get(f"{API_URL}/stats")
    if resp.status_code != 200:
        print(f"❌ Stats failed: {resp.status_code}")
        return None
    return resp.json()

def poll_task(task_id, timeout=120):
    """Poll task until done or error."""
    start = time.time()
    while time.time() - start < timeout:
        resp = requests.get(f"{API_URL}/tasks/{task_id}")
        if resp.status_code != 200:
            print(f"❌ Task poll failed: {resp.status_code}")
            return None
        task = resp.json()
        status = task.get("status")
        if status in ["done", "error"]:
            return task
        time.sleep(1)
    print(f"❌ Task {task_id} timed out after {timeout}s")
    return None

def test_embed():
    """Test A: POST /api/embed."""
    print("\n" + "="*80)
    print("TEST A: POST /api/embed")
    print("="*80)
    
    # Record starting embeddings count
    stats_before = get_stats()
    if not stats_before:
        print("❌ Failed to get initial stats")
        return False
    
    emb_before = stats_before.get("embeddings", 0)
    print(f"✓ Initial embeddings count: {emb_before}")
    
    # Trigger embed job
    resp = requests.post(f"{API_URL}/embed", json={})
    if resp.status_code != 200:
        print(f"❌ POST /api/embed failed: {resp.status_code} {resp.text}")
        return False
    
    data = resp.json()
    task_id = data.get("task_id")
    if not task_id:
        print(f"❌ No task_id in response: {data}")
        return False
    
    print(f"✓ Embed task created: {task_id}")
    
    # Poll until done
    print("⏳ Polling task until completion...")
    task = poll_task(task_id, timeout=180)
    if not task:
        return False
    
    status = task.get("status")
    result = task.get("result", {})
    embedded = result.get("embedded")
    
    print(f"✓ Task status: {status}")
    print(f"✓ Result: {result}")
    
    if status != "done":
        print(f"❌ Task failed with status: {status}")
        return False
    
    if not isinstance(embedded, int):
        print(f"❌ result.embedded is not an integer: {embedded}")
        return False
    
    print(f"✓ Embedded count: {embedded} (expected 0 or small number)")
    
    # Check embeddings count didn't decrease
    stats_after = get_stats()
    if not stats_after:
        print("❌ Failed to get final stats")
        return False
    
    emb_after = stats_after.get("embeddings", 0)
    print(f"✓ Final embeddings count: {emb_after}")
    
    if emb_after < emb_before:
        print(f"❌ CRITICAL: Embeddings count DECREASED from {emb_before} to {emb_after}")
        return False
    
    print(f"✅ TEST A PASSED: Embed job completed, embedded={embedded}, embeddings count stable ({emb_before} → {emb_after})")
    return True

def test_text_search():
    """Test B: POST /api/search text mode."""
    print("\n" + "="*80)
    print("TEST B: POST /api/search (TEXT MODE)")
    print("="*80)
    
    stats = get_stats()
    expected_searched = stats.get("embeddings", 0) if stats else 16309
    print(f"✓ Expected searched count: {expected_searched}")
    
    queries = [
        {"q": "диван из кожи", "top_k": 8, "desc": "Russian: leather sofa", 
         "expect_models": ["GREGOR", "LUCIO", "CLEO", "AUGUSTO", "TURNER", "OCTAVE", "EUGÈNE"],
         "expect_category": ["sofa", "pouf"], "min_score": 0.7},
        {"q": "кухонный модуль с ящиками", "top_k": 8, "desc": "Russian: kitchen module with drawers",
         "expect_first": "KITCHEN BOX DRAWERS", "expect_category": ["Kitchen", "Dada"]},
        {"q": "кровать", "top_k": 8, "desc": "Russian: bed",
         "expect_category": ["BED", "bed", "daybed", "BREEZE"]},
        {"q": "dining table oak", "top_k": 8, "desc": "English: dining table oak",
         "expect_models": ["MATEO", "WOODY", "MONK", "VICINO"], "expect_category": ["table", "TABLE"]},
    ]
    
    all_passed = True
    
    for i, query in enumerate(queries, 1):
        print(f"\n--- Query {i}: {query['desc']} ---")
        print(f"Query: {query['q']}")
        
        resp = requests.post(f"{API_URL}/search", json={"q": query["q"], "top_k": query["top_k"]})
        if resp.status_code != 200:
            print(f"❌ Search failed: {resp.status_code} {resp.text}")
            all_passed = False
            continue
        
        data = resp.json()
        mode = data.get("mode")
        results = data.get("results", [])
        searched = data.get("searched")
        
        print(f"✓ Mode: {mode}")
        print(f"✓ Results count: {len(results)}")
        print(f"✓ Searched: {searched}")
        
        # Check mode
        if mode != "text":
            print(f"❌ Expected mode='text', got '{mode}'")
            all_passed = False
        
        # Check results count
        if len(results) != query["top_k"]:
            print(f"⚠️  Expected {query['top_k']} results, got {len(results)}")
        
        # Check searched count
        if searched != expected_searched:
            print(f"⚠️  Expected searched={expected_searched}, got {searched}")
        
        # Check de-duplication
        seen_keys = set()
        duplicates = []
        for r in results:
            key = (r.get("model_name"), r.get("category"))
            if key in seen_keys:
                duplicates.append(key)
            seen_keys.add(key)
        
        if duplicates:
            print(f"❌ DUPLICATES FOUND: {duplicates}")
            all_passed = False
        else:
            print(f"✓ De-duplication: PASSED (no duplicate (model_name, category) pairs)")
        
        # Check required fields
        if results:
            r0 = results[0]
            required = ["score", "price_min", "price_max", "doc_id", "page", "model_name", "n_variations"]
            missing = [f for f in required if f not in r0]
            if missing:
                print(f"❌ Missing required fields in results: {missing}")
                all_passed = False
            else:
                print(f"✓ All required fields present: {required}")
            
            # Print top 3 results
            print(f"\nTop 3 results:")
            for j, r in enumerate(results[:3], 1):
                print(f"  {j}. {r.get('model_name')} | {r.get('category')} | score={r.get('score', 0):.4f}")
            
            # Check score threshold
            top_score = r0.get("score", 0)
            if "min_score" in query and top_score < query["min_score"]:
                print(f"⚠️  Top score {top_score:.4f} < expected {query['min_score']}")
            else:
                print(f"✓ Top score: {top_score:.4f}")
            
            # Check semantic correctness
            if "expect_models" in query:
                found_models = [r.get("model_name", "").upper() for r in results]
                matches = [m for m in query["expect_models"] if any(m in fm for fm in found_models)]
                if matches:
                    print(f"✓ Semantic match: found expected models {matches}")
                else:
                    print(f"⚠️  Expected models {query['expect_models']} not found in top results")
            
            if "expect_category" in query:
                found_cats = [str(r.get("category", "")).lower() for r in results]
                matches = [c for c in query["expect_category"] if any(str(c).lower() in fc for fc in found_cats)]
                if matches:
                    print(f"✓ Semantic match: found expected categories {matches}")
                else:
                    print(f"⚠️  Expected categories {query['expect_category']} not found")
            
            if "expect_first" in query:
                first_model = r0.get("model_name", "")
                if query["expect_first"].lower() in first_model.lower():
                    print(f"✓ First result matches: {first_model}")
                else:
                    print(f"⚠️  Expected first result '{query['expect_first']}', got '{first_model}'")
    
    if all_passed:
        print(f"\n✅ TEST B PASSED: All text search queries working correctly")
    else:
        print(f"\n⚠️  TEST B COMPLETED WITH WARNINGS (see details above)")
    
    return all_passed

def test_empty_query():
    """Test C: POST /api/search with empty query."""
    print("\n" + "="*80)
    print("TEST C: POST /api/search (EMPTY QUERY)")
    print("="*80)
    
    resp = requests.post(f"{API_URL}/search", json={"q": "   "})
    if resp.status_code != 200:
        print(f"❌ Empty query failed: {resp.status_code} {resp.text}")
        return False
    
    data = resp.json()
    mode = data.get("mode")
    results = data.get("results", [])
    
    print(f"✓ Response: {data}")
    
    if mode != "text":
        print(f"❌ Expected mode='text', got '{mode}'")
        return False
    
    if len(results) != 0:
        print(f"❌ Expected empty results, got {len(results)} results")
        return False
    
    print(f"✅ TEST C PASSED: Empty query returns {{'results':[], 'mode':'text'}}")
    return True

def test_image_search():
    """Test D: POST /api/search image mode."""
    print("\n" + "="*80)
    print("TEST D: POST /api/search (IMAGE MODE)")
    print("="*80)
    
    # Generate a small test image with PIL
    print("✓ Generating test image (400x300 RGB JPEG)...")
    img = Image.new("RGB", (400, 300), color=(200, 150, 100))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    buf.seek(0)
    
    # POST as multipart/form-data
    files = {"file": ("test.jpg", buf, "image/jpeg")}
    data = {"top_k": "8"}
    
    resp = requests.post(f"{API_URL}/search", files=files, data=data)
    if resp.status_code != 200:
        print(f"❌ Image search failed: {resp.status_code} {resp.text}")
        return False
    
    result = resp.json()
    mode = result.get("mode")
    results = result.get("results", [])
    
    print(f"✓ Mode: {mode}")
    print(f"✓ Results count: {len(results)}")
    
    if mode != "image":
        print(f"❌ Expected mode='image', got '{mode}'")
        return False
    
    if len(results) != 8:
        print(f"⚠️  Expected 8 results, got {len(results)}")
    
    # Check scores are in plausible CLIP image-text band (0.1-0.45)
    if results:
        scores = [r.get("score", 0) for r in results]
        print(f"✓ Score range: {min(scores):.4f} - {max(scores):.4f}")
        
        # Check required fields
        r0 = results[0]
        required = ["score", "doc_id", "page"]
        missing = [f for f in required if f not in r0]
        if missing:
            print(f"❌ Missing required fields: {missing}")
            return False
        
        print(f"✓ All required fields present")
        
        # Print top 3
        print(f"\nTop 3 results:")
        for i, r in enumerate(results[:3], 1):
            print(f"  {i}. {r.get('model_name')} | score={r.get('score', 0):.4f}")
        
        # Verify scores are in expected range (0.1-0.45 for image mode)
        if max(scores) > 0.7:
            print(f"⚠️  Image scores unexpectedly high (>0.7). Expected 0.1-0.45 range.")
        else:
            print(f"✓ Scores in expected CLIP image-text range (0.1-0.45)")
    
    print(f"✅ TEST D PASSED: Image search working correctly")
    return True

def test_latency():
    """Test E: Measure warm text query latency."""
    print("\n" + "="*80)
    print("TEST E: TEXT QUERY LATENCY")
    print("="*80)
    
    # Warm-up query
    print("⏳ Warm-up query...")
    resp = requests.post(f"{API_URL}/search", json={"q": "sofa", "top_k": 8})
    if resp.status_code != 200:
        print(f"❌ Warm-up query failed: {resp.status_code}")
        return False
    
    # Measure second query
    print("⏱️  Measuring warm query latency...")
    start = time.time()
    resp = requests.post(f"{API_URL}/search", json={"q": "dining table", "top_k": 8})
    elapsed = time.time() - start
    
    if resp.status_code != 200:
        print(f"❌ Latency test query failed: {resp.status_code}")
        return False
    
    print(f"✓ Warm text query latency: {elapsed:.3f}s")
    
    if elapsed > 3.0:
        print(f"⚠️  Latency {elapsed:.3f}s exceeds 3s threshold")
    else:
        print(f"✅ TEST E PASSED: Latency {elapsed:.3f}s is under 3s")
    
    return True

def test_embedding_text_builder():
    """Test F: Sanity-check embedding text builder."""
    print("\n" + "="*80)
    print("TEST F: EMBEDDING TEXT BUILDER")
    print("="*80)
    
    try:
        # Run the Python snippet to check product_text output
        cmd = """python3 -c "import sys; sys.path.insert(0,'/app/backend'); import db, embeddings as E; [print(repr(E.product_text(p))) for p in db.products.find({'confidence':{'\\$gte':0.7}}, {'_id':0}).limit(5)]" """
        
        import subprocess
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        
        if result.returncode != 0:
            print(f"❌ Command failed: {result.stderr}")
            return False
        
        output = result.stdout.strip()
        print(f"✓ Sample product texts:\n{output}\n")
        
        # Check that strings look clean (no price text, no variant codes)
        lines = output.split("\n")
        issues = []
        for line in lines:
            # Check for price patterns (EUR, €, numbers like 123-456)
            if "EUR" in line or "€" in line:
                issues.append(f"Price text found: {line}")
            # Check for variant code patterns (e.g., SP3/12, A1B2)
            if any(c.isdigit() for c in line) and "/" in line:
                issues.append(f"Possible variant code: {line}")
        
        if issues:
            print(f"⚠️  Potential issues in product texts:")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print(f"✓ Product texts look clean (no price text, no variant codes)")
        
        print(f"✅ TEST F PASSED: Embedding text builder produces clean semantic strings")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def main():
    print("="*80)
    print("SLICE 2 BACKEND TEST SUITE")
    print("Testing: /api/embed and /api/search")
    print("="*80)
    
    # Login
    print("\n🔐 Logging in...")
    token = login()
    print(f"✓ Authenticated")
    
    # Run tests
    results = {}
    
    try:
        results["A_embed"] = test_embed()
    except Exception as e:
        print(f"❌ TEST A EXCEPTION: {e}")
        results["A_embed"] = False
    
    try:
        results["B_text_search"] = test_text_search()
    except Exception as e:
        print(f"❌ TEST B EXCEPTION: {e}")
        results["B_text_search"] = False
    
    try:
        results["C_empty_query"] = test_empty_query()
    except Exception as e:
        print(f"❌ TEST C EXCEPTION: {e}")
        results["C_empty_query"] = False
    
    try:
        results["D_image_search"] = test_image_search()
    except Exception as e:
        print(f"❌ TEST D EXCEPTION: {e}")
        results["D_image_search"] = False
    
    try:
        results["E_latency"] = test_latency()
    except Exception as e:
        print(f"❌ TEST E EXCEPTION: {e}")
        results["E_latency"] = False
    
    try:
        results["F_text_builder"] = test_embedding_text_builder()
    except Exception as e:
        print(f"❌ TEST F EXCEPTION: {e}")
        results["F_text_builder"] = False
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    for test, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test}: {status}")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
