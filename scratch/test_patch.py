import sys
import os
import requests
import json

# Add parent dir to path for imports if needed, but we use requests here
API_BASE = "http://127.0.0.1:8000"
ADMIN_KEY = "AdminFletesJavier20251110!!" # From .env

def test_persistence():
    # 1. Get all requests
    headers = {"X-API-KEY": ADMIN_KEY}
    res = requests.get(f"{API_BASE}/api/requests?status=all", headers=headers)
    all_reqs = res.json()
    print(f"Total requests before test: {len(all_reqs)}")
    
    if not all_reqs:
        print("No requests to test with.")
        return

    target = all_reqs[0]
    qid = target.get("id")
    print(f"Testing with quote ID: {qid}, Name: {target.get('nombre_cliente')}")

    # 2. Patch the name
    new_name = target.get('nombre_cliente') + " (Edited)"
    payload = {"nombre": new_name}
    res = requests.patch(f"{API_BASE}/api/requests/{qid}", headers=headers, json=payload)
    print(f"PATCH status: {res.status_code}")
    print(f"PATCH response: {res.json()}")

    # 3. Verify it's still there
    res = requests.get(f"{API_BASE}/api/requests?status=all", headers=headers)
    all_reqs_after = res.json()
    print(f"Total requests after test: {len(all_reqs_after)}")
    
    found = any(str(r.get("id")) == str(qid) for r in all_reqs_after)
    if found:
        print("SUCCESS: Quote still exists.")
    else:
        print("FAILURE: Quote DISAPPEARED.")

if __name__ == "__main__":
    test_persistence()
