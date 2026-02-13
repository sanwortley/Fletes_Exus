
import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client.get_database()
users = db.users

admin_user = users.find_one({"username": "admin"})
if not admin_user:
    admin_user = users.find_one({"email": "admin"})

if admin_user:
    print(f"Found admin user: {admin_user.get('username') or admin_user.get('email')}")
    print(f"Has password_hash: {'Yes' if admin_user.get('password_hash') else 'No'}")
else:
    print("Admin user not found in database.")
