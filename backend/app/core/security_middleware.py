# backend/app/core/security_middleware.py
"""
Security Headers Middleware
Production için güvenlik header'ları ekler
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Production için güvenlik header'ları ekler:
    - HSTS (HTTP Strict Transport Security)
    - CSP (Content Security Policy)
    - X-Frame-Options
    - X-Content-Type-Options
    - Referrer-Policy
    - Permissions-Policy
    """
    
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        
        # Production'da güvenlik header'larını ekle
        if settings.ENV == "prod":
            # HSTS - HTTPS zorunluluğu (sadece HTTPS'te çalışır)
            # Render/Vercel gibi proxy'ler arkasında olduğumuz için
            # X-Forwarded-Proto header'ını kontrol et
            if request.headers.get("x-forwarded-proto") == "https":
                response.headers["Strict-Transport-Security"] = (
                    "max-age=31536000; includeSubDomains; preload"
                )
            
            # X-Frame-Options - Clickjacking koruması
            response.headers["X-Frame-Options"] = "DENY"
            
            # X-Content-Type-Options - MIME type sniffing koruması
            response.headers["X-Content-Type-Options"] = "nosniff"
            
            # X-XSS-Protection (eski tarayıcılar için)
            response.headers["X-XSS-Protection"] = "1; mode=block"
            
            # Referrer-Policy - Referrer bilgisi kontrolü
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            
            # Permissions-Policy (eski adı Feature-Policy)
            response.headers["Permissions-Policy"] = (
                "geolocation=(), "
                "microphone=(), "
                "camera=(), "
                "payment=(), "
                "usb=()"
            )
            
            # Content-Security-Policy - XSS ve injection koruması
            # API için esnek CSP (frontend'den gelen istekler için)
            csp = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "  # React için gerekli
                "style-src 'self' 'unsafe-inline'; "  # Tailwind için gerekli
                "img-src 'self' data: https:; "
                "font-src 'self' data:; "
                "connect-src 'self' https: wss: ws:; "  # API ve WebSocket için
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self';"
            )
            response.headers["Content-Security-Policy"] = csp
        
        return response

