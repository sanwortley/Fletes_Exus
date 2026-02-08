# security_bootstrap.py  —  versión sin dependencias externas
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

def harden_app(app: FastAPI):
    # ================================
    # 🔒 1) CORS (tomado de .env)
    # ================================
    allowed = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed or [],                     # sin comodín ni "null" (solo para pruebas)
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],        # lo mínimo necesario
        allow_headers=["Authorization", "Content-Type", "X-API-Key"],
        max_age=600,
    )

    # ================================
    # 🔑 2) Cookies/sesiones seguras (opcional)
    # ================================
    app.add_middleware(
        SessionMiddleware,
        secret_key=os.getenv("JWT_SECRET", "change_this"),
        https_only=True,
        same_site="strict",
    )

    # ================================
    # 🧱 3) Security headers (manual)
    # ================================
    CSP = "default-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://maps.googleapis.com; font-src 'self' data: https://fonts.gstatic.com; script-src 'self' 'unsafe-inline' https://maps.googleapis.com; img-src 'self' data: blob: https://maps.gstatic.com https://maps.googleapis.com; connect-src 'self' https: https://maps.googleapis.com; base-uri 'self'; frame-ancestors 'self';"

    FORCE_HSTS = os.getenv("FORCE_HSTS", "0") in ("1", "true", "True")

    @app.middleware("http")
    async def set_security_headers(request: Request, call_next):
        resp = await call_next(request)
        # Solo para debug/verificar que se aplica el CSP correcto
        # print(f"[Security] CSP applied to {request.url.path}")
        
        resp.headers["Content-Security-Policy"] = CSP
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        resp.headers.setdefault("X-XSS-Protection", "1; mode=block")

        # HSTS solo tiene sentido en HTTPS (o fuerzalo con FORCE_HSTS=1)
        if request.url.scheme == "https" or FORCE_HSTS:
            resp.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload")

        return resp
