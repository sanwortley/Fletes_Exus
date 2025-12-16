# backend/security/auth_dep.py

import os
from fastapi import Request, HTTPException

def require_api_key(request: Request):
    api_key = request.headers.get("X-API-Key")

    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing X-API-Key"
        )

    if api_key != os.getenv("ADMIN_API_KEY"):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    return True
