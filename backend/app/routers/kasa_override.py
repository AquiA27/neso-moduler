from typing import Mapping, Any

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

# Import existing kasa router/module to modify in-place
from . import kasa as _kasa
from ..core.deps import get_current_user, get_sube_id, require_roles
from ..db.database import db


ALLOWED_YONTEM = {"nakit", "kart", "havale", "iyzico", "papara", "diger"}


class OdemeInOverride(BaseModel):
    masa: str = Field(min_length=1)
    tutar: float = Field(ge=0.01)
    yontem: str


def _normalize_yontem(val: str) -> str:
    v = (val or "").strip().lower()
    # Basic Turkish to ASCII normalization + common mojibake char
    v = (
        v.replace("ğ", "g")
         .replace("ı", "i")
         .replace("ş", "s")
         .replace("ç", "c")
         .replace("ö", "o")
         .replace("ü", "u")
         .replace("�", "g")
    )
    return v


def _remove_existing_odeme_ekle_route() -> None:
    try:
        _kasa.router.routes = [
            r
            for r in _kasa.router.routes
            if not (
                getattr(r, "path", None) == "/odeme/ekle"
                and "POST" in (getattr(r, "methods", set()) or set())
            )
        ]
    except Exception:
        # If structure changes, fail silently; duplicate route may remain.
        pass


# Ensure original route is removed so this override takes effect first
_remove_existing_odeme_ekle_route()

@_kasa.router.post(
    "/odeme/ekle",
    response_model=_kasa.OdemeOut,
    dependencies=[Depends(require_roles({"admin", "operator", "barista"}))],
)
async def odeme_ekle(
    payload: OdemeInOverride,
    _: Mapping[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    yontem = _normalize_yontem(payload.yontem)
    if yontem not in ALLOWED_YONTEM:
        raise HTTPException(status_code=422, detail=f"Gecersiz yontem: {payload.yontem}")

    ozet = await _kasa._hesap_ozet_core(payload.masa, sube_id)
    if payload.tutar > ozet["bakiye"]:
        raise HTTPException(
            status_code=400,
            detail=f"Fazla odeme: bakiye {ozet['bakiye']} TL, tutar {payload.tutar} TL",
        )

    async with db.transaction():
        row = await db.fetch_one(
            """
            INSERT INTO odemeler (sube_id, masa, tutar, yontem)
            VALUES (:sid, :masa, :tutar, :yontem)
            RETURNING id, masa, tutar, yontem, created_at
            """,
            {"sid": sube_id, "masa": payload.masa, "tutar": payload.tutar, "yontem": yontem},
        )

        # Bakiye kontrolü ve finalize işlemi transaction içinde yapılmalı
        try:
            import logging
            ozet2 = await _kasa._hesap_ozet_core(payload.masa, sube_id)
            # Dictionary'den direkt erişim (database record değil)
            bakiye_value = ozet2.get("bakiye", 0) if isinstance(ozet2, dict) else (ozet2["bakiye"] if "bakiye" in ozet2 else 0)
            logging.info(
                f"[OVERRIDE] Odeme eklendi: masa={payload.masa}, tutar={payload.tutar}, "
                f"yeni_bakiye={bakiye_value}, sube_id={sube_id}"
            )
            # Floating point hassasiyeti için 0.01 TL tolerans
            bakiye = abs(float(bakiye_value) if bakiye_value is not None else 0)
            if bakiye < 0.01:
                logging.info(f"[OVERRIDE] Masa {payload.masa} bakiyesi sifir, siparisler finalize ediliyor (sube_id={sube_id})")
                finalized_ids = await _kasa._finalize_hazir_siparisler(payload.masa, sube_id)
                logging.info(f"[OVERRIDE] Masa {payload.masa} icin {len(finalized_ids)} siparis finalize edildi")
            else:
                logging.info(f"[OVERRIDE] Masa {payload.masa} bakiyesi {bakiye} TL, finalize edilmiyor")
        except Exception as e:
            import logging
            logging.error(f"[OVERRIDE] Error finalizing orders on odeme_ekle: {e}", exc_info=True)
            # Hata olsa bile transaction devam etsin ama loglayalım

    return {
        "id": row["id"],
        "masa": row["masa"],
        "tutar": float(row["tutar"]),
        "yontem": row["yontem"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else "",
    }



# --- Otomatik kapatma: bakiyeyi tek ödemeyle kapat ---
class OdemeKapatIn(BaseModel):
    masa: str = Field(min_length=1)
    yontem: str = "nakit"


@_kasa.router.post(
    "/odeme/kapat",
    response_model=_kasa.OdemeOut,
    dependencies=[Depends(require_roles({"admin", "operator"}))],
)
async def odeme_kapat(
    payload: OdemeKapatIn,
    _: Mapping[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    yontem = _normalize_yontem(payload.yontem)
    if yontem not in ALLOWED_YONTEM:
        raise HTTPException(status_code=422, detail=f"Gecersiz yontem: {payload.yontem}")

    ozet = await _kasa._hesap_ozet_core(payload.masa, sube_id)
    # ozet dict döndürür ama güvenli erişim yapalım
    bakiye = float(ozet.get("bakiye", 0) if isinstance(ozet, dict) else (ozet["bakiye"] if "bakiye" in ozet else 0))
    if bakiye <= 0:
        raise HTTPException(status_code=400, detail="Kapatacak bakiye yok")

    async with db.transaction():
        row = await db.fetch_one(
            """
            INSERT INTO odemeler (sube_id, masa, tutar, yontem)
            VALUES (:sid, :masa, :tutar, :yontem)
            RETURNING id, masa, tutar, yontem, created_at
            """,
            {"sid": sube_id, "masa": payload.masa, "tutar": bakiye, "yontem": yontem},
        )

        try:
            import logging
            logging.info(f"Masa {payload.masa} hesabi kapatiliyor, siparisler finalize ediliyor (sube_id={sube_id})")
            await _kasa._finalize_hazir_siparisler(payload.masa, sube_id)
        except Exception as e:
            import logging
            logging.error(f"Error finalizing orders on odeme_kapat: {e}", exc_info=True)

    return {
        "id": row["id"],
        "masa": row["masa"],
        "tutar": float(row["tutar"]),
        "yontem": row["yontem"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else "",
    }


 # done


# --- Hesap detay: siparişler + ödemeler + özet ---
@_kasa.router.get("/hesap/detay")
async def hesap_detay(
    masa: str,
    _: Mapping[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    ozet = await _kasa._hesap_ozet_core(masa, sube_id)

    import json
    
    # Sepet'i direkt çek (kasa.py'deki gibi)
    siparis_rows = await db.fetch_all(
        """
        SELECT 
            id, 
            tutar, 
            durum, 
            created_at, 
            sepet
          FROM siparisler
         WHERE masa = :masa AND durum <> 'iptal' AND sube_id = :sid
         ORDER BY created_at ASC, id ASC
        """,
        {"masa": masa, "sid": sube_id},
    )
    odeme_rows = await db.fetch_all(
        """
        SELECT id, tutar, yontem, created_at
          FROM odemeler
         WHERE masa = :masa AND iptal = FALSE AND sube_id = :sid
         ORDER BY created_at ASC, id ASC
        """,
        {"masa": masa, "sid": sube_id},
    )

    # Sepet içeriğini decode et
    import logging
    
    def decode_sepet(value, sepet_str_fallback=None):
        """
        kasa.py'deki _decode_sepet ile aynı mantık
        databases/asyncpg JSONB'yi direkt Python objesi (list/dict) olarak döndürür
        """
        if value is None:
            # Fallback olarak string'den parse et
            if sepet_str_fallback:
                try:
                    parsed = json.loads(sepet_str_fallback)
                    logging.info(f"[HESAP_DETAY] Sepet fallback string'den parse edildi")
                    return parsed if isinstance(parsed, list) else []
                except:
                    pass
            return []
        
        if isinstance(value, list):
            logging.info(f"[HESAP_DETAY] Sepet liste olarak geldi, uzunluk: {len(value)}")
            return value
        
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                logging.info(f"[HESAP_DETAY] Sepet string'den parse edildi")
                return parsed if isinstance(parsed, list) else []
            except json.JSONDecodeError as e:
                logging.warning(f"[HESAP_DETAY] Sepet string parse hatasi: {e}")
                return []
        
        # Dict gibi beklenmeyen tip
        logging.warning(f"[HESAP_DETAY] Sepet beklenmeyen tip: {type(value).__name__}, deger: {str(value)[:100]}")
        return []
    
    siparis_list = []
    for r in siparis_rows:
        # Database record'larında direkt erişim yap
        try:
            siparis_id = r["id"]
            tutar = r["tutar"]
            durum = r["durum"]
            created_at = r["created_at"]
            sepet_raw = r["sepet"]
        except (KeyError, AttributeError) as e:
            logging.error(f"[HESAP_DETAY] Siparis record'unda eksik alan: {e}")
            continue
        
        # Debug: Raw sepet değerini logla
        logging.info(
            f"[HESAP_DETAY] Siparis #{siparis_id} sepet_raw: "
            f"tip={type(sepet_raw).__name__}, "
            f"deger={str(sepet_raw)[:200] if sepet_raw is not None else 'None'}"
        )
        
        # decode_sepet fonksiyonunu çağır
        sepet_decoded = decode_sepet(sepet_raw)
        
        # Debug: sepet_decoded değerini logla
        logging.info(
            f"[HESAP_DETAY] Siparis #{siparis_id} sepet_decoded: "
            f"tip={type(sepet_decoded).__name__}, "
            f"uzunluk={len(sepet_decoded) if isinstance(sepet_decoded, list) else 0}, "
            f"icerik={str(sepet_decoded)[:200] if sepet_decoded else 'BOS'}"
        )
        
        siparis_dict = {
            "id": int(siparis_id) if siparis_id is not None else 0,
            "tutar": float(tutar or 0),
            "durum": str(durum) if durum else "yeni",
            "created_at": created_at.isoformat() if created_at else "",
            "sepet": sepet_decoded if isinstance(sepet_decoded, list) else [],  # Her zaman liste olarak gönder
        }
        
        # Debug: eklenmeden önce kontrol
        logging.info(
            f"[HESAP_DETAY] Siparis dict hazir: id={siparis_dict['id']}, "
            f"sepet_tip={type(siparis_dict['sepet']).__name__}, "
            f"sepet_uzunluk={len(siparis_dict['sepet'])}"
        )
        
        siparis_list.append(siparis_dict)
    
    # Ödenmiş siparişlerin toplamını hesapla (ödeme durumu için gerekli)
    row_odenen = await db.fetch_one(
        """
        SELECT COALESCE(SUM(tutar),0) AS toplam
        FROM siparisler
        WHERE masa = :masa AND durum = 'odendi' AND sube_id = :sid
        """,
        {"masa": masa, "sid": sube_id},
    )
    sip_odenen_toplam = float(row_odenen["toplam"] or 0.0)
    
    # Ödemelerin durumunu belirle (ödendi/beklemede)
    odemeler = []
    toplam_odenen = 0.0  # Şu ana kadar toplam ödenen tutar
    
    for row in odeme_rows:
        odeme_tutar = float(row["tutar"] or 0.0)
        onceki_toplam_odenen = toplam_odenen
        toplam_odenen += odeme_tutar
        
        durum = "beklemede"
        if toplam_odenen <= sip_odenen_toplam:
            durum = "ödendi"
        elif onceki_toplam_odenen < sip_odenen_toplam:
            durum = "beklemede"
        
        odemeler.append({
            "id": int(row["id"]) if row["id"] is not None else 0,
            "tutar": odeme_tutar,
            "yontem": str(row["yontem"]) if row["yontem"] else "",
            "created_at": (row["created_at"].isoformat() if row["created_at"] else ""),
            "durum": durum,  # "ödendi" veya "beklemede"
        })
    
    result = {
        "masa": masa,
        "ozet": ozet,
        "siparis_toplam": ozet.get("siparis_toplam", 0),
        "odeme_toplam": ozet.get("odeme_toplam", 0),
        "bakiye": ozet.get("bakiye", 0),
        "toplam": ozet.get("siparis_toplam_tum", ozet.get("siparis_toplam", 0)),
        "siparisler": siparis_list,
        "odemeler": odemeler,
    }
    
    # Debug: Final response'u logla
    logging.info(
        f"[HESAP_DETAY] Response hazir: masa={masa}, "
        f"siparis_sayisi={len(siparis_list)}, "
        f"ilk_siparis_sepet={'VAR' if siparis_list and len(siparis_list[0].get('sepet', [])) > 0 else 'YOK'}"
    )
    
    return result
