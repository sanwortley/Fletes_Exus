
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_BASE = "http://127.0.0.1:8000"
username = "admin"
password = "Fletes111125##"

try:
    res = requests.post(f"{API_BASE}/api/login", json={"email": username, "password": password})
    print(f"Status Code: {res.status_code}")
    print(f"Response: {res.json()}")
except Exception as e:
    print(f"Error: {e}")
