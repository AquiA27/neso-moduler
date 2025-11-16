# backend/app/routers/masalar.py
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid

from ..core.deps import get_current_user, get_sube_id, require_roles
from ..db.database import db

router = APIRouter(prefix="/masalar", tags=["Masalar"])

# ---------- Modeller ----------
class MasaItemIn(BaseModel):
    masa_adi: str = Field(min_length=1)
    kapasite: int = Field(default=4, ge=1, le=20)
    pozisyon_x: Optional[float] = None
    pozisyon_y: Optional[float] = None

class MasaItemOut(BaseModel):
    id: int
    masa_adi: str
    qr_code: Optional[str]
    durum: str
    kapasite: int
    pozisyon_x: Optional[float]
    pozisyon_y: Optional[float]
    created_at: str

class MasaUpdateIn(BaseModel):
    id: int
    masa_adi: Optional[str] = None
    durum: Optional[str] = None
    kapasite: Optional[int] = Field(default=None, ge=1, le=20)
    pozisyon_x: Optional[float] = None
    pozisyon_y: Optional[float] = None

# ---------- Uçlar ----------
@router.post(
    "/ekle",
    response_model=MasaItemOut,
    dependencies=[Depends(require_roles({"admin", "operator"}))]
)
async def masa_ekle(
    item: MasaItemIn,
    _: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """Yeni masa ekle, otomatik QR kod oluştur"""
    qr_code = f"MAS_{sube_id}_{uuid.uuid4().hex[:12].upper()}"
    params = {
        **item.model_dump(),
        "sid": sube_id,
        "qr_code": qr_code
    }
    
    row = await db.fetch_one(
        """
        INSERT INTO masalar (sube_id, masa_adi, qr_code, kapasite, pozisyon_x, pozisyon_y)
        VALUES (:sid, :masa_adi, :qr_code, :kapasite, :pozisyon_x, :pozisyon_y)
        RETURNING id, masa_adi, qr_code, durum, kapasite, pozisyon_x, pozisyon_y, created_at
        """,
        params,
    )
    
    if not row:
        raise HTTPException(status_code=500, detail="Masa eklenemedi")
    
    return {
        "id": row["id"],
        "masa_adi": row["masa_adi"],
        "qr_code": row["qr_code"],
        "durum": row["durum"],
        "kapasite": row["kapasite"],
        "pozisyon_x": float(row["pozisyon_x"]) if row["pozisyon_x"] else None,
        "pozisyon_y": float(row["pozisyon_y"]) if row["pozisyon_y"] else None,
        "created_at": row["created_at"].isoformat(),
    }


@router.get("/liste", response_model=List[MasaItemOut])
async def masa_liste(
    _: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """Masaları listele"""
    rows = await db.fetch_all(
        """
        SELECT id, masa_adi, qr_code, durum, kapasite, pozisyon_x, pozisyon_y, created_at
        FROM masalar
        WHERE sube_id = :sid
        ORDER BY masa_adi
        """,
        {"sid": sube_id},
    )
    
    return [
        {
            "id": row["id"],
            "masa_adi": row["masa_adi"],
            "qr_code": row["qr_code"],
            "durum": row["durum"],
            "kapasite": row["kapasite"],
            "pozisyon_x": float(row["pozisyon_x"]) if row["pozisyon_x"] else None,
            "pozisyon_y": float(row["pozisyon_y"]) if row["pozisyon_y"] else None,
            "created_at": row["created_at"].isoformat(),
        }
        for row in rows
    ]


@router.patch("/guncelle", response_model=MasaItemOut)
async def masa_guncelle(
    payload: MasaUpdateIn,
    _: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """Masa bilgilerini güncelle"""
    existing = await db.fetch_one(
        """
        SELECT id, masa_adi, qr_code, durum, kapasite, pozisyon_x, pozisyon_y, created_at
        FROM masalar
        WHERE sube_id = :sid AND id = :id
        """,
        {"sid": sube_id, "id": payload.id},
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Masa bulunamadı")

    updates = {}
    if payload.masa_adi is not None:
        updates["masa_adi"] = payload.masa_adi
    if payload.durum is not None:
        updates["durum"] = payload.durum
    if payload.kapasite is not None:
        updates["kapasite"] = payload.kapasite
    if payload.pozisyon_x is not None:
        updates["pozisyon_x"] = payload.pozisyon_x
    if payload.pozisyon_y is not None:
        updates["pozisyon_y"] = payload.pozisyon_y
    
    if updates:
        updates["updated_at"] = "NOW()"
        set_clause = ", ".join([f"{k} = :{k}" for k in updates.keys()])
        query = f"""
            UPDATE masalar
            SET {set_clause.replace(':updated_at', 'NOW()')}
            WHERE sube_id = :sid AND id = :id
            RETURNING id, masa_adi, qr_code, durum, kapasite, pozisyon_x, pozisyon_y, created_at
        """
        params = {**updates, "sid": sube_id, "id": payload.id}
        del params["updated_at"]
        row = await db.fetch_one(query, params)
        if not row:
            raise HTTPException(status_code=400, detail="Güncelleme başarısız")
    else:
        row = existing

    return {
        "id": row["id"],
        "masa_adi": row["masa_adi"],
        "qr_code": row["qr_code"],
        "durum": row["durum"],
        "kapasite": row["kapasite"],
        "pozisyon_x": float(row["pozisyon_x"]) if row["pozisyon_x"] else None,
        "pozisyon_y": float(row["pozisyon_y"]) if row["pozisyon_y"] else None,
        "created_at": row["created_at"].isoformat(),
    }


@router.delete("/sil/{masa_id}")
async def masa_sil(
    masa_id: int,
    _: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """Masa sil"""
    existing = await db.fetch_one(
        "SELECT id FROM masalar WHERE sube_id = :sid AND id = :id",
        {"sid": sube_id, "id": masa_id},
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Masa bulunamadı")
    
    await db.execute(
        "DELETE FROM masalar WHERE sube_id = :sid AND id = :id",
        {"sid": sube_id, "id": masa_id},
    )
    
    return {"success": True, "message": "Masa silindi"}


