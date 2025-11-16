from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from ..core.deps import require_roles, get_current_user
from ..db.database import db

router = APIRouter(
    prefix="/subscription",
    tags=["Subscription"],
    dependencies=[Depends(require_roles({"super_admin"}))],
)


# --------- Modeller ---------
class SubscriptionIn(BaseModel):
    isletme_id: int = Field(gt=0)
    plan_type: str = Field(default="basic")  # basic, pro, enterprise
    status: str = Field(default="active")  # active, suspended, cancelled, trial
    max_subeler: int = Field(default=1, ge=1)
    max_kullanicilar: int = Field(default=5, ge=1)
    max_menu_items: int = Field(default=100, ge=10)
    ayllik_fiyat: float = Field(default=0.0, ge=0)
    trial_baslangic: Optional[datetime] = None
    trial_bitis: Optional[datetime] = None
    baslangic_tarihi: Optional[datetime] = None
    bitis_tarihi: Optional[datetime] = None
    otomatik_yenileme: bool = True


class SubscriptionOut(SubscriptionIn):
    id: int
    created_at: datetime
    updated_at: datetime


class SubscriptionStatusUpdate(BaseModel):
    status: str  # active, suspended, cancelled
    bitis_tarihi: Optional[datetime] = None


@router.get("/list", response_model=List[SubscriptionOut])
async def list_subscriptions(
    isletme_id: Optional[int] = Query(None, description="İşletme ID ile filtrele"),
    status: Optional[str] = Query(None, description="Durum ile filtrele"),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Tüm abonelikleri listele"""
    query = """
        SELECT id, isletme_id, plan_type, status, max_subeler, max_kullanicilar,
               max_menu_items, ayllik_fiyat, trial_baslangic, trial_bitis,
               baslangic_tarihi, bitis_tarihi, otomatik_yenileme, created_at, updated_at
        FROM subscriptions
        WHERE 1=1
    """
    params = {}
    
    if isletme_id:
        query += " AND isletme_id = :isletme_id"
        params["isletme_id"] = isletme_id
    
    if status:
        query += " AND status = :status"
        params["status"] = status
    
    query += " ORDER BY created_at DESC"
    
    rows = await db.fetch_all(query, params)
    return [dict(row) for row in rows]


@router.get("/{isletme_id}", response_model=SubscriptionOut)
async def get_subscription(
    isletme_id: int,
    _: Dict[str, Any] = Depends(get_current_user),
):
    """İşletme aboneliğini getir"""
    row = await db.fetch_one(
        """
        SELECT id, isletme_id, plan_type, status, max_subeler, max_kullanicilar,
               max_menu_items, ayllik_fiyat, trial_baslangic, trial_bitis,
               baslangic_tarihi, bitis_tarihi, otomatik_yenileme, created_at, updated_at
        FROM subscriptions
        WHERE isletme_id = :isletme_id
        """,
        {"isletme_id": isletme_id},
    )
    if not row:
        raise HTTPException(404, "Abonelik bulunamadı")
    return dict(row)


@router.post("/create", response_model=SubscriptionOut)
async def create_subscription(
    payload: SubscriptionIn,
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Yeni abonelik oluştur"""
    # İşletme kontrolü
    isletme = await db.fetch_one(
        "SELECT id FROM isletmeler WHERE id = :id",
        {"id": payload.isletme_id},
    )
    if not isletme:
        raise HTTPException(404, "İşletme bulunamadı")
    
    # Mevcut abonelik kontrolü
    existing = await db.fetch_one(
        "SELECT id FROM subscriptions WHERE isletme_id = :id",
        {"id": payload.isletme_id},
    )
    if existing:
        raise HTTPException(400, "Bu işletme için zaten bir abonelik mevcut")
    
    # Varsayılan değerler
    baslangic = payload.baslangic_tarihi or datetime.utcnow()
    data = payload.model_dump()
    data["baslangic_tarihi"] = baslangic
    
    row = await db.fetch_one(
        """
        INSERT INTO subscriptions (
            isletme_id, plan_type, status, max_subeler, max_kullanicilar,
            max_menu_items, ayllik_fiyat, trial_baslangic, trial_bitis,
            baslangic_tarihi, bitis_tarihi, otomatik_yenileme
        )
        VALUES (
            :isletme_id, :plan_type, :status, :max_subeler, :max_kullanicilar,
            :max_menu_items, :ayllik_fiyat, :trial_baslangic, :trial_bitis,
            :baslangic_tarihi, :bitis_tarihi, :otomatik_yenileme
        )
        RETURNING id, isletme_id, plan_type, status, max_subeler, max_kullanicilar,
                  max_menu_items, ayllik_fiyat, trial_baslangic, trial_bitis,
                  baslangic_tarihi, bitis_tarihi, otomatik_yenileme, created_at, updated_at
        """,
        data,
    )
    return dict(row)


@router.patch("/{isletme_id}", response_model=SubscriptionOut)
async def update_subscription(
    isletme_id: int,
    payload: SubscriptionIn,
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Abonelik güncelle"""
    existing = await db.fetch_one(
        "SELECT id FROM subscriptions WHERE isletme_id = :id",
        {"id": isletme_id},
    )
    if not existing:
        raise HTTPException(404, "Abonelik bulunamadı")
    
    data = payload.model_dump(exclude={"isletme_id"})
    data["isletme_id"] = isletme_id
    data["updated_at"] = datetime.utcnow()
    
    row = await db.fetch_one(
        """
        UPDATE subscriptions
        SET plan_type = :plan_type, status = :status,
            max_subeler = :max_subeler, max_kullanicilar = :max_kullanicilar,
            max_menu_items = :max_menu_items, ayllik_fiyat = :ayllik_fiyat,
            trial_baslangic = :trial_baslangic, trial_bitis = :trial_bitis,
            baslangic_tarihi = :baslangic_tarihi, bitis_tarihi = :bitis_tarihi,
            otomatik_yenileme = :otomatik_yenileme, updated_at = :updated_at
        WHERE isletme_id = :isletme_id
        RETURNING id, isletme_id, plan_type, status, max_subeler, max_kullanicilar,
                  max_menu_items, ayllik_fiyat, trial_baslangic, trial_bitis,
                  baslangic_tarihi, bitis_tarihi, otomatik_yenileme, created_at, updated_at
        """,
        data,
    )
    return dict(row)


@router.patch("/{isletme_id}/status", response_model=SubscriptionOut)
async def update_subscription_status(
    isletme_id: int,
    payload: SubscriptionStatusUpdate,
    _: Dict[str, Any] = Depends(get_current_user),
):
    """Abonelik durumunu güncelle"""
    existing = await db.fetch_one(
        "SELECT id FROM subscriptions WHERE isletme_id = :id",
        {"id": isletme_id},
    )
    if not existing:
        raise HTTPException(404, "Abonelik bulunamadı")
    
    data = {
        "isletme_id": isletme_id,
        "status": payload.status,
        "bitis_tarihi": payload.bitis_tarihi,
        "updated_at": datetime.utcnow(),
    }
    
    row = await db.fetch_one(
        """
        UPDATE subscriptions
        SET status = :status, bitis_tarihi = :bitis_tarihi, updated_at = :updated_at
        WHERE isletme_id = :isletme_id
        RETURNING id, isletme_id, plan_type, status, max_subeler, max_kullanicilar,
                  max_menu_items, ayllik_fiyat, trial_baslangic, trial_bitis,
                  baslangic_tarihi, bitis_tarihi, otomatik_yenileme, created_at, updated_at
        """,
        data,
    )
    return dict(row)


@router.get("/{isletme_id}/limits")
async def get_subscription_limits(
    isletme_id: int,
    _: Dict[str, Any] = Depends(get_current_user),
):
    """İşletmenin abonelik limitlerini ve kullanımını getir"""
    sub = await db.fetch_one(
        """
        SELECT plan_type, status, max_subeler, max_kullanicilar, max_menu_items
        FROM subscriptions
        WHERE isletme_id = :id
        """,
        {"id": isletme_id},
    )
    if not sub:
        raise HTTPException(404, "Abonelik bulunamadı")
    
    # Kullanım bilgilerini al
    sube_count = await db.fetch_one(
        "SELECT COUNT(*) as count FROM subeler WHERE isletme_id = :id",
        {"id": isletme_id},
    )
    kullanici_count = await db.fetch_one(
        "SELECT COUNT(*) as count FROM users WHERE aktif = TRUE",
        {},
    )
    menu_count = await db.fetch_one(
        """
        SELECT COUNT(*) as count FROM menu m
        JOIN subeler s ON m.sube_id = s.id
        WHERE s.isletme_id = :id
        """,
        {"id": isletme_id},
    )
    
    return {
        "plan_type": sub["plan_type"],
        "status": sub["status"],
        "limits": {
            "max_subeler": sub["max_subeler"],
            "max_kullanicilar": sub["max_kullanicilar"],
            "max_menu_items": sub["max_menu_items"],
        },
        "usage": {
            "subeler": sube_count["count"] if sube_count else 0,
            "kullanicilar": kullanici_count["count"] if kullanici_count else 0,
            "menu_items": menu_count["count"] if menu_count else 0,
        },
    }


