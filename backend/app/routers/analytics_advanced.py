# backend/app/routers/analytics_advanced.py
"""
Gelişmiş Analitik ve Raporlama
Karlılık, personel performans, müşteri davranış analizi
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime, timedelta
from decimal import Decimal

from ..core.deps import get_current_user, get_sube_id, require_roles
from ..db.database import db
from ..services.audit import audit_service

router = APIRouter(prefix="/analytics/advanced", tags=["Advanced Analytics"])


# ========== MODELS ==========

class ProductProfitability(BaseModel):
    """Ürün karlılık modeli"""
    urun_adi: str
    kategori: Optional[str]
    toplam_satis_adedi: int
    toplam_ciro: float
    maliyet_toplam: float
    brut_kar: float
    kar_marji_yuzde: float
    ortalama_satis_fiyati: float
    ortalama_maliyet: float


class PersonnelPerformance(BaseModel):
    """Personel performans modeli"""
    username: str
    tam_adi: Optional[str]
    toplam_siparis: int
    toplam_ciro: float
    ortalama_sepet: float
    iptal_orani: float
    en_cok_sattigi_urun: Optional[str]
    performans_skoru: float


class CustomerBehavior(BaseModel):
    """Müşteri davranış modeli"""
    masa: str
    ziyaret_sayisi: int
    toplam_harcama: float
    ortalama_sepet: float
    en_cok_siparis_edilen: Optional[str]
    son_ziyaret: Optional[str]
    musteri_segmenti: str  # "yeni", "duzenli", "sadik", "kayip"


class CategoryAnalysis(BaseModel):
    """Kategori analizi"""
    kategori: str
    urun_sayisi: int
    toplam_satis: int
    toplam_ciro: float
    ortalama_fiyat: float
    ciro_payi_yuzde: float


class TimeBasedAnalysis(BaseModel):
    """Zaman bazlı analiz"""
    period: str
    gun: Optional[str]
    saat: Optional[int]
    siparis_sayisi: int
    ciro: float
    ortalama_sepet: float
    en_yogun_saat: bool


# ========== ENDPOINTS ==========

@router.get(
    "/product-profitability",
    dependencies=[Depends(require_roles({"super_admin", "admin"}))],
)
async def get_product_profitability(
    start_date: Optional[str] = Query(None, description="Başlangıç tarihi (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Bitiş tarihi (YYYY-MM-DD)"),
    days: int = Query(30, ge=1, le=365, description="Analiz dönemi (gün)"),
    min_sales: int = Query(5, ge=1, description="Minimum satış adedi"),
    user: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """
    Ürün karlılık analizi

    Her ürün için:
    - Toplam satış adedi ve ciro
    - Maliyet hesabı (reçete bazlı)
    - Brüt kar ve kar marjı
    - Ortalama fiyat ve maliyet

    **Yetkiler:** super_admin, admin
    """
    # Tarih aralığını belirle
    if start_date and end_date:
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date) + timedelta(days=1)  # End of day
    else:
        start_dt = datetime.now() - timedelta(days=days)
        end_dt = datetime.now()

    query = """
    WITH product_sales AS (
        SELECT
            si->>'urun' AS urun_adi,
            (si->>'adet')::int AS adet,
            (si->>'fiyat')::numeric AS fiyat
        FROM siparisler s
        CROSS JOIN LATERAL jsonb_array_elements(s.sepet) AS si
        WHERE s.sube_id = :sube_id
          AND s.created_at >= :start_dt
          AND s.created_at < :end_dt
          AND s.durum = 'odendi'
    ),
    product_costs AS (
        SELECT
            r.urun,
            SUM(r.miktar * sk.alis_fiyat) AS maliyet_per_unit
        FROM receteler r
        JOIN stok_kalemleri sk ON sk.ad = r.stok AND sk.sube_id = r.sube_id
        WHERE r.sube_id = :sube_id
        GROUP BY r.urun
    ),
    aggregated AS (
        SELECT
            ps.urun_adi,
            m.kategori,
            SUM(ps.adet) AS toplam_satis_adedi,
            SUM(ps.adet * ps.fiyat) AS toplam_ciro,
            COALESCE(SUM(ps.adet * pc.maliyet_per_unit), 0) AS maliyet_toplam,
            AVG(ps.fiyat) AS ortalama_satis_fiyati,
            COALESCE(AVG(pc.maliyet_per_unit), 0) AS ortalama_maliyet
        FROM product_sales ps
        LEFT JOIN menu m ON LOWER(TRIM(m.ad)) = LOWER(TRIM(ps.urun_adi)) AND m.sube_id = :sube_id
        LEFT JOIN product_costs pc ON LOWER(TRIM(pc.urun)) = LOWER(TRIM(ps.urun_adi))
        GROUP BY ps.urun_adi, m.kategori
        HAVING SUM(ps.adet) >= :min_sales
    )
    SELECT
        urun_adi,
        kategori,
        toplam_satis_adedi,
        toplam_ciro::float,
        maliyet_toplam::float,
        (toplam_ciro - maliyet_toplam)::float AS brut_kar,
        CASE
            WHEN toplam_ciro > 0 THEN ((toplam_ciro - maliyet_toplam) / toplam_ciro * 100)::float
            ELSE 0
        END AS kar_marji_yuzde,
        ortalama_satis_fiyati::float,
        ortalama_maliyet::float
    FROM aggregated
    ORDER BY brut_kar DESC
    """

    rows = await db.fetch_all(query, {
        "sube_id": sube_id,
        "start_dt": start_dt,
        "end_dt": end_dt,
        "min_sales": min_sales,
    })

    products = []
    for row in rows:
        product = dict(row)
        sales_count = product.get("toplam_satis_adedi") or 0
        revenue = float(product.get("toplam_ciro") or 0)
        cost = float(product.get("maliyet_toplam") or 0)

        # Maliyet toplamı, ciroyu aşmamalı (veri anomalisini engelle)
        if cost > revenue and revenue > 0:
            cost = revenue
        if cost < 0:
            cost = 0

        product["maliyet_toplam"] = cost

        avg_cost = cost / sales_count if sales_count > 0 else 0.0
        product["ortalama_maliyet"] = avg_cost

        profit = revenue - cost
        product["brut_kar"] = profit
        product["kar_marji_yuzde"] = (profit / revenue * 100) if revenue > 0 else 0.0

        products.append(product)

    # Calculate totals
    total_revenue = sum(p['toplam_ciro'] for p in products)
    total_cost = sum(p['maliyet_toplam'] for p in products)
    total_profit = total_revenue - total_cost
    profit_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0

    # Audit log
    await audit_service.log_action(
        action="analytics.product_profitability",
        username=user.get("username"),
        sube_id=sube_id,
        entity_type="analytics",
        success=True,
    )

    # Return formatted response for frontend
    return {
        "total_revenue": total_revenue,
        "total_cost": total_cost,
        "total_profit": total_profit,
        "profit_margin": profit_margin,
        "products": [{
            "urun": p['urun_adi'],
            "total_quantity": p['toplam_satis_adedi'],
            "revenue": p['toplam_ciro'],
            "cost": p['maliyet_toplam'],
            "profit": p['brut_kar'],
            "profit_margin": p['kar_marji_yuzde'],
        } for p in products]
    }


@router.get(
    "/personnel-performance",
    dependencies=[Depends(require_roles({"super_admin", "admin"}))],
)
async def get_personnel_performance(
    start_date: Optional[str] = Query(None, description="Başlangıç tarihi (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Bitiş tarihi (YYYY-MM-DD)"),
    days: int = Query(30, ge=1, le=365),
    period: Literal["day", "week", "month", "custom"] = Query(
        "day",
        description="Analiz dönemi: day=bugün, week=son 7 gün, month=son 30 gün, custom=özel tarih aralığı"
    ),
    user: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """
    Personel performans analizi

    Her personel için:
    - Toplam sipariş sayısı ve ciro
    - Ortalama sepet tutarı
    - İptal oranı
    - En çok sattığı ürün
    - Performans skoru (normalized)

    **Yetkiler:** super_admin, admin
    """
    # Tarih aralığını belirle
    now = datetime.now()
    selected_period: str = period
    if start_date and end_date:
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date) + timedelta(days=1)
        selected_period = "day" if start_date == end_date else "custom"
    else:
        if days and days != 30:
            start_dt = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_dt = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            selected_period = "day" if days == 1 else f"{days}_days"
        else:
            period = period.lower()
            if period == "day":
                start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
                end_dt = start_dt + timedelta(days=1)
            elif period == "week":
                start_dt = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
                end_dt = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            else:  # month
                start_dt = (now - timedelta(days=29)).replace(hour=0, minute=0, second=0, microsecond=0)
                end_dt = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    query = """
    WITH order_stats AS (
        SELECT
            COALESCE(u.username, s.created_by_username, 'ai_assistant') AS username,
            COALESCE(u.username, s.created_by_username, 'AI Asistan') AS display_name,
            COALESCE(u.role, CASE WHEN s.created_by_user_id IS NULL THEN 'ai' ELSE 'personel' END) AS role,
            COUNT(DISTINCT CASE WHEN s.durum = 'odendi' THEN s.id END) AS toplam_siparis,
            SUM(CASE WHEN s.durum = 'odendi' THEN s.tutar ELSE 0 END) AS toplam_ciro,
            AVG(CASE WHEN s.durum = 'odendi' THEN s.tutar END) AS ortalama_sepet,
            SUM(CASE WHEN s.durum = 'iptal' THEN 1 ELSE 0 END)::float /
                NULLIF(COUNT(*), 0) * 100 AS iptal_orani,
            COUNT(*) AS toplam_kayit
        FROM siparisler s
        LEFT JOIN users u ON u.id = s.created_by_user_id
        WHERE s.sube_id = :sube_id
          AND s.created_at >= :start_dt
          AND s.created_at < :end_dt
        GROUP BY 1,2,3
    ),
    top_products AS (
        SELECT username,
               si->>'urun' AS urun,
               COUNT(*) AS adet
        FROM siparisler s
        LEFT JOIN users u ON u.id = s.created_by_user_id
        CROSS JOIN LATERAL jsonb_array_elements(s.sepet) AS si
        WHERE s.sube_id = :sube_id
          AND s.created_at >= :start_dt
          AND s.created_at < :end_dt
          AND s.durum = 'odendi'
        GROUP BY username, si->>'urun'
    ),
    top_products_ranked AS (
        SELECT DISTINCT ON (username)
            username,
            urun AS en_cok_sattigi
        FROM top_products
        ORDER BY username, adet DESC
    )
    SELECT
        os.username,
        COALESCE(NULLIF(os.display_name, ''), os.username) AS tam_adi,
        os.role,
        os.toplam_siparis::int,
        COALESCE(os.toplam_ciro, 0)::float AS toplam_ciro,
        COALESCE(os.ortalama_sepet, 0)::float AS ortalama_sepet,
        COALESCE(os.iptal_orani, 0)::float AS iptal_orani,
        tpr.en_cok_sattigi,
        os.toplam_kayit
    FROM order_stats os
    LEFT JOIN top_products_ranked tpr ON tpr.username = os.username
    WHERE (os.toplam_siparis > 0 OR os.toplam_ciro > 0 OR os.toplam_kayit > 0)
    """

    rows = await db.fetch_all(query, {
        "sube_id": sube_id,
        "start_dt": start_dt,
        "end_dt": end_dt,
    })

    personnel_list = []
    seen_usernames = set()
    for row in rows:
        row_dict = dict(row)
        username = row_dict.get("username") or "ai_assistant"
        if username in seen_usernames:
            continue
        seen_usernames.add(username)
        personnel_list.append({
            "username": username,
            "tam_adi": row_dict.get("tam_adi") or username,
            "role": row_dict.get("role") or ("ai" if username == "ai_assistant" else "personel"),
            "toplam_siparis": int(row_dict.get("toplam_siparis") or 0),
            "toplam_ciro": float(row_dict.get("toplam_ciro") or 0),
            "ortalama_sepet": float(row_dict.get("ortalama_sepet") or 0),
            "iptal_orani": float(row_dict.get("iptal_orani") or 0),
            "en_cok_sattigi": row_dict.get("en_cok_sattigi"),
        })

    # Varsayılan değerleri doldur
    for p in personnel_list:
        p["toplam_ciro"] = float(p.get("toplam_ciro") or 0)
        p["toplam_siparis"] = int(p.get("toplam_siparis") or 0)
        p["ortalama_sepet"] = float(p.get("ortalama_sepet") or 0)
        p["iptal_orani"] = float(p.get("iptal_orani") or 0)

    # Performans skorunu Python tarafında normalize et
    max_ciro = max((p["toplam_ciro"] for p in personnel_list), default=0)
    max_siparis = max((p["toplam_siparis"] for p in personnel_list), default=0)

    for p in personnel_list:
        score = 0.0
        if p["toplam_siparis"] > 0 or p["toplam_ciro"] > 0:
            ciro_component = (p["toplam_ciro"] / max_ciro * 50) if max_ciro > 0 else 0
            siparis_component = (p["toplam_siparis"] / max_siparis * 30) if max_siparis > 0 else 0
            iptal_component = max(0.0, min(100.0, 100 - p["iptal_orani"])) / 100 * 20
            score = min(100.0, ciro_component + siparis_component + iptal_component)
        p["performans_skoru"] = score

    # Performansa göre sırala
    personnel_list.sort(key=lambda x: x.get("performans_skoru", 0), reverse=True)

    # Calculate aggregate stats
    total_personnel = len(personnel_list)
    top_performer = personnel_list[0] if personnel_list else None
    avg_orders = sum(p.get('toplam_siparis', 0) for p in personnel_list) / total_personnel if total_personnel > 0 else 0

    # Audit log
    await audit_service.log_action(
        action="analytics.personnel_performance",
        username=user.get("username"),
        sube_id=sube_id,
        entity_type="analytics",
        success=True,
    )

    # Return formatted response for frontend
    return {
        "personnel_count": total_personnel,
        "period": selected_period,
        "top_performer": {
            "name": top_performer.get('tam_adi') if top_performer else None,
            "score": top_performer.get('performans_skoru', 0) if top_performer else 0
        } if top_performer else None,
        "avg_orders_per_person": avg_orders,
        "personnel": [{
            "name": p.get('tam_adi'),
            "order_count": p.get('toplam_siparis', 0),
            "total_revenue": p.get('toplam_ciro', 0),
            "avg_order_value": p.get('ortalama_sepet', 0),
            "performance_score": p.get('performans_skoru', 0),
        } for p in personnel_list]
    }


@router.get(
    "/customer-behavior",
    dependencies=[Depends(require_roles({"super_admin", "admin"}))],
)
async def get_customer_behavior(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    days: int = Query(90, ge=1, le=365),
    min_visits: int = Query(1, ge=1),
    user: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """
    Müşteri davranış analizi (Masa bazlı)

    Her masa için:
    - Ziyaret sayısı
    - Toplam harcama ve ortalama sepet
    - En çok sipariş edilen ürün
    - Müşteri segmenti (yeni/düzenli/sadık/kayıp)

    **Yetkiler:** super_admin, admin
    """
    if start_date and end_date:
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date) + timedelta(days=1)
    else:
        start_dt = datetime.now() - timedelta(days=days)
        end_dt = datetime.now()

    query = """
    WITH customer_stats AS (
        SELECT
            s.masa,
            COUNT(DISTINCT DATE(s.created_at)) AS ziyaret_sayisi,
            SUM(s.tutar) AS toplam_harcama,
            AVG(s.tutar) AS ortalama_sepet,
            MAX(s.created_at) AS son_ziyaret,
            EXTRACT(EPOCH FROM (NOW() - MAX(s.created_at)))/86400 AS gun_farki
        FROM siparisler s
        WHERE s.sube_id = :sube_id
          AND s.created_at >= :start_dt
          AND s.created_at < :end_dt
          AND s.durum = 'odendi'
        GROUP BY s.masa
        HAVING COUNT(DISTINCT DATE(s.created_at)) >= :min_visits
    ),
    top_products_per_customer AS (
        SELECT DISTINCT ON (s.masa)
            s.masa,
            si->>'urun' AS en_cok_siparis
        FROM siparisler s
        CROSS JOIN LATERAL jsonb_array_elements(s.sepet) AS si
        WHERE s.sube_id = :sube_id
          AND s.created_at >= :start_dt
          AND s.created_at < :end_dt
        GROUP BY s.masa, si->>'urun'
        ORDER BY s.masa, COUNT(*) DESC
    )
    SELECT
        cs.masa,
        cs.ziyaret_sayisi::int,
        cs.toplam_harcama::float,
        cs.ortalama_sepet::float,
        tp.en_cok_siparis AS en_cok_siparis_edilen,
        cs.son_ziyaret::text,
        CASE
            WHEN cs.ziyaret_sayisi = 1 THEN 'yeni'
            WHEN cs.ziyaret_sayisi >= 10 THEN 'sadik'
            WHEN cs.ziyaret_sayisi >= 3 THEN 'duzenli'
            WHEN cs.gun_farki > 30 THEN 'kayip'
            ELSE 'duzenli'
        END AS musteri_segmenti
    FROM customer_stats cs
    LEFT JOIN top_products_per_customer tp ON tp.masa = cs.masa
    ORDER BY cs.toplam_harcama DESC
    """

    rows = await db.fetch_all(query, {
        "sube_id": sube_id,
        "start_dt": start_dt,
        "end_dt": end_dt,
        "min_visits": min_visits,
    })

    customers = [dict(row) for row in rows]

    # Calculate aggregate statistics
    total_orders = sum(c['ziyaret_sayisi'] for c in customers)
    total_revenue = sum(c['toplam_harcama'] for c in customers)
    avg_order_value = total_revenue / total_orders if total_orders > 0 else 0

    # Get popular items across all customers
    popular_items_query = """
    SELECT
        si->>'urun' AS item_name,
        SUM((si->>'adet')::int) AS order_count
    FROM siparisler s
    CROSS JOIN LATERAL jsonb_array_elements(s.sepet) AS si
    WHERE s.sube_id = :sube_id
      AND s.created_at >= :start_dt
      AND s.created_at < :end_dt
      AND s.durum = 'odendi'
    GROUP BY item_name
    ORDER BY order_count DESC
    LIMIT 10
    """

    popular_rows = await db.fetch_all(popular_items_query, {
        "sube_id": sube_id,
        "start_dt": start_dt,
        "end_dt": end_dt,
    })
    popular_items = [dict(row) for row in popular_rows]

    # Audit log
    await audit_service.log_action(
        action="analytics.customer_behavior",
        username=user.get("username"),
        sube_id=sube_id,
        entity_type="analytics",
        success=True,
    )

    # Return formatted response for frontend
    return {
        "total_orders": total_orders,
        "avg_order_value": avg_order_value,
        "customer_count": len(customers),
        "popular_items": popular_items,
        "customers": [{
            "table": c['masa'],
            "visit_count": c['ziyaret_sayisi'],
            "total_spent": c['toplam_harcama'],
            "avg_order_value": c['ortalama_sepet'],
            "segment": c['musteri_segmenti'],
        } for c in customers[:20]]  # Limit to top 20 for display
    }


@router.get(
    "/category-analysis",
    dependencies=[Depends(require_roles({"super_admin", "admin"}))],
)
async def get_category_analysis(
    start_date: Optional[str] = Query(None, description="Başlangıç tarihi (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Bitiş tarihi (YYYY-MM-DD)"),
    days: int = Query(30, ge=1, le=365),
    user: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """
    Kategori bazlı analiz

    Her kategori için:
    - Ürün sayısı
    - Toplam satış ve ciro
    - Ortalama fiyat
    - Ciro payı (yüzde)

    **Yetkiler:** super_admin, admin
    """
    # Tarih aralığını belirle
    if start_date and end_date:
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date) + timedelta(days=1)
    else:
        start_dt = datetime.now() - timedelta(days=days)
        end_dt = datetime.now()

    query = """
    WITH category_sales AS (
        SELECT
            COALESCE(m.kategori, 'Diğer') AS kategori,
            COUNT(DISTINCT m.id) AS urun_sayisi,
            SUM((si->>'adet')::int) AS toplam_satis,
            SUM((si->>'adet')::int * (si->>'fiyat')::numeric) AS toplam_ciro,
            AVG((si->>'fiyat')::numeric) AS ortalama_fiyat
        FROM siparisler s
        CROSS JOIN LATERAL jsonb_array_elements(s.sepet) AS si
        LEFT JOIN menu m ON LOWER(TRIM(m.ad)) = LOWER(TRIM(si->>'urun'))
            AND m.sube_id = s.sube_id
        WHERE s.sube_id = :sube_id
          AND s.created_at >= :start_dt
          AND s.created_at < :end_dt
          AND s.durum = 'odendi'
        GROUP BY kategori
    ),
    total_revenue AS (
        SELECT SUM(toplam_ciro) AS total FROM category_sales
    )
    SELECT
        cs.kategori,
        cs.urun_sayisi::int,
        cs.toplam_satis::int,
        cs.toplam_ciro::float,
        cs.ortalama_fiyat::float,
        (cs.toplam_ciro / tr.total * 100)::float AS ciro_payi_yuzde
    FROM category_sales cs
    CROSS JOIN total_revenue tr
    ORDER BY cs.toplam_ciro DESC
    """

    rows = await db.fetch_all(query, {
        "sube_id": sube_id,
        "start_dt": start_dt,
        "end_dt": end_dt,
    })

    categories = [dict(row) for row in rows]

    # Calculate aggregate statistics
    category_count = len(categories)
    top_category = categories[0] if categories else None
    total_revenue = sum(c['toplam_ciro'] for c in categories)

    # Audit log
    await audit_service.log_action(
        action="analytics.category_analysis",
        username=user.get("username"),
        sube_id=sube_id,
        entity_type="analytics",
        success=True,
    )

    # Return formatted response for frontend
    return {
        "category_count": category_count,
        "top_category": {
            "name": top_category['kategori'] if top_category else None,
            "revenue": top_category['toplam_ciro'] if top_category else 0
        } if top_category else None,
        "total_revenue": total_revenue,
        "categories": [{
            "category": c['kategori'],
            "product_count": c['urun_sayisi'],
            "total_sales": c['toplam_satis'],
            "revenue": c['toplam_ciro'],
            "revenue_share": c['ciro_payi_yuzde'],
        } for c in categories]
    }


@router.get(
    "/time-based-analysis",
    dependencies=[Depends(require_roles({"super_admin", "admin"}))],
)
async def get_time_based_analysis(
    start_date: Optional[str] = Query(None, description="Başlangıç tarihi (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Bitiş tarihi (YYYY-MM-DD)"),
    days: int = Query(30, ge=1, le=90),
    group_by: str = Query("hour", regex="^(hour|day|weekday)$"),
    user: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """
    Zaman bazlı satış analizi

    - hour: Saatlik analiz (hangi saat en yoğun?)
    - day: Günlük analiz (trend analizi)
    - weekday: Haftanın günü analizi (hangi gün en yoğun?)

    **Yetkiler:** super_admin, admin
    """
    # Tarih aralığını belirle
    if start_date and end_date:
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date) + timedelta(days=1)
    else:
        start_dt = datetime.now() - timedelta(days=days)
        end_dt = datetime.now()

    if group_by == "hour":
        query = """
        WITH hourly_stats AS (
            SELECT
                EXTRACT(HOUR FROM created_at)::int AS saat,
                COUNT(*) AS siparis_sayisi,
                SUM(tutar) AS ciro,
                AVG(tutar) AS ortalama_sepet
            FROM siparisler
            WHERE sube_id = :sube_id
              AND created_at >= :start_dt
              AND created_at < :end_dt
              AND durum = 'odendi'
            GROUP BY saat
        ),
        max_hour AS (
            SELECT saat FROM hourly_stats ORDER BY siparis_sayisi DESC LIMIT 1
        )
        SELECT
            'Saat ' || hs.saat::text AS period,
            NULL AS gun,
            hs.saat,
            hs.siparis_sayisi::int,
            hs.ciro::float,
            hs.ortalama_sepet::float,
            (hs.saat = mh.saat) AS en_yogun_saat
        FROM hourly_stats hs
        CROSS JOIN max_hour mh
        ORDER BY hs.saat
        """
    elif group_by == "weekday":
        query = """
        WITH weekday_stats AS (
            SELECT
                CASE EXTRACT(DOW FROM created_at)
                    WHEN 0 THEN 'Pazar'
                    WHEN 1 THEN 'Pazartesi'
                    WHEN 2 THEN 'Salı'
                    WHEN 3 THEN 'Çarşamba'
                    WHEN 4 THEN 'Perşembe'
                    WHEN 5 THEN 'Cuma'
                    WHEN 6 THEN 'Cumartesi'
                END AS gun,
                EXTRACT(DOW FROM created_at)::int AS dow,
                COUNT(*) AS siparis_sayisi,
                SUM(tutar) AS ciro,
                AVG(tutar) AS ortalama_sepet
            FROM siparisler
            WHERE sube_id = :sube_id
              AND created_at >= :start_dt
              AND created_at < :end_dt
              AND durum = 'odendi'
            GROUP BY gun, dow
        ),
        max_day AS (
            SELECT gun FROM weekday_stats ORDER BY siparis_sayisi DESC LIMIT 1
        )
        SELECT
            ws.gun AS period,
            ws.gun,
            NULL AS saat,
            ws.siparis_sayisi::int,
            ws.ciro::float,
            ws.ortalama_sepet::float,
            (ws.gun = md.gun) AS en_yogun_saat
        FROM weekday_stats ws
        CROSS JOIN max_day md
        ORDER BY ws.dow
        """
    else:  # day
        query = """
        SELECT
            TO_CHAR(created_at, 'YYYY-MM-DD') AS period,
            TO_CHAR(created_at, 'DD Mon') AS gun,
            NULL AS saat,
            COUNT(*)::int AS siparis_sayisi,
            SUM(tutar)::float AS ciro,
            AVG(tutar)::float AS ortalama_sepet,
            FALSE AS en_yogun_saat
        FROM siparisler
        WHERE sube_id = :sube_id
          AND created_at >= :start_dt
          AND created_at < :end_dt
          AND durum = 'odendi'
        GROUP BY period, gun
        ORDER BY period DESC
        """

    rows = await db.fetch_all(query, {
        "sube_id": sube_id,
        "start_dt": start_dt,
        "end_dt": end_dt,
    })

    time_data = [dict(row) for row in rows]

    # Calculate aggregate statistics based on group_by type
    if time_data:
        peak_period = max(time_data, key=lambda x: x['siparis_sayisi'])
        peak_revenue_period = max(time_data, key=lambda x: x['ciro'])
        avg_orders = sum(t['siparis_sayisi'] for t in time_data) / len(time_data)
        total_revenue = sum(t['ciro'] for t in time_data)
    else:
        peak_period = None
        peak_revenue_period = None
        avg_orders = 0
        total_revenue = 0

    # Audit log
    await audit_service.log_action(
        action="analytics.time_based_analysis",
        username=user.get("username"),
        sube_id=sube_id,
        entity_type="analytics",
        success=True,
    )

    # Return formatted response for frontend
    return {
        "group_by": group_by,
        "peak_period": peak_period['period'] if peak_period else None,
        "peak_revenue_period": peak_revenue_period['period'] if peak_revenue_period else None,
        "avg_orders_per_period": avg_orders,
        "total_revenue": total_revenue,
        "data": [{
            "period": t['period'],
            "order_count": t['siparis_sayisi'],
            "revenue": t['ciro'],
            "avg_order_value": t['ortalama_sepet'],
            "is_peak": t.get('en_yogun_saat', False),
        } for t in time_data]
    }
