# backend/app/core/domain_middleware.py
"""
Domain-based tenant routing middleware
Subdomain veya custom domain'den tenant'ı tespit eder
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from typing import Optional
import logging

from ..db.database import db

logger = logging.getLogger(__name__)


def extract_subdomain(host: str) -> Optional[str]:
    """
    Host'tan subdomain'i çıkar
    Örnekler:
    - fistikkafe.neso-moduler.vercel.app -> fistikkafe
    - relaxkafe.neso-moduler.vercel.app -> relaxkafe
    - neso-moduler.vercel.app -> None (ana domain)
    - localhost:5173 -> None
    """
    if not host:
        return None
    
    # Port'u temizle
    host = host.split(':')[0]
    
    # localhost veya IP adresi ise subdomain yok
    if host in ['localhost', '127.0.0.1'] or host.replace('.', '').isdigit():
        return None
    
    parts = host.split('.')
    
    # En az 3 parça olmalı (subdomain.domain.tld)
    if len(parts) < 3:
        return None
    
    # İlk parça subdomain
    subdomain = parts[0]
    
    # Özel durumlar: www, api, www2 gibi
    if subdomain.lower() in ['www', 'api', 'www2']:
        return None
    
    return subdomain.lower()


async def get_tenant_id_from_domain(domain_or_subdomain: str) -> Optional[int]:
    """
    Domain veya subdomain'den tenant_id'yi bul
    """
    try:
        # Önce exact domain match dene
        row = await db.fetch_one(
            """
            SELECT tc.isletme_id, i.aktif
            FROM tenant_customizations tc
            JOIN isletmeler i ON tc.isletme_id = i.id
            WHERE tc.domain = :domain
            LIMIT 1
            """,
            {"domain": domain_or_subdomain}
        )
        
        if row:
            tenant_dict = dict(row) if hasattr(row, 'keys') else row
            if tenant_dict.get("aktif"):
                return tenant_dict.get("isletme_id")
        
        # Subdomain'den de dene (domain olarak kaydedilmiş olabilir)
        # Örnek: tenant_customizations.domain = "fistikkafe" ve subdomain = "fistikkafe"
        row2 = await db.fetch_one(
            """
            SELECT tc.isletme_id, i.aktif
            FROM tenant_customizations tc
            JOIN isletmeler i ON tc.isletme_id = i.id
            WHERE LOWER(tc.domain) = LOWER(:subdomain)
            LIMIT 1
            """,
            {"subdomain": domain_or_subdomain}
        )
        
        if row2:
            tenant_dict2 = dict(row2) if hasattr(row2, 'keys') else row2
            if tenant_dict2.get("aktif"):
                return tenant_dict2.get("isletme_id")
        
        return None
    except Exception as e:
        logger.warning(f"Error getting tenant from domain: {e}")
        return None


class DomainTenantMiddleware(BaseHTTPMiddleware):
    """
    Subdomain veya custom domain'den tenant'ı tespit eder
    ve request.state'a ekler
    """
    
    async def dispatch(self, request: Request, call_next):
        # OPTIONS preflight request'leri bypass (CORS için)
        if request.method == "OPTIONS":
            return await call_next(request)
        
        # Public endpoint'ler için bypass (auth/login vb.)
        path = request.url.path
        if path.startswith(("/auth/", "/public/", "/health", "/docs", "/redoc", "/openapi.json", "/", "/ping")):
            return await call_next(request)
        
        # Host header'ından subdomain'i çıkar
        host = request.headers.get("host", "")
        subdomain = extract_subdomain(host)
        
        tenant_id = None
        
        if subdomain:
            # Subdomain'den tenant'ı bul
            tenant_id = await get_tenant_id_from_domain(subdomain)
            
            if tenant_id:
                # Request state'e ekle (diğer middleware'ler ve endpoint'ler kullanabilir)
                request.state.tenant_id = tenant_id
                request.state.subdomain = subdomain
                logger.debug(f"Domain routing: subdomain={subdomain} -> tenant_id={tenant_id}")
            else:
                logger.debug(f"Domain routing: subdomain={subdomain} -> tenant not found")
        else:
            # Ana domain veya localhost - tenant routing yok
            request.state.tenant_id = None
            request.state.subdomain = None
        
        response = await call_next(request)
        return response

