from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import time
import logging

from ..db.database import db
from ..core.deps import get_api_key_business
from ..services.api_tracking import log_api_usage
from .siparis import normalize_name


router = APIRouter(prefix="/public", tags=["Public"])

# Sipariş başına API kullanım maliyeti (TL)
API_COST_PER_ORDER = 0.10  # 10 kuruş


class PublicCreateIn(BaseModel):
    masa: str
    text: str
    sube_id: Optional[int] = 1


def _extract_candidates(text: str) -> List[List[Any]]:
    import re
    t = text.casefold()
    t = re.sub(r"[,.;\n]", " ", t)
    tokens = t.split()
    skip_words = {"tane", "adet", "ve"}
    num_words = {"bir":1, "iki":2, "uc":3, "dort":4, "bes":5, "alti":6, "yedi":7, "sekiz":8, "dokuz":9, "on":10}
    pairs = []
    for i, tok in enumerate(tokens):
        if tok in skip_words:
            continue
        adet = None
        if tok.isdigit():
            adet = int(tok)
        elif tok in num_words:
            adet = num_words[tok]
        if adet is not None:
            if i + 1 < len(tokens):
                pairs.append([tokens[i + 1], adet])
            continue
        if i + 1 < len(tokens) and tokens[i + 1].isdigit():
            pairs.append([tok, int(tokens[i + 1])])
    if not pairs and tokens:
        for tok in tokens:
            if tok.isdigit():
                continue
            pairs.append([tok, 1])
    return pairs


@router.post("/siparis")
async def public_create_order(
    payload: PublicCreateIn,
    api_business: Dict[str, Any] = Depends(get_api_key_business),
):
    """
    API key ile korumalı sipariş oluşturma endpoint'i.
    İşletme verileri API key'den gelir, sube_id ise işletmenin ilk aktif şubesi olur.
    """
    import json
    start_time = time.time()
    isletme_id = api_business["isletme_id"]
    api_key_id = api_business["api_key_id"]
    status_code = 200
    error_message = None
    siparis_id = None
    
    try:
        # İşletmenin şubelerini kontrol et
        sube_rows = await db.fetch_all(
            """
            SELECT id, ad FROM subeler
            WHERE isletme_id = :iid AND aktif = TRUE
            ORDER BY id ASC
            LIMIT 1
            """,
            {"iid": isletme_id},
        )
        
        if not sube_rows:
            status_code = 404
            error_message = "İşletme için aktif şube bulunamadı"
            raise HTTPException(status_code=404, detail=error_message)
        
        sube_id = sube_rows[0]["id"]
        
        # Eğer payload'da sube_id varsa, o şubenin işletmeye ait olduğunu kontrol et
        if payload.sube_id:
            sube_check = await db.fetch_one(
                "SELECT id FROM subeler WHERE id = :sid AND isletme_id = :iid AND aktif = TRUE",
                {"sid": payload.sube_id, "iid": isletme_id},
            )
            if sube_check:
                sube_id = payload.sube_id
            else:
                logging.warning(f"[PUBLIC_API] Sube {payload.sube_id} işletme {isletme_id}'ye ait değil veya pasif, varsayılan şube kullanılıyor")
        
        # Build maps from menu
        rows = await db.fetch_all(
            "SELECT ad, fiyat FROM menu WHERE aktif = TRUE AND sube_id = :sid;",
            {"sid": sube_id},
        )
        price_map: Dict[str, float] = {}
        name_map: Dict[str, str] = {}
        for r in rows:
            k = normalize_name(r["ad"])  # normalize key
            price_map[k] = float(r["fiyat"]) if r["fiyat"] is not None else 0.0
            name_map[k] = r["ad"]

        pairs = _extract_candidates(payload.text)
        aggregated: Dict[str, int] = {}
        not_matched: List[str] = []
        for name, adet in pairs:
            key = normalize_name(name)
            match = None
            if key in price_map:
                match = key
            else:
                for mk in price_map.keys():
                    if key and (key in mk or mk in key):
                        match = mk
                        break
            if match:
                aggregated[match] = aggregated.get(match, 0) + max(1, int(adet))
            else:
                not_matched.append(name)

        if not aggregated:
            status_code = 400
            error_message = "Sipariş anlaşılamadı"
            raise HTTPException(status_code=400, detail=error_message)

        sepet = [
            {"urun": name_map.get(k, k), "adet": a, "fiyat": float(price_map.get(k) or 0)}
            for k, a in aggregated.items()
        ]
        tutar = sum(i["adet"] * i["fiyat"] for i in sepet)

        # Adisyon sistemi: Masada açık adisyon varsa al, yoksa oluştur
        from ..routers.adisyon import _get_or_create_adisyon, _update_adisyon_totals
        adisyon_id = await _get_or_create_adisyon(payload.masa, sube_id)

        row = await db.fetch_one(
            """
            INSERT INTO siparisler (sube_id, masa, adisyon_id, sepet, durum, tutar)
            VALUES (:sid, :masa, :adisyon_id, CAST(:sepet AS JSONB), 'yeni', :tutar)
            RETURNING id, masa, durum, tutar, created_at
            """,
            {"sid": sube_id, "masa": payload.masa, "adisyon_id": adisyon_id, "sepet": json.dumps(sepet, ensure_ascii=False), "tutar": tutar},
        )
        
        siparis_id = row["id"]
        
        # Adisyon toplamlarını güncelle
        try:
            await _update_adisyon_totals(adisyon_id, sube_id)
        except Exception as e:
            logging.warning(f"Adisyon toplamları güncellenirken hata: {e}", exc_info=True)
        
        response_time_ms = int((time.time() - start_time) * 1000)
        
        # API kullanımını logla (başarılı)
        await log_api_usage(
            isletme_id=isletme_id,
            api_key_id=api_key_id,
            api_type="rest_api",
            endpoint="/public/siparis",
            method="POST",
            status="success",
            status_code=200,
            response_time_ms=response_time_ms,
            metadata={
                "sube_id": sube_id,
                "masa": payload.masa,
                "siparis_id": siparis_id,
                "tutar": float(tutar),
                "not_matched": not_matched,
            },
            cost_tl=API_COST_PER_ORDER,  # Sipariş başına maliyet
        )
        
        return {
            "id": row["id"],
            "masa": row["masa"],
            "durum": row["durum"],
            "tutar": float(row["tutar"]),
            "created_at": row["created_at"],
            "not_matched": not_matched,
        }
        
    except HTTPException as he:
        # HTTPException'ları tekrar fırlat
        response_time_ms = int((time.time() - start_time) * 1000)
        await log_api_usage(
            isletme_id=isletme_id,
            api_key_id=api_key_id,
            api_type="rest_api",
            endpoint="/public/siparis",
            method="POST",
            status="error",
            status_code=he.status_code,
            response_time_ms=response_time_ms,
            error_message=he.detail,
            metadata={"sube_id": payload.sube_id, "masa": payload.masa},
            cost_tl=0.0,
        )
        raise
        # HTTPException'ları tekrar fırlat
        response_time_ms = int((time.time() - start_time) * 1000)
        await log_api_usage(
            isletme_id=isletme_id,
            api_key_id=api_key_id,
            api_type="rest_api",
            endpoint="/public/siparis",
            method="POST",
            status="error",
            status_code=status_code,
            response_time_ms=response_time_ms,
            error_message=error_message or "HTTP Exception",
            metadata={"sube_id": payload.sube_id, "masa": payload.masa},
            cost_tl=0.0,
        )
        raise
    except Exception as e:
        # Diğer hataları logla ve fırlat
        response_time_ms = int((time.time() - start_time) * 1000)
        error_msg = str(e)
        logging.error(f"[PUBLIC_API] Error creating order: {e}", exc_info=True)
        await log_api_usage(
            isletme_id=isletme_id,
            api_key_id=api_key_id,
            api_type="rest_api",
            endpoint="/public/siparis",
            method="POST",
            status="error",
            status_code=500,
            response_time_ms=response_time_ms,
            error_message=error_msg,
            metadata={"sube_id": payload.sube_id, "masa": payload.masa},
            cost_tl=0.0,
        )
        raise HTTPException(status_code=500, detail=f"Internal server error: {error_msg}")


@router.get("/menu")
async def public_menu(sube_id: Optional[int] = Query(None, description="Şube ID (zorunlu)")):
    """
    Public menü listeleme endpoint'i (API key gerekmez).
    sube_id parametresi zorunludur. Şube aktif olmalı ve işletme aktif olmalı.
    """
    try:
        if not sube_id:
            raise HTTPException(status_code=400, detail="sube_id parametresi gereklidir")
        
        # Şube var mı ve aktif mi kontrol et
        sube_row = await db.fetch_one(
            """
            SELECT s.id, s.isletme_id, s.aktif as sube_aktif, i.aktif as isletme_aktif
            FROM subeler s
            JOIN isletmeler i ON s.isletme_id = i.id
            WHERE s.id = :sid
            """,
            {"sid": sube_id},
        )
        
        if not sube_row:
            raise HTTPException(status_code=404, detail="Şube bulunamadı")
        
        if not sube_row.get("sube_aktif"):
            raise HTTPException(status_code=404, detail="Şube aktif değil")
        
        if not sube_row.get("isletme_aktif"):
            raise HTTPException(status_code=404, detail="İşletme aktif değil")
        
        # N+1 query düzeltmesi: Tek JOIN sorgusu ile tüm varyasyonları getir
        rows = await db.fetch_all(
            """
            SELECT 
                m.id, m.ad, m.fiyat, m.kategori, m.aciklama, m.gorsel_url,
                mv.id as var_id, mv.ad as var_ad, mv.ek_fiyat as var_ek_fiyat, mv.sira as var_sira
            FROM menu m
            LEFT JOIN menu_varyasyonlar mv ON m.id = mv.menu_id AND mv.aktif = TRUE
            WHERE m.aktif = TRUE AND m.sube_id = :sid
            ORDER BY m.kategori NULLS LAST, m.ad ASC, mv.sira ASC, mv.ad ASC
            """,
            {"sid": sube_id},
        )
        
        # Grupla: menu_id -> variations list
        items_dict: Dict[int, Dict[str, Any]] = {}
        for r in rows:
            menu_id = r["id"]
            if menu_id not in items_dict:
                items_dict[menu_id] = {
                    "id": menu_id,
                    "ad": r["ad"],
                    "fiyat": float(r["fiyat"] or 0),
                    "kategori": r["kategori"] or "",
                    "aciklama": r["aciklama"],
                    "gorsel_url": r["gorsel_url"],
                    "varyasyonlar": []
                }
            
            # Varyasyon varsa ekle
            if r["var_id"]:
                items_dict[menu_id]["varyasyonlar"].append({
                    "id": r["var_id"],
                    "ad": r["var_ad"],
                    "ek_fiyat": float(r["var_ek_fiyat"] or 0),
                    "sira": r["var_sira"] or 0
                })
        
        items = list(items_dict.values())
        
        return items
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        logging.error(f"[PUBLIC_API] Error getting menu: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {error_msg}")


@router.get("/masa/{qr_code}")
async def get_masa_by_qr(qr_code: str):
    """
    QR kod ile masa bilgisini al (Public endpoint - API key gerekmez).
    QR kod benzersiz olduğu için masa bilgisinden şube ve işletme bilgisine erişilebilir.
    """
    try:
        # Masa bilgisini al - QR kod benzersiz olduğu için doğrudan sorgu yapabiliriz
        row = await db.fetch_one(
            """
            SELECT m.id, m.masa_adi, m.qr_code, m.durum, m.kapasite, m.sube_id,
                   s.isletme_id, s.aktif as sube_aktif, i.aktif as isletme_aktif
            FROM masalar m
            JOIN subeler s ON m.sube_id = s.id
            JOIN isletmeler i ON s.isletme_id = i.id
            WHERE m.qr_code = :qr_code
            """,
            {"qr_code": qr_code},
        )
        if not row:
            raise HTTPException(status_code=404, detail="Masa bulunamadı")
        
        # Şube ve işletme aktif mi kontrol et
        if not row.get("sube_aktif"):
            raise HTTPException(status_code=404, detail="Masa bulunamadı")
        
        if not row.get("isletme_aktif"):
            raise HTTPException(status_code=404, detail="İşletme bulunamadı")
        
        return {
            "id": row["id"],
            "masa_adi": row["masa_adi"],
            "qr_code": row["qr_code"],
            "durum": row["durum"],
            "kapasite": row["kapasite"],
            "sube_id": row["sube_id"],
            "isletme_id": row.get("isletme_id"),  # Frontend için isletme_id de döndür
        }
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        logging.error(f"[PUBLIC_API] Error getting masa by QR: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {error_msg}")
