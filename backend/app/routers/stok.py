# backend/app/routers/stok.py
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import logging

from ..core.deps import get_current_user, get_sube_id, require_roles
from ..db.database import db
from ..websocket.manager import manager, Topics
from ..services.notification import notification_service
from ..services.audit import audit_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stok", tags=["Stok"])

# ---------- Modeller ----------
class StokItemIn(BaseModel):
    ad: str = Field(min_length=1)
    kategori: str = Field(min_length=1)
    birim: str = Field(min_length=1)
    mevcut: float = Field(ge=0, default=0)
    min: float = Field(ge=0, default=0)
    alis_fiyat: float = Field(ge=0, default=0)

class StokItemOut(BaseModel):
    id: int
    ad: str
    kategori: str
    birim: str
    mevcut: float
    min: float
    alis_fiyat: float

class StokUpdateIn(BaseModel):
    ad: str = Field(min_length=1, description="Güncellenecek mevcut stok adı")
    yeni_ad: Optional[str] = None
    kategori: Optional[str] = None
    birim: Optional[str] = None
    mevcut: Optional[float] = Field(default=None, ge=0)
    min: Optional[float] = Field(default=None, ge=0)
    alis_fiyat: Optional[float] = Field(default=None, ge=0)

class StokAlertOut(BaseModel):
    id: int
    ad: str
    kategori: str
    birim: str
    mevcut: float
    min: float
    durum: str  # "kritik" veya "tukendi"

# ---------- Uçlar ----------
@router.post(
    "/ekle",
    response_model=StokItemOut,
    dependencies=[Depends(require_roles({"admin", "operator"}))]
)
async def stok_ekle(
    item: StokItemIn,
    _: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    params = {**item.model_dump(), "sid": sube_id}
    try:
        row = await db.fetch_one(
            """
            INSERT INTO stok_kalemleri (sube_id, ad, kategori, birim, mevcut, min, alis_fiyat)
            VALUES (:sid, :ad, :kategori, :birim, :mevcut, :min, :alis_fiyat)
            RETURNING id, ad, kategori, birim, mevcut, min, alis_fiyat
            """,
            params,
        )
    except Exception:
        # Aynı stok varsa - OTOMATİK MALİYET HESAPLAMA YAP
        # Mevcut stok ve fiyatı al
        existing = await db.fetch_one(
            """
            SELECT mevcut, alis_fiyat
            FROM stok_kalemleri
            WHERE sube_id = :sid AND ad = :ad
            """,
            {"sid": sube_id, "ad": item.ad},
        )
        
        if existing:
            # Ağırlıklı ortalama maliyet hesabı
            eski_miktar = float(existing["mevcut"] or 0)
            eski_fiyat = float(existing["alis_fiyat"] or 0)
            yeni_miktar = float(item.mevcut)
            yeni_fiyat = float(item.alis_fiyat)
            
            # Toplam maliyet ve miktar
            if eski_miktar > 0:
                toplam_maliyet = (eski_miktar * eski_fiyat) + (yeni_miktar * yeni_fiyat)
                toplam_miktar = eski_miktar + yeni_miktar
                ortalama_fiyat = toplam_maliyet / toplam_miktar if toplam_miktar > 0 else yeni_fiyat
            else:
                ortalama_fiyat = yeni_fiyat
            
            # Güncelle (miktar artışı + ortalama fiyat)
            params_with_avg = {**params, "alis_fiyat": ortalama_fiyat, "mevcut": eski_miktar + yeni_miktar}
            row = await db.fetch_one(
                """
                UPDATE stok_kalemleri
                   SET kategori = :kategori,
                       birim = :birim,
                       mevcut = :mevcut,
                       min = :min,
                       alis_fiyat = :alis_fiyat
                 WHERE sube_id = :sid
                   AND ad = :ad
             RETURNING id, ad, kategori, birim, mevcut, min, alis_fiyat
                """,
                params_with_avg,
            )
        else:
            raise HTTPException(status_code=400, detail="Stok bulunamadı")
        
        if not row:
            raise HTTPException(status_code=400, detail="Stok ekleme/güncelleme başarısız")
    
    new_item = {
        "id": row["id"],
        "ad": row["ad"],
        "kategori": row["kategori"],
        "birim": row["birim"],
        "mevcut": float(row["mevcut"]),
        "min": float(row["min"]),
        "alis_fiyat": float(row["alis_fiyat"]),
    }
    
    # Stok uyarı kontrolü ve bildirim gönder
    try:
        await _check_and_notify_stock_alerts(sube_id, new_item)
    except Exception as e:
        logger.warning(f"Stok uyarı kontrolü sırasında hata: {e}", exc_info=True)
    
    return new_item

@router.get("/liste", response_model=List[StokItemOut])
async def stok_liste(
    limit: int = Query(200, ge=1, le=2000),
    _: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    rows = await db.fetch_all(
        """
        SELECT id, ad, kategori, birim, mevcut, min, alis_fiyat
        FROM stok_kalemleri
        WHERE sube_id = :sid
        ORDER BY kategori, ad
        LIMIT :lmt
        """,
        {"sid": sube_id, "lmt": limit},
    )
    return [
        {
            "id": r["id"],
            "ad": r["ad"],
            "kategori": r["kategori"] or "",
            "birim": r["birim"] or "",
            "mevcut": float(r["mevcut"] or 0),
            "min": float(r["min"] or 0),
            "alis_fiyat": float(r["alis_fiyat"] or 0),
        }
        for r in rows
    ]

@router.patch(
    "/guncelle",
    response_model=StokItemOut,
    dependencies=[Depends(require_roles({"admin", "operator"}))]
)
async def stok_guncelle(
    payload: StokUpdateIn,
    _: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    # Önce mevcut kaydı bul
    existing = await db.fetch_one(
        """
        SELECT id, ad, kategori, birim, mevcut, min, alis_fiyat
        FROM stok_kalemleri
        WHERE sube_id = :sid AND ad = :ad
        """,
        {"sid": sube_id, "ad": payload.ad},
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Stok bulunamadı")

    # Güncelleme parametrelerini hazırla
    updates = {}
    if payload.yeni_ad is not None:
        updates["ad"] = payload.yeni_ad
    if payload.kategori is not None:
        updates["kategori"] = payload.kategori
    if payload.birim is not None:
        updates["birim"] = payload.birim
    if payload.min is not None:
        updates["min"] = payload.min
    
    # Mevcut stok ve fiyat değişirse - AĞIRLIKLI ORTALAMA HESABI
    eski_miktar = float(existing["mevcut"] or 0)
    eski_fiyat = float(existing["alis_fiyat"] or 0)
    
    if payload.mevcut is not None and payload.alis_fiyat is not None:
        # Yeni miktar ve fiyat verildi - STOK EKLE mantığı
        yeni_miktar = float(payload.mevcut)
        yeni_fiyat = float(payload.alis_fiyat)
        
        # Ağırlıklı ortalama hesapla (mevcut stok üzerine ekleme)
        if eski_miktar > 0:
            toplam_maliyet = (eski_miktar * eski_fiyat) + (yeni_miktar * yeni_fiyat)
            toplam_miktar = eski_miktar + yeni_miktar
            ortalama_fiyat = toplam_maliyet / toplam_miktar if toplam_miktar > 0 else yeni_fiyat
            updates["mevcut"] = toplam_miktar
            updates["alis_fiyat"] = ortalama_fiyat
        else:
            updates["mevcut"] = yeni_miktar
            updates["alis_fiyat"] = yeni_fiyat
    else:
        # Sadece miktar veya sadece fiyat değişti - normal güncelleme
        if payload.mevcut is not None:
            updates["mevcut"] = payload.mevcut
        if payload.alis_fiyat is not None:
            updates["alis_fiyat"] = payload.alis_fiyat

    if not updates:
        # Hiçbir şey güncellenmemişse mevcut kaydı döndür
        return {
            "id": existing["id"],
            "ad": existing["ad"],
            "kategori": existing["kategori"] or "",
            "birim": existing["birim"] or "",
            "mevcut": float(existing["mevcut"] or 0),
            "min": float(existing["min"] or 0),
            "alis_fiyat": float(existing["alis_fiyat"] or 0),
        }

    # UPDATE yap
    set_clause = ", ".join([f"{k} = :{k}" for k in updates.keys()])
    query = f"""
        UPDATE stok_kalemleri
        SET {set_clause}
        WHERE sube_id = :sid AND id = :id
        RETURNING id, ad, kategori, birim, mevcut, min, alis_fiyat
    """
    params = {**updates, "sid": sube_id, "id": existing["id"]}
    row = await db.fetch_one(query, params)
    if not row:
        raise HTTPException(status_code=400, detail="Güncelleme başarısız")

    updated_item = {
        "id": row["id"],
        "ad": row["ad"],
        "kategori": row["kategori"] or "",
        "birim": row["birim"] or "",
        "mevcut": float(row["mevcut"] or 0),
        "min": float(row["min"] or 0),
        "alis_fiyat": float(row["alis_fiyat"] or 0),
    }
    
    # Stok uyarı kontrolü ve bildirim gönder
    try:
        await _check_and_notify_stock_alerts(sube_id, updated_item)
    except Exception as e:
        logger.warning(f"Stok uyarı kontrolü sırasında hata: {e}", exc_info=True)
    
    return updated_item

async def _check_and_notify_stock_alerts(sube_id: int, item: Dict[str, Any]) -> None:
    """Stok seviyesini kontrol et ve gerekirse uyarı gönder"""
    mevcut = float(item.get("mevcut", 0))
    min_seviye = float(item.get("min", 0))

    # Eğer min seviye 0 ise uyarı gönderme
    if min_seviye <= 0:
        return

    durum = None
    if mevcut <= 0:
        durum = "tukendi"
    elif mevcut <= min_seviye:
        durum = "kritik"

    if durum:
        # WebSocket bildirimi
        alert_message = {
            "type": "stock_alert",
            "item": {
                "id": item["id"],
                "ad": item["ad"],
                "kategori": item.get("kategori", ""),
                "birim": item.get("birim", ""),
                "mevcut": mevcut,
                "min": min_seviye,
                "durum": durum,
            },
            "sube_id": sube_id,
        }
        await manager.broadcast(alert_message, topic=Topics.STOCK)
        logger.info(f"Stok uyarısı gönderildi (WebSocket): {item['ad']} - {durum}")

        # Database'e uyarı kaydı
        try:
            await db.execute(
                """
                INSERT INTO stock_alert_history
                (sube_id, stok_id, stok_ad, alert_type, mevcut_miktar, min_miktar,
                 notification_sent, notification_method)
                VALUES (:sube_id, :stok_id, :stok_ad, :alert_type, :mevcut, :min,
                        TRUE, 'websocket')
                """,
                {
                    "sube_id": sube_id,
                    "stok_id": item["id"],
                    "stok_ad": item["ad"],
                    "alert_type": durum,
                    "mevcut": mevcut,
                    "min": min_seviye,
                },
            )
        except Exception as e:
            logger.warning(f"Stok uyarı geçmişi kaydetme hatası: {e}")

        # Email bildirimi (opsiyonel - kritik durumlarda)
        if durum == "tukendi":
            try:
                # Şube adını al
                sube_row = await db.fetch_one(
                    "SELECT ad FROM subeler WHERE id = :sid",
                    {"sid": sube_id}
                )
                sube_name = sube_row["ad"] if sube_row else "Bilinmeyen Şube"

                # Email gönder
                email_sent = await notification_service.send_stock_alert_email(
                    stock_name=item["ad"],
                    alert_type=durum,
                    current_amount=mevcut,
                    min_amount=min_seviye,
                    unit=item.get("birim", ""),
                    sube_name=sube_name,
                )

                if email_sent:
                    logger.info(f"Stok uyarısı emaili gönderildi: {item['ad']}")
                    # Email gönderimini de kaydet
                    await db.execute(
                        """
                        INSERT INTO stock_alert_history
                        (sube_id, stok_id, stok_ad, alert_type, mevcut_miktar, min_miktar,
                         notification_sent, notification_method)
                        VALUES (:sube_id, :stok_id, :stok_ad, :alert_type, :mevcut, :min,
                                TRUE, 'email')
                        """,
                        {
                            "sube_id": sube_id,
                            "stok_id": item["id"],
                            "stok_ad": item["ad"],
                            "alert_type": durum,
                            "mevcut": mevcut,
                            "min": min_seviye,
                        },
                    )
            except Exception as e:
                logger.warning(f"Email uyarı gönderme hatası: {e}")

@router.get("/uyarilar", response_model=List[StokAlertOut])
async def stok_uyarilar(
    _: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """Kritik ve tükenen stokları listele"""
    rows = await db.fetch_all(
        """
        SELECT id, ad, kategori, birim, mevcut, min, alis_fiyat
        FROM stok_kalemleri
        WHERE sube_id = :sid
          AND min > 0
          AND (mevcut <= 0 OR mevcut <= min)
        ORDER BY
          CASE WHEN mevcut <= 0 THEN 0 ELSE 1 END,
          (mevcut - min) ASC,
          ad ASC
        """,
        {"sid": sube_id},
    )
    alerts = []
    for r in rows:
        mevcut = float(r["mevcut"] or 0)
        min_seviye = float(r["min"] or 0)
        durum = "tukendi" if mevcut <= 0 else "kritik"
        alerts.append({
            "id": r["id"],
            "ad": r["ad"],
            "kategori": r["kategori"] or "",
            "birim": r["birim"] or "",
            "mevcut": mevcut,
            "min": min_seviye,
            "durum": durum,
        })
    return alerts


class StokAlertHistoryOut(BaseModel):
    """Stok uyarı geçmişi modeli"""
    id: int
    stok_ad: str
    alert_type: str
    mevcut_miktar: float
    min_miktar: float
    notification_method: Optional[str]
    created_at: str


@router.get("/uyarilar/gecmis", response_model=List[StokAlertHistoryOut])
async def stok_uyari_gecmisi(
    limit: int = Query(100, ge=1, le=500),
    _: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """Stok uyarı geçmişini listele"""
    rows = await db.fetch_all(
        """
        SELECT
            id, stok_ad, alert_type, mevcut_miktar, min_miktar,
            notification_method, created_at
        FROM stock_alert_history
        WHERE sube_id = :sid
        ORDER BY created_at DESC
        LIMIT :lmt
        """,
        {"sid": sube_id, "lmt": limit},
    )
    return [
        {
            "id": r["id"],
            "stok_ad": r["stok_ad"],
            "alert_type": r["alert_type"],
            "mevcut_miktar": float(r["mevcut_miktar"] or 0),
            "min_miktar": float(r["min_miktar"] or 0),
            "notification_method": r["notification_method"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]

@router.delete(
    "/sil",
    dependencies=[Depends(require_roles({"admin"}))]
)
async def stok_sil(
    ad: str = Query(..., description="Silinecek stok adı"),
    _: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    result = await db.execute(
        """
        DELETE FROM stok_kalemleri
        WHERE sube_id = :sid AND ad = :ad
        """,
        {"sid": sube_id, "ad": ad},
    )
    return {"message": "Stok silindi", "ad": ad}
