# backend/app/routers/adisyon.py
"""
Adisyon (Hesap) Yönetimi
Her masa için bir adisyon (hesap) açılır, siparişler ve ödemeler adisyon'a bağlanır.
"""
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Literal, Optional, List, Dict, Any, Mapping
from datetime import datetime

from ..core.deps import get_current_user, get_sube_id, require_roles
from ..db.database import db

router = APIRouter(prefix="/adisyon", tags=["Adisyon"])

# ------ Modeller ------
class AdisyonOut(BaseModel):
    id: int
    sube_id: int
    masa: str
    acilis_zamani: str
    kapanis_zamani: Optional[str]
    durum: str
    toplam_tutar: float
    odeme_toplam: float
    bakiye: float
    iskonto_orani: float
    iskonto_tutari: float
    created_at: str

class AdisyonOlusturIn(BaseModel):
    masa: str = Field(min_length=1)

class AdisyonKapatIn(BaseModel):
    adisyon_id: int

# ------ Yardımcı Fonksiyonlar ------
async def _get_or_create_adisyon(masa: str, sube_id: int) -> int:
    """
    Masada açık adisyon varsa döndürür, yoksa yeni oluşturur.
    Returns: adisyon_id
    """
    import logging
    
    # Açık adisyon var mı kontrol et
    mevcut = await db.fetch_one(
        """
        SELECT id FROM adisyons
        WHERE sube_id = :sid AND masa = :masa AND durum = 'acik'
        ORDER BY acilis_zamani DESC
        LIMIT 1
        """,
        {"sid": sube_id, "masa": masa},
    )
    
    if mevcut:
        return mevcut["id"]
    
    # Yeni adisyon oluştur
    yeni = await db.fetch_one(
        """
        INSERT INTO adisyons (sube_id, masa, durum, acilis_zamani)
        VALUES (:sid, :masa, 'acik', NOW())
        RETURNING id
        """,
        {"sid": sube_id, "masa": masa},
    )
    logging.info(f"Yeni adisyon oluşturuldu: masa={masa}, adisyon_id={yeni['id']}, sube_id={sube_id}")
    return yeni["id"]


def _decode_sepet(value):
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


def _to_float(val, default=0.0) -> float:
    try:
        if val is None or val == "":
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def _normalize_items(value):
    """
    siparis.sepet alanını normalize ederek ürün listesine dönüştürür.
    """
    normalized = []
    for item in _decode_sepet(value):
        if not isinstance(item, dict):
            continue

        urun = str(item.get("urun") or item.get("ad") or "").strip()
        if not urun:
            continue

        miktar = _to_float(
            item.get("adet")
            or item.get("miktar")
            or item.get("quantity")
            or item.get("qty"),
            default=1.0,
        )
        if miktar <= 0:
            miktar = 1.0

        fiyat = _to_float(
            item.get("fiyat")
            or item.get("birim_fiyat")
            or item.get("unit_price")
            or item.get("price"),
            default=0.0,
        )

        toplam = _to_float(
            item.get("toplam")
            or item.get("tutar")
            or item.get("total"),
            default=fiyat * miktar,
        )

        if fiyat == 0 and miktar:
            fiyat = toplam / miktar if toplam else 0.0

        normalized_item = {
            "urun": urun,
            "adet": miktar,
            "miktar": miktar,
            "fiyat": fiyat,
            "toplam": toplam if toplam else fiyat * miktar,
        }

        if "varyasyon" in item:
            normalized_item["varyasyon"] = item["varyasyon"]

        note = item.get("notlar") or item.get("not") or item.get("note")
        if note:
            normalized_item["notlar"] = note

        if "ikram" in item:
            normalized_item["ikram"] = item["ikram"]

        normalized.append(normalized_item)

    return normalized


def _build_adisyon_siparis_detay(rows) -> List[Dict[str, Any]]:
    """
    Sipariş satırlarını (adisyon_id -> siparisler) UI'nin beklediği formata dönüştür.
    """
    detaylar: List[Dict[str, Any]] = []
    counter = 0
    last_personel_username: Optional[str] = None
    last_personel_role: Optional[str] = None

    for row in rows:
        row_dict = dict(row)
        siparis_id = row_dict.get("id")
        durum = row_dict.get("durum") or "yeni"
        notlar_row = row_dict.get("notlar")
        created_at = row_dict.get("created_at")
        created_by_user_id = row_dict.get("created_by_user_id")
        created_by_username = row_dict.get("created_by_username")
        personel_username = row_dict.get("personel_username") or created_by_username
        personel_role = row_dict.get("personel_role")

        has_personel_source = bool(created_by_user_id or created_by_username or personel_username)
        if not has_personel_source and last_personel_username:
            personel_username = last_personel_username
            personel_role = personel_role or last_personel_role
            has_personel_source = True

        if has_personel_source:
            source_type = "personel"
            if personel_username:
                source_label = f"Personel: {personel_username}"
            else:
                source_label = "Personel"
            last_personel_username = personel_username or last_personel_username
            last_personel_role = personel_role or last_personel_role
        else:
            source_type = "asistan"
            source_label = "AI Asistan"

        # Eğer siparisler tablosunda ürün kolonları varsa doğrudan kullan
        if "urun_adi" in row_dict:
            counter += 1
            detaylar.append({
                "id": f"{siparis_id}-{counter}",
                "siparis_id": siparis_id,
                "urun_adi": row_dict.get("urun_adi"),
                "miktar": _to_float(row_dict.get("miktar"), 1.0),
                "birim_fiyat": _to_float(row_dict.get("birim_fiyat"), 0.0),
                "tutar": _to_float(row_dict.get("tutar"), 0.0),
                "durum": durum,
                "notlar": notlar_row or row_dict.get("urun_notu"),
                "created_at": created_at.isoformat() if created_at else None,
                "source_type": source_type,
                "source_label": source_label,
                "personel_username": personel_username,
                "personel_role": personel_role,
                "created_by_username": created_by_username,
            })
            continue

        sepet_items = _normalize_items(row_dict.get("sepet"))

        if sepet_items:
            for idx, item in enumerate(sepet_items, start=1):
                counter += 1
                miktar = _to_float(item.get("adet") or item.get("miktar"), 1.0)
                toplam = _to_float(item.get("toplam"), 0.0)
                fiyat = _to_float(item.get("fiyat"), toplam / miktar if miktar else 0.0)

                detaylar.append({
                    "id": f"{siparis_id}-{idx}",
                    "siparis_id": siparis_id,
                    "urun_adi": item.get("urun") or "Ürün",
                    "miktar": miktar,
                    "birim_fiyat": fiyat,
                    "tutar": toplam if toplam else fiyat * miktar,
                    "durum": durum,
                    "notlar": item.get("notlar") or notlar_row,
                    "created_at": created_at.isoformat() if created_at else None,
                    "source_type": source_type,
                    "source_label": source_label,
                    "personel_username": personel_username,
                    "personel_role": personel_role,
                    "created_by_username": created_by_username,
                })
        else:
            # Yedek: sepet boşsa yine de satırı göstermek için minimal veri ekle
            counter += 1
            toplam = _to_float(row_dict.get("tutar"), 0.0)
            detaylar.append({
                "id": f"{siparis_id}-0",
                "siparis_id": siparis_id,
                "urun_adi": "Sipariş",
                "miktar": 1.0,
                "birim_fiyat": toplam,
                "tutar": toplam,
                "durum": durum,
                "notlar": notlar_row,
                "created_at": created_at.isoformat() if created_at else None,
                "source_type": source_type,
                "source_label": source_label,
                "personel_username": personel_username,
                "personel_role": personel_role,
                "created_by_username": created_by_username,
            })

    return detaylar

async def _update_adisyon_totals(adisyon_id: int, sube_id: int) -> None:
    """
    Adisyon toplamlarını güncelle (toplam_tutar, odeme_toplam, bakiye)
    """
    import logging
    
    # Sipariş toplamı (iptal hariç tüm siparişler) ve aktif (ödenmemiş) toplam
    siparis_row = await db.fetch_one(
        """
        SELECT
            COALESCE(SUM(CASE WHEN durum <> 'iptal' THEN tutar ELSE 0 END), 0) AS toplam,
            COUNT(CASE WHEN durum <> 'iptal' THEN 1 END) AS siparis_sayisi,
            COALESCE(SUM(CASE WHEN durum IN ('yeni', 'hazirlaniyor', 'hazir') THEN tutar ELSE 0 END), 0) AS aktif_toplam
        FROM siparisler
        WHERE adisyon_id = :aid AND sube_id = :sid
        """,
        {"aid": adisyon_id, "sid": sube_id},
    )
    toplam_tutar = float(siparis_row["toplam"] or 0) if siparis_row else 0.0
    siparis_sayisi = int(siparis_row["siparis_sayisi"] or 0) if siparis_row else 0
    aktif_toplam = float(siparis_row["aktif_toplam"] or 0) if siparis_row else 0.0
    
    # Önce adisyon açılış tarihini al
    adisyon_info = await db.fetch_one(
        "SELECT acilis_zamani FROM adisyons WHERE id = :aid",
        {"aid": adisyon_id},
    )
    acilis_zamani = adisyon_info["acilis_zamani"] if adisyon_info else None
    
    # Ödeme toplamı - SADECE bu adisyona ait ödemeler
    # ÖNEMLİ: Ödeme tarihi adisyon açılış tarihinden sonra olmalı (eski ödemeleri filtrele)
    if acilis_zamani:
        odeme_row = await db.fetch_one(
            """
            SELECT COALESCE(SUM(tutar), 0) AS toplam, COUNT(*) AS odeme_sayisi
            FROM odemeler
            WHERE adisyon_id = :aid AND sube_id = :sid AND iptal = FALSE 
              AND created_at >= :acilis_zamani
            """,
            {"aid": adisyon_id, "sid": sube_id, "acilis_zamani": acilis_zamani},
        )
    else:
        # Fallback: acilis_zamani yoksa tüm ödemeleri say (bu olmamalı)
        odeme_row = await db.fetch_one(
            """
            SELECT COALESCE(SUM(tutar), 0) AS toplam, COUNT(*) AS odeme_sayisi
            FROM odemeler
            WHERE adisyon_id = :aid AND sube_id = :sid AND iptal = FALSE
            """,
            {"aid": adisyon_id, "sid": sube_id},
        )
    odeme_toplam = float(odeme_row["toplam"] or 0) if odeme_row else 0.0
    odeme_sayisi = int(odeme_row["odeme_sayisi"] or 0) if odeme_row else 0
    
    # İskonto bilgilerini al (debug log'u için masa'ya ihtiyacımız var)
    adisyon_row = await db.fetch_one(
        "SELECT iskonto_orani, iskonto_tutari, masa FROM adisyons WHERE id = :aid",
        {"aid": adisyon_id},
    )
    iskonto_orani = float(adisyon_row["iskonto_orani"] or 0) if adisyon_row else 0.0
    iskonto_tutari_db = float(adisyon_row["iskonto_tutari"] or 0) if adisyon_row else 0.0
    masa = adisyon_row["masa"] if adisyon_row else "?"
    
    # Debug: Eğer ödeme toplamı sipariş toplamından fazlaysa, uyarı ver ve düzelt
    if odeme_toplam > toplam_tutar + 0.01:  # 0.01 tolerans
        # Detaylı ödeme bilgilerini logla
        odeme_detay = await db.fetch_all(
            """
            SELECT id, tutar, created_at, masa
            FROM odemeler
            WHERE adisyon_id = :aid AND sube_id = :sid AND iptal = FALSE
            ORDER BY created_at ASC
            """,
            {"aid": adisyon_id, "sid": sube_id},
        )
        odeme_detay_str = ", ".join([f"#{r['id']}: {r['tutar']} TL ({r['created_at']})" for r in odeme_detay])
        logging.warning(
            f"[ADISYON_UPDATE] UYARI: Adisyon #{adisyon_id} (masa={masa}, açılış={acilis_zamani}) için ödeme toplamı ({odeme_toplam:.2f} TL) "
            f"sipariş toplamından ({toplam_tutar:.2f} TL) fazla! Ödemeler: {odeme_detay_str}"
        )
        
        # Eğer ödeme toplamı sipariş toplamından fazlaysa, fazla ödemeleri kontrol et
        # Bu ödemeler muhtemelen eski adisyona ait ve yanlış bağlanmış
        if acilis_zamani and odeme_detay:
            # Strateji: 
            # 1. Eğer sipariş varsa (toplam_tutar > 0): En yeni ödemeleri tut, fazlasını ayır
            # 2. Eğer sipariş yoksa (toplam_tutar = 0): Tüm ödemeleri ayır (boş adisyon için ödeme olmaz)
            if toplam_tutar > 0.01:
                # Sipariş var: En yeni ödemeleri tutup, fazlasını ayır
                odeme_toplam_hesapla = 0.0
                fazla_odemeler = []
                normal_odemeler = []
                
                # Ödemeleri tarihe göre sırala (en yeni önce)
                sorted_odemeler = sorted(odeme_detay, key=lambda x: x['created_at'], reverse=True)
                
                for odeme in sorted_odemeler:
                    odeme_tutar = float(odeme['tutar'])
                    if odeme_toplam_hesapla + odeme_tutar <= toplam_tutar + 0.01:
                        normal_odemeler.append(odeme)
                        odeme_toplam_hesapla += odeme_tutar
                    else:
                        fazla_odemeler.append(odeme)
                
                # Eğer fazla ödemeler varsa, bunları adisyon_id'den ayır
                if fazla_odemeler:
                    fazla_odeme_ids = [r['id'] for r in fazla_odemeler]
                    await db.execute(
                        """
                        UPDATE odemeler
                        SET adisyon_id = NULL
                        WHERE id = ANY(:ids) AND sube_id = :sid
                        """,
                        {"ids": fazla_odeme_ids, "sid": sube_id},
                    )
                    logging.info(
                        f"[ADISYON_UPDATE] {len(fazla_odeme_ids)} fazla ödeme adisyon #{adisyon_id} "
                        f"bağlantısından kaldırıldı: {fazla_odeme_ids}. Kalan ödemeler: {[r['id'] for r in normal_odemeler]}"
                    )
                    # Ödeme toplamını yeniden hesapla (sadece kalan ödemeler)
                    odeme_toplam = odeme_toplam_hesapla
                    odeme_sayisi = len(normal_odemeler)
            else:
                # Sipariş yok: Tüm ödemeleri ayır (boş adisyon için ödeme olmaz)
                tum_odeme_ids = [r['id'] for r in odeme_detay]
                await db.execute(
                    """
                    UPDATE odemeler
                    SET adisyon_id = NULL
                    WHERE id = ANY(:ids) AND sube_id = :sid
                    """,
                    {"ids": tum_odeme_ids, "sid": sube_id},
                )
                logging.info(
                    f"[ADISYON_UPDATE] {len(tum_odeme_ids)} ödeme adisyon #{adisyon_id} "
                    f"bağlantısından kaldırıldı (sipariş yok): {tum_odeme_ids}"
                )
                odeme_toplam = 0.0
                odeme_sayisi = 0
    
    # İskonto tutarını hesapla ve net toplamı belirle
    iskonto_tutari_calc = 0.0
    if iskonto_orani > 0:
        iskonto_tutari_calc = round((toplam_tutar * iskonto_orani) / 100.0, 2)
    if iskonto_tutari_db > 0:
        iskonto_tutari = min(max(iskonto_tutari_db, 0.0), toplam_tutar)
    else:
        iskonto_tutari = min(max(iskonto_tutari_calc, 0.0), toplam_tutar)

    net_toplam = max(0.0, toplam_tutar - iskonto_tutari)

    # Bakiye hesapla
    bakiye = max(0.0, net_toplam - odeme_toplam)
    aktif_bakiye = max(0.0, aktif_toplam - odeme_toplam)
    
    # Debug log
    logging.info(
        f"[ADISYON_UPDATE] Adisyon #{adisyon_id} (masa={masa}): "
        f"siparis_sayisi={siparis_sayisi}, toplam_tutar={toplam_tutar:.2f}, net_toplam={net_toplam:.2f}, "
        f"aktif_toplam={aktif_toplam:.2f}, odeme_sayisi={odeme_sayisi}, odeme_toplam={odeme_toplam:.2f}, "
        f"iskonto={iskonto_orani}%, iskonto_tutari={iskonto_tutari:.2f}, bakiye={bakiye:.2f}, aktif_bakiye={aktif_bakiye:.2f}"
    )
    
    # Adisyonu güncelle
    await db.execute(
        """
        UPDATE adisyons
        SET toplam_tutar = :toplam,
            odeme_toplam = :odeme,
            bakiye = :bakiye,
            iskonto_tutari = :iskonto
        WHERE id = :aid
        """,
        {
            "aid": adisyon_id,
            "toplam": toplam_tutar,
            "odeme": odeme_toplam,
            "bakiye": bakiye,
            "iskonto": iskonto_tutari,
        },
    )

# ------ Endpoint'ler ------
@router.post("/olustur", response_model=AdisyonOut)
async def adisyon_olustur(
    payload: AdisyonOlusturIn,
    _: Mapping[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """Yeni adisyon oluştur"""
    adisyon_id = await _get_or_create_adisyon(payload.masa, sube_id)
    
    row = await db.fetch_one(
        "SELECT * FROM adisyons WHERE id = :aid",
        {"aid": adisyon_id},
    )
    
    return AdisyonOut(
        id=row["id"],
        sube_id=row["sube_id"],
        masa=row["masa"],
        acilis_zamani=row["acilis_zamani"].isoformat() if row["acilis_zamani"] else "",
        kapanis_zamani=row["kapanis_zamani"].isoformat() if row["kapanis_zamani"] else None,
        durum=row["durum"],
        toplam_tutar=float(row["toplam_tutar"] or 0),
        odeme_toplam=float(row["odeme_toplam"] or 0),
        bakiye=float(row["bakiye"] or 0),
        iskonto_orani=float(row["iskonto_orani"] or 0),
        iskonto_tutari=float(row.get("iskonto_tutari") or 0),
        created_at=row["created_at"].isoformat() if row["created_at"] else "",
    )

@router.get("/acik", response_model=List[AdisyonOut])
async def acik_adisyons(
    limit: int = Query(200, ge=1, le=2000),
    durum: Optional[str] = Query(None, description="'acik', 'kapali' veya None (tümü)"),
    _: Mapping[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """Adisyonları listele - durum filtresi ile açık/kapalı/tümü"""
    import logging
    
    if durum and durum in ['acik', 'kapali']:
        where_clause = "WHERE sube_id = :sid AND durum = :durum"
        params = {"sid": sube_id, "limit": limit, "durum": durum}
    else:
        where_clause = "WHERE sube_id = :sid"
        params = {"sid": sube_id, "limit": limit}
    
    rows = await db.fetch_all(
        f"""
        SELECT * FROM adisyons
        {where_clause}
        ORDER BY acilis_zamani DESC
        LIMIT :limit
        """,
        params,
    )
    
    # Sadece açık adisyonların toplamlarını güncelle (kapalı adisyonlar değişmez)
    for r in rows:
        adisyon_id = r["id"]
        try:
            adisyon_durum = r["durum"] if "durum" in r else "acik"
        except (KeyError, AttributeError):
            adisyon_durum = "acik"
        
        # Sadece açık adisyonların toplamlarını güncelle
        if adisyon_durum == "acik":
            try:
                await _update_adisyon_totals(adisyon_id, sube_id)
            except Exception as e:
                logging.warning(f"[ADISYON] Adisyon #{adisyon_id} toplamları güncellenirken hata: {e}", exc_info=True)
    
    # Güncellenmiş verileri tekrar çek (sadece açık adisyonlar güncellendi)
    if durum == "acik" or not durum:
        rows = await db.fetch_all(
            f"""
            SELECT * FROM adisyons
            {where_clause}
            ORDER BY acilis_zamani DESC
            LIMIT :limit
            """,
            params,
        )
    # Kapalı adisyonlar için tekrar çekmeye gerek yok, değişmedi
    
    return [
        AdisyonOut(
            id=r["id"],
            sube_id=r["sube_id"],
            masa=r["masa"],
            acilis_zamani=r["acilis_zamani"].isoformat() if r["acilis_zamani"] else "",
            kapanis_zamani=r["kapanis_zamani"].isoformat() if r["kapanis_zamani"] else None,
            durum=r["durum"],
            toplam_tutar=float(r["toplam_tutar"] or 0),
            odeme_toplam=float(r["odeme_toplam"] or 0),
            bakiye=float(r["bakiye"] or 0),
            iskonto_orani=float(r["iskonto_orani"] or 0),
            iskonto_tutari=float(dict(r).get("iskonto_tutari") or 0),
            created_at=r["created_at"].isoformat() if r["created_at"] else "",
        )
        for r in rows
    ]

@router.get("/masa/{masa}", response_model=Optional[AdisyonOut])
async def masa_adisyon(
    masa: str,
    _: Mapping[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """Masada açık adisyon varsa döndürür"""
    row = await db.fetch_one(
        """
        SELECT * FROM adisyons
        WHERE sube_id = :sid AND masa = :masa AND durum = 'acik'
        ORDER BY acilis_zamani DESC
        LIMIT 1
        """,
        {"sid": sube_id, "masa": masa},
    )
    
    if not row:
        return None
    
    return AdisyonOut(
        id=row["id"],
        sube_id=row["sube_id"],
        masa=row["masa"],
        acilis_zamani=row["acilis_zamani"].isoformat() if row["acilis_zamani"] else "",
        kapanis_zamani=row["kapanis_zamani"].isoformat() if row["kapanis_zamani"] else None,
        durum=row["durum"],
        toplam_tutar=float(row["toplam_tutar"] or 0),
        odeme_toplam=float(row["odeme_toplam"] or 0),
        bakiye=float(row["bakiye"] or 0),
        iskonto_orani=float(row["iskonto_orani"] or 0),
        iskonto_tutari=float(row.get("iskonto_tutari") or 0),
        created_at=row["created_at"].isoformat() if row["created_at"] else "",
    )

@router.get("/{adisyon_id}", response_model=AdisyonOut)
async def adisyon_detay(
    adisyon_id: int,
    _: Mapping[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """Adisyon detayını getir"""
    row = await db.fetch_one(
        "SELECT * FROM adisyons WHERE id = :aid AND sube_id = :sid",
        {"aid": adisyon_id, "sid": sube_id},
    )
    
    if not row:
        raise HTTPException(status_code=404, detail="Adisyon bulunamadı")
    
    return AdisyonOut(
        id=row["id"],
        sube_id=row["sube_id"],
        masa=row["masa"],
        acilis_zamani=row["acilis_zamani"].isoformat() if row["acilis_zamani"] else "",
        kapanis_zamani=row["kapanis_zamani"].isoformat() if row["kapanis_zamani"] else None,
        durum=row["durum"],
        toplam_tutar=float(row["toplam_tutar"] or 0),
        odeme_toplam=float(row["odeme_toplam"] or 0),
        bakiye=float(row["bakiye"] or 0),
        iskonto_orani=float(row["iskonto_orani"] or 0),
        iskonto_tutari=float(row.get("iskonto_tutari") or 0),
        created_at=row["created_at"].isoformat() if row["created_at"] else "",
    )

@router.post("/{adisyon_id}/kapat")
async def adisyon_kapat(
    adisyon_id: int,
    _: Mapping[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """
    Adisyonu kapat:
    - Tüm 'hazir' durumundaki siparişleri 'odendi' yap
    - Stoktan düş
    - Adisyon durumunu 'kapali' yap
    """
    import logging
    from ..routers.kasa import _finalize_hazir_siparisler
    
    # Adisyon kontrolü
    adisyon = await db.fetch_one(
        "SELECT * FROM adisyons WHERE id = :aid AND sube_id = :sid",
        {"aid": adisyon_id, "sid": sube_id},
    )
    
    if not adisyon:
        raise HTTPException(status_code=404, detail="Adisyon bulunamadı")
    
    if adisyon["durum"] == "kapali":
        raise HTTPException(status_code=400, detail="Adisyon zaten kapalı")
    
    masa = adisyon["masa"]
    
    async with db.transaction():
        # Hazir siparişleri finalize et (odendi yap ve stoktan düş)
        finalized_ids = await _finalize_hazir_siparisler(masa, sube_id)
        logging.info(f"Adisyon #{adisyon_id} kapatılıyor: {len(finalized_ids)} sipariş finalize edildi")

        # Adisyonu kapat
        await db.execute(
            """
            UPDATE adisyons
            SET durum = 'kapali', kapanis_zamani = NOW()
            WHERE id = :aid
            """,
            {"aid": adisyon_id},
        )

        # Masayı boşalt - masanın durumunu 'bos' yap
        await db.execute(
            """
            UPDATE masalar
            SET durum = 'bos'
            WHERE sube_id = :sid AND masa_adi = :masa
            """,
            {"sid": sube_id, "masa": masa},
        )
        logging.info(f"Masa '{masa}' durumu 'bos' olarak güncellendi (adisyon #{adisyon_id} kapatıldı)")

        # Toplamları güncelle
        await _update_adisyon_totals(adisyon_id, sube_id)
        
        # Cache invalidation: Analytics ve istatistiklerini temizle
        # Önemli: Adisyon kapatıldığında ciro değiştiği için cache'i temizlemeliyiz
        if finalized_ids:  # Sadece sipariş kapatıldıysa cache'i temizle
            try:
                from ..core.cache import cache
                # Analytics cache'lerini temizle (analytics:ozet, analytics:saatlik vb.)
                await cache.delete_pattern("analytics:*")
                # İstatistik cache'lerini temizle
                await cache.delete_pattern("istatistik:*")
                logging.info(f"[CACHE_INVALIDATION] Analytics ve istatistik cache'leri temizlendi (adisyon_id={adisyon_id}, sube_id={sube_id}, finalized_count={len(finalized_ids)})")
            except Exception as e:
                logging.warning(f"[CACHE_INVALIDATION] Cache temizleme hatası: {e}", exc_info=True)
                # Cache hatası adisyon kapatma işlemini engellemez
    
    return {"message": "Adisyon başarıyla kapatıldı", "finalized_orders": len(finalized_ids)}

@router.patch("/{adisyon_id}/iskonto")
async def adisyon_iskonto(
    adisyon_id: int,
    iskonto_orani: float = Query(..., ge=0.0, le=100.0),
    _: Mapping[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """Adisyon iskonto oranını güncelle"""
    # Adisyon kontrolü
    adisyon = await db.fetch_one(
        "SELECT * FROM adisyons WHERE id = :aid AND sube_id = :sid",
        {"aid": adisyon_id, "sid": sube_id},
    )
    
    if not adisyon:
        raise HTTPException(status_code=404, detail="Adisyon bulunamadı")
    
    if adisyon["durum"] == "kapali":
        raise HTTPException(status_code=400, detail="Kapalı adisyona iskonto uygulanamaz")
    
    # Güncel sipariş toplamını al (hazir/yeni siparişler)
    siparis_row = await db.fetch_one(
        """
        SELECT COALESCE(SUM(tutar), 0) AS toplam
        FROM siparisler
        WHERE adisyon_id = :aid AND sube_id = :sid AND durum IN ('yeni', 'hazirlaniyor', 'hazir')
        """,
        {"aid": adisyon_id, "sid": sube_id},
    )
    siparis_toplam = float(siparis_row["toplam"] or 0) if siparis_row else 0.0
    iskonto_tutari = round((siparis_toplam * iskonto_orani) / 100.0, 2) if siparis_toplam > 0 else 0.0

    # İskonto oranını güncelle
    await db.execute(
        """
        UPDATE adisyons 
        SET iskonto_orani = :iskonto,
            iskonto_tutari = :iskonto_tutari
        WHERE id = :aid
        """,
        {"iskonto": iskonto_orani, "iskonto_tutari": iskonto_tutari, "aid": adisyon_id},
    )

    # İskonto kaydını logla
    await db.execute(
        """
        INSERT INTO iskonto_kayitlari (adisyon_id, sube_id, masa, tutar, oran, kaynak, aciklama)
        VALUES (:aid, :sid, :masa, :tutar, :oran, :kaynak, :aciklama)
        """,
        {
            "aid": adisyon_id,
            "sid": sube_id,
            "masa": adisyon["masa"],
            "tutar": iskonto_tutari,
            "oran": iskonto_orani,
            "kaynak": "manuel",
            "aciklama": None,
        },
    )
    
    # Toplamları güncelle
    await _update_adisyon_totals(adisyon_id, sube_id)

    return {"message": "İskonto oranı güncellendi", "iskonto_orani": iskonto_orani}

@router.get("/{adisyon_id}/detayli", response_model=Dict[str, Any])
async def adisyon_detayli(
    adisyon_id: int,
    _: Mapping[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """
    Adisyon detayını siparişler ve ödemelerle birlikte getir
    """
    # Adisyon bilgisi
    adisyon = await db.fetch_one(
        "SELECT * FROM adisyons WHERE id = :aid AND sube_id = :sid",
        {"aid": adisyon_id, "sid": sube_id},
    )

    if not adisyon:
        raise HTTPException(status_code=404, detail="Adisyon bulunamadı")

    # Siparişler
    siparisler_rows = await db.fetch_all(
        """
        SELECT s.id,
               s.masa,
               s.sepet,
               s.durum,
               s.tutar,
               s.created_at,
               s.created_by_user_id,
               s.created_by_username,
               u.username AS personel_username,
               u.role AS personel_role
        FROM siparisler s
        LEFT JOIN users u ON (
            (s.created_by_user_id IS NOT NULL AND u.id = s.created_by_user_id)
            OR (s.created_by_user_id IS NULL AND s.created_by_username IS NOT NULL AND u.username = s.created_by_username)
        )
        WHERE s.adisyon_id = :aid AND s.sube_id = :sid
        ORDER BY s.created_at ASC
        """,
        {"aid": adisyon_id, "sid": sube_id},
    )

    detay_siparisler = _build_adisyon_siparis_detay(siparisler_rows)

    # Ödemeler
    odemeler = await db.fetch_all(
        """
        SELECT id, tutar, yontem, created_at, iptal
        FROM odemeler
        WHERE adisyon_id = :aid AND sube_id = :sid
        ORDER BY created_at ASC
        """,
        {"aid": adisyon_id, "sid": sube_id},
    )

    adisyon_dict = dict(adisyon)

    return {
        "adisyon": {
            "id": adisyon_dict["id"],
            "sube_id": adisyon_dict["sube_id"],
            "masa": adisyon_dict["masa"],
            "acilis_zamani": adisyon_dict["acilis_zamani"].isoformat() if adisyon_dict["acilis_zamani"] else None,
            "kapanis_zamani": adisyon_dict["kapanis_zamani"].isoformat() if adisyon_dict["kapanis_zamani"] else None,
            "durum": adisyon_dict["durum"],
            "toplam_tutar": float(adisyon_dict.get("toplam_tutar") or 0),
            "odeme_toplam": float(adisyon_dict.get("odeme_toplam") or 0),
            "bakiye": float(adisyon_dict.get("bakiye") or 0),
            "iskonto_orani": float(adisyon_dict.get("iskonto_orani") or 0),
            "iskonto_tutari": float(adisyon_dict.get("iskonto_tutari") or 0),
            "created_at": adisyon_dict["created_at"].isoformat() if adisyon_dict["created_at"] else None,
        },
        "siparisler": detay_siparisler,
        "odemeler": [
            {
                "id": o_dict["id"],
                "tutar": float(o_dict.get("tutar") or 0),
                "yontem": o_dict.get("yontem"),
                "iptal": o_dict.get("iptal"),
                "tip": float(o_dict.get("tip") or 0),
                "created_at": o_dict["created_at"].isoformat() if o_dict.get("created_at") else None,
            }
            for o in odemeler
            for o_dict in [dict(o)]
        ],
    }

