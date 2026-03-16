# security_auth.py
from datetime import datetime, timedelta, timezone
from typing import Optional
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import re
from sqlmodel import Session

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
        if not hash_: return False
        return ph.verify(hash_, plain)
    except VerifyMismatchError:
        return False

# ====== Lock por usuario (antifuerza bruta distribuida) ======
def check_lock(user) -> None:
    # No usamos session aquí porque solo leemos atributos que ya deberían estar cargados (username, lock_until)
    try:
        lock_until = user.lock_until
        if lock_until and lock_until > datetime.now(timezone.utc):
            raise PermissionError("Usuario temporalmente bloqueado. Probá más tarde.")
    except Exception as e:
        print(f"[Error] check_lock: {e}")
        raise

def register_fail(session: Session, user) -> None:
    # Asegurar que el objeto está en la sesión
    session.add(user)
    fails = (user.failed_logins or 0) + 1
    backoff = min(2 ** max(fails - 5, 0), 300)
    lock_until = None
    if fails >= 5:
        lock_until = datetime.now(timezone.utc) + timedelta(seconds=backoff)
    
    user.failed_logins = fails
    user.lock_until = lock_until
    user.updated_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(user)

def reset_fail(session: Session, user) -> None:
    session.add(user)
    user.failed_logins = 0
    user.lock_until = None
    user.updated_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(user)
