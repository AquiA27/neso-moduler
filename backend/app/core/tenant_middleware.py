# backend/app/core/tenant_middleware.py
"""
SaaS Multi-Tenancy Middleware'leri
- Tenant durumu kontrolü (suspended/cancelled)
- Subscription limit kontrolü (kullanıcı, şube, menü limitleri)
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from typing import Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class TenantStatusMiddleware(BaseHTTPMiddleware):
    """
    İşletme (tenant) durumunu kontrol eder.

    Kontroller:
    - Subscription aktif mi? (suspended, cancelled, expired kontrolü)
    - Trial süresi dolmuş mu?
    - İşletme aktif mi?

    Super admin ve public endpoint'ler bypass edilir.
    """

    # Bu endpoint'ler kontrol edilmez
    EXACT_BYPASS_PATHS = {
        "/",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/health",
        "/auth/token",
        "/auth/refresh",
        "/ping",
    }

    PREFIX_BYPASS_PATHS = {
        "/public",
        "/media",
    }

    async def dispatch(self, request: Request, call_next):
        # OPTIONS preflight request'leri bypass (CORS için)
        if request.method == "OPTIONS":
            return await call_next(request)
        
        # Bypass kontrolü
        if self._should_bypass(request):
            return await call_next(request)

        # Authorization header'dan tenant bilgisini al
        tenant_info = await self._get_tenant_from_request(request)

        if tenant_info:
            isletme_id = tenant_info.get("isletme_id")
            role = tenant_info.get("role", "").lower()

            # Super admin bypass
            if role == "super_admin":
                return await call_next(request)

            # Tenant durumunu kontrol et
            if isletme_id:
                status_check = await self._check_tenant_status(isletme_id)

                if not status_check["allowed"]:
                    return JSONResponse(
                        {
                            "ok": False,
                            "error_code": status_check["error_code"],
                            "detail": status_check["detail"],
                        },
                        status_code=403,
                    )

        return await call_next(request)

    def _should_bypass(self, request: Request) -> bool:
        """Bu path'leri bypass et"""
        path = request.url.path

        # Exact match
        if path in self.EXACT_BYPASS_PATHS:
            return True

        # Prefix match
        for bypass_path in self.PREFIX_BYPASS_PATHS:
            if path.startswith(bypass_path):
                return True

        return False

    async def _get_tenant_from_request(self, request: Request) -> Optional[Dict[str, Any]]:
        """Request'ten tenant bilgisini çıkar (JWT token'dan)"""
        try:
            from .deps import decode_token
            from ..db.database import db

            # Authorization header'ı al
            auth_header = request.headers.get("authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return None

            token = auth_header.replace("Bearer ", "")

            try:
                payload = decode_token(token)
            except Exception:
                return None

            username = payload.get("sub")
            if not username:
                return None

            # Kullanıcı bilgilerini al
            user_row = await db.fetch_one(
                """
                SELECT u.id, u.username, u.role, s.isletme_id
                FROM users u
                LEFT JOIN user_sube_izinleri usi ON usi.username = u.username
                LEFT JOIN subeler s ON s.id = usi.sube_id
                WHERE u.username = :username
                LIMIT 1
                """,
                {"username": username},
            )

            if not user_row:
                return None

            return {
                "user_id": user_row["id"],
                "username": user_row["username"],
                "role": user_row["role"],
                "isletme_id": user_row["isletme_id"],
            }

        except Exception as e:
            logger.error(f"Error getting tenant from request: {e}")
            return None

    async def _check_tenant_status(self, isletme_id: int) -> Dict[str, Any]:
        """Tenant durumunu kontrol et"""
        try:
            from ..db.database import db

            # İşletme ve subscription bilgilerini al
            row = await db.fetch_one(
                """
                SELECT
                    i.aktif as isletme_aktif,
                    s.status as sub_status,
                    s.trial_bitis,
                    s.bitis_tarihi
                FROM isletmeler i
                LEFT JOIN subscriptions s ON s.isletme_id = i.id
                WHERE i.id = :isletme_id
                """,
                {"isletme_id": isletme_id},
            )

            if not row:
                return {
                    "allowed": False,
                    "error_code": "TENANT_NOT_FOUND",
                    "detail": "İşletme bulunamadı",
                }

            # İşletme aktif değilse
            if not row["isletme_aktif"]:
                return {
                    "allowed": False,
                    "error_code": "TENANT_INACTIVE",
                    "detail": "İşletme hesabı devre dışı bırakılmış",
                }

            # Subscription yoksa izin ver (backward compatibility)
            if not row["sub_status"]:
                logger.warning(f"İşletme {isletme_id} için subscription bulunamadı, izin veriliyor")
                return {"allowed": True}

            sub_status = row["sub_status"].lower()

            # Suspended kontrolü
            if sub_status == "suspended":
                return {
                    "allowed": False,
                    "error_code": "SUBSCRIPTION_SUSPENDED",
                    "detail": "Aboneliğiniz askıya alınmış. Lütfen ödeme yapın veya destek ile iletişime geçin.",
                }

            # Cancelled kontrolü
            if sub_status == "cancelled":
                return {
                    "allowed": False,
                    "error_code": "SUBSCRIPTION_CANCELLED",
                    "detail": "Aboneliğiniz iptal edilmiş. Yeniden aktif hale getirmek için lütfen destek ile iletişime geçin.",
                }

            # Trial süresi kontrolü
            if sub_status == "trial":
                trial_bitis = row["trial_bitis"]
                if trial_bitis and datetime.utcnow() > trial_bitis:
                    return {
                        "allowed": False,
                        "error_code": "TRIAL_EXPIRED",
                        "detail": "Deneme süreniz sona ermiş. Lütfen bir plan seçin ve ödeme yapın.",
                    }

            # Subscription süresi kontrolü
            if sub_status == "active":
                bitis_tarihi = row["bitis_tarihi"]
                if bitis_tarihi and datetime.utcnow() > bitis_tarihi:
                    return {
                        "allowed": False,
                        "error_code": "SUBSCRIPTION_EXPIRED",
                        "detail": "Aboneliğinizin süresi dolmuş. Lütfen yenileyin.",
                    }

            # Tüm kontroller geçti
            return {"allowed": True}

        except Exception as e:
            logger.error(f"Error checking tenant status: {e}")
            # Hata durumunda izin ver (fail-open) ama log'la
            return {"allowed": True}


class SubscriptionLimitMiddleware(BaseHTTPMiddleware):
    """
    Subscription limitlerini kontrol eder.

    Kontroller:
    - Şube ekleme limiti (max_subeler)
    - Kullanıcı ekleme limiti (max_kullanicilar)
    - Menü item ekleme limiti (max_menu_items)

    Super admin ve read-only endpoint'ler bypass edilir.
    """

    # Bu method'lar kontrol edilmez (read-only)
    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

    # Bu path'ler limit kontrolünden muaf
    EXACT_BYPASS_PATHS = {
        "/",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/health",
        "/ping",
    }

    PREFIX_BYPASS_PATHS = {
        "/auth",
        "/public",
        "/media",
        "/subscription",  # Subscription yönetimi super admin için
    }

    # Limitli endpoint'ler ve limit tipleri
    LIMIT_CHECKS = {
        "/sube/ekle": "subeler",
        "/sube/create": "subeler",
        "/admin/kullanici/ekle": "kullanicilar",
        "/superadmin/user/create": "kullanicilar",
        "/menu/ekle": "menu_items",
        "/menu/create": "menu_items",
        "/menu/yukle-csv": "menu_items",  # CSV upload da limit kontrolü yapmalı
    }

    async def dispatch(self, request: Request, call_next):
        # Safe method'lar bypass
        if request.method in self.SAFE_METHODS:
            return await call_next(request)

        # Bypass kontrolü
        if self._should_bypass(request):
            return await call_next(request)

        # Limit kontrolü gerekli mi?
        limit_type = self._get_limit_type(request.url.path)
        if not limit_type:
            return await call_next(request)

        # Tenant bilgisini al
        tenant_info = await self._get_tenant_from_request(request)

        if tenant_info:
            role = tenant_info.get("role", "").lower()

            # Super admin bypass
            if role == "super_admin":
                return await call_next(request)

            isletme_id = tenant_info.get("isletme_id")

            if isletme_id:
                # Limit kontrolü yap
                limit_check = await self._check_limit(isletme_id, limit_type)

                if not limit_check["allowed"]:
                    return JSONResponse(
                        {
                            "ok": False,
                            "error_code": limit_check["error_code"],
                            "detail": limit_check["detail"],
                            "current": limit_check.get("current"),
                            "limit": limit_check.get("limit"),
                        },
                        status_code=403,
                    )

        return await call_next(request)

    def _should_bypass(self, request: Request) -> bool:
        """Bu path'leri bypass et"""
        path = request.url.path

        if path in self.EXACT_BYPASS_PATHS:
            return True

        for bypass_path in self.PREFIX_BYPASS_PATHS:
            if path.startswith(bypass_path):
                return True

        return False

    def _get_limit_type(self, path: str) -> Optional[str]:
        """Path'e göre limit tipini döndür"""
        for endpoint_path, limit_type in self.LIMIT_CHECKS.items():
            if path.startswith(endpoint_path):
                return limit_type
        return None

    async def _get_tenant_from_request(self, request: Request) -> Optional[Dict[str, Any]]:
        """Request'ten tenant bilgisini çıkar"""
        try:
            from .deps import decode_token
            from ..db.database import db

            auth_header = request.headers.get("authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return None

            token = auth_header.replace("Bearer ", "")

            try:
                payload = decode_token(token)
            except Exception:
                return None

            username = payload.get("sub")
            if not username:
                return None

            # Kullanıcı ve tenant bilgilerini al
            user_row = await db.fetch_one(
                """
                SELECT u.id, u.username, u.role, s.isletme_id
                FROM users u
                LEFT JOIN user_sube_izinleri usi ON usi.username = u.username
                LEFT JOIN subeler s ON s.id = usi.sube_id
                WHERE u.username = :username
                LIMIT 1
                """,
                {"username": username},
            )

            if not user_row:
                return None

            return {
                "user_id": user_row["id"],
                "username": user_row["username"],
                "role": user_row["role"],
                "isletme_id": user_row["isletme_id"],
            }

        except Exception as e:
            logger.error(f"Error getting tenant from request: {e}")
            return None

    async def _check_limit(self, isletme_id: int, limit_type: str) -> Dict[str, Any]:
        """Limit kontrolü yap"""
        try:
            from ..db.database import db

            # Subscription limitlerini al
            sub_row = await db.fetch_one(
                """
                SELECT max_subeler, max_kullanicilar, max_menu_items
                FROM subscriptions
                WHERE isletme_id = :isletme_id
                """,
                {"isletme_id": isletme_id},
            )

            if not sub_row:
                # Subscription yoksa izin ver (backward compatibility)
                logger.warning(f"İşletme {isletme_id} için subscription bulunamadı, limit kontrolü atlanıyor")
                return {"allowed": True}

            # Limit tipine göre kontrol yap
            if limit_type == "subeler":
                max_limit = sub_row["max_subeler"]
                current = await db.fetch_one(
                    "SELECT COUNT(*) as count FROM subeler WHERE isletme_id = :id AND aktif = TRUE",
                    {"id": isletme_id},
                )
                current_count = current["count"] if current else 0

                if current_count >= max_limit:
                    return {
                        "allowed": False,
                        "error_code": "LIMIT_EXCEEDED_SUBELER",
                        "detail": f"Şube limiti aşıldı. Mevcut plan: {max_limit} şube. Daha fazla şube eklemek için planınızı yükseltin.",
                        "current": current_count,
                        "limit": max_limit,
                    }

            elif limit_type == "kullanicilar":
                max_limit = sub_row["max_kullanicilar"]
                current = await db.fetch_one(
                    """
                    SELECT COUNT(DISTINCT u.id) as count
                    FROM users u
                    LEFT JOIN user_sube_izinleri usi ON usi.username = u.username
                    LEFT JOIN subeler s ON s.id = usi.sube_id
                    WHERE s.isletme_id = :id AND u.aktif = TRUE
                    """,
                    {"id": isletme_id},
                )
                current_count = current["count"] if current else 0

                if current_count >= max_limit:
                    return {
                        "allowed": False,
                        "error_code": "LIMIT_EXCEEDED_KULLANICILAR",
                        "detail": f"Kullanıcı limiti aşıldı. Mevcut plan: {max_limit} kullanıcı. Daha fazla kullanıcı eklemek için planınızı yükseltin.",
                        "current": current_count,
                        "limit": max_limit,
                    }

            elif limit_type == "menu_items":
                max_limit = sub_row["max_menu_items"]
                current = await db.fetch_one(
                    """
                    SELECT COUNT(*) as count
                    FROM menu m
                    JOIN subeler s ON m.sube_id = s.id
                    WHERE s.isletme_id = :id AND m.aktif = TRUE
                    """,
                    {"id": isletme_id},
                )
                current_count = current["count"] if current else 0

                if current_count >= max_limit:
                    return {
                        "allowed": False,
                        "error_code": "LIMIT_EXCEEDED_MENU_ITEMS",
                        "detail": f"Menü item limiti aşıldı. Mevcut plan: {max_limit} ürün. Daha fazla ürün eklemek için planınızı yükseltin.",
                        "current": current_count,
                        "limit": max_limit,
                    }

            # Limit aşılmamış
            return {"allowed": True}

        except Exception as e:
            logger.error(f"Error checking limit: {e}")
            # Hata durumunda izin ver (fail-open) ama log'la
            return {"allowed": True}
