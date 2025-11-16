# backend/app/routers/giderler.py
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import date, datetime

from ..core.deps import get_current_user, get_sube_id, require_roles
from ..db.database import db

router = APIRouter(prefix="/giderler", tags=["Giderler"])

# ---------- Modeller ----------
class GiderItemIn(BaseModel):
    kategori: str = Field(min_length=1)
    aciklama: Optional[str] = None
    tutar: float = Field(gt=0)
    tarih: date
    fatura_no: Optional[str] = None

class GiderItemOut(BaseModel):
    id: int
    kategori: str
    aciklama: Optional[str]
    tutar: float
    tarih: date
    fatura_no: Optional[str]
    created_at: datetime

class GiderUpdateIn(BaseModel):
    id: int
    kategori: Optional[str] = None
    aciklama: Optional[str] = None
    tutar: Optional[float] = Field(default=None, gt=0)
    tarih: Optional[date] = None
    fatura_no: Optional[str] = None

# ---------- Uçlar ----------
@router.post(
    "/ekle",
    response_model=GiderItemOut,
    dependencies=[Depends(require_roles({"admin", "operator"}))]
)
async def gider_ekle(
    item: GiderItemIn,
    user: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """
    Yeni gider ekle.
    """
    params = {
        "sid": sube_id,
        "kategori": item.kategori,
        "aciklama": item.aciklama,
        "tutar": item.tutar,
        "tarih": item.tarih,
        "fatura_no": item.fatura_no,
        "user_id": user.get("id")
    }
    
    row = await db.fetch_one(
        """
        INSERT INTO giderler (sube_id, kategori, aciklama, tutar, tarih, fatura_no, created_by_user_id)
        VALUES (:sid, :kategori, :aciklama, :tutar, :tarih, :fatura_no, :user_id)
        RETURNING id, kategori, aciklama, tutar, tarih, fatura_no, created_at
        """,
        params,
    )
    
    if not row:
        raise HTTPException(status_code=500, detail="Gider eklenemedi")
    
    return {
        "id": row["id"],
        "kategori": row["kategori"],
        "aciklama": row["aciklama"],
        "tutar": float(row["tutar"]),
        "tarih": row["tarih"],
        "fatura_no": row["fatura_no"],
        "created_at": row["created_at"]
    }


@router.get(
    "/liste",
    response_model=List[GiderItemOut],
    dependencies=[Depends(require_roles({"admin", "operator"}))]
)
async def gider_liste(
    baslangic_tarih: Optional[date] = None,
    bitis_tarih: Optional[date] = None,
    kategori: Optional[str] = None,
    _: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """
    Giderleri listele. Tarih aralığı ve kategori ile filtreleme yapılabilir.
    """
    # SQL sorgusu dinamik oluştur
    query = """
        SELECT id, kategori, aciklama, tutar, tarih, fatura_no, created_at
        FROM giderler
        WHERE sube_id = :sid
    """
    params = {"sid": sube_id}
    
    if baslangic_tarih:
        query += " AND tarih >= :baslangic"
        params["baslangic"] = baslangic_tarih
    
    if bitis_tarih:
        query += " AND tarih <= :bitis"
        params["bitis"] = bitis_tarih
    
    if kategori:
        query += " AND LOWER(kategori) = LOWER(:kategori)"
        params["kategori"] = kategori
    
    query += " ORDER BY tarih DESC, created_at DESC"
    
    rows = await db.fetch_all(query, params)
    
    return [
        {
            "id": row["id"],
            "kategori": row["kategori"],
            "aciklama": row["aciklama"],
            "tutar": float(row["tutar"]),
            "tarih": row["tarih"],
            "fatura_no": row["fatura_no"],
            "created_at": row["created_at"]
        }
        for row in rows
    ]


@router.patch(
    "/guncelle",
    response_model=GiderItemOut,
    dependencies=[Depends(require_roles({"admin", "operator"}))]
)
async def gider_guncelle(
    payload: GiderUpdateIn,
    _: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """
    Mevcut gideri güncelle.
    """
    # Önce mevcut kaydı bul
    existing = await db.fetch_one(
        """
        SELECT id, kategori, aciklama, tutar, tarih, fatura_no, created_at
        FROM giderler
        WHERE sube_id = :sid AND id = :id
        """,
        {"sid": sube_id, "id": payload.id},
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Gider bulunamadı")

    # Güncelleme parametrelerini hazırla
    updates = {}
    if payload.kategori is not None:
        updates["kategori"] = payload.kategori
    if payload.aciklama is not None:
        updates["aciklama"] = payload.aciklama
    if payload.tutar is not None:
        updates["tutar"] = payload.tutar
    if payload.tarih is not None:
        updates["tarih"] = payload.tarih
    if payload.fatura_no is not None:
        updates["fatura_no"] = payload.fatura_no

    if not updates:
        # Hiçbir şey güncellenmemişse mevcut kaydı döndür
        return {
            "id": existing["id"],
            "kategori": existing["kategori"],
            "aciklama": existing["aciklama"],
            "tutar": float(existing["tutar"]),
            "tarih": existing["tarih"],
            "fatura_no": existing["fatura_no"],
            "created_at": existing["created_at"]
        }

    # UPDATE yap
    set_clause = ", ".join([f"{k} = :{k}" for k in updates.keys()])
    query = f"""
        UPDATE giderler
        SET {set_clause}
        WHERE sube_id = :sid AND id = :id
        RETURNING id, kategori, aciklama, tutar, tarih, fatura_no, created_at
    """
    params = {**updates, "sid": sube_id, "id": payload.id}
    row = await db.fetch_one(query, params)
    if not row:
        raise HTTPException(status_code=400, detail="Güncelleme başarısız")

    return {
        "id": row["id"],
        "kategori": row["kategori"],
        "aciklama": row["aciklama"],
        "tutar": float(row["tutar"]),
        "tarih": row["tarih"],
        "fatura_no": row["fatura_no"],
        "created_at": row["created_at"]
    }


@router.delete(
    "/sil/{gider_id}",
    dependencies=[Depends(require_roles({"admin"}))]
)
async def gider_sil(
    gider_id: int,
    _: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """
    Gideri sil (sadece admin).
    """
    # Önce mevcut kaydı kontrol et
    existing = await db.fetch_one(
        """
        SELECT id FROM giderler
        WHERE sube_id = :sid AND id = :id
        """,
        {"sid": sube_id, "id": gider_id},
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Gider bulunamadı")
    
    # Sil
    await db.execute(
        """
        DELETE FROM giderler
        WHERE sube_id = :sid AND id = :id
        """,
        {"sid": sube_id, "id": gider_id},
    )
    
    return {"success": True, "message": "Gider silindi"}


@router.get(
    "/kategoriler",
    response_model=List[str],
    dependencies=[Depends(require_roles({"admin", "operator"}))]
)
async def gider_kategoriler(
    _: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """
    Kullanılan kategorileri listele.
    """
    rows = await db.fetch_all(
        """
        SELECT DISTINCT kategori
        FROM giderler
        WHERE sube_id = :sid
        ORDER BY kategori
        """,
        {"sid": sube_id}
    )
    
    return [row["kategori"] for row in rows]

