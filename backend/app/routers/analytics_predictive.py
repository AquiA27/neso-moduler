# backend/app/routers/analytics_predictive.py
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict
import json

from ..core.deps import get_current_user, get_sube_id, require_roles
from ..db.database import db
from ..services.audit import audit_service

router = APIRouter(prefix="/analytics/predictive", tags=["Predictive Analytics"])

# ========== MODELS ==========

class ForecastItem(BaseModel):
    date: str
    predicted_sales: float
    confidence: float

class ProductForecast(BaseModel):
    urun: str
    forecast: List[ForecastItem]
    total_predicted_7d: float
    stock_status: str # "yeterli", "riskli", "yetersiz"

class ProductAffinity(BaseModel):
    product_a: str
    product_b: str
    co_occurrence_count: int
    correlation_score: float # 0-1

class MenuSuggestion(BaseModel):
    urun: str
    kategori: str
    tip: str # "hero", "sleeping", "underperformer"
    oneri: str
    metrikler: Dict[str, Any]

# ========== HELPERS ==========

def parse_sepet(sepet_value) -> List[Dict[str, Any]]:
    if sepet_value is None: return []
    if isinstance(sepet_value, list): return sepet_value
    if isinstance(sepet_value, str):
        try: return json.loads(sepet_value)
        except: return []
    return []

# ========== ENDPOINTS ==========

@router.get("/demand-forecast", dependencies=[Depends(require_roles({"admin", "super_admin"}))])
async def get_demand_forecast(
    days_back: int = Query(60, ge=30, le=120),
    user: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """
    Satış Tahminleme (Talep Tahmini)
    Son X gündeki satış verilerini analiz ederek önümüzdeki 7 günü tahmin eder.
    """
    start_dt = datetime.now() - timedelta(days=days_back)
    
    # 1. Geçmiş verileri çek
    query = """
    SELECT 
        DATE(created_at) as tarih,
        EXTRACT(DOW FROM created_at) as dow,
        sepet
    FROM siparisler
    WHERE sube_id = :sube_id AND durum = 'odendi' AND created_at >= :start_dt
    """
    rows = await db.fetch_all(query, {"sube_id": sube_id, "start_dt": start_dt})
    
    # 2. Ürün ve Gün bazlı grupla
    # dow_stats[urun][dow] = [adet1, adet2, ...]
    dow_stats = defaultdict(lambda: defaultdict(list))
    
    for row in rows:
        dow = int(row["dow"])
        sepet = parse_sepet(row["sepet"])
        for item in sepet:
            urun = item.get("urun") or item.get("ad")
            adet = float(item.get("adet") or 1)
            if urun:
                dow_stats[urun][dow].append(adet)
                
    # 3. Tahmin oluştur (Basit ortalama + Trend)
    predictions = []
    today = datetime.now().date()
    
    # En çok satan 20 ürüne odaklan
    top_products = sorted(dow_stats.keys(), 
                         key=lambda x: sum(sum(v) for v in dow_stats[x].values()), 
                         reverse=True)[:20]
    
    for urun in top_products:
        forecast_items = []
        total_7d = 0
        for i in range(1, 8):
            target_date = today + timedelta(days=i)
            target_dow = target_date.weekday() + 1 # Monday=1 in Py, but 0=Sunday in PG
            if target_dow == 7: target_dow = 0 # Adjust to PG DOW
            
            history = dow_stats[urun][target_dow]
            if history:
                avg = sum(history) / len(history)
                # Basit bir trend çarpanı (son haftalar daha önemli)
                predicted = round(avg, 2)
            else:
                predicted = 0.0
            
            forecast_items.append({
                "date": target_date.isoformat(),
                "predicted_sales": predicted,
                "confidence": 0.8 if len(history) > 4 else 0.5
            })
            total_7d += predicted
            
        # Stok kontrolü (varsa)
        stock_status = "bilinmiyor"
        stock_row = await db.fetch_one(
            "SELECT mevcut, min FROM stok_kalemleri WHERE sube_id = :sid AND ad = :ad",
            {"sid": sube_id, "ad": urun}
        )
        if stock_row:
            current = float(stock_row["mevcut"])
            if current < total_7d: stock_status = "yetersiz"
            elif current < total_7d * 1.5: stock_status = "riskli"
            else: stock_status = "yeterli"

        predictions.append({
            "urun": urun,
            "forecast": forecast_items,
            "total_predicted_7d": round(total_7d, 2),
            "stock_status": stock_status
        })
        
    await audit_service.log_action("analytics.demand_forecast", user["username"], sube_id)
    return predictions

@router.get("/product-affinity", dependencies=[Depends(require_roles({"admin", "super_admin"}))])
async def get_product_affinity(
    days_back: int = Query(30, ge=7, le=90),
    user: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """
    Ürün Birliktelik Analizi (Sepet Analizi)
    Hangi ürünlerin birlikte satıldığını analiz eder.
    """
    start_dt = datetime.now() - timedelta(days=days_back)
    
    query = """
    SELECT sepet
    FROM siparisler
    WHERE sube_id = :sube_id AND durum = 'odendi' AND created_at >= :start_dt
    """
    rows = await db.fetch_all(query, {"sube_id": sube_id, "start_dt": start_dt})
    
    pair_counts = defaultdict(int)
    product_counts = defaultdict(int)
    total_orders = len(rows)
    
    for row in rows:
        sepet = parse_sepet(row["sepet"])
        items = sorted(list(set([str(item.get("urun") or item.get("ad")) for item in sepet if item.get("urun") or item.get("ad")])))
        
        for item in items:
            product_counts[item] += 1
            
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                pair_counts[(items[i], items[j])] += 1
                
    affinities = []
    for (p1, p2), count in pair_counts.items():
        if count < 3: continue # Minimum anlamlılık
        
        # Jaccard Similarity veya Lift benzeri bir skor
        # Support(A and B) / Support(A)
        score = count / product_counts[p1]
        
        affinities.append({
            "product_a": p1,
            "product_b": p2,
            "co_occurrence_count": count,
            "correlation_score": round(score, 2)
        })
        
    # Skora göre sırala
    affinities.sort(key=lambda x: x["correlation_score"], reverse=True)
    
    await audit_service.log_action("analytics.product_affinity", user["username"], sube_id)
    return affinities[:15]

@router.get("/menu-optimization", dependencies=[Depends(require_roles({"admin", "super_admin"}))])
async def get_menu_optimization(
    user: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """
    Akıllı Menü Optimizasyonu
    Satış hacmi ve karlılığa göre ürünleri kategorize eder ve öneriler sunar.
    """
    # 1. Ürün karlılık ve satış verilerini çek (Son 30 gün)
    # Bu veriyi analytics_advanced'deki mantığa benzer şekilde çekiyoruz
    query = """
    WITH product_stats AS (
        SELECT 
            si->>'urun' as urun,
            SUM((si->>'adet')::numeric) as adet,
            SUM((si->>'adet')::numeric * (si->>'fiyat')::numeric) as ciro
        FROM siparisler s, jsonb_array_elements(s.sepet) si
        WHERE s.sube_id = :sid AND s.durum = 'odendi' AND s.created_at >= NOW() - INTERVAL '30 days'
        GROUP BY 1
    ),
    product_costs AS (
        SELECT 
            r.urun,
            SUM(r.miktar * sk.alis_fiyat) as birim_maliyet
        FROM receteler r
        JOIN stok_kalemleri sk ON r.stok = sk.ad AND r.sube_id = sk.sube_id
        WHERE r.sube_id = :sid
        GROUP BY 1
    )
    SELECT 
        ps.urun,
        m.kategori,
        ps.adet,
        ps.ciro,
        COALESCE(pc.birim_maliyet, 0) as maliyet
    FROM product_stats ps
    LEFT JOIN menu m ON ps.urun = m.ad AND m.sube_id = :sid
    LEFT JOIN product_costs pc ON ps.urun = pc.urun
    """
    rows = await db.fetch_all(query, {"sid": sube_id})
    
    if not rows:
        return []
        
    # Ortalamaları hesapla
    avg_sales = sum(float(r["adet"]) for r in rows) / len(rows)
    
    suggestions = []
    for r in rows:
        adet = float(r["adet"])
        ciro = float(r["ciro"])
        maliyet = float(r["maliyet"])
        fiyat = ciro / adet if adet > 0 else 0
        kar_marji = (fiyat - maliyet) / fiyat if fiyat > 0 else 0
        
        tip = ""
        oneri = ""
        
        if adet >= avg_sales and kar_marji >= 0.4:
            tip = "hero"
            oneri = "Yüksek kar ve yüksek satış. Menüde öne çıkarılmalı, kampanya odağı olmalı."
        elif adet < avg_sales and kar_marji >= 0.5:
            tip = "sleeping"
            oneri = "Karı yüksek ama az satıyor. Tanıtım veya yan ürün olarak öneri (upsell) yapılmalı."
        elif adet >= avg_sales and kar_marji < 0.2:
            tip = "underperformer"
            oneri = "Çok satıyor ama karı düşük. Reçete maliyeti düşürülmeli veya fiyat güncellenmeli."
        else:
            tip = "normal"
            oneri = "Performansı stabil. Mevcut durum korunabilir."
            
        suggestions.append({
            "urun": r["urun"],
            "kategori": r["kategori"] or "Genel",
            "tip": tip,
            "oneri": oneri,
            "metrikler": {
                "adet": adet,
                "kar_marji": round(kar_marji * 100, 1),
                "birim_kar": round(fiyat - maliyet, 2)
            }
        })
        
    await audit_service.log_action("analytics.menu_optimization", user["username"], sube_id)
    return suggestions
