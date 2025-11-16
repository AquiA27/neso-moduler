# backend/app/routers/backup.py
"""
Yedekleme Router
Database backup ve restore işlemleri
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from ..core.deps import get_current_user, require_roles
from ..services.backup import backup_service
from ..services.audit import audit_service

router = APIRouter(prefix="/system/backup", tags=["Backup"])


class BackupHistoryOut(BaseModel):
    """Yedekleme geçmişi modeli"""
    id: int
    backup_type: str
    file_path: str
    file_size_bytes: Optional[int]
    file_size_mb: Optional[float]
    status: str
    error_message: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    created_by: Optional[str]
    duration_seconds: Optional[float]


class BackupCreateOut(BaseModel):
    """Yedekleme oluşturma sonucu"""
    success: bool
    backup_id: Optional[int] = None
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    filename: Optional[str] = None
    error: Optional[str] = None


class RestoreOut(BaseModel):
    """Restore sonucu"""
    success: bool
    backup_id: Optional[int] = None
    restored_from: Optional[str] = None
    error: Optional[str] = None


@router.post(
    "/create",
    response_model=BackupCreateOut,
    dependencies=[Depends(require_roles({"super_admin"}))],
)
async def create_backup(
    background_tasks: BackgroundTasks,
    backup_type: str = "full",
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Manuel veritabanı yedeği oluştur

    **Yetkiler:** super_admin

    **Parametreler:**
    - backup_type: 'full' (tam yedek) veya 'incremental' (artımlı)

    **Not:** Yedekleme arka planda çalışır. Durum için /system/backup/history endpoint'ini kullanın.

    **Örnek:**
    ```
    POST /system/backup/create?backup_type=full
    ```
    """
    username = user.get("username", "unknown")

    # Audit log
    await audit_service.log_action(
        action="backup.create",
        username=username,
        user_id=user.get("id"),
        entity_type="backup",
        success=True,
    )

    # Arka planda yedekleme başlat
    result = await backup_service.create_backup(
        backup_type=backup_type,
        created_by=username,
    )

    return result


@router.get(
    "/history",
    response_model=List[BackupHistoryOut],
    dependencies=[Depends(require_roles({"super_admin", "admin"}))],
)
async def get_backup_history(
    limit: int = 100,
    status: Optional[str] = None,
    _: Dict[str, Any] = Depends(get_current_user),
):
    """
    Yedekleme geçmişini listele

    **Yetkiler:** super_admin, admin

    **Parametreler:**
    - limit: Maksimum kayıt sayısı (varsayılan: 100)
    - status: Durum filtresi ('success', 'failed', 'in_progress')

    **Örnek:**
    ```
    GET /system/backup/history?status=success&limit=50
    ```
    """
    history = await backup_service.get_backup_history(limit=limit, status=status)
    return history


@router.post(
    "/restore/{backup_id}",
    response_model=RestoreOut,
    dependencies=[Depends(require_roles({"super_admin"}))],
)
async def restore_backup(
    backup_id: int,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Yedekten geri yükle (DANGEROUS!)

    **Yetkiler:** super_admin

    ⚠️ **UYARI:** Bu işlem mevcut veritabanını tamamen değiştirir. Geri alınamaz!

    **Parametreler:**
    - backup_id: Yedekleme ID (backup history'den alınır)

    **Örnek:**
    ```
    POST /system/backup/restore/123
    ```
    """
    username = user.get("username", "unknown")

    # Audit log (restore işlemi)
    await audit_service.log_action(
        action="backup.restore",
        username=username,
        user_id=user.get("id"),
        entity_type="backup",
        entity_id=backup_id,
        success=False,  # Başlangıçta başarısız, sonra güncellenecek
    )

    # Restore işlemi
    result = await backup_service.restore_backup(backup_id=backup_id)

    # Audit log güncelle
    if result["success"]:
        await audit_service.log_action(
            action="backup.restore_success",
            username=username,
            user_id=user.get("id"),
            entity_type="backup",
            entity_id=backup_id,
            success=True,
        )
    else:
        await audit_service.log_action(
            action="backup.restore_failed",
            username=username,
            user_id=user.get("id"),
            entity_type="backup",
            entity_id=backup_id,
            success=False,
            error_message=result.get("error"),
        )

    return result
