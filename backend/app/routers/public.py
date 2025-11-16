from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional, List

from ..db.database import db
from .siparis import normalize_name


router = APIRouter(prefix="/public", tags=["Public"])


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
async def public_create_order(payload: PublicCreateIn):
    sube_id = int(payload.sube_id or 1)
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
        raise HTTPException(status_code=400, detail="Sipariş anlaşılamadı")

    import json
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
    
    # Adisyon toplamlarını güncelle
    try:
        await _update_adisyon_totals(adisyon_id, sube_id)
    except Exception as e:
        import logging
        logging.warning(f"Adisyon toplamları güncellenirken hata: {e}", exc_info=True)
    return {
        "id": row["id"],
        "masa": row["masa"],
        "durum": row["durum"],
        "tutar": float(row["tutar"]),
        "created_at": row["created_at"],
        "not_matched": not_matched,
    }


@router.get("/menu")
async def public_menu(sube_id: int = 1):
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


@router.get("/masa/{qr_code}")
async def get_masa_by_qr(qr_code: str):
    """QR kod ile masa bilgisini al (public endpoint)"""
    row = await db.fetch_one(
        """
        SELECT id, masa_adi, qr_code, durum, kapasite
        FROM masalar
        WHERE qr_code = :qr_code
        """,
        {"qr_code": qr_code},
    )
    if not row:
        raise HTTPException(status_code=404, detail="Masa bulunamadı")
    
    return {
        "id": row["id"],
        "masa_adi": row["masa_adi"],
        "qr_code": row["qr_code"],
        "durum": row["durum"],
        "kapasite": row["kapasite"],
    }
