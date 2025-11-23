# backend/app/routers/mutfak.py
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Literal, Dict, Any, Mapping, Optional
from pydantic import BaseModel, Field

from ..core.deps import get_current_user, get_sube_id, require_roles
from ..db.database import db

router = APIRouter(prefix="/mutfak", tags=["Mutfak"])

# ---- Modeller ----
class SepetItem(BaseModel):
    urun: str
    adet: int = Field(ge=1)
    fiyat: float = Field(ge=0)
    miktar: Optional[float] = Field(default=None, ge=0)
    toplam: Optional[float] = Field(default=None, ge=0)
    varyasyon: Optional[str] = None

class SiparisRow(BaseModel):
    id: int
    masa: str
    durum: Literal["yeni", "hazirlaniyor", "hazir", "iptal", "odendi"]
    tutar: float
    created_at: str  # ISO string
    sepet: List[SepetItem] = Field(default_factory=list)


def _decode_sepet(value: Any) -> List[Dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return []
    return []


def _normalize_sepet(value: Any) -> List[Dict[str, Any]]:
    def _num(val: Any, default: float = 0.0) -> float:
        try:
            if val is None or val == "":
                return default
            return float(val)
        except (TypeError, ValueError):
            return default

    normalized: List[Dict[str, Any]] = []
    for item in _decode_sepet(value):
        if isinstance(item, dict):
            urun = str(item.get("urun") or item.get("ad") or "").strip()
            adet = _num(
                item.get("adet")
                or item.get("miktar")
                or item.get("quantity")
                or item.get("qty"),
                default=1.0,
            )
            if adet <= 0:
                adet = 1.0
            fiyat = _num(
                item.get("fiyat")
                or item.get("birim_fiyat")
                or item.get("unit_price")
                or item.get("price"),
                default=0.0,
            )
            toplam = _num(
                item.get("toplam")
                or item.get("tutar")
                or item.get("total"),
                default=fiyat * adet,
            )
            if fiyat == 0 and adet:
                fiyat = toplam / adet if toplam else 0.0
            
            # Create normalized item
            normalized_item = {
                "urun": urun,
                "adet": adet,
                "miktar": adet,
                "fiyat": fiyat,
                "toplam": fiyat * adet if fiyat else toplam,
            }
            
            # Include variation if present
            if "varyasyon" in item:
                normalized_item["varyasyon"] = item["varyasyon"]
            
            normalized.append(normalized_item)
    return normalized


def _row_map(r: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "id": r["id"],
        "masa": r["masa"],
        "durum": r["durum"],
        "tutar": float(r["tutar"] or 0),
        "created_at": r["created_at"].isoformat() if r["created_at"] else "",
        "sepet": _normalize_sepet(r["sepet"]),
    }

# ---- Uçlar ----
@router.get("/kuyruk", response_model=List[SiparisRow])
async def kuyruk(
    _: Mapping[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
    durum: Optional[Literal["yeni", "hazirlaniyor", "hazir", "iptal", "aktif", "tumu"]] = Query(
        "yeni", description='"aktif" → yeni + hazirlaniyor, "tumu" → tüm aktif siparişler (odendi hariç)'
    ),
    limit: int = Query(50, ge=1, le=200),
):
    """
    Mutfak kuyruğu: varsayılan sadece 'yeni'.
    durum=aktif → ['yeni','hazirlaniyor'] birlikte döner.
    durum=tumu → tüm durumlar (odendi ve iptal hariç).
    """
    params = {"sid": sube_id, "limit": limit}
    base = """
        SELECT id, masa, durum, tutar, sepet, created_at
        FROM siparisler
        WHERE sube_id = :sid
    """
    if durum == "aktif":
        base += " AND durum IN ('yeni','hazirlaniyor')"
    elif durum == "tumu":
        # Tüm aktif siparişleri göster (odendi ve iptal hariç)
        base += " AND durum IN ('yeni','hazirlaniyor','hazir')"
    else:
        base += " AND durum = :durum"
        params["durum"] = durum

    base += " ORDER BY created_at DESC, id DESC LIMIT :limit"
    rows = await db.fetch_all(base, params)
    return [_row_map(r) for r in rows]

@router.get("/poll", response_model=List[SiparisRow])
async def poll(
    _: Mapping[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
    since_id: int = Query(0, ge=0, description="Bu id'den büyük siparişleri getir"),
    only_active: bool = Query(True, description="True → sadece yeni+hazirlaniyor"),
    limit: int = Query(100, ge=1, le=500),
):
    """
    Basit polling: son görülen id'yi tut ve periyodik çağır.
    Frontend 3-10 sn arası aralıkla çağırabilir.
    """
    params = {"sid": sube_id, "since": since_id, "limit": limit}
    base = """
        SELECT id, masa, durum, tutar, sepet, created_at
        FROM siparisler
        WHERE sube_id = :sid AND id > :since
    """
    if only_active:
        base += " AND durum IN ('yeni','hazirlaniyor')"

    base += " ORDER BY id ASC LIMIT :limit"
    rows = await db.fetch_all(base, params)
    return [_row_map(r) for r in rows]

@router.patch(
    "/durum/{id}",
    response_model=SiparisRow,
    dependencies=[Depends(require_roles({"admin", "operator", "mutfak", "barista", "garson"}))]
)
async def durum_guncelle(
    id: int,
    yeni_durum: Literal["yeni", "hazirlaniyor", "hazir", "iptal", "odendi"],
    _: Mapping[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """
    Mutfaktan durum güncelle: hazırlanmaya geçti, hazır oldu, iptal oldu gibi.
    Sipariş 'hazir' durumuna geçtiğinde kasada görünür hale gelir.
    NOT: Stok düşürme işlemi kasa'dan ödeme alınınca yapılır, mutfak'ta değil.
    """
    import logging
    
    owner = await db.fetch_one(
        "SELECT id, masa FROM siparisler WHERE id = :id AND sube_id = :sid",
        {"id": id, "sid": sube_id},
    )
    if not owner:
        raise HTTPException(status_code=404, detail="Sipariş bulunamadı veya bu şubeye ait değil")

    # NOT: Stok düşürme işlemi artık mutfak'ta yapılmıyor
    # Stok sadece kasa'dan ödeme alınınca düşer (ödeme işlemi sırasında)
    # Bu sayede henüz ödenmemiş siparişler için stok rezerve edilmez

    await db.execute(
        "UPDATE siparisler SET durum = :d WHERE id = :id",
        {"d": yeni_durum, "id": id},
    )

    row = await db.fetch_one(
        "SELECT id, masa, durum, tutar, sepet, created_at, adisyon_id FROM siparisler WHERE id = :id",
        {"id": id},
    )
    
    # Adisyon toplamlarını güncelle (özellikle 'hazir' durumuna geçtiğinde)
    if row:
        try:
            # Record objesi için güvenli erişim - direkt key ile erişim
            adisyon_id = row["adisyon_id"]
            if adisyon_id:
                from ..routers.adisyon import _update_adisyon_totals
                await _update_adisyon_totals(adisyon_id, sube_id)
                logging.info(f"Mutfak: Adisyon #{adisyon_id} toplamları güncellendi (sipariş #{id} durum={yeni_durum})")
        except (KeyError, AttributeError):
            # adisyon_id kolonu yoksa veya None ise, sessizce devam et
            pass
        except Exception as e:
            logging.warning(f"Mutfak: Adisyon toplamları güncellenirken hata: {e}", exc_info=True)
    
    # WebSocket broadcast - kitchen, orders, and cashier topics
    from ..websocket.manager import manager, Topics
    broadcast_message = {
        "type": "status_change",
        "order_id": id,
        "masa": owner["masa"],
        "new_status": yeni_durum,
        "status": yeni_durum,  # Also include 'status' for compatibility
        "sube_id": sube_id
    }
    
    logging.info(f"Mutfak: Broadcasting status change for order #{id} (masa={owner['masa']}, status={yeni_durum}) to topics: kitchen, orders, cashier")
    
    # Broadcast to kitchen topic (for mutfak page)
    await manager.broadcast(broadcast_message, topic=Topics.KITCHEN)
    
    # Broadcast to orders topic (for general order updates)
    await manager.broadcast(broadcast_message, topic=Topics.ORDERS)
    
    # Broadcast to cashier topic (for kasa page) - ÖNEMLİ: Hazır siparişler kasada görünmeli
    await manager.broadcast(broadcast_message, topic=Topics.CASHIER)
    
    # Özellikle 'hazir' durumunda ekstra log
    if yeni_durum == "hazir":
        logging.info(f"Mutfak: Sipariş #{id} hazır durumuna geçti, kasa sayfasına bildirim gönderildi (masa={owner['masa']})")
    
    logging.info(f"Mutfak: Broadcast completed for order #{id}")
    
    return _row_map(row)
