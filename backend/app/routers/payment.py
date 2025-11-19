from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from ..core.deps import require_roles, get_current_user
from ..db.database import db

router = APIRouter(
    prefix="/payment",
    tags=["Payment"],
    dependencies=[Depends(require_roles({"super_admin"}))],
)


# --------- Modeller ---------
class PaymentIn(BaseModel):
    isletme_id: int = Field(gt=0)
    subscription_id: Optional[int] = None
    tutar: float = Field(gt=0)
    odeme_turu: str = Field(default="odeme_sistemi")  # nakit, kredi_karti, havale, odeme_sistemi
    durum: str = Field(default="pending")  # pending, completed, failed, refunded
    fatura_no: Optional[str] = None
    aciklama: Optional[str] = None
    odeme_tarihi: Optional[datetime] = None


class PaymentOut(PaymentIn):
    id: int
    created_at: datetime
    updated_at: datetime


class PaymentStatusUpdate(BaseModel):
    durum: str  # pending, completed, failed, refunded
    odeme_tarihi: Optional[datetime] = None


@router.get("/list")
async def list_payments(
    isletme_id: Optional[int] = Query(None, description="İşletme ID ile filtrele"),
    subscription_id: Optional[int] = Query(None, description="Abonelik ID ile filtrele"),
    durum: Optional[str] = Query(None, description="Durum ile filtrele"),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Tüm ödemeleri listele (işletme adı ile birlikte)"""
    query = """
        SELECT p.id, p.isletme_id, COALESCE(i.ad, 'Bilinmeyen İşletme') as isletme_ad, p.subscription_id, 
               p.tutar, p.odeme_turu, p.durum, p.fatura_no, p.aciklama, 
               p.odeme_tarihi, p.created_at, p.updated_at
        FROM payments p
        LEFT JOIN isletmeler i ON p.isletme_id = i.id
        WHERE 1=1
    """
    params = {}
    
    if isletme_id:
        query += " AND p.isletme_id = :isletme_id"
        params["isletme_id"] = isletme_id
    
    if subscription_id:
        query += " AND p.subscription_id = :subscription_id"
        params["subscription_id"] = subscription_id
    
    if durum:
        query += " AND p.durum = :durum"
        params["durum"] = durum
    
    query += " ORDER BY p.created_at DESC"
    
    rows = await db.fetch_all(query, params)
    return [dict(row) for row in rows]


@router.get("/{payment_id}", response_model=PaymentOut)
async def get_payment(
    payment_id: int,
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Ödeme detayını getir"""
    row = await db.fetch_one(
        """
        SELECT id, isletme_id, subscription_id, tutar, odeme_turu, durum,
               fatura_no, aciklama, odeme_tarihi, created_at, updated_at
        FROM payments
        WHERE id = :id
        """,
        {"id": payment_id},
    )
    if not row:
        raise HTTPException(404, "Ödeme bulunamadı")
    return dict(row)


@router.post("/create", response_model=PaymentOut)
async def create_payment(
    payload: PaymentIn,
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Yeni ödeme kaydı oluştur"""
    # İşletme kontrolü
    isletme = await db.fetch_one(
        "SELECT id FROM isletmeler WHERE id = :id",
        {"id": payload.isletme_id},
    )
    if not isletme:
        raise HTTPException(404, "İşletme bulunamadı")
    
    # Abonelik kontrolü (varsa)
    if payload.subscription_id:
        sub = await db.fetch_one(
            "SELECT id FROM subscriptions WHERE id = :id",
            {"id": payload.subscription_id},
        )
        if not sub:
            raise HTTPException(404, "Abonelik bulunamadı")
    
    data = payload.model_dump()
    if not data.get("odeme_tarihi") and data["durum"] == "completed":
        data["odeme_tarihi"] = datetime.utcnow()
    
    row = await db.fetch_one(
        """
        INSERT INTO payments (
            isletme_id, subscription_id, tutar, odeme_turu, durum,
            fatura_no, aciklama, odeme_tarihi
        )
        VALUES (
            :isletme_id, :subscription_id, :tutar, :odeme_turu, :durum,
            :fatura_no, :aciklama, :odeme_tarihi
        )
        RETURNING id, isletme_id, subscription_id, tutar, odeme_turu, durum,
                  fatura_no, aciklama, odeme_tarihi, created_at, updated_at
        """,
        data,
    )
    return dict(row)


@router.patch("/{payment_id}/status", response_model=PaymentOut)
async def update_payment_status(
    payment_id: int,
    payload: PaymentStatusUpdate,
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Ödeme durumunu güncelle"""
    existing = await db.fetch_one(
        "SELECT id FROM payments WHERE id = :id",
        {"id": payment_id},
    )
    if not existing:
        raise HTTPException(404, "Ödeme bulunamadı")
    
    data = {
        "id": payment_id,
        "durum": payload.durum,
        "odeme_tarihi": payload.odeme_tarihi or (datetime.utcnow() if payload.durum == "completed" else None),
        "updated_at": datetime.utcnow(),
    }
    
    row = await db.fetch_one(
        """
        UPDATE payments
        SET durum = :durum, odeme_tarihi = :odeme_tarihi, updated_at = :updated_at
        WHERE id = :id
        RETURNING id, isletme_id, subscription_id, tutar, odeme_turu, durum,
                  fatura_no, aciklama, odeme_tarihi, created_at, updated_at
        """,
        data,
    )
    return dict(row)


@router.get("/isletme/{isletme_id}/summary")
async def get_payment_summary(
    isletme_id: int,
    _: Dict[str, Any] = Depends(get_current_user),
):
    """İşletmenin ödeme özetini getir"""
    # Toplam ödeme
    total = await db.fetch_one(
        """
        SELECT COALESCE(SUM(tutar), 0) as total
        FROM payments
        WHERE isletme_id = :id AND durum = 'completed'
        """,
        {"id": isletme_id},
    )
    
    # Bu ay ödeme
    this_month = await db.fetch_one(
        """
        SELECT COALESCE(SUM(tutar), 0) as total
        FROM payments
        WHERE isletme_id = :id 
          AND durum = 'completed'
          AND DATE_TRUNC('month', odeme_tarihi) = DATE_TRUNC('month', CURRENT_DATE)
        """,
        {"id": isletme_id},
    )
    
    # Bekleyen ödemeler
    pending = await db.fetch_one(
        """
        SELECT COALESCE(SUM(tutar), 0) as total, COUNT(*) as count
        FROM payments
        WHERE isletme_id = :id AND durum = 'pending'
        """,
        {"id": isletme_id},
    )
    
    # Son ödemeler
    recent = await db.fetch_all(
        """
        SELECT id, tutar, odeme_turu, durum, odeme_tarihi, created_at
        FROM payments
        WHERE isletme_id = :id
        ORDER BY created_at DESC
        LIMIT 10
        """,
        {"id": isletme_id},
    )
    
    return {
        "total_paid": float(total["total"]) if total else 0.0,
        "this_month": float(this_month["total"]) if this_month else 0.0,
        "pending": {
            "total": float(pending["total"]) if pending else 0.0,
            "count": pending["count"] if pending else 0,
        },
        "recent_payments": [dict(r) for r in recent],
    }


