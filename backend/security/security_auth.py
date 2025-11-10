# security_auth.py
from datetime import datetime, timedelta, timezone
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import re
from pymongo.collection import Collection

# Argon2id parámetros seguros
ph = PasswordHasher(time_cost=3, memory_cost=64*1024, parallelism=2, hash_len=32)

# Política mínima: 10+ chars, mayús, minús, número
PWD_POLICY = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{10,}$")

def hash_password(plain: str) -> str:
    if not PWD_POLICY.match(plain):
        raise ValueError("La contraseña no cumple la política (10+ chars, mayús/minús/número).")
    return ph.hash(plain)

def verify_password(hash_: str, plain: str) -> bool:
    try:
        return ph.verify(hash_, plain)
    except VerifyMismatchError:
        return False

# ====== Lock por usuario (antifuerza bruta distribuida) ======
def check_lock(user: dict) -> None:
    lock_until = user.get("lock_until")
    if lock_until and lock_until > datetime.now(timezone.utc):
        raise PermissionError("Usuario temporalmente bloqueado. Probá más tarde.")

def register_fail(users: Collection, user: dict) -> None:
    fails = int(user.get("failed_logins", 0)) + 1
    # backoff exponencial desde el 5° fallo, máx 300s
    backoff = min(2 ** max(fails - 5, 0), 300)
    lock_until = None
    if fails >= 5:
        lock_until = datetime.now(timezone.utc) + timedelta(seconds=backoff)
    users.update_one({"_id": user["_id"]}, {"$set": {"failed_logins": fails, "lock_until": lock_until}})

def reset_fail(users: Collection, user_id) -> None:
    users.update_one({"_id": user_id}, {"$set": {"failed_logins": 0, "lock_until": None}})
