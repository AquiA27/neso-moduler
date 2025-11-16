# backend/app/routers/cache.py
"""
Cache Management Router
Cache istatistiklerini görüntüleme ve yönetim endpoint'leri
"""
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from ..services.cache import cache_service
from ..core.deps import get_current_user

router = APIRouter(prefix="/cache", tags=["Cache Management"])


@router.get("/stats")
async def get_cache_stats(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Cache istatistiklerini getir

    **Gerekli Rol:** admin, superadmin

    **Döndürülen bilgiler:**
    - enabled: Cache aktif mi?
    - connected_clients: Bağlı client sayısı
    - used_memory_human: Kullanılan bellek
    - total_keys: Toplam key sayısı
    - hit_rate: Cache hit oranı (0-1 arası)
    """
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")

    stats = await cache_service.get_stats()
    return {
        "success": True,
        "data": stats
    }


@router.post("/clear")
async def clear_cache(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Tüm cache'i temizle

    **Gerekli Rol:** superadmin

    **Uyarı:** Bu işlem tüm cache'i siler, dikkatli kullanın!
    """
    if current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Bu işlem için superadmin yetkisi gerekli")

    success = await cache_service.clear_all()

    if not success:
        raise HTTPException(status_code=500, detail="Cache temizlenirken hata oluştu")

    return {
        "success": True,
        "message": "Tüm cache temizlendi"
    }


@router.delete("/key/{key}")
async def delete_cache_key(
    key: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Belirli bir cache key'ini sil

    **Gerekli Rol:** admin, superadmin
    """
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")

    success = await cache_service.delete(key)

    if not success:
        raise HTTPException(status_code=404, detail="Key bulunamadı veya silinemedi")

    return {
        "success": True,
        "message": f"Key '{key}' silindi"
    }


@router.delete("/pattern/{pattern}")
async def delete_cache_pattern(
    pattern: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Pattern ile eşleşen cache key'lerini sil

    **Gerekli Rol:** admin, superadmin

    **Örnek pattern'ler:**
    - menu:* (tüm menu cache'lerini sil)
    - analytics:* (tüm analytics cache'lerini sil)
    - tenant:123:* (belirli bir tenant'ın tüm cache'lerini sil)
    """
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")

    deleted_count = await cache_service.delete_pattern(pattern)

    return {
        "success": True,
        "message": f"{deleted_count} adet key silindi",
        "deleted_count": deleted_count
    }


@router.get("/health")
async def cache_health():
    """
    Cache sağlık kontrolü (public endpoint)

    Cache'in aktif ve çalışır durumda olup olmadığını kontrol eder
    """
    is_enabled = cache_service.is_enabled()

    return {
        "success": True,
        "cache_enabled": is_enabled,
        "status": "healthy" if is_enabled else "disabled"
    }
