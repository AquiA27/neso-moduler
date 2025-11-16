# backend/app/routers/siparis.py
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Dict, Any, Mapping
from datetime import datetime
import json
import unicodedata

from ..core.deps import get_current_user, get_sube_id, require_roles
from ..db.database import db

router = APIRouter(prefix="/siparis", tags=["Siparis"])

# --------------------- MODELLER ---------------------
class SepetItem(BaseModel):
    urun: str
    adet: int = Field(ge=1)
    # Gönderilse bile MENÜDEKİ fiyat esas alınır
    fiyat: Optional[float] = Field(default=None, ge=0)
    # Varyasyon bilgisi (örn: "Sade", "Orta", "Şekerli")
    varyasyon: Optional[str] = None
    kategori: Optional[str] = None

class SiparisIn(BaseModel):
    masa: str
    sepet: List[SepetItem]
    durum: Literal["yeni", "hazirlaniyor", "hazir", "iptal", "odendi"] = "yeni"

class SiparisOut(BaseModel):
    id: int
    masa: str
    durum: str
    tutar: float
    created_at: datetime

# --------------------- YARDIMCI ARAÇLAR ---------------------
def normalize_name(s: str) -> str:
    if s is None:
        return ""
    s = s.casefold().strip()
    repl = {
        "ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u",
        "â": "a", "ê": "e", "î": "i", "ô": "o", "û": "u"
    }
    for k, v in repl.items():
        s = s.replace(k, v)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(s.split())

async def load_menu_map(sube_id: int) -> Dict[str, float]:
    """
    Aktif menü ürünlerini çeker ve normalize edilmiş ada göre fiyat haritası döner.
    Şube bazlıdır.
    """
    rows = await db.fetch_all(
        "SELECT ad, fiyat FROM menu WHERE aktif = TRUE AND sube_id = :sid;",
        {"sid": sube_id},
    )
    return {normalize_name(r["ad"]): float(r["fiyat"]) for r in rows}

def row_to_out(row: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "masa": row["masa"],
        "durum": row["durum"],
        "tutar": float(row["tutar"]) if row["tutar"] is not None else 0.0,
        "created_at": row["created_at"],
    }

# --------------------- UÇLAR ---------------------
@router.post(
    "/ekle",
    response_model=SiparisOut,
    dependencies=[Depends(require_roles({"admin", "operator", "barista", "mutfak", "garson"}))]
)
async def siparis_ekle(
    siparis: SiparisIn,
    current_user: Mapping[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    import logging
    logging.info(f"siparis_ekle called: masa={siparis.masa}, sepet_len={len(siparis.sepet)}, durum={siparis.durum}")
    
    if not siparis.sepet:
        raise HTTPException(status_code=400, detail="Sepet boş olamaz.")

    # 1) Menü haritasını yükle (aksan/şapka duyarsız eşleşme) - ŞUBE BAZLI
    try:
        menu_map = await load_menu_map(sube_id)
    except Exception as e:
        logging.error(f"Menü okuma hatası: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Menü okuma hatası: {e}")

    # 2) Sepeti fiyatlarla oluştur (varyasyon ve kategori bilgisini koru)
    sepet_kayit: List[Dict[str, Any]] = []
    for item in siparis.sepet:
        key = normalize_name(item.urun)
        fiyat = menu_map.get(key)
        if fiyat is None:
            raise HTTPException(status_code=400, detail=f"Menüde bulunmayan/pasif ürün: {item.urun}")
        
        # Sepet öğesini oluştur, varyasyon ve kategori varsa ekle
        sepet_item = {"urun": item.urun, "adet": item.adet, "fiyat": fiyat}
        if item.varyasyon:
            sepet_item["varyasyon"] = item.varyasyon
        if item.kategori:
            sepet_item["kategori"] = item.kategori
        
        sepet_kayit.append(sepet_item)

    # 3) Tutar
    tutar = sum(i["adet"] * i["fiyat"] for i in sepet_kayit)

    # 4) Adisyon sistemi: Masada açık adisyon varsa al, yoksa oluştur
    from ..routers.adisyon import _get_or_create_adisyon
    adisyon_id = await _get_or_create_adisyon(siparis.masa, sube_id)
    
    # 5) Kayıt (JSONB) – iki farklı cast denemesi ile garanti
    username = current_user.get("username") if isinstance(current_user, dict) else getattr(current_user, "username", None)
    user_id = current_user.get("id") if isinstance(current_user, dict) else getattr(current_user, "id", None)
    if not user_id and username:
        row_user = await db.fetch_one(
            "SELECT id FROM users WHERE username = :username",
            {"username": username},
        )
        if row_user:
            user_id = row_user["id"]

    try:
        user_id_int = int(user_id) if user_id is not None else None
    except (TypeError, ValueError):
        user_id_int = None

    sepet_json = json.dumps(sepet_kayit, ensure_ascii=False)
    
    params = {
        "sid": sube_id,
        "masa": siparis.masa,
        "adisyon_id": adisyon_id,
        "sepet": sepet_json,
        "durum": siparis.durum,
        "tutar": tutar,
        "user_id": user_id_int,
        "username": username or None,
    }

    import logging

    params_with_user_id = {
        "sid": sube_id,
        "masa": siparis.masa,
        "adisyon_id": adisyon_id,
        "sepet": sepet_json,
        "durum": siparis.durum,
        "tutar": tutar,
        "user_id": user_id_int,
    }

    params_old = {
        "sid": sube_id,
        "masa": siparis.masa,
        "sepet": sepet_json,
        "durum": siparis.durum,
        "tutar": tutar,
    }
    
    # Önce adisyon_id + created_by_user_id ile dene
    try:
        row = await db.fetch_one(
            """
            INSERT INTO siparisler (sube_id, masa, adisyon_id, sepet, durum, tutar, created_by_user_id, created_by_username)
            VALUES (:sid, :masa, :adisyon_id, :sepet::jsonb, :durum, :tutar, :user_id, :username)
            RETURNING id, masa, durum, tutar, created_at;
            """,
            params,
        )
    except Exception as e:
        logging.warning(f"SQL error (with adisyon_id + created_by_user_id + username, trying fallback): {e}")
        # Kolon yoksa/sürüm uyumsuzsa eski SQL'i dene (created_by_user_id ile)
        try:
            row = await db.fetch_one(
                """
                INSERT INTO siparisler (sube_id, masa, adisyon_id, sepet, durum, tutar, created_by_user_id)
                VALUES (:sid, :masa, :adisyon_id, :sepet::jsonb, :durum, :tutar, :user_id)
                RETURNING id, masa, durum, tutar, created_at;
                """,
                params_with_user_id,
            )
        except Exception as e2:
            logging.warning(f"SQL error (with adisyon_id + created_by_user_id, trying without adisyon_id): {e2}")
            try:
                row = await db.fetch_one(
                    """
                    INSERT INTO siparisler (sube_id, masa, sepet, durum, tutar)
                    VALUES (:sid, :masa, CAST(:sepet AS JSONB), :durum, :tutar)
                    RETURNING id, masa, durum, tutar, created_at;
                    """,
                    params_old,
                )
            except Exception as e3:
                logging.error(f"All SQL attempts failed. Last error: {e3}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail=f"Sipariş kaydedilemedi: {str(e3)}"
                )

    # Eğer created_by_username kolonu mevcutsa ve boşsa doldur
    if row and username:
        try:
            await db.execute(
                """
                UPDATE siparisler
                SET created_by_username = :username
                WHERE id = :order_id AND (created_by_username IS NULL OR created_by_username = '')
                """,
                {"username": username, "order_id": row["id"]},
            )
        except Exception as e:
            logging.warning(f"created_by_username update skipped (order_id={row['id']}): {e}")
    
    # Adisyon toplamlarını güncelle
    try:
        from ..routers.adisyon import _update_adisyon_totals
        await _update_adisyon_totals(adisyon_id, sube_id)
    except Exception as e:
        logging.warning(f"Adisyon toplamları güncellenirken hata: {e}", exc_info=True)
    
    # WebSocket broadcast for new order
    from ..websocket.manager import manager, Topics
    await manager.broadcast({
        "type": "new_order",
        "order_id": row["id"],
        "masa": row["masa"],
        "durum": row["durum"],
        "sube_id": sube_id
    }, topic=Topics.KITCHEN)
    
    await manager.broadcast({
        "type": "order_added",
        "order_id": row["id"],
        "masa": row["masa"],
        "status": row["durum"],
        "sube_id": sube_id
    }, topic=Topics.ORDERS)
    
    return row_to_out(row)

@router.get("/liste", response_model=List[SiparisOut])
async def siparis_liste(
    limit: int = Query(10, ge=1, le=100),
    _: Mapping[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    rows = await db.fetch_all(
        """
        SELECT id, masa, durum, tutar, created_at
        FROM siparisler
        WHERE sube_id = :sid
        ORDER BY created_at DESC, id DESC
        LIMIT :limit
        """,
        {"sid": sube_id, "limit": limit},
    )
    return [row_to_out(r) for r in rows]

@router.get("/{id}", response_model=SiparisOut)
async def siparis_get(
    id: int,
    _: Mapping[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    row = await db.fetch_one(
        """
        SELECT id, masa, durum, tutar, created_at
        FROM siparisler
        WHERE id = :id AND sube_id = :sid
        """,
        {"id": id, "sid": sube_id},
    )
    if not row:
        raise HTTPException(status_code=404, detail="Sipariş bulunamadı")
    return row_to_out(row)

@router.patch(
    "/{id}/durum",
    response_model=SiparisOut,
    dependencies=[Depends(require_roles({"admin", "operator"}))]
)
async def siparis_durum_guncelle(
    id: int,
    yeni_durum: Literal["yeni", "hazirlaniyor", "hazir", "iptal", "odendi"],
    _: Mapping[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    owner = await db.fetch_one(
        "SELECT id FROM siparisler WHERE id = :id AND sube_id = :sid",
        {"id": id, "sid": sube_id},
    )
    if not owner:
        raise HTTPException(status_code=404, detail="Sipariş bulunamadı veya bu şubeye ait değil")

    await db.execute(
        "UPDATE siparisler SET durum = :durum WHERE id = :id",
        {"durum": yeni_durum, "id": id},
    )
    row = await db.fetch_one(
        "SELECT id, masa, durum, tutar, created_at FROM siparisler WHERE id = :id",
        {"id": id},
    )
    return row_to_out(row)
