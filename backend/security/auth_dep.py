# auth_dep.py
import os
from fastapi import Header, HTTPException
def require_api_key(x_api_key: str = Header(None)):
    if x_api_key != os.getenv("X_API_KEY"): raise HTTPException(401, "Unauthorized")
