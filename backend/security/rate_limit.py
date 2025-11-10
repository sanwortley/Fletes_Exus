# rate_limit.py
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse

# 👇 Rate limit global por IP (aplica a todo, salvo que eximas una ruta)
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

def install_rate_limit(app):
    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    def _rate_limit_handler(request, exc):
        return JSONResponse(
            status_code=429,
            content={"detail": "Demasiadas solicitudes, esperá un poco."},
            headers={"Retry-After": "30"},
        )

    from slowapi.middleware import SlowAPIMiddleware
    app.add_middleware(SlowAPIMiddleware)
