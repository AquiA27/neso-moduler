# backend/app/routers/kasa.py
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Literal, Optional, List, Dict, Any, Mapping

from ..core.deps import get_current_user, get_sube_id, require_roles
from ..db.database import db

router = APIRouter(prefix="/kasa", tags=["Kasa"])

# deme yntemleri
Yontem = Literal["nakit", "kart", "havale", "iyzico", "papara", "diger"]

# ------ Modeller ------
class OdemeIn(BaseModel):
    masa: str = Field(min_length=1)
    tutar: float = Field(ge=0.01)
    yontem: Yontem
    iskonto_orani: Optional[float] = Field(default=0.0, ge=0.0, le=100.0, description="İskonto yüzdesi (0-100)")


class ItemMasaDegistirIn(BaseModel):
    siparis_id: int
    item_index: int
    yeni_masa: str


class ItemIkramIn(BaseModel):
    siparis_id: int
    item_index: int

class OdemeOut(BaseModel):
    id: int
    masa: str
    tutar: float
    yontem: str
    created_at: str
    remaining_balance: float
    auto_closed: bool = False
    tip: float = 0.0

class HesapOzetOut(BaseModel):
    masa: str
    siparis_toplam: float
    odeme_toplam: float
    bakiye: float

# ------  yardmc ------
async def _hesap_ozet_core(masa: str, sube_id: int) -> Dict[str, Any]:
    params_base = {"sid": sube_id, "masa": masa}

    adisyon_row = await db.fetch_one(
        """
        SELECT id, acilis_zamani
        FROM adisyons
        WHERE sube_id = :sid
          AND masa = :masa
          AND durum = 'acik'
        ORDER BY acilis_zamani DESC
        LIMIT 1
        """,
        params_base,
    )

    adisyon_id = adisyon_row["id"] if adisyon_row else None
    session_start_dt = adisyon_row["acilis_zamani"] if adisyon_row else None

    orders_condition = ""
    orders_params: Dict[str, Any] = {"sid": sube_id}

    if adisyon_id is not None:
        orders_condition = "adisyon_id = :aid"
        orders_params["aid"] = adisyon_id
    else:
        orders_condition = "masa = :masa"
        orders_params["masa"] = masa
        if session_start_dt is None:
            start_row = await db.fetch_one(
                """
                SELECT MIN(created_at) AS first_created
                FROM siparisler
                WHERE masa = :masa AND sube_id = :sid AND durum IN ('yeni', 'hazirlaniyor', 'hazir')
                """,
                params_base,
            )
            session_start_dt = start_row["first_created"] if start_row else None

    time_filter_clause = ""
    if session_start_dt is not None and adisyon_id is None:
        orders_params["start_time"] = session_start_dt
        time_filter_clause = " AND created_at >= :start_time"

    row1 = await db.fetch_one(
        f"""
        SELECT COALESCE(SUM(tutar),0) AS toplam
        FROM siparisler
        WHERE {orders_condition}
          AND durum IN ('yeni', 'hazirlaniyor', 'hazir')
          AND sube_id = :sid
        """,
        orders_params,
    )
    sip_toplam = float(row1["toplam"] or 0)

    row_hazir = await db.fetch_one(
        f"""
        SELECT COALESCE(SUM(tutar),0) AS toplam
        FROM siparisler
        WHERE {orders_condition}
          AND durum = 'hazir'
          AND sube_id = :sid
        """,
        orders_params,
    )
    hazir_toplam = float(row_hazir["toplam"] or 0)

    row_odendi = await db.fetch_one(
        f"""
        SELECT COALESCE(SUM(tutar),0) AS toplam
        FROM siparisler
        WHERE {orders_condition}
          AND durum = 'odendi'
          AND sube_id = :sid
          {time_filter_clause}
        """,
        orders_params,
    )
    odendi_toplam = float(row_odendi["toplam"] or 0)

    row_all = await db.fetch_one(
        f"""
        SELECT COALESCE(SUM(tutar),0) AS toplam
        FROM siparisler
        WHERE {orders_condition}
          AND durum <> 'iptal'
          AND sube_id = :sid
          {time_filter_clause}
        """,
        orders_params,
    )
    sip_all_toplam = float(row_all["toplam"] or 0)

    if adisyon_id is not None:
        payment_params: Dict[str, Any] = {"sid": sube_id, "aid": adisyon_id}
        if session_start_dt is not None:
            payment_params["start_time"] = session_start_dt
            payments_sql = """
                SELECT COALESCE(SUM(tutar),0) AS toplam
                FROM odemeler
                WHERE sube_id = :sid
                  AND adisyon_id = :aid
                  AND iptal = FALSE
                  AND created_at >= :start_time
            """
        else:
            payments_sql = """
                SELECT COALESCE(SUM(tutar),0) AS toplam
                FROM odemeler
                WHERE sube_id = :sid
                  AND adisyon_id = :aid
                  AND iptal = FALSE
            """
        row2 = await db.fetch_one(payments_sql, payment_params)
    else:
        if session_start_dt is not None:
            payment_params = {
                "sid": sube_id,
                "masa": masa,
                "start_time": session_start_dt,
            }
            payments_sql = """
                SELECT COALESCE(SUM(tutar),0) AS toplam
                FROM odemeler
                WHERE sube_id = :sid
                  AND masa = :masa
                  AND iptal = FALSE
                  AND adisyon_id IS NULL
                  AND created_at >= :start_time
            """
            row2 = await db.fetch_one(payments_sql, payment_params)
        else:
            # Hiç aktif sipariş yoksa mevcut seansı yok say
            row2 = {"toplam": 0}

    od_toplam = float(row2["toplam"] or 0)

    # Bakiye hesaplama mantığı:
    # "hazir" durumundaki siparişler henüz ödenmemiş kabul edilir
    # Ödemeler önce "odendi" durumundaki siparişlere uygulanır, sonra "hazir" siparişlere
    # Bakiye = hazir_toplam - max(0, ödemeler - odendi_toplam)
    # Eğer ödemeler >= (odendi_toplam + hazir_toplam) ise: bakiye = 0
    # Aksi halde: bakiye = hazir_toplam - max(0, ödemeler - odendi_toplam)
    if hazir_toplam > 0:
        # "hazir" durumundaki siparişler var
        # Ödemeler önce "odendi" siparişlere uygulanır, sonra "hazir" siparişlere
        odendi_icin_odeme = min(od_toplam, odendi_toplam)
        hazir_icin_odeme = max(0.0, od_toplam - odendi_icin_odeme)
        
        if hazir_icin_odeme >= hazir_toplam:
            # Tüm "hazir" siparişler ödenmiş, bakiye 0
            bakiye = 0.0
        else:
            # "hazir" siparişlerin bir kısmı ödenmemiş
            bakiye = hazir_toplam - hazir_icin_odeme
    elif sip_toplam > 0:
        # Aktif siparişler var ama "hazir" yok, normal hesaplama
        bakiye = max(0.0, sip_toplam - od_toplam)
    else:
        # Aktif sipariş yok
        if od_toplam >= sip_all_toplam and sip_all_toplam > 0:
            # Tüm siparişler öденmiş, bakiye 0
            bakiye = 0.0
        else:
            # Aktif sipariş yok ve finalize edilmiş, bakiye 0
            bakiye = 0.0

    return {
        "masa": masa,
        "siparis_toplam": sip_toplam,
        "odeme_toplam": od_toplam,
        "bakiye": round(max(0.0, bakiye), 2),
        "adisyon_id": adisyon_id,
        "session_start": session_start_dt.isoformat() if session_start_dt else None,
    }


async def _finalize_hazir_siparisler(masa: str, sube_id: int) -> List[int]:
    """
    Masadaki aktif siparişleri 'odendi' durumuna çeker ve stoktan düşer.
    NOT: Tüm aktif siparişler ('yeni', 'hazirlaniyor', 'hazir') için stok düşülür.
    Ödeme alındığında artık siparişler hazır olup olmadığına bakılmaksızın stoktan düşülmelidir.
    Donus olarak kapanan siparis ID'lerini verir.
    """
    import logging
    
    # Tüm aktif siparişleri bul (stok düşürme için ödeme alındığında tüm aktif siparişler düşülmeli)
    # ÖNEMLİ: Artık sadece 'hazir' değil, tüm aktif siparişler finalize ediliyor
    ready_orders = await db.fetch_all(
        """
        SELECT id, sepet, durum
        FROM siparisler
        WHERE sube_id = :sid AND masa = :masa AND durum IN ('yeni', 'hazirlaniyor', 'hazir')
        ORDER BY created_at ASC, id ASC
        """,
        {"sid": sube_id, "masa": masa},
    )
    
    if not ready_orders:
        logging.info(f"Masa {masa} icin aktif siparis bulunamadi, stok dusurme yapilmayacak (sube_id={sube_id})")
        return []
    
    durum_dagilimi = {}
    for r in ready_orders:
        durum = r.get("durum", "bilinmeyen")
        durum_dagilimi[durum] = durum_dagilimi.get(durum, 0) + 1
    
    logging.info(
        f"Masa {masa} icin {len(ready_orders)} aktif siparis bulundu (durum dagilimi: {durum_dagilimi}), "
        f"stok dusuluyor... (sube_id={sube_id})"
    )

    # ÖNEMLİ: Stok düşürme işlemi sipariş durumu değişmeden ÖNCE yapılmalı
    logging.info(f"Masa {masa} icin stok dusurme islemi baslatiliyor...")
    await _dus_stok_recepte(masa, sube_id, ready_orders)
    logging.info(f"Masa {masa} icin stok dusurme islemi tamamlandi.")
    
    # Database record'larda .get() yok, direkt erişim yap
    ids = []
    for r in ready_orders:
        try:
            if r["id"] is not None:
                ids.append(int(r["id"]))
        except (KeyError, AttributeError, ValueError):
            continue
    if not ids:
        logging.warning(f"Masa {masa} icin siparis ID'leri bulunamadi")
        return []

    # Sipariş durumlarını güncelle
    result = await db.execute(
        """
        UPDATE siparisler
           SET durum = 'odendi'
         WHERE sube_id = :sid
           AND id = ANY(:ids)
        """,
        {"sid": sube_id, "ids": ids},
    )
    logging.info(f"Masa {masa} icin {len(ids)} siparis 'odendi' durumuna gecirildi")
    
    # Cache invalidation: Analytics ve admin istatistiklerini temizle
    # Önemli: Ödeme sonrası ciro değiştiği için cache'i temizlemeliyiz
    if ids:  # Sadece sipariş kapatıldıysa cache'i temizle
        try:
            from ..core.cache import cache
            # Analytics cache'lerini temizle (analytics:ozet, analytics:saatlik vb.)
            await cache.delete_pattern("analytics:*")
            # İstatistik cache'lerini temizle
            await cache.delete_pattern("istatistik:*")
            logging.info(f"[CACHE_INVALIDATION] Analytics ve istatistik cache'leri temizlendi (masa={masa}, sube_id={sube_id}, finalized_count={len(ids)})")
        except Exception as e:
            logging.warning(f"[CACHE_INVALIDATION] Cache temizleme hatası: {e}", exc_info=True)
            # Cache hatası ödeme işlemini engellemez
    
    return ids

# ------ Ular ------
@router.get("/hesap/ozet", response_model=HesapOzetOut)
async def hesap_ozet(
    masa: str = Query(..., min_length=1),
    _: Mapping[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    return await _hesap_ozet_core(masa, sube_id)

@router.post(
    "/odeme/ekle",
    response_model=OdemeOut,
    dependencies=[Depends(require_roles({"admin", "operator"}))]
)
async def odeme_ekle(
    payload: OdemeIn,
    _: Mapping[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    import logging
    
    # Adisyon sistemine göre bakiye kontrolü
    # Önce adisyon tablosundan bakiyeyi al
    adisyon_row = await db.fetch_one(
        """
        SELECT id, bakiye FROM adisyons
        WHERE sube_id = :sid AND masa = :masa AND durum = 'acik'
        ORDER BY acilis_zamani DESC
        LIMIT 1
        """,
        {"sid": sube_id, "masa": payload.masa},
    )
    
    adisyon_id = None
    if adisyon_row:
        adisyon_id = adisyon_row["id"]
        # Adisyon varsa, toplamları güncelle ve bakiyeyi al
        from ..routers.adisyon import _update_adisyon_totals
        await _update_adisyon_totals(adisyon_id, sube_id)
        # Güncellenmiş bakiyeyi tekrar al
        adisyon_row_updated = await db.fetch_one(
            "SELECT bakiye FROM adisyons WHERE id = :aid",
            {"aid": adisyon_id},
        )
        bakiye = float(adisyon_row_updated["bakiye"] or 0) if adisyon_row_updated else 0.0
    else:
        # Adisyon yoksa eski sistemi kullan
        ozet = await _hesap_ozet_core(payload.masa, sube_id)
        bakiye = float(ozet.get("bakiye", 0) if isinstance(ozet, dict) else (ozet["bakiye"] if "bakiye" in ozet else 0))
    
    if bakiye is None or bakiye < 0:
        bakiye = 0.0
    
    logging.info(f"[ODEME_EKLE] Masa: {payload.masa}, bakiye: {bakiye:.2f} TL, tutar: {payload.tutar:.2f} TL, iskonto: {payload.iskonto_orani or 0}%")
    
    # İskonto uygula
    iskonto_orani = payload.iskonto_orani or 0.0
    if iskonto_orani > 0:
        # Kullanıcıya gösterilen bakiye üzerinden uygulanacak iskonto varsayılanı
        iskonto_tutari_teorik = (bakiye * iskonto_orani) / 100.0
        odenecek_tutar = max(0.0, bakiye - iskonto_tutari_teorik)
        # Eğer kullanıcı bakiye kadar girip iskonto istedi ise otomatik uygula
        if abs(payload.tutar - bakiye) < 0.01:
            final_tutar = odenecek_tutar
        else:
            # Kullanıcının girdiği tutarı esas al
            final_tutar = payload.tutar
    else:
        final_tutar = payload.tutar

    tip_amount = 0.0
    if final_tutar > bakiye + 0.01:
        tip_amount = round(final_tutar - bakiye, 2)
        final_tutar = bakiye

    final_tutar = max(0.0, round(final_tutar, 2))
    discount_amount = 0.0
    if iskonto_orani > 0:
        # Gerçekte uygulanan iskonto, bakiye ile ödenen tutar arasındaki farktır (en az 0)
        discount_amount = round(max(0.0, bakiye - final_tutar), 2)

    if final_tutar > bakiye + 0.01 and bakiye > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Fazla ödeme: bakiye {bakiye:.2f} TL, ödeme tutarı {final_tutar:.2f} TL"
        )
    if discount_amount > bakiye + 0.01:
        raise HTTPException(
            status_code=400,
            detail=f"İskonto tutarı bakiyeden yüksek: bakiye {bakiye:.2f} TL, iskonto {discount_amount:.2f} TL"
        )

    # Adisyon sistemi: Masada açık adisyon varsa al (yukarıda zaten aldık, yoksa oluştur)
    if not adisyon_id:
        from ..routers.adisyon import _get_or_create_adisyon
        adisyon_id = await _get_or_create_adisyon(payload.masa, sube_id)
    
    from ..routers.adisyon import _update_adisyon_totals
    
    finalized_ids: List[int] = []
    auto_closed = False
    remaining_balance = bakiye
    async with db.transaction():
        row = await db.fetch_one(
            """
            INSERT INTO odemeler (sube_id, masa, adisyon_id, tutar, yontem)
            VALUES (:sid, :masa, :adisyon_id, :tutar, :yontem)
            RETURNING id, masa, tutar, yontem, created_at
            """,
            {"sid": sube_id, "masa": payload.masa, "adisyon_id": adisyon_id, "tutar": final_tutar, "yontem": payload.yontem},
        )

        # İskonto uygulandıysa adisyonu güncelle ve kayıt altına al
        if discount_amount > 0 and adisyon_id:
            # İskonto yüzdesini, indirimin uygulandığı toplam üzerinden hesapla
            discount_base = discount_amount + final_tutar if (discount_amount + final_tutar) > 0 else bakiye or 1
            applied_ratio = min(100.0, round((discount_amount / discount_base) * 100.0, 2))

            await db.execute(
                """
                UPDATE adisyons
                SET iskonto_tutari = COALESCE(iskonto_tutari, 0) + :discount,
                    iskonto_orani = CASE 
                        WHEN COALESCE(iskonto_orani, 0) = 0 THEN :ratio
                        ELSE iskonto_orani
                    END
                WHERE id = :aid
                """,
                {
                    "aid": adisyon_id,
                    "discount": discount_amount,
                    "ratio": applied_ratio,
                },
            )

            await db.execute(
                """
                INSERT INTO iskonto_kayitlari (adisyon_id, sube_id, masa, tutar, oran, kaynak, aciklama)
                VALUES (:aid, :sid, :masa, :tutar, :oran, :kaynak, :aciklama)
                """,
                {
                    "aid": adisyon_id,
                    "sid": sube_id,
                    "masa": payload.masa,
                    "tutar": discount_amount,
                    "oran": applied_ratio,
                    "kaynak": "odeme",
                    "aciklama": None,
                },
            )
        
        # Adisyon toplamlarını güncelle
        try:
            await _update_adisyon_totals(adisyon_id, sube_id)
        except Exception as e:
            logging.warning(f"Adisyon toplamları güncellenirken hata: {e}", exc_info=True)
        # Bakiye sıfırlandıysa hazir siparisleri kapat ve stoktan dus
        # Transaction içinde yapılmalı ki atomik olsun
        try:
            # Adisyon sistemine göre: Güncel bakiyeyi adisyon tablosundan al (eski ödemeler dahil edilmemeli)
            adisyon_final_check = await db.fetch_one(
                "SELECT bakiye FROM adisyons WHERE id = :aid",
                {"aid": adisyon_id},
            )
            yeni_bakiye = float(adisyon_final_check["bakiye"] or 0) if adisyon_final_check else 0.0
            logging.info(
                f"Ödeme eklendi: masa={payload.masa}, tutar={final_tutar:.2f} TL, "
                f"iskonto={iskonto_orani}%, yeni_bakiye={yeni_bakiye:.2f} TL, sube_id={sube_id}"
            )
            # Floating point hassasiyeti için 0.01 TL tolerans
            if abs(yeni_bakiye) < 0.01:
                logging.info(f"Masa {payload.masa} bakiyesi sıfır, siparişler otomatik finalize ediliyor...")
                finalized_ids = await _finalize_hazir_siparisler(payload.masa, sube_id)
                logging.info(f"Masa {payload.masa} için {len(finalized_ids)} sipariş finalize edildi")
                await db.execute(
                    """
                    UPDATE adisyons
                    SET durum = 'kapali', kapanis_zamani = NOW(), bakiye = 0
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
                    {"sid": sube_id, "masa": payload.masa},
                )
                logging.info(f"Masa '{payload.masa}' durumu 'bos' olarak güncellendi (adisyon #{adisyon_id} otomatik kapatıldı)")
                await _update_adisyon_totals(adisyon_id, sube_id)
                auto_closed = True
                remaining_balance = 0.0
            else:
                logging.info(f"Masa {payload.masa} bakiyesi {yeni_bakiye:.2f} TL, finalize edilmiyor")
                remaining_balance = round(yeni_bakiye, 2)
        except Exception as e:
            logging.error(f"Error finalizing order on odeme_ekle: {e}", exc_info=True)
            finalized_ids = []
            remaining_balance = max(0.0, round(bakiye - final_tutar, 2))
    return {
        "id": row["id"],
        "masa": row["masa"],
        "tutar": float(row["tutar"]),
        "yontem": row["yontem"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else "",
        "remaining_balance": float(remaining_balance if remaining_balance is not None else 0.0),
        "auto_closed": auto_closed,
        "tip": float(tip_amount),
    }

@router.post(
    "/hesap/kapat",
    dependencies=[Depends(require_roles({"admin", "operator"}))]
)
async def hesap_kapat(
    masa: str = Query(..., min_length=1),
    force: bool = False,
    _: Mapping[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """
    Adisyon sistemine göre hesap kapatma.
    force=True: bakiye sıfır olmasa da kapatıldı kabul eder (bilgilendirme amaçlı).
    Adisyon kapatıldığında hazir siparisleri kapatır ve stoktan düşer.
    """
    # Adisyon sistemine göre: Masada açık adisyon varsa kapat
    from ..routers.adisyon import _get_or_create_adisyon
    adisyon_row = await db.fetch_one(
        """
        SELECT id, bakiye FROM adisyons
        WHERE sube_id = :sid AND masa = :masa AND durum = 'acik'
        ORDER BY acilis_zamani DESC
        LIMIT 1
        """,
        {"sid": sube_id, "masa": masa},
    )
    
    if not adisyon_row:
        raise HTTPException(status_code=404, detail="Açık adisyon bulunamadı")
    
    adisyon_id = adisyon_row["id"]
    bakiye = float(adisyon_row["bakiye"] or 0)
    
    # Floating point hassasiyeti için 0.01 TL tolerans
    if abs(bakiye) >= 0.01 and not force:
        raise HTTPException(status_code=400, detail=f"Bakiye sıfır değil: {bakiye:.2f} TL")

    # Adisyon kapatma fonksiyonunu direkt çağır (bu fonksiyon finalize işlemini de yapar)
    from ..routers.adisyon import adisyon_kapat as adisyon_kapat_func
    
    # Adisyon kapatma fonksiyonunu çağır
    result = await adisyon_kapat_func(adisyon_id, _, sube_id)
    
    finalized_ids = result.get("finalized_orders", [])

    return {
        "message": "Hesap kapatıldı" if abs(bakiye) < 0.01 or force else "Hesap kapatılamadı",
        "finalized_orders": finalized_ids,
        "force": force,
        "finalized_order_ids": finalized_ids,
    }

@router.get("/ozet/gunluk")
async def ozet_gunluk(
    _: Mapping[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    # Gnlk sipari cirosu (sadece ödenen siparişler - ciro gerçekten ödenen tutardır)
    ciro = await db.fetch_one(
        """
        SELECT COALESCE(SUM(tutar),0) AS ciro
        FROM siparisler
        WHERE created_at::date = CURRENT_DATE AND durum = 'odendi' AND sube_id = :sid
        """,
        {"sid": sube_id},
    )
    # Gnlk demeler dalm (iptal olmayanlar)
    dagilim = await db.fetch_all(
        """
        SELECT yontem, COALESCE(SUM(tutar),0) AS toplam
        FROM odemeler
        WHERE created_at::date = CURRENT_DATE AND iptal = FALSE AND sube_id = :sid
        GROUP BY yontem
        ORDER BY toplam DESC
        """,
        {"sid": sube_id},
    )
    iskonto_row = await db.fetch_one(
        """
        SELECT COALESCE(SUM(tutar),0) AS toplam
        FROM iskonto_kayitlari
        WHERE created_at::date = CURRENT_DATE AND sube_id = :sid
        """,
        {"sid": sube_id},
    )
    ikram_rows = await db.fetch_all(
        """
        SELECT sepet
        FROM siparisler
        WHERE created_at::date = CURRENT_DATE
          AND durum = 'odendi'
          AND sube_id = :sid
        """,
        {"sid": sube_id},
    )
    gunluk_ikram = 0.0
    for row in ikram_rows:
        try:
            sepet = json.loads(row["sepet"]) if isinstance(row["sepet"], str) else row["sepet"]
        except Exception:
            sepet = []
        if not sepet:
            continue
        for item in sepet:
            if isinstance(item, dict) and item.get("ikram"):
                if "ikram_edilen_tutar" in item:
                    gunluk_ikram += float(item.get("ikram_edilen_tutar") or 0)
                else:
                    adet = float(item.get("adet") or 1)
                    fiyat = float(item.get("fiyat") or 0)
                    gunluk_ikram += adet * fiyat

    gunluk_iskonto = float(iskonto_row["toplam"] or 0) if iskonto_row else 0.0

    odeme_records = [{"yontem": r["yontem"], "tutar": float(r["toplam"])} for r in dagilim]
    odeme_records.append({"yontem": "iskonto", "tutar": gunluk_iskonto})
    odeme_records.append({"yontem": "ikram", "tutar": gunluk_ikram})
    return {
        "gunluk_ciro_siparis": float(ciro["ciro"] or 0),
        "gunluk_odeme_dagilimi": odeme_records,
        "gunluk_iskonto": gunluk_iskonto,
        "gunluk_ikram": gunluk_ikram,
    }


# ------ Ak masalar listesi ------
@router.get("/masalar")
async def acik_masalar(
    limit: int = Query(200, ge=1, le=2000),
    tumu: bool = Query(False, description="True ise tüm masaları getir (bakiye 0 olsa bile)"),
    _: Mapping[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """
    Adisyon sistemine göre açık masaları listele.
    Adisyon tablosundan açık adisyonları çeker ve bakiye bilgilerini döndürür.
    Eğer adisyon yoksa ama aktif siparişler varsa, adisyon oluşturur.
    """
    import logging
    
    # Önce adisyon tablosundan açık adisyonları çek
    sql = """
    SELECT 
      a.masa,
      a.toplam_tutar AS siparis_toplam,
      a.odeme_toplam,
      a.bakiye,
      a.id AS adisyon_id,
      -- Hazır sipariş sayısını da ekle
      COALESCE((
        SELECT COUNT(*)
        FROM siparisler
        WHERE adisyon_id = a.id AND durum = 'hazir'
      ), 0) AS hazir_count
    FROM adisyons a
    WHERE a.sube_id = :sid AND a.durum = 'acik'
    """
    
    if not tumu:
        # Sadece bakiye > 0 veya hazır siparişi olanları göster
        sql += """
      AND (a.bakiye > 0 OR EXISTS (
        SELECT 1 FROM siparisler
        WHERE adisyon_id = a.id AND durum = 'hazir'
      ))
        """
    
    sql += """
    ORDER BY a.bakiye DESC, a.masa ASC
    LIMIT :limit
    """
    rows = await db.fetch_all(sql, {"sid": sube_id, "limit": limit})
    
    # Tüm açık adisyonların toplamlarını güncelle (sipariş durumu değişmiş olabilir)
    if rows:
        from ..routers.adisyon import _update_adisyon_totals
        for r in rows:
            try:
                adisyon_id = r["adisyon_id"] if r["adisyon_id"] is not None else None
                if adisyon_id:
                    await _update_adisyon_totals(adisyon_id, sube_id)
            except (KeyError, AttributeError) as e:
                logging.warning(f"[KASA] Adisyon ID alınamadı: {e}", exc_info=True)
            except Exception as e:
                logging.warning(f"[KASA] Adisyon toplamları güncellenirken hata: {e}", exc_info=True)
        # Güncellenmiş verileri tekrar çek
        rows = await db.fetch_all(sql, {"sid": sube_id, "limit": limit})
    
    # Eğer adisyon olmayan ama aktif siparişi olan masalar varsa, onlar için adisyon oluştur
    # Bu durum eski sistemden kalan siparişler için gerekli
    # ÖNEMLİ: Eski ödemelerin adisyon_id'sini güncelleme - sadece siparişleri yeni adisyona bağla
    aktif_siparis_masalar = await db.fetch_all(
        """
        SELECT DISTINCT masa
        FROM siparisler
        WHERE sube_id = :sid 
          AND durum IN ('yeni', 'hazirlaniyor', 'hazir')
          AND (adisyon_id IS NULL OR adisyon_id = 0)
        """,
        {"sid": sube_id},
    )
    
    if aktif_siparis_masalar:
        from ..routers.adisyon import _get_or_create_adisyon, _update_adisyon_totals
        for masa_row in aktif_siparis_masalar:
            masa = masa_row["masa"]
            try:
                # Adisyon oluştur veya mevcut adisyonu al
                adisyon_id = await _get_or_create_adisyon(masa, sube_id)
                
                # SADECE siparişlerin adisyon_id'sini güncelle - ÖDEMELERİ GÜNCELLEME!
                # Eski ödemeler eski adisyonlarına bağlı kalmalı veya NULL olmalı
                await db.execute(
                    """
                    UPDATE siparisler
                    SET adisyon_id = :aid
                    WHERE sube_id = :sid AND masa = :masa AND (adisyon_id IS NULL OR adisyon_id = 0)
                    """,
                    {"aid": adisyon_id, "sid": sube_id, "masa": masa},
                )
                
                # Adisyon toplamlarını güncelle
                await _update_adisyon_totals(adisyon_id, sube_id)
                logging.info(f"[KASA] Eksik adisyon oluşturuldu/güncellendi: masa={masa}, adisyon_id={adisyon_id}")
            except Exception as e:
                logging.warning(f"[KASA] Eksik adisyon oluşturulurken hata (masa={masa}): {e}", exc_info=True)
        
        # Adisyonları tekrar çek
        rows = await db.fetch_all(sql, {"sid": sube_id, "limit": limit})
    
    logging.info(f"[KASA] acik_masalar çağrıldı: sube_id={sube_id}, tumu={tumu}, limit={limit}, dönen masa sayısı={len(rows)}")
    if rows:
        # Debug: Her masa için detaylı bilgi logla
        for r in rows[:10]:
            try:
                hazir_count = r['hazir_count'] if r['hazir_count'] is not None else 0
            except (KeyError, AttributeError):
                hazir_count = 0
            try:
                siparis_toplam = r['siparis_toplam'] if 'siparis_toplam' in r else 0
                odeme_toplam = r['odeme_toplam'] if 'odeme_toplam' in r else 0
                bakiye = r['bakiye'] if 'bakiye' in r else 0
            except (KeyError, AttributeError):
                siparis_toplam = 0
                odeme_toplam = 0
                bakiye = 0
            logging.info(f"[KASA] Masa: {r['masa']}, bakiye: {bakiye}, siparis_toplam: {siparis_toplam}, odeme_toplam: {odeme_toplam}, hazir_count: {hazir_count}")
    else:
        # Debug için: hazir durumundaki masaları kontrol et
        debug_rows = await db.fetch_all(
            "SELECT masa, COUNT(*) as cnt FROM siparisler WHERE sube_id = :sid AND durum = 'hazir' GROUP BY masa",
            {"sid": sube_id}
        )
        if debug_rows:
            logging.warning(f"[KASA] DEBUG: Hazir durumunda {len(debug_rows)} masa var ama acik_masalar'da gözükmüyor: {[r['masa'] for r in debug_rows]}")
    result = []
    mevcut_masalar = set()
    for r in rows:
        try:
            # SQL'den gelen kolon adlarını kullan: siparis_toplam, odeme_toplam, bakiye
            # Record objesi için try-except kullanıyoruz
            try:
                siparis_toplam = r["siparis_toplam"]
            except (KeyError, AttributeError):
                siparis_toplam = 0
                
            try:
                odeme_toplam = r["odeme_toplam"]
            except (KeyError, AttributeError):
                odeme_toplam = 0
                
            try:
                bakiye = r["bakiye"]
            except (KeyError, AttributeError):
                bakiye = 0
            
            result.append({
                "masa": r["masa"],
                "siparis_toplam": float(siparis_toplam or 0),
                "odeme_toplam": float(odeme_toplam or 0),
                "bakiye": float(bakiye or 0),
                "adisyon_id": r["adisyon_id"] if "adisyon_id" in r else None,
                "hazir_count": r["hazir_count"] if "hazir_count" in r else 0,
            })
            mevcut_masalar.add(r["masa"])
        except Exception as e:
            logging.warning(f"[KASA] Masa verisi işlenirken hata: {e}", exc_info=True)
            continue

    if tumu:
        try:
            kayitli_masalar = await db.fetch_all(
                """
                SELECT masa_adi
                FROM masalar
                WHERE sube_id = :sid
                ORDER BY masa_adi
                """,
                {"sid": sube_id},
            )
            for masa_row in kayitli_masalar:
                masa_adi = masa_row["masa_adi"]
                if masa_adi not in mevcut_masalar:
                    result.append({
                        "masa": masa_adi,
                        "siparis_toplam": 0.0,
                        "odeme_toplam": 0.0,
                        "bakiye": 0.0,
                        "adisyon_id": None,
                        "hazir_count": 0,
                    })
        except Exception as e:
            logging.warning(f"[KASA] Kayıtlı masalar alınırken hata: {e}", exc_info=True)

    return result


# ------ Siparis + masa detayi ------
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


def _normalize_items(value):
    def _num(val, default=0.0):
        try:
            if val is None or val == "":
                return default
            return float(val)
        except (TypeError, ValueError):
            return default

    items = []
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
            item_dict = {
                "urun": urun,
                "adet": adet,
                "miktar": adet,
                "fiyat": fiyat,
                "toplam": fiyat * adet if fiyat else toplam,
            }
            
            # Include variation if present
            if "varyasyon" in item:
                item_dict["varyasyon"] = item["varyasyon"]
            
            # Include ikram flag if present
            if "ikram" in item:
                item_dict["ikram"] = item["ikram"]
            
            items.append(item_dict)
    return items


@router.get("/hesap/detay")
async def hesap_detay(
    masa: str = Query(..., min_length=1),
    _: Mapping[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    masa_clean = masa.strip()
    if not masa_clean:
        raise HTTPException(status_code=400, detail="Masa bilgisi gerekli")

    summary = await _hesap_ozet_core(masa_clean, sube_id)

    siparis_rows = await db.fetch_all(
        """
        SELECT s.id,
               s.masa,
               s.durum,
               s.tutar,
               s.sepet,
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
        WHERE s.sube_id = :sid
          AND s.masa = :masa
          AND s.durum IN ('yeni', 'hazirlaniyor', 'hazir')
        ORDER BY s.created_at ASC, s.id ASC
        """,
        {"sid": sube_id, "masa": masa_clean},
    )

    siparisler = []
    last_personel_username: Optional[str] = None
    last_personel_role: Optional[str] = None

    for row in siparis_rows:
        items = _normalize_items(row["sepet"])
        created_by_user_id = row["created_by_user_id"] if "created_by_user_id" in row else None
        created_by_username = row["created_by_username"] if "created_by_username" in row else None
        personel_username = row["personel_username"] if "personel_username" in row else None
        if not personel_username and created_by_username:
            personel_username = created_by_username
        personel_role = row["personel_role"] if "personel_role" in row else None

        has_personel_source = bool(created_by_user_id or created_by_username or personel_username)
        if not has_personel_source and last_personel_username:
            personel_username = last_personel_username
            personel_role = personel_role or last_personel_role
            has_personel_source = True

        if has_personel_source:
            source_type = "personel"
            source_label = f"Personel: {personel_username}" if personel_username else "Personel"
            last_personel_username = personel_username or last_personel_username
            last_personel_role = personel_role or last_personel_role
        else:
            source_type = "asistan"
            source_label = "AI Asistan"

        siparisler.append(
            {
                "id": row["id"],
                "masa": row["masa"],
                "durum": row["durum"],
                "tutar": float(row["tutar"] or 0.0),
                "created_at": row["created_at"].isoformat() if row["created_at"] else "",
                "sepet": items,
                "source_type": source_type,
                "source_label": source_label,
                "personel_username": personel_username,
                "personel_role": personel_role,
                "created_by_username": created_by_username,
            }
        )

    odemeler = []

    return {
        "masa": masa_clean,
        "ozet": summary,
        "siparis_toplam": summary["siparis_toplam"],
        "odeme_toplam": summary["odeme_toplam"],
        "bakiye": summary["bakiye"],
        "toplam": summary["siparis_toplam"],
        "siparisler": siparisler,
        "odemeler": odemeler,
    }


@router.get("/siparisler")
async def kasa_siparisler(
    limit: int = Query(200, ge=1, le=500),
    _: Mapping[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    base_sql = """
    WITH sip AS (
  SELECT masa, COALESCE(SUM(tutar),0) AS sip_toplam
  FROM siparisler
  WHERE sube_id = :sid AND durum IN ('yeni', 'hazirlaniyor', 'hazir')
  GROUP BY masa
    ), od AS (
      SELECT masa, COALESCE(SUM(tutar),0) AS od_toplam
      FROM odemeler
      WHERE sube_id = :sid AND iptal = FALSE
      GROUP BY masa
    ), balance AS (
      SELECT
        sip.masa,
        sip.sip_toplam,
        COALESCE(od.od_toplam, 0) AS od_toplam,
        (sip.sip_toplam - COALESCE(od.od_toplam, 0))::float AS bakiye
      FROM sip
      LEFT JOIN od USING (masa)
    )
    SELECT
      s.id,
      s.masa,
      s.durum,
      s.tutar,
      s.sepet,
      s.created_at,
      b.sip_toplam AS masa_siparis_toplam,
      b.od_toplam AS masa_odeme_toplam,
      b.bakiye AS masa_bakiye
    FROM siparisler s
    JOIN balance b ON b.masa = s.masa
    WHERE s.sube_id = :sid
  AND s.durum IN ('yeni', 'hazirlaniyor', 'hazir')
      AND b.bakiye > 0
    ORDER BY s.created_at DESC, s.id DESC
    LIMIT :limit
    """
    rows = await db.fetch_all(base_sql, {"sid": sube_id, "limit": limit})
    result = []
    for row in rows:
        items = _normalize_items(row["sepet"])
        result.append({
            "id": row["id"],
            "masa": row["masa"],
            "durum": row["durum"],
            "tutar": float(row["tutar"] or 0.0),
            "created_at": row["created_at"].isoformat() if row["created_at"] else "",
            "items": items,
            "sepet": items,
            "table_summary": {
                "masa": row["masa"],
                "siparis_toplam": float(row["masa_siparis_toplam"] or 0.0),
                "odeme_toplam": float(row["masa_odeme_toplam"] or 0.0),
                "bakiye": float(row["masa_bakiye"] or 0.0),
            },
        })
    return result

# ------ Ek: deme listesi + iade ------
@router.get("/odeme/liste")
async def odeme_liste(
    baslangic: Optional[str] = Query(None, description="YYYY-MM-DD"),
    bitis: Optional[str]    = Query(None, description="YYYY-MM-DD"),
    masa: Optional[str]     = None,
    sadece_iptal: bool      = False,
    limit: int              = Query(200, ge=1, le=2000),
    _: Mapping[str, Any]    = Depends(get_current_user),
    sube_id: int            = Depends(get_sube_id),
):
    clauses = ["sube_id = :sid"]
    params: Dict[str, Any] = {"limit": limit, "sid": sube_id}

    if baslangic:
        clauses.append("created_at::date >= :d1")
        params["d1"] = baslangic
    if bitis:
        clauses.append("created_at::date <= :d2")
        params["d2"] = bitis
    if masa:
        clauses.append("masa = :masa")
        params["masa"] = masa
    clauses.append("iptal = TRUE" if sadece_iptal else "iptal = FALSE")

    where_sql = " WHERE " + " AND ".join(clauses)
    sql = f"""
        SELECT id, masa, tutar, yontem, iptal, created_at
          FROM odemeler
          {where_sql}
         ORDER BY created_at DESC, id DESC
         LIMIT :limit
    """
    rows = await db.fetch_all(sql, params)
    return [
        {
            "id": r["id"],
            "masa": r["masa"],
            "tutar": float(r["tutar"]),
            "yontem": r["yontem"],
            "iptal": r["iptal"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else "",
        }
        for r in rows
    ]

@router.post(
    "/odeme/iptal",
    dependencies=[Depends(require_roles({"admin", "operator"}))]
)
async def odeme_iptal(
    odeme_id: int = Query(..., ge=1),
    _: Mapping[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    row = await db.fetch_one(
        "SELECT id, iptal FROM odemeler WHERE id = :id AND sube_id = :sid",
        {"id": odeme_id, "sid": sube_id},
    )
    if not row:
        raise HTTPException(status_code=404, detail="deme bulunamad")
    if row["iptal"]:
        return {"message": "Zaten iptal edilmi", "id": odeme_id}

    await db.execute(
        "UPDATE odemeler SET iptal = TRUE WHERE id = :id",
        {"id": odeme_id},
    )
    return {"message": "deme iptal edildi", "id": odeme_id}



# ------ Stok dme (basit reçete mantığı) ------
def _convert_unit_to_base(amount: float, unit: str) -> float:
    """
    Birimleri temel birime çevir (ml->ml, litre->ml, gr->gr, kg->gr)
    Basitleştirilmiş: Birimleri normalize et ve çevir
    """
    if not unit:
        return amount
    
    unit_lower = unit.lower().strip()
    
    # Hacim birimleri -> ml
    if unit_lower in ["litre", "l", "lt", "liter"]:
        return amount * 1000  # litre -> ml
    elif unit_lower in ["ml", "mililitre", "milliliter"]:
        return amount
    elif unit_lower in ["cl", "centilitre"]:
        return amount * 10  # cl -> ml
    
    # Ağırlık birimleri -> gr
    elif unit_lower in ["kg", "kilogram", "kilo"]:
        return amount * 1000  # kg -> gr
    elif unit_lower in ["gr", "gram", "g"]:
        return amount
    elif unit_lower in ["mg", "miligram"]:
        return amount / 1000  # mg -> gr
    
    # Adet birimleri
    elif unit_lower in ["adet", "ad", "pcs", "piece", "birim"]:
        return amount
    
    # Bilinmeyen birim için olduğu gibi döndür
    return amount


async def _dus_stok_recepte(
    masa: str,
    sube_id: int,
    siparis_rows: Optional[List[Mapping[str, Any]]] = None,
) -> None:
    """
    Basitleştirilmiş stok düşürme mantığı:
    - Siparişteki her ürün için reçete kontrolü yapılır
    - Reçete miktarı × sipariş adedi = düşülecek miktar
    - Birim dönüşümü yapılır (ml/litre, gr/kg)
    """
    try:
        # Masadaki aktif siparislerin sepetlerini topla
        # ÖNEMLİ: Artık sadece 'hazir' değil, tüm aktif siparişler ('yeni', 'hazirlaniyor', 'hazir') işleniyor
        rows = siparis_rows
        if rows is None:
            rows = await db.fetch_all(
                """
                SELECT sepet
                FROM siparisler
                WHERE sube_id = :sid AND masa = :masa AND durum IN ('yeni', 'hazirlaniyor', 'hazir')
                """,
                {"sid": sube_id, "masa": masa},
            )
        
        import json
        from ..routers.siparis import normalize_name
        
        # Ürün bazında toplam adet hesapla
        # {urun_normalized: toplam_adet}
        toplam: Dict[str, int] = {}
        for r in rows:
            val = r["sepet"]
            if isinstance(val, list):
                arr = val
            elif isinstance(val, str):
                arr = json.loads(val)
            else:
                arr = []
            
            for it in arr:
                urun_adi = str(it.get("urun", "")).strip()
                if not urun_adi:
                    continue
                key = normalize_name(urun_adi)
                adet = int(it.get("adet", 0) or 0)
                if key and adet > 0:
                    toplam[key] = toplam.get(key, 0) + adet

        if not toplam:
            return

        # Her ürün için reçete kontrolü ve stoktan düşme
        for urun_key, siparis_adet in toplam.items():
            # Reçeteyi bul: Tüm reçeteleri çekip normalize ederek karşılaştır
            # (Çünkü reçete tablosunda normalize edilmemiş ürün adı kaydedilmiş olabilir)
            all_recs = await db.fetch_all(
                """
                SELECT stok, miktar, birim, urun
                FROM receteler 
                WHERE sube_id = :sid
                """,
                {"sid": sube_id},
            )
            # Normalize edilmiş ürün adı ile eşleşen reçeteleri bul
            recs = [
                rec for rec in all_recs 
                if normalize_name(str(rec["urun"]).strip()) == urun_key
            ]
            
            # Debug log - reçete bulunamazsa uyar
            if not recs:
                import logging
                mevcut_receteler_str = ", ".join([normalize_name(str(r['urun']).strip()) for r in all_recs[:10]])
                logging.warning(
                    f"[STOK_DUSME] Recete bulunamadi: urun_key='{urun_key}', siparis_adet={siparis_adet}, "
                    f"masa='{masa}', sube_id={sube_id}. "
                    f"Mevcut receteler (ilk 10): {mevcut_receteler_str}. "
                    f"Fallback mekanizmasi deneniyor..."
                )
            else:
                import logging
                logging.info(
                    f"[STOK_DUSME] Recete bulundu: urun_key='{urun_key}', siparis_adet={siparis_adet}, "
                    f"recete_sayisi={len(recs)}, masa='{masa}', sube_id={sube_id}"
                )
            
            if recs:
                # Reçete tanımlı: Reçete miktarı × Sipariş adedi
                for rec in recs:
                    try:
                        stok_adi = str(rec["stok"]).strip()
                        recete_miktar = float(rec["miktar"] or 0)
                        # Database record'da .get() yok, direkt erişim
                        recete_birim = str(rec["birim"] if rec["birim"] else "").strip()
                    except (KeyError, AttributeError) as e:
                        import logging
                        logging.warning(f"Recete record'unda eksik alan: {e}")
                        continue
                    
                    # Toplam düşülecek miktar = reçete_miktar × siparis_adet
                    # Örn: 100 ml × 2 latte = 200 ml
                    toplam_dusulecek = recete_miktar * siparis_adet
                    
                    # Stok kaleminin birimini al
                    stok_row = await db.fetch_one(
                        """
                        SELECT ad, birim FROM stok_kalemleri 
                        WHERE sube_id = :sid AND ad = :stok_adi
                        LIMIT 1
                        """,
                        {"sid": sube_id, "stok_adi": stok_adi},
                    )
                    
                    if stok_row:
                        # Database record'da .get() yok, direkt erişim
                        try:
                            stok_birim = str(stok_row["birim"] if stok_row["birim"] else "").strip()
                        except (KeyError, AttributeError):
                            stok_birim = ""
                        
                        # Birim dönüşümü: Reçete birimi ile stok birimi aynıysa direkt kullan
                        # Farklıysa temel birime çevir ve stok birimine dönüştür
                        if recete_birim and stok_birim:
                            # Her iki birimi de temel birime çevir
                            recete_base = _convert_unit_to_base(toplam_dusulecek, recete_birim)
                            
                            # Stok birimine göre tekrar çevir
                            if stok_birim.lower() in ["litre", "l", "lt", "liter"]:
                                dusulecek_miktar = recete_base / 1000  # ml -> litre
                            elif stok_birim.lower() in ["kg", "kilogram", "kilo"]:
                                dusulecek_miktar = recete_base / 1000  # gr -> kg
                            elif stok_birim.lower() in ["ml", "mililitre", "milliliter"]:
                                dusulecek_miktar = recete_base  # zaten ml
                            elif stok_birim.lower() in ["gr", "gram", "g"]:
                                dusulecek_miktar = recete_base  # zaten gr
                            else:
                                # Aynı birim veya bilinmeyen -> reçete miktarını olduğu gibi kullan
                                dusulecek_miktar = toplam_dusulecek
                        elif recete_birim:
                            # Sadece reçete birimi var, temel birime çevir
                            dusulecek_miktar = _convert_unit_to_base(toplam_dusulecek, recete_birim)
                        else:
                            # Birim bilgisi yok, olduğu gibi kullan
                            dusulecek_miktar = toplam_dusulecek
                        
                        # Stoktan düş
                        result = await db.execute(
                    """
                    UPDATE stok_kalemleri
                       SET mevcut = GREATEST(0, (mevcut - :m))
                     WHERE sube_id = :sid AND ad = :stok_adi
                    """,
                            {"sid": sube_id, "stok_adi": stok_adi, "m": dusulecek_miktar},
                        )
                        import logging
                        logging.info(
                            f"[STOK_DUSME] Stok dusuldu (recete ile): stok_adi='{stok_adi}', "
                            f"dusulecek={dusulecek_miktar} {stok_birim or recete_birim or 'birim'}, "
                            f"recete_miktar={recete_miktar} {recete_birim or 'birim'}, "
                            f"siparis_adet={siparis_adet}, urun='{urun_key}', masa='{masa}', sube_id={sube_id}, "
                            f"UPDATE result={result}"
                        )
            else:
                # Reçete tanımlı değil: Ürün adı = Stok adı ise direkt düş (basit fallback)
                import logging
                
                # Önce normalize edilmiş isimle kontrol et
                stok_row = await db.fetch_one(
                    """
                    SELECT ad FROM stok_kalemleri 
                    WHERE sube_id = :sid AND LOWER(ad) = LOWER(:urun)
                    LIMIT 1
                    """,
                    {"sid": sube_id, "urun": urun_key},
                )
                
                # Bulunamazsa, normalize edilmiş isimle kontrol et
                if not stok_row:
                    # Tüm stok kalemlerini çek ve normalize ederek karşılaştır
                    all_stok = await db.fetch_all(
                        """
                        SELECT ad FROM stok_kalemleri 
                        WHERE sube_id = :sid
                        """,
                        {"sid": sube_id},
                    )
                    for stok_item in all_stok:
                        stok_normalized = normalize_name(str(stok_item["ad"]).strip())
                        if stok_normalized == urun_key:
                            stok_row = stok_item
                            break
                
                if stok_row:
                    stok_adi = stok_row["ad"]
                    result = await db.execute(
                        """
                        UPDATE stok_kalemleri
                           SET mevcut = GREATEST(0, (mevcut - :adet))
                         WHERE sube_id = :sid AND ad = :stok_adi
                        """,
                        {"sid": sube_id, "stok_adi": stok_adi, "adet": siparis_adet},
                    )
                    logging.info(
                        f"[STOK_DUSME] Fallback: Stok dusuldu (recete yok): stok_adi='{stok_adi}', "
                        f"dusulecek_adet={siparis_adet}, urun='{urun_key}', masa='{masa}', sube_id={sube_id}"
                    )
                else:
                    # Stok kalemi de bulunamadı
                    logging.warning(
                        f"[STOK_DUSME] Stok kalemi bulunamadi: urun_key='{urun_key}', siparis_adet={siparis_adet}, "
                        f"masa='{masa}', sube_id={sube_id}. "
                        f"Stok dusurme yapilamadi - recete tanimli degil ve stok kalemi bulunamadi."
                    )
                    
    except Exception as e:
        # Stok/recete tablolar yoksa veya hata oluşursa detaylı log
        # ÖNEMLİ: Exception'ı fırlatmıyoruz çünkü ödeme zaten alınmış olabilir
        # Ancak hatayı ERROR seviyesinde loglayalım ki görünsün
        import logging
        logging.error(
            f"[STOK_DUSME_HATASI] masa='{masa}', sube_id={sube_id}, "
            f"hata_tipi={type(e).__name__}, hata_mesaji={str(e)}", 
            exc_info=True
        )
        # Exception'ı fırlatmıyoruz - ödeme işlemi devam etmeli

@router.post("/siparis/item/masa-degistir")
async def siparis_item_masa_degistir(
    payload: ItemMasaDegistirIn,
    _: Mapping[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """
    Bir sipariş içindeki belirli bir item'ı başka bir masaya taşır.
    Yeni bir sipariş oluşturur veya hedef masada varsa oraya ekler.
    """
    import json
    import logging
    
    # Mevcut siparişi getir
    siparis = await db.fetch_one(
        """
        SELECT id, masa, sepet, tutar, durum
        FROM siparisler
        WHERE id = :id AND sube_id = :sid
        """,
        {"id": payload.siparis_id, "sid": sube_id},
    )
    
    if not siparis:
        raise HTTPException(status_code=404, detail="Sipariş bulunamadı")
    
    sepet = _decode_sepet(siparis["sepet"])
    if payload.item_index < 0 or payload.item_index >= len(sepet):
        raise HTTPException(status_code=400, detail="Geçersiz item index")
    
    # Item'ı al ve sepetten çıkar
    item = sepet[payload.item_index]
    yeni_sepet = sepet[:payload.item_index] + sepet[payload.item_index + 1:]
    
    # Eski siparişin tutarını güncelle
    yeni_tutar = sum(i.get("fiyat", 0) * i.get("adet", 1) for i in yeni_sepet)
    
    from ..routers.adisyon import _get_or_create_adisyon, _update_adisyon_totals

    hedef_masa = payload.yeni_masa.strip()
    eski_adisyon_id = siparis.get("adisyon_id")
    
    async with db.transaction():
        # Eski siparişi güncelle (item çıkarıldı)
        if yeni_sepet:
            await db.execute(
                """
                UPDATE siparisler
                SET sepet = CAST(:sepet AS JSONB), tutar = :tutar
                WHERE id = :id
                """,
                {
                    "id": payload.siparis_id,
                    "sepet": json.dumps(yeni_sepet, ensure_ascii=False),
                    "tutar": yeni_tutar,
                },
            )
        else:
            await db.execute(
                "DELETE FROM siparisler WHERE id = :id",
                {"id": payload.siparis_id},
            )
        
        # Hedef masa için adisyon al/oluştur
        hedef_adisyon_id = await _get_or_create_adisyon(hedef_masa, sube_id)

        # Hedef masada aktif sipariş var mı kontrol et
        hedef_siparis = await db.fetch_one(
            """
            SELECT id, sepet, tutar, adisyon_id
            FROM siparisler
            WHERE masa = :masa AND sube_id = :sid 
            AND durum IN ('yeni', 'hazirlaniyor', 'hazir')
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            {"masa": hedef_masa, "sid": sube_id},
        )
        
        if hedef_siparis:
            # Mevcut siparişe ekle
            hedef_sepet = _decode_sepet(hedef_siparis["sepet"])
            hedef_sepet.append(item)
            hedef_tutar = sum(i.get("fiyat", 0) * i.get("adet", 1) for i in hedef_sepet)
            
            await db.execute(
                """
                UPDATE siparisler
                SET sepet = CAST(:sepet AS JSONB), tutar = :tutar, adisyon_id = :adisyon_id
                WHERE id = :id
                """,
                {
                    "id": hedef_siparis["id"],
                    "sepet": json.dumps(hedef_sepet, ensure_ascii=False),
                    "tutar": hedef_tutar,
                    "adisyon_id": hedef_adisyon_id,
                },
            )
            logging.info(f"Item {payload.item_index} from siparis {payload.siparis_id} moved to existing siparis {hedef_siparis['id']} at masa {payload.yeni_masa}")
        else:
            # Yeni sipariş oluştur - durum 'hazir' olarak ayarla çünkü taşınan ürünler zaten hazırlanmış
            # Bu ürünlerin mutfağa gitmemesi gerekiyor, direkt kasada görünmeli
            yeni_siparis_id = await db.fetch_one(
                """
                INSERT INTO siparisler (sube_id, masa, sepet, durum, tutar, adisyon_id)
                VALUES (:sid, :masa, CAST(:sepet AS JSONB), 'hazir', :tutar, :adisyon_id)
                RETURNING id
                """,
                {
                    "sid": sube_id,
                    "masa": hedef_masa,
                    "sepet": json.dumps([item], ensure_ascii=False),
                    "tutar": item.get("fiyat", 0) * item.get("adet", 1),
                    "adisyon_id": hedef_adisyon_id,
                },
            )
            logging.info(f"Item {payload.item_index} from siparis {payload.siparis_id} moved to new siparis {yeni_siparis_id['id']} at masa {payload.yeni_masa} (durum: hazir)")

        # Adisyon toplamlarını güncelle
        if eski_adisyon_id:
            try:
                await _update_adisyon_totals(int(eski_adisyon_id), sube_id)
            except Exception as e:
                logging.warning(f"Eski adisyon toplamı güncellenemedi (adisyon_id={eski_adisyon_id}): {e}", exc_info=True)
        try:
            await _update_adisyon_totals(hedef_adisyon_id, sube_id)
        except Exception as e:
            logging.warning(f"Hedef adisyon toplamı güncellenemedi (adisyon_id={hedef_adisyon_id}): {e}", exc_info=True)

    # WebSocket broadcast - notify cashier and orders topics about table transfer
    from ..websocket.manager import manager, Topics
    await manager.broadcast({
        "type": "table_transfer",
        "from_order_id": payload.siparis_id,
        "from_masa": siparis["masa"],
        "to_masa": payload.yeni_masa.strip(),
        "item_index": payload.item_index,
        "sube_id": sube_id
    }, topic=Topics.CASHIER)

    await manager.broadcast({
        "type": "table_transfer",
        "from_order_id": payload.siparis_id,
        "from_masa": siparis["masa"],
        "to_masa": payload.yeni_masa.strip(),
        "item_index": payload.item_index,
        "sube_id": sube_id
    }, topic=Topics.ORDERS)

    logging.info(f"Kasa: Broadcast table transfer from {siparis['masa']} to {payload.yeni_masa.strip()}")

    return {"message": "Item başarıyla taşındı", "yeni_masa": payload.yeni_masa.strip()}


@router.post("/siparis/item/ikram")
async def siparis_item_ikram(
    payload: ItemIkramIn,
    _: Mapping[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """
    Bir sipariş içindeki belirli bir item'ı ikram olarak işaretler (tutarı 0 yapar).
    """
    import json
    import logging
    
    # Mevcut siparişi getir
    siparis = await db.fetch_one(
        """
        SELECT id, masa, sepet, tutar, durum
        FROM siparisler
        WHERE id = :id AND sube_id = :sid
        """,
        {"id": payload.siparis_id, "sid": sube_id},
    )
    
    if not siparis:
        raise HTTPException(status_code=404, detail="Sipariş bulunamadı")
    
    sepet = _decode_sepet(siparis["sepet"])
    if payload.item_index < 0 or payload.item_index >= len(sepet):
        raise HTTPException(status_code=400, detail="Geçersiz item index")
    
    # Item'ın fiyatını 0 yap
    item = sepet[payload.item_index].copy()
    eski_fiyat = item.get("fiyat", 0) * item.get("adet", 1)
    item["fiyat"] = 0.0
    item["ikram"] = True  # İkram işareti
    item["ikram_edilen_tutar"] = round(eski_fiyat, 2)
    
    sepet[payload.item_index] = item
    
    # Sipariş tutarını güncelle
    yeni_tutar = sum(i.get("fiyat", 0) * i.get("adet", 1) for i in sepet)
    
    await db.execute(
        """
        UPDATE siparisler
        SET sepet = CAST(:sepet AS JSONB), tutar = :tutar
        WHERE id = :id
        """,
        {
            "id": payload.siparis_id,
            "sepet": json.dumps(sepet, ensure_ascii=False),
            "tutar": yeni_tutar,
        },
    )
    
    logging.info(f"Item {payload.item_index} from siparis {payload.siparis_id} marked as ikram (price set to 0)")
    
    return {"message": "Item ikram olarak işaretlendi", "fiyat_indirimi": eski_fiyat}
