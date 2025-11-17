# backend/app/middleware.py
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
import traceback

from .config import settings

class DefaultSubeMiddleware(BaseHTTPMiddleware):
    """
    DEV ortamında: X-Sube-Id yoksa 1 olarak enjekte eder.
    PROD ortamında: X-Sube-Id yoksa 400 döner (yanlış konfigürasyonu erken yakalar).
    
    Public endpoint'ler (auth, public, health, docs) için bypass edilir.
    """
    # Public endpoint'ler - X-Sube-Id gerektirmez
    PUBLIC_PATHS = [
        "/auth/",
        "/public/",
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/",
        "/ping",
    ]
    
    async def dispatch(self, request: Request, call_next):
        # Public endpoint'leri bypass et
        path = request.url.path
        if any(path.startswith(public_path) for public_path in self.PUBLIC_PATHS):
            return await call_next(request)
        
        headers = dict(request.headers)
        has_sube = "x-sube-id" in headers

        if settings.ENV == "prod":
            if not has_sube:
                return JSONResponse(
                    {"ok": False, "error_code": "MISSING_SUBE_ID", "detail": "X-Sube-Id header zorunlu (prod)."},
                    status_code=400,
                )
            return await call_next(request)
        else:
            # dev: yoksa 1 ekle
            if not has_sube:
                # scope['headers'] (list of (bytes, bytes)) içine header enjekte et
                # (Starlette/ASGI'de güvenli yöntem)
                request.scope["headers"] = list(request.scope.get("headers") or [])
                request.scope["headers"].append((b"x-sube-id", str(1).encode("utf-8")))
            return await call_next(request)


class ErrorMiddleware(BaseHTTPMiddleware):
    """
    Tüm beklenmeyen hataları tek biçimde döndürür.
    DEV: stack izini de ekler.
    """
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            import logging
            import sys
            print(f"[ERROR_MIDDLEWARE] Unhandled exception in {request.method} {request.url.path}: {e}", file=sys.stderr)
            traceback.print_exc()
            logging.error(f"Unhandled exception in {request.method} {request.url.path}: {e}", exc_info=True)
            payload = {
                "ok": False,
                "error_code": "INTERNAL_ERROR",
                "detail": "Internal Server Error" if settings.ENV == "prod" else str(e),
            }
            if settings.ENV != "prod":
                payload["stack"] = traceback.format_exc()
            return JSONResponse(payload, status_code=500)
