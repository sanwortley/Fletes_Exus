import requests

url = "http://127.0.0.1:8000/api/availability/day"
headers = {"X-API-Key": "AdminFletesJavier20251110!!"}
payload = {
    "date": "2026-02-01",
    "enabled": True,
    "slots": ["10:00", "11:00", "12:00"]
}

print("Habilitando día 2026-02-01...")
try:
    res = requests.post(url, json=payload, headers=headers)
    print("Status:", res.status_code)
    print("Response:", res.json())
except Exception as e:
    print("Error:", e)
