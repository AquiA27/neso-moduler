# backend/app/main.py
import os
import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi  # << Swagger özelleştirme için

from .core.config import settings
from .core.middleware import ErrorMiddleware, DefaultSubeMiddleware
from .core.tenant_middleware import TenantStatusMiddleware, SubscriptionLimitMiddleware
from .core.domain_middleware import DomainTenantMiddleware
from .core.startup_checks import validate_startup
from .core.logging_config import setup_logging
from .db.database import db
from .db.schema import create_tables

# Setup logging first, before anything else
setup_logging(
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    json_logs=settings.ENV == "prod"
)
logger = logging.getLogger(__name__)
logger.info(f"[STARTUP] Application starting in {settings.ENV} mode")

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
# Debug router - sadece development'ta
if settings.ENV != "prod":
    from .routers.auth_debug import router as debug_router
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
    docs_url="/docs" if settings.ENV != "prod" else None,
    redoc_url="/redoc" if settings.ENV != "prod" else None,
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
# ÖNEMLİ: CORS middleware EN SON eklenmeli (en önce çalışmalı - OPTIONS preflight için)
# Middleware'ler ters sırada çalışır: son eklenen ilk çalışır

# CORS_ORIGINS'in list olduğundan emin ol (field_validator parse ediyor ama yine de kontrol edelim)
from .core.config import _parse_list

cors_origins_list = settings.CORS_ORIGINS
if isinstance(cors_origins_list, str):
    # Eğer hala string ise parse et
    cors_origins_list = _parse_list(cors_origins_list)
elif not isinstance(cors_origins_list, list):
    cors_origins_list = []

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins_list,  # List[str] olmalı
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)

# ---- SaaS Multi-Tenancy Middleware'leri ----
# NOT: Middleware'ler ters sırada çalışır (son eklenen ilk çalışır)
# 1. Domain/subdomain'den tenant'ı tespit et
# 2. Tenant durumunu kontrol et (suspended/cancelled)
# 3. Subscription limitlerini kontrol et
app.add_middleware(DomainTenantMiddleware)  # Domain'den tenant'ı tespit eder
app.add_middleware(TenantStatusMiddleware)  # Tenant durumunu kontrol eder
app.add_middleware(SubscriptionLimitMiddleware)  # Subscription limitlerini kontrol eder

# ---- Hata Yakalama Orta Katmanı ----
app.add_middleware(ErrorMiddleware)

# ---- DB Yaşam Döngüsü ----
@app.on_event("startup")
async def on_startup():
    import logging

    # Validate environment configuration before starting
    logger.info("[STARTUP] Validating configuration...")
    # validate_startup()  # Geçici olarak devre dışı (local development için)
    
    # Debug: CORS ayarlarını logla
    logger.info(f"[STARTUP] CORS_ORIGINS (raw): {settings.CORS_ORIGINS}")
    logger.info(f"[STARTUP] CORS_ORIGINS (type): {type(settings.CORS_ORIGINS)}")
    logger.info(f"[STARTUP] CORS_ORIGINS (parsed): {cors_origins_list}")
    logger.info(f"[STARTUP] CORS_ALLOW_CREDENTIALS: {settings.CORS_ALLOW_CREDENTIALS}")
    logger.info(f"[STARTUP] CORS_ALLOW_METHODS: {settings.CORS_ALLOW_METHODS}")
    logger.info(f"[STARTUP] CORS_ALLOW_HEADERS: {settings.CORS_ALLOW_HEADERS}")

    logger.info("[STARTUP] Connecting to database...")
    # min_size ve max_size validasyonu (min_size max_size'tan küçük veya eşit olmalı)
    min_size = min(settings.DB_POOL_MIN_SIZE, settings.DB_POOL_MAX_SIZE)
    max_size = max(settings.DB_POOL_MIN_SIZE, settings.DB_POOL_MAX_SIZE)
    logger.info(f"[STARTUP] Connection pool: min={min_size}, max={max_size}, timeout={settings.DB_COMMAND_TIMEOUT}s")
    await db.connect()
    logger.info("[STARTUP] Database connected, creating tables...")
    try:
        await create_tables(db)
        logger.info("[STARTUP] Tables created successfully")
    except Exception as e:
        logger.error(f"[STARTUP] Error creating tables: {e}", exc_info=True)

    # Redis Cache'i başlat
    try:
        await cache_service.connect()
        logger.info("[STARTUP] Redis cache initialized")
    except Exception as e:
        logger.warning(f"[STARTUP] Error initializing cache: {e}")

    # Scheduler'ı başlat (otomatik yedekleme için)
    try:
        scheduler_service.start()
        logger.info("[STARTUP] Scheduler started successfully")
    except Exception as e:
        logger.error(f"[STARTUP] Error starting scheduler: {e}", exc_info=True)
    
    logger.info("[STARTUP] Application startup completed successfully")

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
if settings.ENV != "prod":
    app.include_router(debug_router)       # /debug/* - sadece development'ta
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
