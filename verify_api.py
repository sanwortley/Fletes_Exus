import requests
import json

BASE_URL = "http://127.0.0.1:8000/api"
API_KEY = "AdminFletesJavier20251110!!"

def test_endpoints():
    print("--- Testing API Endpoints ---")
    
    # 1. Health
    try:
        r = requests.get(f"{BASE_URL}/health")
        print(f"Health: {r.status_code} - {r.json()}")
    except Exception as e:
        print(f"Health failed: {e}")

    # 2. Config (Public)
    try:
        r = requests.get(f"{BASE_URL}/config")
        print(f"Config: {r.status_code} - {r.json().get('default_locality')}")
    except Exception as e:
        print(f"Config failed: {e}")

    # 3. Config Vars (Admin)
    try:
        headers = {"x-api-key": API_KEY}
        r = requests.get(f"{BASE_URL}/admin/config-vars", headers=headers)
        if r.status_code == 200:
            config = r.json()
            # Verificamos si KM_POR_LITRO es 8 (valor por defecto en .env o migrado de mongo)
            print(f"Admin Config (KM_POR_LITRO): {config.get('KM_POR_LITRO')}")
        else:
            print(f"Admin Config Failed: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"Admin Config failed: {e}")

    # 4. Requests (Admin)
    try:
        headers = {"x-api-key": API_KEY}
        r = requests.get(f"{BASE_URL}/requests?status=all", headers=headers)
        if r.status_code == 200:
            data = r.json()
            items = data.get("items", [])
            print(f"Total Migrated Quotes: {len(items)}")
            if items:
                print(f"Sample Quote: {items[0].get('nombre_cliente')} - {items[0].get('estado')}")
        else:
            print(f"Listing Requests Failed: {r.status_code}")
    except Exception as e:
        print(f"Listing Requests failed: {e}")

if __name__ == "__main__":
    test_endpoints()
