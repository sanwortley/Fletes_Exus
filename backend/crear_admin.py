# crear_admin.py
from pymongo import MongoClient
from datetime import datetime
from backend.security.security_auth import hash_password

client = MongoClient("mongodb://localhost:27017")
db = client["fletes_db"]
users = db["users"]

email = "sanwortley@gmail.com"
password = "1234"

users.insert_one({
    "email": email,
    "username": "santi",
    "password_hash": hash_password(password),
    "role": "admin",
    "created_at": datetime.utcnow(),
    "fail_count": 0,
    "locked_until": None
})

print(f"✅ Usuario creado: {email} / {password}")
