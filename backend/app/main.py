# backend/app/main.py
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi  # << Swagger özelleştirme için

from .core.config import settings
from .core.middleware import ErrorMiddleware, DefaultSubeMiddleware
from .core.tenant_middleware import TenantStatusMiddleware, SubscriptionLimitMiddleware
from .core.domain_middleware import DomainTenantMiddleware
from .core.startup_checks import validate_startup
from .db.database import db
from .db.schema import create_tables

# Routers
from .routers.system import router as system_router    # /health, /version, /me
from .routers.ping import router as ping_router        # /ping (secure pong)
from .routers.auth import router as auth_router        # /auth/*
from .routers.superadmin import router as superadmin_router  # /superadmin/*
from .routers.menu import router as menu_router        # /menu/*
from .routers.siparis import router as siparis_router  # /siparis/*
from .routers.mutfak import router as mutfak_router    # /mutfak/*
from .routers.kasa import router as kasa_router        # /kasa/*
from .routers.admin import router as admin_router      # /admin/*
from .routers.istatistik import router as istatistik_router  # /istatistik/*
from .core.observability import RequestIdAndRateLimitMiddleware
from .routers.rapor import router as rapor_router
from .routers.isletme import router as isletme_router
from .routers.sube import router as sube_router
from .routers.assistant import router as assistant_router  # /assistant/*
from .routers.auth_debug import router as debug_router  # /debug/* - temporary
from .routers.stok import router as stok_router        # /stok/*
from .routers.recete import router as recete_router    # /recete/*
from .routers.analytics import router as analytics_router  # /analytics/*
from .routers.public import router as public_router     # /public/*
from .routers.bi_assistant import router as bi_assistant_router  # /bi-assistant/*
from .routers.customer_assistant import router as customer_assistant_router  # /customer-assistant/*
from .routers.giderler import router as giderler_router  # /giderler/*
from .routers.masalar import router as masalar_router  # /masalar/*
from .routers.websocket_router import router as websocket_router  # /ws/*
from .routers.menu_varyasyonlar import router as menu_varyasyonlar_router  # /menu-varyasyonlar/*
from .routers.adisyon import router as adisyon_router  # /adisyon/*
from .routers.subscription import router as subscription_router  # /subscription/*
from .routers.payment import router as payment_router  # /payment/*
from .routers.customization import router as customization_router  # /customization/*
from .routers.audit import router as audit_router  # /audit/*
from .routers.backup import router as backup_router  # /system/backup/*
from .routers.analytics_advanced import router as analytics_advanced_router  # /analytics/advanced/*
from .routers.cache import router as cache_router  # /cache/*

from pathlib import Path

# Scheduler servisi (otomatik yedekleme için)
from .services.scheduler import scheduler_service
# Cache servisi (performans için)
from .services.cache import cache_service

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---- Statik medya ----
media_dir = Path(settings.MEDIA_ROOT)
media_dir.mkdir(parents=True, exist_ok=True)
app.mount(
    settings.MEDIA_URL,
    StaticFiles(directory=media_dir, check_dir=True),
    name="media",
)

# ---- CORS (frontend rahat bağlansın) ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)

# ---- Hata Yakalama Orta Katmanı ----
app.add_middleware(ErrorMiddleware)

# ---- SaaS Multi-Tenancy Middleware'leri ----
# NOT: Middleware'ler ters sırada çalışır (son eklenen ilk çalışır)
# 1. Domain/subdomain'den tenant'ı tespit et
# 2. Tenant durumunu kontrol et (suspended/cancelled)
# 3. Subscription limitlerini kontrol et
app.add_middleware(DomainTenantMiddleware)  # İlk çalışır - domain'den tenant'ı tespit eder
app.add_middleware(TenantStatusMiddleware)
app.add_middleware(SubscriptionLimitMiddleware)

# ---- DB Yaşam Döngüsü ----
@app.on_event("startup")
async def on_startup():
    import logging

    # Validate environment configuration before starting
    print("[STARTUP] Validating configuration...")
    validate_startup()
    
    # Debug: CORS ayarlarını logla
    print(f"[STARTUP] CORS_ORIGINS: {settings.CORS_ORIGINS}")
    print(f"[STARTUP] CORS_ALLOW_CREDENTIALS: {settings.CORS_ALLOW_CREDENTIALS}")

    print("[STARTUP] Connecting to database...")
    # min_size ve max_size validasyonu (min_size max_size'tan küçük veya eşit olmalı)
    min_size = min(settings.DB_POOL_MIN_SIZE, settings.DB_POOL_MAX_SIZE)
    max_size = max(settings.DB_POOL_MIN_SIZE, settings.DB_POOL_MAX_SIZE)
    print(f"[STARTUP] Connection pool: min={min_size}, max={max_size}, timeout={settings.DB_COMMAND_TIMEOUT}s")
    await db.connect()
    print("[STARTUP] Database connected, creating tables...")
    try:
        await create_tables(db)
        print("[STARTUP] Tables created successfully")
    except Exception as e:
        print(f"[STARTUP] Error creating tables: {e}")
        logging.error(f"Error in create_tables: {e}", exc_info=True)

    # Redis Cache'i başlat
    try:
        await cache_service.connect()
        print("[STARTUP] Redis cache initialized")
    except Exception as e:
        print(f"[STARTUP] Error initializing cache: {e}")
        logging.warning(f"Cache initialization failed: {e}")

    # Scheduler'ı başlat (otomatik yedekleme için)
    try:
        scheduler_service.start()
        print("[STARTUP] Scheduler started successfully")
    except Exception as e:
        print(f"[STARTUP] Error starting scheduler: {e}")
        logging.error(f"Error starting scheduler: {e}", exc_info=True)

@app.on_event("shutdown")
async def on_shutdown():
    await db.disconnect()

    # Cache'i kapat
    try:
        await cache_service.disconnect()
        print("[SHUTDOWN] Redis cache closed")
    except Exception as e:
        print(f"[SHUTDOWN] Error closing cache: {e}")

    # Scheduler'ı kapat
    try:
        scheduler_service.shutdown()
        print("[SHUTDOWN] Scheduler stopped")
    except Exception as e:
        print(f"[SHUTDOWN] Error stopping scheduler: {e}")

# ---- Router Kayıtları ----
app.include_router(system_router)      # /health, /version, /me
app.include_router(ping_router)        # /ping
app.include_router(auth_router)        # /auth/token ...
app.include_router(superadmin_router)  # /superadmin/* - users, tenants, settings
app.include_router(menu_router)        # /menu/ekle, /menu/liste, /menu/yukle-csv, ...
app.include_router(siparis_router)     # /siparis/ekle, /siparis/liste, ...
app.include_router(mutfak_router)      # /mutfak/siparisler, /mutfak/siparis/{id}/durum
app.include_router(kasa_router)        # /kasa/hesap/ozet, /kasa/odeme/ekle, ...
app.include_router(istatistik_router)  # /istatistik/gunluk, ...
app.include_router(rapor_router)       # /rapor/
app.include_router(admin_router)       # /admin/*
app.include_router(isletme_router)
app.include_router(sube_router)
app.include_router(assistant_router)   # /assistant/*
app.include_router(debug_router)       # /debug/* - temporary
app.include_router(stok_router)        # /stok/*
app.include_router(recete_router)      # /recete/*
app.include_router(analytics_router)   # /analytics/*
app.include_router(public_router)      # /public/*
app.include_router(bi_assistant_router)  # /bi-assistant/*
app.include_router(customer_assistant_router)  # /customer-assistant/*
app.include_router(giderler_router)    # /giderler/*
app.include_router(masalar_router)     # /masalar/*
app.include_router(websocket_router)   # /ws/*
app.include_router(menu_varyasyonlar_router)  # /menu-varyasyonlar/*
app.include_router(adisyon_router)     # /adisyon/*
app.include_router(subscription_router)  # /subscription/*
app.include_router(payment_router)     # /payment/*
app.include_router(customization_router)  # /customization/*
app.include_router(audit_router)       # /audit/*
app.include_router(backup_router)      # /system/backup/*
app.include_router(analytics_advanced_router)  # /analytics/advanced/*
app.include_router(cache_router)       # /cache/*

# ---- Observability & Varsayılan Şube ----
app.add_middleware(RequestIdAndRateLimitMiddleware)
app.add_middleware(DefaultSubeMiddleware)

# ---- Root kısa bilgi ----
@app.get("/")
async def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.VERSION,
        "env": settings.ENV,
        "docs": "/docs",
        "health": "/health",
    }

# ==== Swagger/OpenAPI özelleştirme (RBAC + Çok Şube) ====
# Amaç: Authorize penceresinde hem Bearer (JWT) hem de X-Sube-Id header'ını
# tek seferde tanımlayıp UI’nin hatırlamasını sağlamak.
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Security tanımları
    components = schema.setdefault("components", {}).setdefault("securitySchemes", {})

    # Bearer JWT
    components["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "Girişten aldığın access token'ı buraya gir."
    }

    # Çok şube: X-Sube-Id
    components["X-Sube-Id"] = {
        "type": "apiKey",
        "in": "header",
        "name": "X-Sube-Id",
        "description": "Şube seçimi. Varsayılan: 1 (Authorize ekranına 1 yaz; UI hatırlar)."
    }

    # Global güvenlik: tüm uçlar Bearer + X-Sube-Id beklesin.
    # (Eğer bazı uçlarda X-Sube-Id gerekmiyorsa, ilgili router için openapi_extra ile override edebiliriz.)
    schema["security"] = [
        {"BearerAuth": []},
        {"X-Sube-Id": []}
    ]

    app.openapi_schema = schema
    return app.openapi_schema

# FastAPI'ye özel şemayı atıyoruz.
app.openapi = custom_openapi
# Reload trigger
