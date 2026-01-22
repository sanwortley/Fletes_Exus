import requests
from datetime import datetime

url = "http://127.0.0.1:8000/api/quote/send?debug=true"

payload = {
  "nombre": "Cliente Prueba",
  "telefono": "3511112222",
  "tipo_carga": "mudanza",
  "origen": "Plaza San Martín, Córdoba",
  "destino": "Dinosaurio Mall, Córdoba",
  "fecha": "2026-02-01",
  "ayudante": True,
  "fecha_turno": "2026-02-01",
  "hora_turno": "11:00"
}

print("Simulando creación de presupuesto desde la web...")
try:
    res = requests.post(url, json=payload)
    print("Status:", res.status_code)
    print("Response:", res.json())
except Exception as e:
    print("Error:", e)
