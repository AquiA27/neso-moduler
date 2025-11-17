# backend/app/routers/analytics.py
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Literal
from datetime import datetime, timedelta
from ..core.deps import get_current_user, get_sube_id, require_roles
from ..core.cache import cache, cache_key
from ..db.database import db
import json

router = APIRouter(prefix="/analytics", tags=["Analytics"])


# ------ Modeller ------
class HourlyData(BaseModel):
    saat: int  # 0-23
    siparis_sayisi: int
    toplam_tutar: float

class ProductPopularity(BaseModel):
    urun_adi: str
    satis_adeti: int
    toplam_tutar: float
    kategori: Optional[str] = None

class AnalyticsSummary(BaseModel):
    period: Literal["gunluk", "haftalik", "aylik"]
    period_label: str
    start_tarih: str
    end_tarih: str
    siparis_sayisi: int
    toplam_ciro: float
    toplam_gider: float
    ortalama_sepet: float
    ortalama_masa_tutari: float
    en_populer_urun: Optional[str] = None
    odeme_dagilim: Optional[Dict[str, float]] = None
    toplam_iskonto: float = 0.0
    toplam_ikram: float = 0.0
    en_cok_ikram: Optional[Dict[str, Any]] = None
    top_personeller: List[Dict[str, Any]] = []


# ------ Yardımcı Fonksiyonlar ------
def parse_sepet(sepet_value) -> List[Dict[str, Any]]:
    """Sepet JSONB'yi parse et"""
    if sepet_value is None:
        return []
    if isinstance(sepet_value, list):
        return sepet_value
    if isinstance(sepet_value, str):
        try:
            return json.loads(sepet_value)
        except:
            return []
    return []


def _get_period_range(
    period: Literal["gunluk", "haftalik", "aylik"],
    reference: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Seçilen periyot için başlangıç/bitiş tarihini ve etiketini döndür."""
    base_date = reference or datetime.now()
    base_date = base_date.replace(hour=0, minute=0, second=0, microsecond=0)

    if period == "gunluk":
        start_date = base_date
        end_date = start_date + timedelta(days=1)
        label = "Günlük"
    elif period == "haftalik":
        start_date = (base_date - timedelta(days=base_date.weekday()))
        end_date = start_date + timedelta(days=7)
        label = "Haftalık"
    else:  # aylik
        start_date = base_date.replace(day=1)
        if start_date.month == 12:
            end_date = start_date.replace(year=start_date.year + 1, month=1)
        else:
            end_date = start_date.replace(month=start_date.month + 1)
        label = "Aylık"

    return {
        "start": start_date,
        "end": end_date,
        "label": label,
    }


# ------ Endpoint'ler ------
@router.get("/saatlik-yogunluk")
async def saatlik_yogunluk(
    period: Literal["gunluk", "haftalik", "aylik"] = Query("gunluk"),
    tarih: Optional[str] = Query(None, description="YYYY-MM-DD formatında tarih (opsiyonel, varsayılan: bugün)"),
    _: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """
    Saatlik yoğunluk verilerini döndürür.
    period: gunluk, haftalik, aylik
    """
    # Cache key oluştur
    cache_key_str = cache_key("analytics:saatlik", sube_id, period, tarih)
    
    # Cache'den kontrol et
    cached_result = await cache.get(cache_key_str)
    if cached_result is not None:
        return cached_result
    
    try:
        if tarih:
            base_date = datetime.strptime(tarih, "%Y-%m-%d")
        else:
            base_date = datetime.now()
        
        if period == "gunluk":
            start_date = base_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=1)
        elif period == "haftalik":
            start_date = (base_date - timedelta(days=base_date.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=7)
        else:  # aylik
            start_date = base_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if start_date.month == 12:
                end_date = start_date.replace(year=start_date.year + 1, month=1)
            else:
                end_date = start_date.replace(month=start_date.month + 1)
        
        # Ödeme tamamlanmış siparişler (odendi durumundaki) için saatlik veri topla
        rows = await db.fetch_all(
            """
            SELECT 
                EXTRACT(HOUR FROM created_at)::int AS saat,
                COUNT(*)::int AS siparis_sayisi,
                COALESCE(SUM(tutar), 0)::float AS toplam_tutar
            FROM siparisler
            WHERE sube_id = :sid
              AND durum = 'odendi'
              AND created_at >= :start_date
              AND created_at < :end_date
            GROUP BY EXTRACT(HOUR FROM created_at)
            ORDER BY saat
            """,
            {"sid": sube_id, "start_date": start_date, "end_date": end_date},
        )
        
        # Tüm saatler için veri hazırla (0-23)
        hourly_map = {r["saat"]: {"siparis_sayisi": r["siparis_sayisi"], "toplam_tutar": float(r["toplam_tutar"])} for r in rows}
        result = []
        max_hour = 23 if period == "gunluk" else 23
        for hour in range(max_hour + 1):
            result.append({
                "saat": hour,
                "siparis_sayisi": hourly_map.get(hour, {}).get("siparis_sayisi", 0),
                "toplam_tutar": hourly_map.get(hour, {}).get("toplam_tutar", 0.0),
            })
        
        # Cache'e kaydet (2 dakika TTL)
        await cache.set(cache_key_str, result, ttl=120)
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Hata: {str(e)}")


@router.get("/en-cok-tercih-edilen-urunler")
async def en_cok_tercih_edilen_urunler(
    limit: int = Query(10, ge=1, le=50),
    period: Literal["gunluk", "haftalik", "aylik", "tumu"] = Query("tumu"),
    tarih: Optional[str] = Query(None),
    _: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """En çok tercih edilen ürünleri döndürür"""
    try:
        # Tarih filtresi
        if period == "gunluk":
            if tarih:
                start_date = datetime.strptime(tarih, "%Y-%m-%d")
            else:
                start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=1)
        elif period == "haftalik":
            if tarih:
                base_date = datetime.strptime(tarih, "%Y-%m-%d")
            else:
                base_date = datetime.now()
            start_date = (base_date - timedelta(days=base_date.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=7)
        elif period == "aylik":
            if tarih:
                base_date = datetime.strptime(tarih, "%Y-%m-%d")
            else:
                base_date = datetime.now()
            start_date = base_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if start_date.month == 12:
                end_date = start_date.replace(year=start_date.year + 1, month=1)
            else:
                end_date = start_date.replace(month=start_date.month + 1)
        else:  # tumu
            start_date = None
            end_date = None
        
        # Tüm ödenmiş siparişleri al
        if start_date and end_date:
            rows = await db.fetch_all(
                """
                SELECT sepet, tutar
                FROM siparisler
                WHERE sube_id = :sid
                  AND durum = 'odendi'
                  AND created_at >= :start_date
                  AND created_at < :end_date
                """,
                {"sid": sube_id, "start_date": start_date, "end_date": end_date},
            )
        else:
            rows = await db.fetch_all(
                """
                SELECT sepet, tutar
                FROM siparisler
                WHERE sube_id = :sid
                  AND durum = 'odendi'
                """,
                {"sid": sube_id},
            )
        
        # Ürün bazında toplama
        product_stats: Dict[str, Dict[str, Any]] = {}
        
        for row in rows:
            sepet = parse_sepet(row["sepet"])
            siparis_tutar = float(row["tutar"] or 0)
            
            for item in sepet:
                urun_adi = str(item.get("urun") or item.get("ad") or "").strip()
                if not urun_adi:
                    continue
                
                adet = int(item.get("adet") or 1)
                # Ürün fiyatını hesapla (sepet içindeki fiyat varsa onu kullan, yoksa sipariş tutarını adetlere böl)
                item_fiyat = float(item.get("fiyat") or 0)
                if item_fiyat == 0 and len(sepet) > 0:
                    # Sipariş tutarını adetlere böl
                    toplam_adet = sum(int(i.get("adet") or 1) for i in sepet)
                    if toplam_adet > 0:
                        item_fiyat = siparis_tutar / toplam_adet
                
                if urun_adi not in product_stats:
                    product_stats[urun_adi] = {
                        "satis_adeti": 0,
                        "toplam_tutar": 0.0,
                        "kategori": None,
                    }
                
                product_stats[urun_adi]["satis_adeti"] += adet
                product_stats[urun_adi]["toplam_tutar"] += item_fiyat * adet
        
        # Kategorileri al
        menu_rows = await db.fetch_all(
            """
            SELECT DISTINCT ad, kategori
            FROM menu
            WHERE sube_id = :sid AND aktif = TRUE
            """,
            {"sid": sube_id},
        )
        kategori_map = {r["ad"]: r["kategori"] for r in menu_rows}
        
        # Sonuçları hazırla ve sırala
        result = []
        for urun_adi, stats in product_stats.items():
            result.append({
                "urun_adi": urun_adi,
                "satis_adeti": stats["satis_adeti"],
                "toplam_tutar": round(stats["toplam_tutar"], 2),
                "kategori": kategori_map.get(urun_adi),
            })
        
        # Satış adedine göre sırala
        result.sort(key=lambda x: x["satis_adeti"], reverse=True)
        
        return result[:limit]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Hata: {str(e)}")


@router.get("/ozet", response_model=AnalyticsSummary)
async def analytics_ozet(
    period: Literal["gunluk", "haftalik", "aylik"] = Query("gunluk"),
    tarih: Optional[str] = Query(None, description="YYYY-MM-DD formatında referans tarihi"),
    start: Optional[str] = Query(None, description="Özel aralık başlangıcı (YYYY-MM-DD)"),
    end: Optional[str] = Query(None, description="Özel aralık bitişi (YYYY-MM-DD)"),
    _: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """Seçilen periyot veya özel tarih aralığı için genel analitik özeti döndürür."""
    # Cache key oluştur
    cache_key_str = cache_key("analytics:ozet", sube_id, period, tarih, start, end)
    
    # Cache'den kontrol et
    cached_result = await cache.get(cache_key_str)
    if cached_result is not None:
        return cached_result
    
    try:
        if start and end:
            start_date = datetime.strptime(start, "%Y-%m-%d")
            end_date = datetime.strptime(end, "%Y-%m-%d") + timedelta(days=1)
            period_label = "Özel Aralık"
        else:
            reference_date = datetime.strptime(tarih, "%Y-%m-%d") if tarih else None
            period_info = _get_period_range(period, reference_date)
            start_date = period_info["start"]
            end_date = period_info["end"]
            period_label = period_info["label"]

        if end_date <= start_date:
            raise HTTPException(status_code=400, detail="Bitiş tarihi başlangıç tarihinden büyük olmalıdır.")

        display_end_date = end_date - timedelta(seconds=1)

        common_params = {"sid": sube_id, "start_date": start_date, "end_date": end_date}

        total_row = await db.fetch_one(
            """
            SELECT 
                COUNT(*)::int AS siparis_sayisi,
                COALESCE(SUM(tutar), 0)::float AS toplam_ciro
            FROM siparisler
            WHERE sube_id = :sid 
              AND durum = 'odendi'
              AND created_at >= :start_date
              AND created_at < :end_date
            """,
            common_params,
        )

        siparis_sayisi = int(total_row["siparis_sayisi"] or 0)
        toplam_ciro = float(total_row["toplam_ciro"] or 0.0)
        ortalama_sepet = round(toplam_ciro / siparis_sayisi, 2) if siparis_sayisi else 0.0

        popular_rows = await db.fetch_all(
            """
            SELECT sepet
            FROM siparisler
            WHERE sube_id = :sid 
              AND durum = 'odendi'
              AND created_at >= :start_date
              AND created_at < :end_date
            LIMIT 500
            """,
            common_params,
        )

        product_counts: Dict[str, int] = {}
        for row in popular_rows:
            sepet = parse_sepet(row["sepet"])
            for item in sepet:
                urun_adi = str(item.get("urun") or item.get("ad") or "").strip()
                if urun_adi:
                    adet = int(item.get("adet") or 1)
                    product_counts[urun_adi] = product_counts.get(urun_adi, 0) + adet

        en_populer = None
        if product_counts:
            en_populer = max(product_counts.items(), key=lambda x: x[1])[0]

        payment_rows = await db.fetch_all(
            """
            SELECT yontem, COALESCE(SUM(tutar), 0)::float AS toplam
            FROM odemeler
            WHERE sube_id = :sid 
              AND iptal = FALSE 
              AND created_at >= :start_date
              AND created_at < :end_date
            GROUP BY yontem
            """,
            common_params,
        )
        odeme_dagilim = {
            r["yontem"]: round(float(r["toplam"] or 0), 2)
            for r in payment_rows
            if r["yontem"] and str(r["yontem"]).lower() != "iskonto"
        }

        discount_row = await db.fetch_one(
            """
            SELECT COALESCE(SUM(tutar), 0)::float AS toplam
            FROM iskonto_kayitlari
            WHERE sube_id = :sid
              AND created_at >= :start_date
              AND created_at < :end_date
            """,
            common_params,
        )
        toplam_iskonto = round(float(discount_row["toplam"] or 0), 2) if discount_row else 0.0

        ikram_rows = await db.fetch_all(
            """
            SELECT sepet
            FROM siparisler
            WHERE sube_id = :sid
              AND durum = 'odendi'
              AND created_at >= :start_date
              AND created_at < :end_date
            """,
            common_params,
        )
        toplam_ikram = 0.0
        ikram_map: Dict[str, Dict[str, Any]] = {}
        for row in ikram_rows:
            sepet = parse_sepet(row["sepet"])
            for item in sepet:
                ikram_flag = item.get("ikram")
                if not ikram_flag:
                    continue
                if isinstance(ikram_flag, str) and ikram_flag.strip().lower() in {"false", "0", "hayır", "hayir", "no"}:
                    continue

                urun_adi = str(item.get("urun") or item.get("ad") or "").strip() or "İkram"
                adet = int(item.get("adet") or 1)
                tutar = float(item.get("ikram_edilen_tutar") or 0)
                if tutar == 0:
                    fiyat = float(item.get("fiyat") or 0)
                    tutar = fiyat * adet
                toplam_ikram += tutar

                stats = ikram_map.setdefault(urun_adi, {"adet": 0, "tutar": 0.0})
                stats["adet"] += adet
                stats["tutar"] += tutar

        en_cok_ikram = None
        if ikram_map:
            urun_adi, stats = max(ikram_map.items(), key=lambda x: (x[1]["tutar"], x[1]["adet"]))
            en_cok_ikram = {
                "urun_adi": urun_adi,
                "adet": stats["adet"],
                "tutar": round(stats["tutar"], 2),
            }
        toplam_ikram = round(toplam_ikram, 2)

        masa_avg_row = await db.fetch_one(
            """
            WITH masa_totals AS (
                SELECT masa, COALESCE(SUM(tutar), 0)::float AS toplam_tutar
                FROM siparisler
                WHERE sube_id = :sid 
                  AND durum = 'odendi'
                  AND created_at >= :start_date
                  AND created_at < :end_date
                GROUP BY masa
            )
            SELECT COALESCE(AVG(toplam_tutar), 0)::float AS ortalama_masa_tutari
            FROM masa_totals
            """,
            common_params,
        )
        ortalama_masa_tutari = round(float(masa_avg_row["ortalama_masa_tutari"] or 0), 2)

        personel_rows = await db.fetch_all(
            """
            SELECT 
                COALESCE(u.username, NULLIF(s.created_by_username, ''), 'ai_assistant') AS username,
                COALESCE(u.username, NULLIF(s.created_by_username, ''), 'AI Asistan') AS display_name,
                COALESCE(u.role, CASE WHEN s.created_by_user_id IS NULL THEN 'ai' ELSE 'personel' END) AS role,
                SUM(CASE WHEN s.durum = 'odendi' THEN 1 ELSE 0 END)::int AS siparis_sayisi,
                COALESCE(SUM(CASE WHEN s.durum = 'odendi' THEN s.tutar ELSE 0 END), 0)::float AS toplam_ciro
            FROM siparisler s
            LEFT JOIN users u ON u.id = s.created_by_user_id
            WHERE s.sube_id = :sid
              AND s.created_at >= :start_date
              AND s.created_at < :end_date
            GROUP BY 1,2,3
            HAVING SUM(CASE WHEN s.durum = 'odendi' THEN 1 ELSE 0 END) > 0
            ORDER BY siparis_sayisi DESC, toplam_ciro DESC
            LIMIT 2
            """,
            common_params,
        )

        top_personeller = []
        for row in personel_rows:
            username = row["username"] or "ai_assistant"
            display_name = row["display_name"] or ("AI Asistan" if username == "ai_assistant" else username)
            top_personeller.append(
                {
                    "username": username,
                    "display_name": display_name,
                    "role": row["role"],
                    "siparis_sayisi": int(row["siparis_sayisi"] or 0),
                    "toplam_ciro": round(float(row["toplam_ciro"] or 0), 2),
                }
            )

        expense_params = {
            "sid": sube_id,
            "start_date": start_date.date(),
            "end_date": end_date.date(),
        }
        expense_row = await db.fetch_one(
            """
            SELECT COALESCE(SUM(tutar), 0)::float AS toplam
            FROM giderler
            WHERE sube_id = :sid
              AND tarih >= :start_date
              AND tarih < :end_date
            """,
            expense_params,
        )
        toplam_gider = round(float(expense_row["toplam"] or 0), 2) if expense_row else 0.0

        return {
            "period": period,
            "period_label": period_label,
            "start_tarih": start_date.isoformat(),
            "end_tarih": display_end_date.isoformat(),
            "siparis_sayisi": siparis_sayisi,
            "toplam_ciro": round(toplam_ciro, 2),
            "toplam_gider": toplam_gider,
            "ortalama_sepet": ortalama_sepet,
            "ortalama_masa_tutari": ortalama_masa_tutari,
            "en_populer_urun": en_populer,
            "odeme_dagilim": odeme_dagilim,
            "toplam_iskonto": toplam_iskonto,
            "toplam_ikram": toplam_ikram,
            "en_cok_ikram": en_cok_ikram,
            "top_personeller": top_personeller,
        }
        
        # Cache'e kaydet (2 dakika TTL - analytics verileri sık değişebilir)
        await cache.set(cache_key_str, result, ttl=120)
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Hata: {str(e)}")





