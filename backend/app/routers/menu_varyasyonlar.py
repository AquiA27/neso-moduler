# backend/app/routers/menu_varyasyonlar.py
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from ..core.deps import get_current_user, get_sube_id, require_roles
from ..db.database import db

router = APIRouter(prefix="/menu-varyasyonlar", tags=["Menu Varyasyonlar"])

# ---------- Modeller ----------
class VaryasyonItemIn(BaseModel):
    menu_id: int
    ad: str = Field(min_length=1)
    ek_fiyat: float = Field(default=0.0)
    sira: int = Field(default=0)
    aktif: bool = True

class VaryasyonItemOut(BaseModel):
    id: int
    menu_id: int
    ad: str
    ek_fiyat: float
    sira: int
    aktif: bool
    created_at: str

class VaryasyonUpdateIn(BaseModel):
    id: int
    ad: Optional[str] = None
    ek_fiyat: Optional[float] = None
    sira: Optional[int] = None
    aktif: Optional[bool] = None

# ---------- Uçlar ----------
@router.post(
    "/ekle",
    response_model=VaryasyonItemOut,
    dependencies=[Depends(require_roles({"admin", "operator"}))]
)
async def varyasyon_ekle(
    item: VaryasyonItemIn,
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Yeni menü varyasyonu ekle"""
    # Menu ID'nin geçerli olduğunu kontrol et
    menu = await db.fetch_one(
        "SELECT id FROM menu WHERE id = :mid",
        {"mid": item.menu_id}
    )
    if not menu:
        raise HTTPException(status_code=404, detail="Menü bulunamadı")
    
    params = item.model_dump()
    
    row = await db.fetch_one(
        """
        INSERT INTO menu_varyasyonlar (menu_id, ad, ek_fiyat, sira, aktif)
        VALUES (:menu_id, :ad, :ek_fiyat, :sira, :aktif)
        RETURNING id, menu_id, ad, ek_fiyat, sira, aktif, created_at
        """,
        params,
    )
    
    if not row:
        raise HTTPException(status_code=500, detail="Varyasyon eklenemedi")
    
    return {
        "id": row["id"],
        "menu_id": row["menu_id"],
        "ad": row["ad"],
        "ek_fiyat": float(row["ek_fiyat"]),
        "sira": row["sira"],
        "aktif": row["aktif"],
        "created_at": row["created_at"].isoformat(),
    }


@router.get("/liste", response_model=List[VaryasyonItemOut])
async def varyasyon_liste(
    menu_id: Optional[int] = Query(None, description="Menu ID'ye göre filtrele"),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Varyasyonları listele"""
    if menu_id:
        rows = await db.fetch_all(
            """
            SELECT id, menu_id, ad, ek_fiyat, sira, aktif, created_at
            FROM menu_varyasyonlar
            WHERE menu_id = :mid
            ORDER BY sira ASC, ad ASC
            """,
            {"mid": menu_id},
        )
    else:
        rows = await db.fetch_all(
            """
            SELECT id, menu_id, ad, ek_fiyat, sira, aktif, created_at
            FROM menu_varyasyonlar
            ORDER BY menu_id, sira ASC, ad ASC
            """,
        )
    
    return [
        {
            "id": row["id"],
            "menu_id": row["menu_id"],
            "ad": row["ad"],
            "ek_fiyat": float(row["ek_fiyat"]),
            "sira": row["sira"],
            "aktif": row["aktif"],
            "created_at": row["created_at"].isoformat(),
        }
        for row in rows
    ]


@router.patch("/guncelle", response_model=VaryasyonItemOut)
async def varyasyon_guncelle(
    payload: VaryasyonUpdateIn,
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Varyasyon bilgilerini güncelle"""
    existing = await db.fetch_one(
        "SELECT id FROM menu_varyasyonlar WHERE id = :id",
        {"id": payload.id}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Varyasyon bulunamadı")
    
    updates = {}
    if payload.ad is not None:
        updates["ad"] = payload.ad
    if payload.ek_fiyat is not None:
        updates["ek_fiyat"] = payload.ek_fiyat
    if payload.sira is not None:
        updates["sira"] = payload.sira
    if payload.aktif is not None:
        updates["aktif"] = payload.aktif
    
    if not updates:
        # Hiçbir şey güncellenmemişse mevcut kaydı döndür
        row = await db.fetch_one(
            "SELECT id, menu_id, ad, ek_fiyat, sira, aktif, created_at FROM menu_varyasyonlar WHERE id = :id",
            {"id": payload.id}
        )
    else:
        set_clause = ", ".join([f"{k} = :{k}" for k in updates.keys()])
        query = f"""
            UPDATE menu_varyasyonlar
            SET {set_clause}
            WHERE id = :id
            RETURNING id, menu_id, ad, ek_fiyat, sira, aktif, created_at
        """
        params = {**updates, "id": payload.id}
        row = await db.fetch_one(query, params)
    
    if not row:
        raise HTTPException(status_code=400, detail="Güncelleme başarısız")
    
    return {
        "id": row["id"],
        "menu_id": row["menu_id"],
        "ad": row["ad"],
        "ek_fiyat": float(row["ek_fiyat"]),
        "sira": row["sira"],
        "aktif": row["aktif"],
        "created_at": row["created_at"].isoformat(),
    }


@router.delete("/sil/{varyasyon_id}")
async def varyasyon_sil(
    varyasyon_id: int,
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Varyasyon sil"""
    existing = await db.fetch_one(
        "SELECT id FROM menu_varyasyonlar WHERE id = :id",
        {"id": varyasyon_id}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Varyasyon bulunamadı")
    
    await db.execute(
        "DELETE FROM menu_varyasyonlar WHERE id = :id",
        {"id": varyasyon_id}
    )
    
    return {"success": True, "message": "Varyasyon silindi"}


