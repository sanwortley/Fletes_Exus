import requests

BASE_URL = "http://127.0.0.1:8000/api"

def test_login():
    print("--- Testing /api/login ---")
    payload = {
        "email": "admin",
        "password": "admin123"
    }
    try:
        r = requests.post(f"{BASE_URL}/login", json=payload)
        print(f"Status: {r.status_code}")
        print(f"Response: {r.text}")
    except Exception as e:
        print(f"Login request failed: {e}")

if __name__ == "__main__":
    test_login()
