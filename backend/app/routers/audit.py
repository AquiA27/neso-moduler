# backend/app/routers/audit.py
"""
Audit Log Router
Kritik işlemlerin loglarını görüntüleme ve filtreleme
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

from ..core.deps import get_current_user, require_roles, get_sube_id
from ..services.audit import audit_service

router = APIRouter(prefix="/audit", tags=["Audit Log"])


class AuditLogOut(BaseModel):
    """Audit log çıktı modeli"""
    id: int
    action: str
    user_id: Optional[int]
    username: Optional[str]
    sube_id: Optional[int]
    entity_type: Optional[str]
    entity_id: Optional[int]
    old_values: Optional[Dict[str, Any]]
    new_values: Optional[Dict[str, Any]]
    ip_address: Optional[str]
    user_agent: Optional[str]
    success: bool
    error_message: Optional[str]
    created_at: Optional[str]


class AuditStatisticsOut(BaseModel):
    """Audit log istatistik modeli"""
    total_actions: int
    successful_actions: int
    failed_actions: int
    top_users: List[Dict[str, Any]]
    top_actions: List[Dict[str, Any]]


@router.get(
    "/logs",
    response_model=List[AuditLogOut],
    dependencies=[Depends(require_roles({"super_admin", "admin"}))],
)
async def get_audit_logs(
    limit: int = Query(100, ge=1, le=1000, description="Maksimum kayıt sayısı"),
    offset: int = Query(0, ge=0, description="Sayfa kaydırma"),
    username: Optional[str] = Query(None, description="Kullanıcı adı filtresi"),
    action: Optional[str] = Query(None, description="İşlem türü filtresi (LIKE)"),
    entity_type: Optional[str] = Query(None, description="Varlık tipi filtresi"),
    start_date: Optional[datetime] = Query(None, description="Başlangıç tarihi"),
    end_date: Optional[datetime] = Query(None, description="Bitiş tarihi"),
    success_only: Optional[bool] = Query(None, description="Sadece başarılı işlemler"),
    _: Dict[str, Any] = Depends(get_current_user),
    sube_id: Optional[int] = Depends(get_sube_id),
):
    """
    Audit log'ları filtrele ve getir

    **Yetkiler:** super_admin, admin

    **Filtreleme Seçenekleri:**
    - username: Belirli kullanıcının işlemleri
    - action: İşlem türü (örn: "menu.create", "siparis.update")
    - entity_type: Etkilenen varlık (örn: "menu", "siparis", "stok")
    - start_date/end_date: Tarih aralığı
    - success_only: Sadece başarılı işlemler

    **Örnek Kullanım:**
    ```
    GET /audit/logs?action=menu&success_only=true&limit=50
    GET /audit/logs?username=admin&start_date=2025-01-01T00:00:00
    ```
    """
    logs = await audit_service.get_logs(
        limit=limit,
        offset=offset,
        username=username,
        sube_id=sube_id,
        action=action,
        entity_type=entity_type,
        start_date=start_date,
        end_date=end_date,
        success_only=success_only,
    )
    return logs


@router.get(
    "/statistics",
    response_model=AuditStatisticsOut,
    dependencies=[Depends(require_roles({"super_admin", "admin"}))],
)
async def get_audit_statistics(
    start_date: Optional[datetime] = Query(None, description="Başlangıç tarihi"),
    end_date: Optional[datetime] = Query(None, description="Bitiş tarihi"),
    _: Dict[str, Any] = Depends(get_current_user),
    sube_id: Optional[int] = Depends(get_sube_id),
):
    """
    Audit log istatistiklerini getir

    **Yetkiler:** super_admin, admin

    **Dönen Veriler:**
    - Toplam işlem sayısı
    - Başarılı/başarısız işlem sayısı
    - En aktif kullanıcılar (top 10)
    - En çok yapılan işlemler (top 10)

    **Örnek:**
    ```
    GET /audit/statistics
    GET /audit/statistics?start_date=2025-01-01T00:00:00&end_date=2025-01-31T23:59:59
    ```
    """
    stats = await audit_service.get_statistics(
        sube_id=sube_id,
        start_date=start_date,
        end_date=end_date,
    )
    return stats
