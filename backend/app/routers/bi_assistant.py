# backend/app/routers/bi_assistant.py
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Tuple, Callable, Awaitable
from datetime import datetime, timedelta
from collections import defaultdict
import ast
import json
import logging
import operator
import re

from ..core.deps import get_current_user, get_sube_id, require_roles
from ..db.database import db
from ..llm import get_llm_provider
from ..llm.bi_intelligence import generate_smart_response, QueryIntent

router = APIRouter(prefix="/bi-assistant", tags=["BI Assistant"])

class BIQueryRequest(BaseModel):
    text: str = Field(min_length=1)
    sube_id: Optional[int] = None  # Allow explicit sube_id for super_admin

class BIQueryResponse(BaseModel):
    reply: str
    data: Optional[Dict[str, Any]] = None
    suggestions: Optional[List[str]] = None


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


async def get_revenue_data(sube_id: int, days: int = 30) -> Dict[str, Any]:
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    rows = await db.fetch_all(
        """
        SELECT 
            COALESCE(SUM(tutar), 0)::float AS total_revenue,
            COUNT(*)::int AS total_orders
        FROM siparisler
        WHERE sube_id = :sid AND durum = 'odendi' AND created_at BETWEEN :start AND :end;
        """,
        {"sid": sube_id, "start": start_date, "end": end_date}
    )
    
    daily_revenue_rows = await db.fetch_all(
        """
        SELECT 
            DATE(created_at) AS date,
            COALESCE(SUM(tutar), 0)::float AS daily_revenue
        FROM siparisler
        WHERE sube_id = :sid AND durum = 'odendi' AND created_at BETWEEN :start AND :end
        GROUP BY DATE(created_at)
        ORDER BY date;
        """,
        {"sid": sube_id, "start": start_date, "end": end_date}
    )
    
    return {
        "total_revenue": rows[0]["total_revenue"] if rows else 0.0,
        "total_orders": rows[0]["total_orders"] if rows else 0,
        "daily_revenue_trend": [{"date": r["date"].isoformat(), "revenue": r["daily_revenue"]} for r in daily_revenue_rows]
    }


async def get_expense_data(sube_id: int, days: int = 30) -> Dict[str, Any]:
    """
    Gider verilerini gerçek veritabanından al.
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Kategori bazında toplam giderler
        category_rows = await db.fetch_all(
            """
            SELECT 
                kategori,
                COALESCE(SUM(tutar), 0)::float AS amount
            FROM giderler
            WHERE sube_id = :sid AND tarih BETWEEN :start AND :end
            GROUP BY kategori
            ORDER BY amount DESC;
            """,
            {"sid": sube_id, "start": start_date.date(), "end": end_date.date()}
        )
        
        expense_breakdown = [
            {"category": row["kategori"], "amount": row["amount"]}
            for row in category_rows
        ]
        
        total_expenses = sum(e["amount"] for e in expense_breakdown)
        
        # Eğer gider yoksa mock data dön (backward compatibility)
        if total_expenses == 0:
            return {
                "total_expenses": 0.0,
                "expense_breakdown": [],
                "days": days
            }
        
        return {
            "total_expenses": total_expenses,
            "expense_breakdown": expense_breakdown,
            "days": days
        }
    except Exception as e:
        logging.warning(f"Expense query error: {e}")
        # Hata durumunda boş veri dön
        return {
            "total_expenses": 0.0,
            "expense_breakdown": [],
            "days": days
        }


async def get_inventory_status(sube_id: int) -> List[Dict[str, Any]]:
    try:
        rows = await db.fetch_all(
            """
            SELECT ad, mevcut, min, birim
            FROM stok_kalemleri
            WHERE sube_id = :sid AND mevcut <= min;
            """,
            {"sid": sube_id}
        )
        
        # Son 30 günlük satış verilerinden tüketim hesapla
        sales_rows = await db.fetch_all(
            """
            SELECT sepet, created_at
            FROM siparisler
            WHERE sube_id = :sid AND durum = 'odendi' 
            AND created_at >= NOW() - INTERVAL '30 days';
            """,
            {"sid": sube_id}
        )
        
        # Reçetelerden malzeme tüketimini hesapla
        daily_consumption: Dict[str, float] = defaultdict(float)
        for row in sales_rows:
            sepet = parse_sepet(row["sepet"])
            for item in sepet:
                urun_adi = str(item.get("urun") or item.get("ad") or "").strip()
                if urun_adi:
                    # Bu ürünün reçetesini getir
                    recete_rows = await db.fetch_all(
                        """
                        SELECT stok, miktar
                        FROM receteler
                        WHERE urun = :urun;
                        """,
                        {"urun": urun_adi}
                    )
                    adet = float(item.get("adet") or 1)
                    for rec in recete_rows:
                        stok_adi = str(rec["stok"]).strip()
                        miktar = float(rec["miktar"] or 0)
                        daily_consumption[stok_adi] += miktar * adet
        
        # 30 güne böl
        avg_daily = {k: v / 30.0 for k, v in daily_consumption.items()}
        
        # Her stok için kalan gün hesapla
        result = []
        for row in rows:
            stock_name = str(row["ad"])
            current = float(row["mevcut"])
            minimum = float(row["min"])
            unit = str(row["birim"])
            
            daily_usage = avg_daily.get(stock_name, 0)
            
            # Kalan gün hesapla
            days_remaining = None
            if daily_usage > 0:
                days_remaining = current / daily_usage
            elif current > 0:
                # Tüketim verisi yoksa "çok" göster
                days_remaining = 999
            
            item = dict(row)
            item["gunluk_tuketim"] = round(daily_usage, 2)
            item["kalan_gun"] = round(days_remaining, 1) if days_remaining else None
            item["onem"] = "KRİTİK" if current <= minimum else "DİKKAT"
            result.append(item)
        
        return result
    except Exception as e:
        logging.warning(f"Inventory query error: {e}")
        return []


async def get_personnel_performance(sube_id: int, days: int = 30) -> List[Dict[str, Any]]:
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    try:
        rows = await db.fetch_all(
            """
            SELECT 
                u.username,
                u.role,
                COUNT(s.id)::int AS siparis_adedi,
                COALESCE(SUM(s.tutar), 0)::float AS toplam_ciro
            FROM users u
            JOIN siparisler s ON u.id = s.created_by_user_id
            WHERE s.sube_id = :sid AND s.created_at BETWEEN :start AND :end AND s.durum = 'odendi'
            GROUP BY u.username, u.role
            ORDER BY toplam_ciro DESC;
            """,
            {"sid": sube_id, "start": start_date, "end": end_date}
        )
        return [dict(r) for r in rows]
    except Exception as e:
        logging.warning(f"Personnel query error: {e}")
        return []


async def get_top_products(sube_id: int, days: int = 30) -> List[Dict[str, Any]]:
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    try:
        popular_rows = await db.fetch_all(
            """
            SELECT sepet
            FROM siparisler
            WHERE sube_id = :sid AND durum = 'odendi' AND created_at BETWEEN :start AND :end;
            """,
            {"sid": sube_id, "start": start_date, "end": end_date}
        )
        
        product_counts: Dict[str, float] = defaultdict(float)
        for row in popular_rows:
            sepet = parse_sepet(row["sepet"])
            for item in sepet:
                urun_adi = str(item.get("urun") or item.get("ad") or "").strip()
                if urun_adi:
                    product_counts[urun_adi] += float(item.get("adet") or 1) * float(item.get("fiyat") or 0)
        
        sorted_products = sorted(product_counts.items(), key=lambda x: x[1], reverse=True)
        return [{"urun_adi": k, "toplam_tutar": v} for k, v in sorted_products[:10]]
    except Exception as e:
        logging.warning(f"Top products query error: {e}")
        return []


async def get_category_sales(sube_id: int, days: int = 30) -> List[Dict[str, Any]]:
    """
    Satışları kategori bazında özetle.
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    try:
        menu_rows = await db.fetch_all(
            """
            SELECT ad, kategori
            FROM menu
            WHERE sube_id = :sid
            """,
            {"sid": sube_id}
        )
        name_to_category: Dict[str, str] = {}
        for row in menu_rows:
            name = str(row["ad"] or "").strip().lower()
            if name:
                name_to_category[name] = row.get("kategori") or "Kategori Belirtilmemiş"

        sales_rows = await db.fetch_all(
            """
            SELECT sepet
            FROM siparisler
            WHERE sube_id = :sid
              AND durum = 'odendi'
              AND created_at BETWEEN :start AND :end;
            """,
            {"sid": sube_id, "start": start_date, "end": end_date}
        )

        category_totals: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"ciro": 0.0, "adet": 0})
        for row in sales_rows:
            sepet = parse_sepet(row["sepet"])
            for item in sepet:
                urun_adi = str(item.get("urun") or item.get("ad") or "").strip()
                if not urun_adi:
                    continue
                kategorize_name = urun_adi.lower()
                category = name_to_category.get(kategorize_name, "Kategori Belirtilmemiş")
                adet = float(item.get("adet") or 1)
                fiyat = float(item.get("fiyat") or 0)
                category_totals[category]["ciro"] += fiyat * adet
                category_totals[category]["adet"] += adet

        # Toplam ciro
        total_revenue = sum(info["ciro"] for info in category_totals.values())
        results = []
        for category, info in category_totals.items():
            pay = (info["ciro"] / total_revenue * 100) if total_revenue > 0 else 0
            results.append({
                "kategori": category,
                "ciro": round(info["ciro"], 2),
                "adet": round(info["adet"], 2),
                "pay": round(pay, 1),
            })

        results.sort(key=lambda x: x["ciro"], reverse=True)
        return results
    except Exception as e:
        logging.warning(f"Category sales query error: {e}")
        return []


async def get_shopping_suggestions(sube_id: int) -> Dict[str, Any]:
    """Alışveriş önerileri: düşük stoklar + ortalama tüketim"""
    try:
        # Kritik stoklar
        critical_stocks = await db.fetch_all(
            """
            SELECT ad, mevcut, min, birim
            FROM stok_kalemleri
            WHERE sube_id = :sid AND mevcut <= min * 1.5
            ORDER BY mevcut / NULLIF(min, 0);
            """,
            {"sid": sube_id}
        )
        
        # Son 30 günlük satış verilerinden tüketim hesapla
        sales_rows = await db.fetch_all(
            """
            SELECT sepet, DATE(created_at) as tarih
            FROM siparisler
            WHERE sube_id = :sid AND durum = 'odendi' 
            AND created_at >= NOW() - INTERVAL '30 days'
            ORDER BY tarih DESC;
            """,
            {"sid": sube_id}
        )
        
        # Reçetelerden malzeme tüketimini hesapla
        daily_consumption: Dict[str, float] = defaultdict(float)
        for row in sales_rows:
            sepet = parse_sepet(row["sepet"])
            for item in sepet:
                urun_adi = str(item.get("urun") or item.get("ad") or "").strip()
                if urun_adi:
                    # Bu ürünün reçetesini getir
                    recete_rows = await db.fetch_all(
                        """
                        SELECT stok, miktar, birim
                        FROM receteler
                        WHERE urun = :urun;
                        """,
                        {"urun": urun_adi}
                    )
                    adet = float(item.get("adet") or 1)
                    for rec in recete_rows:
                        stok_adi = str(rec["stok"]).strip()
                        miktar = float(rec["miktar"] or 0)
                        daily_consumption[stok_adi] += miktar * adet
        
        # 30 güne böl
        avg_daily = {k: v / 30.0 for k, v in daily_consumption.items()}
        
        # Kritik stoklar için önerilen miktar hesapla (7 günlük tüketim)
        suggestions = []
        for stock in critical_stocks:
            stock_name = str(stock["ad"])
            current = float(stock["mevcut"])
            minimum = float(stock["min"])
            unit = str(stock["birim"])
            
            daily_usage = avg_daily.get(stock_name, 0)
            recommended_qty = max(0, (minimum * 2) - current) if daily_usage == 0 else max(0, (daily_usage * 7) - current)
            
            suggestions.append({
                "stok_adi": stock_name,
                "mevcut": current,
                "min": minimum,
                "birim": unit,
                "onem": "YÜKSEK" if current <= minimum else "ORTA",
                "oneri_miktar": round(recommended_qty, 2)
            })
        
        return {"kritik_stoklar": suggestions, "ortalama_gunluk_tuketim": avg_daily}
    except Exception as e:
        logging.warning(f"Shopping suggestions error: {e}")
        return {"kritik_stoklar": [], "ortalama_gunluk_tuketim": {}}


async def get_profit_margin_analysis(sube_id: int) -> Dict[str, Any]:
    """Kar marjı analizi: satış fiyatı vs alış fiyatı + reçete"""
    try:
        # Menü ürünleri ve fiyatları
        menu_items = await db.fetch_all(
            """
            SELECT ad, fiyat, kategori
            FROM menu
            WHERE sube_id = :sid AND aktif = TRUE;
            """,
            {"sid": sube_id}
        )
        
        # Son 30 günlük satışlar
        sales_rows = await db.fetch_all(
            """
            SELECT sepet, tutar
            FROM siparisler
            WHERE sube_id = :sid AND durum = 'odendi' 
            AND created_at >= NOW() - INTERVAL '30 days';
            """,
            {"sid": sube_id}
        )
        
        product_analysis = []
        for menu_item in menu_items:
            urun_adi = str(menu_item["ad"])
            satis_fiyati = float(menu_item["fiyat"])
            
            # Bu ürünün reçetesini getir
            recete_rows = await db.fetch_all(
                """
                SELECT stok, miktar, birim
                FROM receteler
                WHERE urun = :urun;
                """,
                {"urun": urun_adi}
            )
            
            # Reçete toplam maliyeti hesapla
            toplam_maliyet = 0.0
            for rec in recete_rows:
                stok_adi = str(rec["stok"])
                miktar = float(rec["miktar"] or 0)
                
                # Stok kaleminden alış fiyatını al
                stok_row = await db.fetch_one(
                    """
                    SELECT alis_fiyat, birim
                    FROM stok_kalemleri
                    WHERE sube_id = :sid AND ad = :ad
                    LIMIT 1;
                    """,
                    {"sid": sube_id, "ad": stok_adi}
                )
                
                if stok_row:
                    stok_data = dict(stok_row)
                    alis_fiyat = float(stok_data.get("alis_fiyat") or 0)
                    toplam_maliyet += miktar * alis_fiyat
            
            # Satış sayısı
            satis_sayisi = 0
            for row in sales_rows:
                sepet = parse_sepet(row["sepet"])
                for item in sepet:
                    if str(item.get("urun") or item.get("ad") or "").strip() == urun_adi:
                        satis_sayisi += int(item.get("adet") or 1)
            
            # Kar marjı hesapla
            kar = satis_fiyati - toplam_maliyet
            kar_yuzdesi = (kar / satis_fiyati * 100) if satis_fiyati > 0 else 0
            
            product_analysis.append({
                "urun": urun_adi,
                "satis_fiyati": satis_fiyati,
                "toplam_maliyet": round(toplam_maliyet, 2),
                "kar": round(kar, 2),
                "kar_marji_yuzde": round(kar_yuzdesi, 1),
                "satis_sayisi_30gun": satis_sayisi,
                "toplam_kar_30gun": round(kar * satis_sayisi, 2),
                "durum": "İYİ" if kar_yuzdesi >= 50 else "ORTA" if kar_yuzdesi >= 30 else "DÜŞÜK"
            })
        
        # En düşük kar marjlı ürünler
        low_margin = sorted([p for p in product_analysis if p["kar_marji_yuzde"] < 30], 
                           key=lambda x: x["kar_marji_yuzde"])
        high_profit = sorted(product_analysis, key=lambda x: x["toplam_kar_30gun"], reverse=True)
        
        return {
            "urun_analizleri": product_analysis,
            "dusuk_karli": low_margin[:5],
            "en_cok_kazandiran": high_profit[:5]
        }
    except Exception as e:
        logging.warning(f"Profit margin analysis error: {e}")
        return {"urun_analizleri": [], "dusuk_karli": [], "en_cok_kazandiran": []}


async def get_stock_costs(sube_id: int) -> List[Dict[str, Any]]:
    """Tüm stok kalemlerinin maliyet bilgileri"""
    try:
        rows = await db.fetch_all(
            """
            SELECT ad, kategori, birim, mevcut, min, alis_fiyat
            FROM stok_kalemleri
            WHERE sube_id = :sid
            ORDER BY kategori, ad;
            """,
            {"sid": sube_id}
        )
        return [
            {
                "stok_adi": r["ad"],
                "kategori": r["kategori"] or "",
                "birim": r["birim"] or "",
                "mevcut": float(r["mevcut"]),
                "min": float(r["min"]),
                "maliyet": float(r["alis_fiyat"] or 0),
                "toplam_deger": float(r["mevcut"] or 0) * float(r["alis_fiyat"] or 0)
            }
            for r in rows
        ]
    except Exception as e:
        logging.warning(f"Stock costs query error: {e}")
        return []


async def get_menu_items(sube_id: int) -> List[Dict[str, Any]]:
    """Menü ürünleri ve fiyatları"""
    try:
        rows = await db.fetch_all(
            """
            SELECT ad, kategori, fiyat, aktif
            FROM menu
            WHERE sube_id = :sid
            ORDER BY kategori, ad;
            """,
            {"sid": sube_id}
        )
        return [
            {
                "urun": r["ad"],
                "kategori": r["kategori"] or "",
                "fiyat": float(r["fiyat"] or 0),
                "durum": "Aktif" if r["aktif"] else "Pasif"
            }
            for r in rows
        ]
    except Exception as e:
        logging.warning(f"Menu query error: {e}")
        return []


async def get_recipes(sube_id: int) -> List[Dict[str, Any]]:
    """Reçeteler ve malzemeleri"""
    try:
        rows = await db.fetch_all(
            """
            SELECT urun, stok, miktar, birim
            FROM receteler
            WHERE sube_id = :sid
            ORDER BY urun, stok;
            """,
            {"sid": sube_id}
        )
        # Ürüne göre grupla
        by_product = defaultdict(list)
        for r in rows:
            by_product[r["urun"]].append({
                "stok": r["stok"],
                "miktar": float(r["miktar"] or 0),
                "birim": r["birim"] or ""
            })
        
        return [
            {"urun": product, "malzemeler": materials}
            for product, materials in sorted(by_product.items())
        ]
    except Exception as e:
        logging.warning(f"Recipes query error: {e}")
        return []


async def get_personnel_list(sube_id: int) -> List[Dict[str, Any]]:
    """Tüm personel listesi"""
    try:
        rows = await db.fetch_all(
            """
            SELECT 
                u.username,
                u.role,
                u.aktif,
                ARRAY_REMOVE(ARRAY_AGG(DISTINCT usi.sube_id), NULL) AS sube_list
            FROM users u
            LEFT JOIN user_sube_izinleri usi ON usi.username = u.username
            WHERE u.role != 'customer'
              AND (
                  usi.sube_id = :sid
                  OR u.role IN ('super_admin', 'admin')
                  OR usi.sube_id IS NULL
              )
            GROUP BY u.username, u.role, u.aktif
            ORDER BY u.role, u.username;
            """,
            {"sid": sube_id}
        )
        return [
            {
                "username": r["username"],
                "rol": r["role"],
                "durum": "Aktif" if r["aktif"] else "Pasif",
                "subeler": [sid for sid in (r["sube_list"] or [])],
            }
            for r in rows
        ]
    except Exception as e:
        logging.warning(f"Personnel list query error: {e}")
        return []


async def get_recent_orders(sube_id: int, days: int = 7) -> Dict[str, Any]:
    """Son siparişler özeti"""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        rows = await db.fetch_all(
            """
            SELECT 
                COUNT(*)::int AS toplam_siparis,
                COALESCE(SUM(tutar), 0)::float AS toplam_tutar,
                COUNT(DISTINCT masa)::int AS kullanilan_masa,
                AVG(tutar)::float AS ortalama_sepet
            FROM siparisler
            WHERE sube_id = :sid AND durum = 'odendi' 
            AND created_at BETWEEN :start AND :end;
            """,
            {"sid": sube_id, "start": start_date, "end": end_date}
        )
        
        return rows[0] if rows else {
            "toplam_siparis": 0,
            "toplam_tutar": 0.0,
            "kullanilan_masa": 0,
            "ortalama_sepet": 0.0
        }
    except Exception as e:
        logging.warning(f"Recent orders query error: {e}")
        return {
            "toplam_siparis": 0,
            "toplam_tutar": 0.0,
            "kullanilan_masa": 0,
            "ortalama_sepet": 0.0
        }


ALLOWED_AST_NODES = {
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Num,
    ast.Constant,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.Mod,
    ast.FloorDiv,
    ast.USub,
    ast.UAdd,
    ast.Call,
}


def _is_safe_math_expr(node: ast.AST) -> bool:
    if type(node) not in ALLOWED_AST_NODES:
        return False
    if isinstance(node, ast.Expression):
        return _is_safe_math_expr(node.body)
    if isinstance(node, ast.BinOp):
        return _is_safe_math_expr(node.left) and _is_safe_math_expr(node.right) and _is_safe_math_expr(node.op)
    if isinstance(node, ast.UnaryOp):
        return _is_safe_math_expr(node.operand) and _is_safe_math_expr(node.op)
    if isinstance(node, (ast.Num, ast.Constant)):
        return True
    if isinstance(node, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.FloorDiv, ast.UAdd, ast.USub)):
        return True
    if isinstance(node, ast.Call):
        return False
    return False


def _evaluate_math_expression(expr: str) -> Optional[float]:
    try:
        tree = ast.parse(expr, mode="eval")
    except Exception:
        return None
    if not _is_safe_math_expr(tree):
        return None
    try:
        return eval(compile(tree, filename="<math>", mode="eval"), {"__builtins__": {}})
    except Exception:
        return None


TIME_KEYWORD_MAP = [
    ("daily", 1, ["bugün", "bugun", "bu gün", "günlük", "gunluk", "today", "bugunki", "günün"]),
    ("weekly", 7, ["hafta", "haftalık", "haftalik", "weekly", "son yedi gün", "son 7 gün", "geçen hafta", "gecen hafta"]),
    ("monthly", 30, ["ay", "aylık", "aylik", "monthly", "bu ay", "geçen ay", "gecen ay", "30 gün", "30 gun"]),
]


def detect_time_window(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    lowered = text.lower()

    # Önce "son X gün" kalıbını yakala
    range_match = re.search(r"(son|geçen|gecen)\s+(\d+)\s*g[uü]n", lowered)
    if range_match:
        days = int(range_match.group(2))
        if days <= 0:
            return None
        label = "weekly" if days == 7 else "monthly" if days == 30 else "custom"
        return {"label": label, "days": days, "raw": range_match.group(0)}

    for label, default_days, keywords in TIME_KEYWORD_MAP:
        for keyword in keywords:
            if keyword in lowered:
                # "hafta" içeren ama "haftasonu" değil
                if keyword.strip() == "hafta" and "haftasonu" in lowered:
                    continue
                # "ay" içeren ama "ayran" değil
                if keyword.strip() == "ay" and "ayran" in lowered:
                    continue
                return {"label": label, "days": default_days, "raw": keyword}
    return None


def format_time_window_label(window: Optional[Dict[str, Any]]) -> str:
    if not window:
        return "Son 30 gün"
    label = window.get("label")
    days = window.get("days")
    if label == "daily":
        return "Bugün"
    if label == "weekly":
        return "Son 7 gün"
    if label == "monthly":
        return "Son 30 gün"
    if label == "custom" and days:
        return f"Son {days} gün"
    if days:
        return f"Son {days} gün"
    return "Son 30 gün"


def llm_headlines_for_window(window: Optional[Dict[str, Any]]) -> Tuple[str, str, str]:
    if not window:
        return ("🎯 İşletme Nabzı", "📊 Öne Çıkanlar", "🚀 Önerilen Adımlar")
    label = window.get("label")
    if label == "daily":
        return ("🎯 Günlük Nabız", "📊 Öne Çıkanlar", "🚀 Bugünün Aksiyonları")
    if label == "weekly":
        return ("🎯 Haftalık Nabız", "📊 Öne Çıkanlar", "🚀 Hemen Yapılacaklar")
    if label == "monthly":
        return ("🎯 Aylık Nabız", "📊 Öne Çıkanlar", "🚀 Stratejik Adımlar")
    days = window.get("days")
    if days and days < 7:
        return ("🎯 Günlük Nabız", "📊 Öne Çıkanlar", "🚀 Bugünün Aksiyonları")
    if days and days >= 7 and days < 21:
        return ("🎯 Haftalık Nabız", "📊 Öne Çıkanlar", "🚀 Hemen Yapılacaklar")
    return ("🎯 İşletme Nabzı", "📊 Öne Çıkanlar", "🚀 Önerilen Adımlar")


@router.post("/query", response_model=BIQueryResponse, dependencies=[Depends(require_roles({"admin", "super_admin"}))])
async def bi_query(
    payload: BIQueryRequest,
    user: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """
    BI Assistant'a genel bir sorgu göndermek için kullanılır.
    """
    response_data = {}
    reply_text = "İşletme verilerinizle ilgili size nasıl yardımcı olabilirim?"
    suggestions = [
        "Bugünkü ciromuz ne kadar?",
        "Bu ayki toplam ciromuz ne kadar?",
        "Hangi ürünlerin stoğu kritik seviyede?",
        "Kar marjı analizini göster.",
        "Alışveriş önerileri ver.",
        "Geçen hafta en çok satan ürünler nelerdi?",
        "Bugün personel performansları nasıl?"
    ]

    if user.get("role") == "super_admin" and payload.sube_id is not None:
        target_sube_id = payload.sube_id
    else:
        target_sube_id = sube_id

    greeting_phrases = {
        "merhaba",
        "merhaba neso",
        "selam",
        "selam neso",
        "hey",
        "hello",
        "hi",
        "günaydın",
        "gunaydin",
        "iyi günler",
        "iyi gunler",
        "iyi akşamlar",
        "iyi aksamlar",
        "nasılsın",
        "nasilsin",
    }
    greeting_tokens = {
        "merhaba",
        "selam",
        "neso",
        "hey",
        "hello",
        "hi",
        "günaydın",
        "gunaydin",
        "iyi",
        "günler",
        "gunler",
        "akşamlar",
        "aksamlar",
        "nasılsın",
        "nasilsin",
    }

    raw_text = (payload.text or "").strip()
    normalized_text = raw_text.lower()

    if not raw_text:
        return BIQueryResponse(reply=reply_text, data=None, suggestions=suggestions[:4])

    if normalized_text in greeting_phrases:
        return BIQueryResponse(
            reply="Merhaba! Hazırım. Örneğin bugünkü ciroyu, kritik stokları veya son haftanın satış trendini sorabilirsiniz.",
            suggestions=suggestions[:4],
            data=None,
        )

    tokens = [tok for tok in normalized_text.replace("?", "").replace("!", "").split() if tok]
    if tokens and all(tok in greeting_tokens for tok in tokens):
        return BIQueryResponse(
            reply="Selam! İşletme performansını konuşalım mı? Ciro, stok ya da personel performansı gibi başlıklardan birini seçebilirsiniz.",
            suggestions=suggestions[:4],
            data=None,
        )

    data_cache: Dict[str, Any] = {}

    async def load_data(key: str, loader: Callable[[], Awaitable[Any]]):
        if key not in data_cache:
            data_cache[key] = await loader()
        return data_cache[key]

    math_candidate = re.sub(r"[^0-9\.\+\-\*/\(\)\s]", "", normalized_text)
    if math_candidate and any(op in math_candidate for op in "+-*/"):
        result = _evaluate_math_expression(math_candidate.strip())
        if result is not None:
            return BIQueryResponse(
                reply=str(result),
                data={"result": result},
                suggestions=suggestions[:3],
            )

    text = normalized_text
    time_window = detect_time_window(text)
    window_label = time_window["label"] if time_window else None
    window_days = time_window["days"] if time_window else None

    try:
        # Basit anahtar kelime eşleşmeleri ile sorgu yönlendirme
        if "ciro" in text or "gelir" in text or "kazanç" in text or "revenue" in text or "kar" in text:
            def build_revenue_reply(period_label: str, rev: Dict[str, Any], exp: Dict[str, Any]) -> str:
                net_kar_local = rev['total_revenue'] - exp['total_expenses']
                kar_yuzdesi_local = (net_kar_local / rev['total_revenue'] * 100) if rev['total_revenue'] > 0 else 0
                return (
                    f"💰 {period_label} cironuz: {rev['total_revenue']:.2f} ₺ ({rev['total_orders']} sipariş).\n"
                    f"Giderler: {exp['total_expenses']:.2f} ₺\n"
                    f"✅ Net Kar: {net_kar_local:.2f} ₺ (%{kar_yuzdesi_local:.1f})"
                )

            handled = False
            if window_label in {"daily"}:
                handled = True
                period_text = format_time_window_label(time_window)
                revenue_daily = await load_data("revenue_1", lambda: get_revenue_data(target_sube_id, days=1))
                expense_daily = await load_data("expense_1", lambda: get_expense_data(target_sube_id, days=1))
                reply_text = build_revenue_reply(period_text, revenue_daily, expense_daily)
                response_data["revenue"] = revenue_daily
                response_data["expenses"] = expense_daily
            elif window_label == "weekly":
                handled = True
                days = window_days or 7
                revenue_weekly = await load_data(f"revenue_{days}", lambda d=days: get_revenue_data(target_sube_id, days=d))
                expense_weekly = await load_data(f"expense_{days}", lambda d=days: get_expense_data(target_sube_id, days=d))
                label_text = format_time_window_label({"label": "weekly" if days == 7 else "custom", "days": days})
                reply_text = build_revenue_reply(label_text, revenue_weekly, expense_weekly)
                response_data["revenue"] = revenue_weekly
                response_data["expenses"] = expense_weekly
            elif window_label == "monthly":
                handled = True
                period_text = format_time_window_label(time_window)
                revenue_info = await load_data("revenue_30", lambda: get_revenue_data(target_sube_id))
                expense_info = await load_data("expense_30", lambda: get_expense_data(target_sube_id))
                reply_text = build_revenue_reply(period_text, revenue_info, expense_info)
                response_data["revenue"] = revenue_info
                response_data["expenses"] = expense_info
            elif window_label == "custom" and window_days:
                handled = True
                revenue_custom = await load_data(f"revenue_{window_days}", lambda d=window_days: get_revenue_data(target_sube_id, days=d))
                expense_custom = await load_data(f"expense_{window_days}", lambda d=window_days: get_expense_data(target_sube_id, days=d))
                label_text = format_time_window_label(time_window)
                reply_text = build_revenue_reply(label_text, revenue_custom, expense_custom)
                response_data["revenue"] = revenue_custom
                response_data["expenses"] = expense_custom

            if not handled:
                if "bugün" in text or "günlük" in text or "dün" in text or ("gün" in text and "hafta" not in text and "ay" not in text):
                    revenue_daily = await load_data("revenue_1", lambda: get_revenue_data(target_sube_id, days=1))
                    expense_daily = await load_data("expense_1", lambda: get_expense_data(target_sube_id, days=1))
                    reply_text = build_revenue_reply("Bugünkü", revenue_daily, expense_daily)
                    response_data["revenue"] = revenue_daily
                    response_data["expenses"] = expense_daily
                elif "hafta" in text or "geçen hafta" in text or "son hafta" in text:
                    days = 7
                    revenue_weekly = await load_data("revenue_7", lambda: get_revenue_data(target_sube_id, days=7))
                    expense_weekly = await load_data("expense_7", lambda: get_expense_data(target_sube_id, days=7))
                    reply_text = build_revenue_reply("Son 7 gündeki", revenue_weekly, expense_weekly)
                    response_data["revenue"] = revenue_weekly
                    response_data["expenses"] = expense_weekly
                elif "ay" in text or "bu ay" in text or "geçen ay" in text or "30" in text:
                    revenue_info = await load_data("revenue_30", lambda: get_revenue_data(target_sube_id))
                    expense_info = await load_data("expense_30", lambda: get_expense_data(target_sube_id))
                    reply_text = build_revenue_reply("Son 30 gündeki", revenue_info, expense_info)
                    response_data["revenue"] = revenue_info
                    response_data["expenses"] = expense_info
                else:
                    revenue_info = await load_data("revenue_30", lambda: get_revenue_data(target_sube_id))
                    expense_info = await load_data("expense_30", lambda: get_expense_data(target_sube_id))
                    reply_text = build_revenue_reply("Son 30 gündeki", revenue_info, expense_info)
                    response_data["revenue"] = revenue_info
                    response_data["expenses"] = expense_info
        elif ("gider" in text or "maliyet" in text or "harcama" in text or "expense" in text) and "stok" not in text:
            handled = False
            if window_label in {"daily"}:
                handled = True
                expense_daily = await load_data("expense_1", lambda: get_expense_data(target_sube_id, days=1))
                reply_text = f"💸 {format_time_window_label(time_window)} giderleriniz: {expense_daily['total_expenses']:.2f} ₺\n"
                for e in expense_daily['expense_breakdown']:
                    reply_text += f"• {e['category']}: {e['amount']:.2f} ₺\n"
                response_data["expenses"] = expense_daily
            elif window_label == "weekly":
                handled = True
                days = window_days or 7
                expense_weekly = await load_data(f"expense_{days}", lambda d=days: get_expense_data(target_sube_id, days=d))
                reply_text = f"💸 {format_time_window_label({'label': 'weekly' if days == 7 else 'custom', 'days': days})} giderleriniz: {expense_weekly['total_expenses']:.2f} ₺\n"
                for e in expense_weekly['expense_breakdown']:
                    reply_text += f"• {e['category']}: {e['amount']:.2f} ₺\n"
                response_data["expenses"] = expense_weekly
            elif window_label == "monthly":
                handled = True
                expense_info = await load_data("expense_30", lambda: get_expense_data(target_sube_id))
                reply_text = f"💸 {format_time_window_label(time_window)} giderleriniz: {expense_info['total_expenses']:.2f} ₺\n"
                for e in expense_info['expense_breakdown']:
                    reply_text += f"• {e['category']}: {e['amount']:.2f} ₺\n"
                response_data["expenses"] = expense_info
            elif window_label == "custom" and window_days:
                handled = True
                expense_custom = await load_data(f"expense_{window_days}", lambda d=window_days: get_expense_data(target_sube_id, days=d))
                reply_text = f"💸 {format_time_window_label(time_window)} giderleriniz: {expense_custom['total_expenses']:.2f} ₺\n"
                for e in expense_custom['expense_breakdown']:
                    reply_text += f"• {e['category']}: {e['amount']:.2f} ₺\n"
                response_data["expenses"] = expense_custom

            if not handled:
                if "bugün" in text or "günlük" in text or "dün" in text or ("gün" in text and "hafta" not in text and "ay" not in text):
                    expense_daily = await load_data("expense_1", lambda: get_expense_data(target_sube_id, days=1))
                    reply_text = f"💸 Bugünkü giderleriniz: {expense_daily['total_expenses']:.2f} ₺\n"
                    for e in expense_daily['expense_breakdown']:
                        reply_text += f"• {e['category']}: {e['amount']:.2f} ₺\n"
                    response_data["expenses"] = expense_daily
                elif "hafta" in text or "geçen hafta" in text or "son hafta" in text:
                    expense_weekly = await load_data("expense_7", lambda: get_expense_data(target_sube_id, days=7))
                    reply_text = f"💸 Son 7 gündeki toplam giderleriniz: {expense_weekly['total_expenses']:.2f} ₺\n"
                    for e in expense_weekly['expense_breakdown']:
                        reply_text += f"• {e['category']}: {e['amount']:.2f} ₺\n"
                    response_data["expenses"] = expense_weekly
                elif "ay" in text or "bu ay" in text or "geçen ay" in text or "30" in text:
                    expense_info = await load_data("expense_30", lambda: get_expense_data(target_sube_id))
                    reply_text = f"💸 Son 30 gündeki toplam giderleriniz: {expense_info['total_expenses']:.2f} ₺\n"
                    for e in expense_info['expense_breakdown']:
                        reply_text += f"• {e['category']}: {e['amount']:.2f} ₺\n"
                    response_data["expenses"] = expense_info
                else:
                    expense_info = await load_data("expense_30", lambda: get_expense_data(target_sube_id))
                    reply_text = f"💸 Toplam giderleriniz: {expense_info['total_expenses']:.2f} ₺\n"
                    for e in expense_info['expense_breakdown']:
                        reply_text += f"• {e['category']}: {e['amount']:.2f} ₺\n"
                    response_data["expenses"] = expense_info
        elif "stok maliyet" in text or "stok değer" in text or "stok değeri" in text:
            stock_costs = await load_data("stock_costs", lambda: get_stock_costs(target_sube_id))
            total_stock_value = sum(s.get('toplam_deger', 0) for s in stock_costs)
            if stock_costs:
                reply_text = f"📦 STOK MALİYET ANALİZİ:\n\n"
                reply_text += f"Toplam Değer: {total_stock_value:.2f} ₺\n"
                reply_text += f"Toplam Kalem: {len(stock_costs)} ürün\n\n"
                # Kategoriye göre grupla
                by_category = defaultdict(list)
                for s in stock_costs:
                    by_category[s['kategori']].append(s)
                for category, items in sorted(by_category.items()):
                    if category:
                        category_total = sum(s['toplam_deger'] for s in items)
                        reply_text += f"\n{category}: {category_total:.2f} ₺ ({len(items)} ürün)\n"
            else:
                reply_text = "Stok maliyet verisi bulunamadı."
            response_data["stock_costs"] = stock_costs
        elif "alışveriş" in text or "market" in text or "güncel stok" in text or "stok bilgisi" in text:
            shopping_data = await load_data("shopping", lambda: get_shopping_suggestions(target_sube_id))
            criticals = shopping_data.get('kritik_stoklar', [])
            if criticals:
                reply_text = "🛒 ALIŞVERİŞ ÖNERİLERİ:\n\n"
                for item in criticals[:10]:
                    reply_text += f"⚠️ {item['stok_adi']}: {item['mevcut']} {item['birim']} (Min: {item['min']})\n"
                    if item['oneri_miktar'] > 0:
                        reply_text += f"   → Almanız gereken: ~{item['oneri_miktar']:.1f} {item['birim']}\n"
            else:
                reply_text = "✅ Tüm stoklar yeterli seviyede görünüyor."
            response_data["shopping"] = shopping_data
        elif "stok" in text or "envanter" in text:
            inventory_info = await load_data("inventory", lambda: get_inventory_status(target_sube_id))
            if inventory_info:
                reply_text = "⚠️ KRİTİK SEVİYEDEKİ STOKLAR:\n\n"
                for item in inventory_info:
                    onem_icon = "🔴" if item.get('onem') == 'KRİTİK' else "🟠"
                    reply_text += f"{onem_icon} {item['ad']}: {item['mevcut']} {item['birim']} (Min: {item['min']} {item['birim']})"
                    
                    # Kalan gün bilgisini ekle
                    if item.get('kalan_gun') is not None:
                        if item['kalan_gun'] >= 999:
                            reply_text += " - 🔵 Tüketim verisi yok\n"
                        else:
                            kalan_gun = item['kalan_gun']
                            if kalan_gun < 1:
                                reply_text += f" - ⛔ Yetersiz! (~{kalan_gun*24:.0f} saat)\n"
                            elif kalan_gun < 3:
                                reply_text += f" - 🚨 Kritik! (~{int(kalan_gun)} gün)\n"
                            elif kalan_gun < 7:
                                reply_text += f" - ⚠️ Acil! (~{int(kalan_gun)} gün)\n"
                            else:
                                reply_text += f" - ⏱️ ~{int(kalan_gun)} gün yeterli\n"
                    else:
                        reply_text += "\n"
            else:
                reply_text = "✅ Tüm stoklar normal seviyede."
            response_data["inventory"] = inventory_info
        elif "kar" in text and ("marj" in text or "maliyet" in text or "fiyat" in text):
            profit_data = await load_data("profit", lambda: get_profit_margin_analysis(target_sube_id))
            low_margin = profit_data.get('dusuk_karli', [])
            high_profit = profit_data.get('en_cok_kazandiran', [])
            reply_text = "📊 KAR MARJI ANALİZİ:\n\n"
            if low_margin:
                reply_text += "⚠️ DÜŞÜK KARLI ÜRÜNLER:\n"
                for p in low_margin[:5]:
                    reply_text += f"- {p['urun']}: {p['kar_marji_yuzde']:.1f}% (Kar: {p['kar']:.2f} ₺)\n"
            if high_profit:
                reply_text += "\n💰 EN ÇOK KAZANDIRAN ÜRÜNLER:\n"
                for p in high_profit[:5]:
                    reply_text += f"- {p['urun']}: {p['toplam_kar_30gun']:.2f} ₺ kar ({p['kar_marji_yuzde']:.1f}%)\n"
            response_data["profit"] = profit_data
        elif "personel" in text or "çalışan" in text:
            async def fetch_personnel(days: int):
                return await load_data(f"personnel_{days}", lambda d=days: get_personnel_performance(target_sube_id, days=d))

            if "performans" in text or "ciro" in text or "satış" in text:
                handled = False
                if window_label in {"daily"}:
                    handled = True
                    personnel_daily = await fetch_personnel(1)
                    if personnel_daily:
                        reply_text = f"👥 PERSONEL PERFORMANSI ({format_time_window_label(time_window)}):\n\n"
                        for p in personnel_daily:
                            reply_text += f"- {p['username']} ({p['role']}): {p['siparis_adedi']} sipariş, {p['toplam_ciro']:.2f} ₺ ciro\n"
                    else:
                        reply_text = "Bugün personel performans verisi bulunamadı."
                    response_data["personnel"] = personnel_daily
                elif window_label == "weekly":
                    handled = True
                    days = window_days or 7
                    personnel_weekly = await fetch_personnel(days)
                    if personnel_weekly:
                        reply_text = f"👥 PERSONEL PERFORMANSI ({format_time_window_label({'label': 'weekly' if days == 7 else 'custom', 'days': days})}):\n\n"
                        for p in personnel_weekly:
                            reply_text += f"- {p['username']} ({p['role']}): {p['siparis_adedi']} sipariş, {p['toplam_ciro']:.2f} ₺ ciro\n"
                    else:
                        reply_text = "Son hafta personel performans verisi bulunamadı."
                    response_data["personnel"] = personnel_weekly
                elif window_label == "monthly":
                    handled = True
                    personnel_info = await fetch_personnel(30)
                    if personnel_info:
                        reply_text = f"👥 PERSONEL PERFORMANSI ({format_time_window_label(time_window)}):\n\n"
                        for p in personnel_info:
                            reply_text += f"- {p['username']} ({p['role']}): {p['siparis_adedi']} sipariş, {p['toplam_ciro']:.2f} ₺ ciro\n"
                    else:
                        reply_text = "Personel performans verisi bulunamadı."
                    response_data["personnel"] = personnel_info
                elif window_label == "custom" and window_days:
                    handled = True
                    personnel_custom = await fetch_personnel(window_days)
                    if personnel_custom:
                        reply_text = f"👥 PERSONEL PERFORMANSI ({format_time_window_label(time_window)}):\n\n"
                        for p in personnel_custom:
                            reply_text += f"- {p['username']} ({p['role']}): {p['siparis_adedi']} sipariş, {p['toplam_ciro']:.2f} ₺ ciro\n"
                    else:
                        reply_text = "Bu dönem için personel performans verisi bulunamadı."
                    response_data["personnel"] = personnel_custom

                if not handled:
                    if "bugün" in text or "günlük" in text or "dün" in text or "gün" in text:
                        personnel_daily = await fetch_personnel(1)
                        if personnel_daily:
                            reply_text = "👥 PERSONEL PERFORMANSI (Bugün):\n\n"
                            for p in personnel_daily:
                                reply_text += f"- {p['username']} ({p['role']}): {p['siparis_adedi']} sipariş, {p['toplam_ciro']:.2f} ₺ ciro\n"
                        else:
                            reply_text = "Bugün personel performans verisi bulunamadı."
                        response_data["personnel"] = personnel_daily
                    elif "hafta" in text or "geçen hafta" in text or "son hafta" in text:
                        personnel_weekly = await fetch_personnel(7)
                        if personnel_weekly:
                            reply_text = "👥 PERSONEL PERFORMANSI (Son 7 gün):\n\n"
                            for p in personnel_weekly:
                                reply_text += f"- {p['username']} ({p['role']}): {p['siparis_adedi']} sipariş, {p['toplam_ciro']:.2f} ₺ ciro\n"
                        else:
                            reply_text = "Son hafta personel performans verisi bulunamadı."
                        response_data["personnel"] = personnel_weekly
                    elif "ay" in text or "bu ay" in text or "geçen ay" in text or "30" in text:
                        personnel_info = await fetch_personnel(30)
                        if personnel_info:
                            reply_text = "👥 PERSONEL PERFORMANSI (Son 30 gün):\n\n"
                            for p in personnel_info:
                                reply_text += f"- {p['username']} ({p['role']}): {p['siparis_adedi']} sipariş, {p['toplam_ciro']:.2f} ₺ ciro\n"
                        else:
                            reply_text = "Personel performans verisi bulunamadı."
                        response_data["personnel"] = personnel_info
                    else:
                        personnel_info = await fetch_personnel(30)
                        if personnel_info:
                            reply_text = "👥 PERSONEL PERFORMANSI (Son 30 gün):\n\n"
                            for p in personnel_info:
                                reply_text += f"- {p['username']} ({p['role']}): {p['siparis_adedi']} sipariş, {p['toplam_ciro']:.2f} ₺ ciro\n"
                        else:
                            reply_text = "Personel performans verisi bulunamadı."
                        response_data["personnel"] = personnel_info
            else:
                # Personel listesi
                personnel_list = await load_data("personnel_list", lambda: get_personnel_list(target_sube_id))
                if personnel_list:
                    reply_text = f"👥 PERSONEL LİSTESİ ({len(personnel_list)} kişi):\n\n"
                    by_role = defaultdict(list)
                    for p in personnel_list:
                        by_role[p['rol']].append(p)
                    for role, people in sorted(by_role.items()):
                        reply_text += f"\n{role.upper()}:\n"
                        for p in people:
                            durum_icon = "✅" if p['durum'] == 'Aktif' else "❌"
                            reply_text += f"  {durum_icon} {p['username']}\n"
                else:
                    reply_text = "Personel verisi bulunamadı."
                response_data["personnel_list"] = personnel_list
        elif "en çok satan" in text or "popüler" in text or ("en çok" in text and "satış" in text):
            async def fetch_top_products(days: int):
                return await load_data(f"top_products_{days}", lambda d=days: get_top_products(target_sube_id, days=d))

            handled = False
            if window_label in {"daily"}:
                handled = True
                top_daily = await fetch_top_products(1)
                if top_daily:
                    reply_text = f"🏆 EN ÇOK SATAN ÜRÜNLER ({format_time_window_label(time_window)}):\n\n"
                    for i, p in enumerate(top_daily[:10], 1):
                        reply_text += f"{i}. {p['urun_adi']}: {p['toplam_tutar']:.2f} ₺\n"
                else:
                    reply_text = "Bugün ürün verisi bulunamadı."
                response_data["top_products"] = top_daily
            elif window_label == "weekly":
                handled = True
                days = window_days or 7
                top_weekly = await fetch_top_products(days)
                if top_weekly:
                    reply_text = f"🏆 EN ÇOK SATAN ÜRÜNLER ({format_time_window_label({'label': 'weekly' if days == 7 else 'custom', 'days': days})}):\n\n"
                    for i, p in enumerate(top_weekly[:10], 1):
                        reply_text += f"{i}. {p['urun_adi']}: {p['toplam_tutar']:.2f} ₺\n"
                else:
                    reply_text = "Son hafta ürün verisi bulunamadı."
                response_data["top_products"] = top_weekly
            elif window_label == "monthly":
                handled = True
                top_products = await fetch_top_products(30)
                if top_products:
                    reply_text = f"🏆 EN ÇOK SATAN ÜRÜNLER ({format_time_window_label(time_window)}):\n\n"
                    for i, p in enumerate(top_products[:10], 1):
                        reply_text += f"{i}. {p['urun_adi']}: {p['toplam_tutar']:.2f} ₺\n"
                else:
                    reply_text = "En çok satan ürün verisi bulunamadı."
                response_data["top_products"] = top_products
            elif window_label == "custom" and window_days:
                handled = True
                top_custom = await fetch_top_products(window_days)
                if top_custom:
                    reply_text = f"🏆 EN ÇOK SATAN ÜRÜNLER ({format_time_window_label(time_window)}):\n\n"
                    for i, p in enumerate(top_custom[:10], 1):
                        reply_text += f"{i}. {p['urun_adi']}: {p['toplam_tutar']:.2f} ₺\n"
                else:
                    reply_text = "Bu dönem için ürün verisi bulunamadı."
                response_data["top_products"] = top_custom

            if not handled:
                if "bugün" in text or "günlük" in text or "dün" in text or ("gün" in text and "hafta" not in text and "ay" not in text):
                    top_daily = await fetch_top_products(1)
                    if top_daily:
                        reply_text = "🏆 EN ÇOK SATAN ÜRÜNLER (Bugün):\n\n"
                        for i, p in enumerate(top_daily[:10], 1):
                            reply_text += f"{i}. {p['urun_adi']}: {p['toplam_tutar']:.2f} ₺\n"
                    else:
                        reply_text = "Bugün ürün verisi bulunamadı."
                    response_data["top_products"] = top_daily
                elif "hafta" in text or "geçen hafta" in text or "son hafta" in text:
                    top_weekly = await fetch_top_products(7)
                    if top_weekly:
                        reply_text = "🏆 EN ÇOK SATAN ÜRÜNLER (Son 7 gün):\n\n"
                        for i, p in enumerate(top_weekly[:10], 1):
                            reply_text += f"{i}. {p['urun_adi']}: {p['toplam_tutar']:.2f} ₺\n"
                    else:
                        reply_text = "Son hafta ürün verisi bulunamadı."
                    response_data["top_products"] = top_weekly
                elif "ay" in text or "bu ay" in text or "geçen ay" in text or "30" in text:
                    top_products = await fetch_top_products(30)
                    if top_products:
                        reply_text = "🏆 EN ÇOK SATAN ÜRÜNLER (Son 30 gün):\n\n"
                        for i, p in enumerate(top_products[:10], 1):
                            reply_text += f"{i}. {p['urun_adi']}: {p['toplam_tutar']:.2f} ₺\n"
                    else:
                        reply_text = "En çok satan ürün verisi bulunamadı."
                    response_data["top_products"] = top_products
                else:
                    top_products = await fetch_top_products(30)
                    if top_products:
                        reply_text = "🏆 EN ÇOK SATAN ÜRÜNLER (Son 30 gün):\n\n"
                        for i, p in enumerate(top_products[:10], 1):
                            reply_text += f"{i}. {p['urun_adi']}: {p['toplam_tutar']:.2f} ₺\n"
                    else:
                        reply_text = "En çok satan ürün verisi bulunamadı."
                    response_data["top_products"] = top_products
        elif "kategori" in text and ("ürün" in text or "satış" in text or "rapor" in text or "ciro" in text):
            if time_window:
                period_days = window_days or (1 if window_label == "daily" else 7 if window_label == "weekly" else 30)
                period_label = format_time_window_label(time_window)
            else:
                period_label = "Son 30 gün"
                period_days = 30
                if "bugün" in text or "günlük" in text or "dün" in text:
                    period_label = "Bugün"
                    period_days = 1
                elif "hafta" in text or "geçen hafta" in text or "son hafta" in text:
                    period_label = "Son 7 gün"
                    period_days = 7
                elif "ay" in text or "bu ay" in text or "geçen ay" in text or "30" in text:
                    period_label = "Son 30 gün"
                    period_days = 30

            category_sales = await load_data(f"category_sales_{period_days}", lambda d=period_days: get_category_sales(target_sube_id, days=d))
            if category_sales:
                total_ciro = sum(item["ciro"] for item in category_sales)
                reply_text = f"📂 {period_label} için kategori bazlı satış raporu:\n\n"
                top_items = category_sales[:5]
                for item in top_items:
                    reply_text += (
                        f"- {item['kategori']}: {item['ciro']:.2f} ₺ (adet: {item['adet']:.0f}, pay: %{item['pay']:.1f})\n"
                    )
                if len(category_sales) > 5:
                    reply_text += f"... ve {len(category_sales) - 5} kategori daha mevcut.\n"
                reply_text += f"\nToplam ciro: {total_ciro:.2f} ₺"
                response_data["category_sales"] = {
                    "period_days": period_days,
                    "total": total_ciro,
                    "items": category_sales,
                }
            else:
                reply_text = f"{period_label} için kategori bazlı satış verisi bulunamadı."
        elif "menü" in text or "menu" in text or "ürün fiyat" in text:
            menu_items = await load_data("menu_items", lambda: get_menu_items(target_sube_id))
            if menu_items:
                reply_text = f"📋 MENÜ LİSTESİ ({len(menu_items)} ürün):\n\n"
                by_category = defaultdict(list)
                for item in menu_items:
                    by_category[item['kategori']].append(item)
                for category, items in sorted(by_category.items()):
                    if category:
                        reply_text += f"\n{category.upper()}:\n"
                        for item in items[:10]:
                            durum_icon = "✅" if item['durum'] == 'Aktif' else "❌"
                            reply_text += f"  {durum_icon} {item['urun']}: {item['fiyat']:.2f} ₺\n"
                        if len(items) > 10:
                            reply_text += f"  ... ve {len(items) - 10} ürün daha\n"
            else:
                reply_text = "Menü verisi bulunamadı."
            response_data["menu"] = menu_items
        elif "reçete" in text or "recipe" in text or "tarif" in text:
            recipes = await load_data("recipes", lambda: get_recipes(target_sube_id))
            if recipes:
                reply_text = f"🍳 REÇETELER ({len(recipes)} ürün):\n\n"
                for recipe in recipes[:10]:
                    reply_text += f"📝 {recipe['urun']}:\n"
                    for malzeme in recipe['malzemeler'][:5]:
                        reply_text += f"  • {malzeme['stok']}: {malzeme['miktar']} {malzeme['birim']}\n"
                    if len(recipe['malzemeler']) > 5:
                        reply_text += f"  • ... ve {len(recipe['malzemeler']) - 5} malzeme daha\n"
                if len(recipes) > 10:
                    reply_text += f"\n... ve {len(recipes) - 10} ürün reçetesi daha\n"
            else:
                reply_text = "Reçete verisi bulunamadı."
            response_data["recipes"] = recipes
        else:
            # ⚡ YENİ: Gelişmiş akıllı LLM analizi
            try:
                # Tenant ID'yi al (super admin için switched_tenant_id, normal kullanıcı için tenant_id)
                tenant_id = user.get("switched_tenant_id") or user.get("tenant_id")
                
                # Şube'den işletme ID'sini al (super admin için gerekli)
                if not tenant_id and target_sube_id:
                    sube_row = await db.fetch_one(
                        "SELECT isletme_id FROM subeler WHERE id = :id",
                        {"id": target_sube_id}
                    )
                    if sube_row:
                        sube_dict = dict(sube_row) if hasattr(sube_row, 'keys') else sube_row
                        tenant_id = sube_dict.get("isletme_id")
                
                provider = await get_llm_provider(tenant_id=tenant_id, assistant_type="business")

                revenue_info = await load_data("revenue_30", lambda: get_revenue_data(target_sube_id))
                expense_info = await load_data("expense_30", lambda: get_expense_data(target_sube_id))
                revenue_daily = await load_data("revenue_1", lambda: get_revenue_data(target_sube_id, days=1))
                expense_daily = await load_data("expense_1", lambda: get_expense_data(target_sube_id, days=1))
                inventory_info = await load_data("inventory", lambda: get_inventory_status(target_sube_id))
                personnel_info = await load_data("personnel_30", lambda: get_personnel_performance(target_sube_id))
                top_products = await load_data("top_products_30", lambda: get_top_products(target_sube_id, days=30))
                shopping_data = await load_data("shopping", lambda: get_shopping_suggestions(target_sube_id))
                profit_data = await load_data("profit", lambda: get_profit_margin_analysis(target_sube_id))
                stock_costs = await load_data("stock_costs", lambda: get_stock_costs(target_sube_id))
                menu_items = await load_data("menu_items", lambda: get_menu_items(target_sube_id))
                recipes = await load_data("recipes", lambda: get_recipes(target_sube_id))
                personnel_list = await load_data("personnel_list", lambda: get_personnel_list(target_sube_id))
                recent_orders = await load_data("recent_orders_7", lambda: get_recent_orders(target_sube_id, days=7))
                category_sales = await load_data("category_sales_30", lambda: get_category_sales(target_sube_id, days=30))

                # Tüm veriyi hazırla (akıllı sistem sadece gerekeni seçecek)
                all_business_data = {
                    "revenue_info": revenue_info,
                    "revenue_daily": revenue_daily,
                    "expense_info": expense_info,
                    "expense_daily": expense_daily,
                    "inventory_info": inventory_info,
                    "personnel_info": personnel_info,
                    "top_products": top_products,
                    "shopping_data": shopping_data,
                    "profit_data": profit_data,
                    "stock_costs": stock_costs,
                    "menu_items": menu_items,
                    "recipes": recipes,
                    "personnel_list": personnel_list,
                    "recent_orders": recent_orders,
                    "category_sales": await get_category_sales(target_sube_id, days=30),
                }

                # Zaman periyodu belirle
                requested_period = format_time_window_label(time_window)

                # 🧠 Akıllı prompt oluştur (intent detection + context selection + few-shot examples)
                smart_prompt, detected_intent, relevant_data = generate_smart_response(
                    user_question=text,
                    all_data=all_business_data,
                    time_period=requested_period
                )

                logging.info(f"[BI_ASSISTANT] Intent: {detected_intent}, Data sources: {len(relevant_data)}")

                # LLM'e gönder (BI analizi için optimize edilmiş parametrelerle)
                if hasattr(provider, 'chat'):
                    # OpenAI provider için task_type parametresi
                    import inspect
                    sig = inspect.signature(provider.chat)
                    if 'task_type' in sig.parameters:
                        result = await provider.chat([{"role": "user", "content": smart_prompt}], task_type="bi_analysis")
                    else:
                        result = await provider.chat([{"role": "user", "content": smart_prompt}])
                    
                    # OpenAIProvider tuple döndürür (text, usage_info), diğerleri string
                    if isinstance(result, tuple):
                        llm_reply, usage_info = result
                    else:
                        llm_reply, usage_info = result, None
                    
                    # API kullanımını logla (tenant_id varsa)
                    if usage_info and tenant_id:
                        from ..services.api_usage_tracker import log_api_usage
                        model = getattr(provider, 'model', 'gpt-4o-mini')
                        
                        await log_api_usage(
                            isletme_id=tenant_id,
                            api_type="openai",
                            model=model,
                            endpoint="/v1/chat/completions",
                            prompt_tokens=usage_info.get("prompt_tokens", 0),
                            completion_tokens=usage_info.get("completion_tokens", 0),
                            total_tokens=usage_info.get("total_tokens", 0),
                            cost_usd=usage_info.get("cost_usd", 0.0),
                            response_time_ms=usage_info.get("response_time_ms"),
                            status="success",
                        )
                else:
                    llm_reply = ""

                if llm_reply and llm_reply.strip():
                    reply_text = llm_reply.strip()
                    # İlgili veriyi response'a ekle
                    response_data.update(relevant_data)
                else:
                    reply_text = "Anlayamadım, lütfen daha spesifik soru sorun. Örneğin: 'Bu ayki ciromuz ne kadar?' veya 'Hangi ürünlerin stoğu kritik?'"

            except Exception as llm_e:
                logging.error(f"LLM query failed: {llm_e}", exc_info=True)
                reply_text = "Üzgünüm, şu anda analiz yapamıyorum. Lütfen tekrar deneyin veya farklı bir soru sorun."
    except Exception as e:
        logging.error(f"BI query error: {e}", exc_info=True)
        reply_text = f"Bir hata oluştu: {str(e)}"

    return BIQueryResponse(reply=reply_text, data=response_data, suggestions=suggestions)


@router.get("/morning-brief", response_model=BIQueryResponse, dependencies=[Depends(require_roles({"admin", "super_admin"}))])
async def get_morning_brief(
    sube_id: Optional[int] = Query(None, description="Opsiyonel şube ID (Super Admin için)"),
    user: Dict[str, Any] = Depends(get_current_user),
    user_sube_id: int = Depends(get_sube_id),
):
    """
    Proaktif Sabah Özeti: Dünün satışlarını, kritik stokları ve bugünün önerilerini getirir.
    """
    try:
        target_sube_id = sube_id if (sube_id and user.get("role") == "super_admin") else user_sube_id
        
        # 1. Verileri topla (Dün)
        yesterday_revenue = await get_revenue_data(target_sube_id, days=1)
        critical_stocks = await get_inventory_status(target_sube_id)
        
        # 2. LLM Prompt'u hazırla
        tenant_id = user.get("switched_tenant_id") or user.get("tenant_id")
        if not tenant_id and target_sube_id:
            sube_row = await db.fetch_one("SELECT isletme_id FROM subeler WHERE id = :id", {"id": target_sube_id})
            if sube_row:
                tenant_id = dict(sube_row).get("isletme_id")

        provider = await get_llm_provider(tenant_id=tenant_id, assistant_type="business")
        
        prompt = f"""Sen Neso'nun proaktif işletme zekası asistanısın. Yönetici şu an sisteme giriş yaptı ve senden bir 'Sabah Özeti' (Morning Brief) bekliyor.
Lütfen aşağıdaki verileri kullanarak enerjik, motive edici ve yöneticiyi yönlendirici kısa bir özet metni hazırla.

# Veriler:
* Dünkü Ciro: {yesterday_revenue.get('total_revenue', 0):.2f} TL
* Dünkü Sipariş Sayısı: {yesterday_revenue.get('total_orders', 0)}
* Kritik Stok Uyarıları: {len(critical_stocks)} ürün kritik seviyede. {', '.join([s['ad'] for s in critical_stocks[:3]])} {'ve diğerleri' if len(critical_stocks) > 3 else ''}

Yanıtını şu formatta yapılandır:
1. Günaydın mesajı ve dünün kısa değerlendirmesi (Örn: "Dün harika bir gündü, X TL ciro yaptık...")
2. Dikkat etmesi gerekenler (Örn: "Stokta azalan XY ürünleri için sipariş vermeyi unutmayın.")
3. Bugün için kısa bir strateji/öneri.

(Maksimum 4-5 cümle kullan, emoji ekle.)"""

        llm_reply = ""
        if hasattr(provider, 'chat'):
            import inspect
            sig = inspect.signature(provider.chat)
            if 'task_type' in sig.parameters:
                result = await provider.chat([{"role": "user", "content": prompt}], task_type="bi_analysis")
            else:
                result = await provider.chat([{"role": "user", "content": prompt}])
                
            if isinstance(result, tuple):
                llm_reply, _ = result
            else:
                llm_reply = result

        if not llm_reply or not llm_reply.strip():
            llm_reply = f"🌅 Günaydın! Dün {yesterday_revenue.get('total_orders', 0)} siparişten toplam {yesterday_revenue.get('total_revenue', 0):.2f} ₺ ciro elde ettik. Tüm ekibin eline sağlık!\n\n🛒 {'Stoklarınız gayet iyi durumda!' if not critical_stocks else f'Dikkat: {len(critical_stocks)} ürününüz kritik stok seviyesinde. Tedarikçilerle iletişime geçmenizi öneririm.'}\n\nBugün için harika bir gün diliyorum!"
            
        return BIQueryResponse(
            reply=llm_reply,
            data={"yesterday_revenue": yesterday_revenue, "critical_stocks": len(critical_stocks)}
        )
    except Exception as e:
        logging.error(f"Morning brief error: {e}", exc_info=True)
        return BIQueryResponse(reply="Günaydın! Sabah özetinizi şu an getiremiyorum, ancak işlerinizde kolaylıklar dilerim.")

