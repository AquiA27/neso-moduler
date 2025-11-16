# backend/app/routers/rapor.py
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import io
from ..core.deps import get_current_user, get_sube_id, require_roles
from ..db.database import db
from ..services.export import export_service
from ..services.audit import audit_service

router = APIRouter(
    prefix="/rapor",
    tags=["Rapor"],
    dependencies=[Depends(get_current_user)],  # tüm uçlar auth ister
)

# ---------- OUT modelleri ----------
class CiroSatiri(BaseModel):
    period: str
    ciro: float
    adet: int

class UrunSatiri(BaseModel):
    urun: str
    adet: int
    ciro: float

class SaatlikSatir(BaseModel):
    saat: str   # 2025-10-28 12:00 gibi
    adet: int
    ciro: float

# ---------- Günlük ciro ----------
@router.get("/ciro/gunluk", response_model=List[CiroSatiri])
async def ciro_gunluk(limit: int = Query(30, ge=1, le=365)):
    """
    Son N gün için (bugün dahil) günlük ciro ve sipariş adedi.
    """
    rows = await db.fetch_all(
        """
        SELECT
          to_char(date_trunc('day', created_at), 'YYYY-MM-DD') AS period,
          SUM(tutar)::float AS ciro,
          COUNT(*)::int AS adet
        FROM siparisler
        GROUP BY 1
        ORDER BY 1 DESC
        LIMIT :limit;
        """,
        {"limit": limit},
    )
    return rows

# ---------- Aylık ciro ----------
@router.get("/ciro/aylik", response_model=List[CiroSatiri])
async def ciro_aylik(limit: int = Query(12, ge=1, le=120)):
    """
    Son N ay için aylık ciro ve sipariş adedi.
    """
    rows = await db.fetch_all(
        """
        SELECT
          to_char(date_trunc('month', created_at), 'YYYY-MM') AS period,
          SUM(tutar)::float AS ciro,
          COUNT(*)::int AS adet
        FROM siparisler
        GROUP BY 1
        ORDER BY 1 DESC
        LIMIT :limit;
        """,
        {"limit": limit},
    )
    return rows

# ---------- En çok satan ürünler ----------
@router.get("/top-urunler", response_model=List[UrunSatiri])
async def top_urunler(
    gun: int = Query(30, ge=1, le=365),
    limit: int = Query(20, ge=1, le=200),
):
    """
    Son N gün içinde adet ve ciroya göre en çok satan ürünler.
    Sepet JSONB: [{urun, adet, fiyat}] üstünden hesaplanır.
    """
    rows = await db.fetch_all(
        """
        WITH z AS (
          SELECT
            lower(unaccent(trim(si->>'urun'))) AS urun_norm,
            (si->>'adet')::int AS adet,
            (si->>'fiyat')::numeric AS fiyat
          FROM siparisler s
          CROSS JOIN LATERAL jsonb_array_elements(s.sepet) AS si
          WHERE s.created_at >= (NOW() - make_interval(days => :gun))
        )
        SELECT
          urun_norm AS urun,
          SUM(adet)::int AS adet,
          SUM(adet * fiyat)::float AS ciro
        FROM z
        GROUP BY urun_norm
        ORDER BY ciro DESC, adet DESC
        LIMIT :limit;
        """,
        {"gun": gun, "limit": limit},
    )
    return rows

# ---------- Saatlik yoğunluk (son N saat) ----------
@router.get("/saatlik", response_model=List[SaatlikSatir])
async def saatlik_yogunluk(saat: int = Query(72, ge=1, le=24*14)):
    """
    Son N saatlik zaman serisi (her saat için sipariş sayısı ve ciro).
    """
    rows = await db.fetch_all(
        """
        WITH s AS (
          SELECT date_trunc('hour', created_at) AS h, COUNT(*)::int AS adet, SUM(tutar)::float AS ciro
          FROM siparisler
          WHERE created_at >= (NOW() - make_interval(hours => :saat))
          GROUP BY 1
        )
        SELECT to_char(h, 'YYYY-MM-DD HH24:00') AS saat, adet, ciro
        FROM s
        ORDER BY saat DESC;
        """,
        {"saat": saat},
    )
    return rows


# ---------- EXPORT ENDPOINTLERİ ----------

@router.get(
    "/export/gunluk",
    dependencies=[Depends(require_roles({"super_admin", "admin", "operator"}))],
)
async def export_gunluk_rapor(
    format: str = Query("excel", regex="^(excel|pdf)$"),
    days: int = Query(30, ge=1, le=365),
    user: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """
    Günlük raporu Excel veya PDF olarak indir

    **Yetkiler:** super_admin, admin, operator

    **Parametreler:**
    - format: 'excel' veya 'pdf'
    - days: Son kaç günün raporu (varsayılan: 30)

    **Örnek:**
    ```
    GET /rapor/export/gunluk?format=excel&days=30
    GET /rapor/export/gunluk?format=pdf&days=7
    ```
    """
    # Audit log
    await audit_service.log_action(
        action=f"report.export_daily_{format}",
        username=user.get("username"),
        user_id=user.get("id"),
        sube_id=sube_id,
        entity_type="report",
        success=True,
    )

    # Verileri al
    start_date = datetime.now() - timedelta(days=days)

    # Siparişler
    orders = await db.fetch_all(
        """
        SELECT
            to_char(created_at, 'YYYY-MM-DD') AS tarih,
            COUNT(*) AS siparis_sayisi,
            SUM(tutar)::float AS toplam_tutar
        FROM siparisler
        WHERE sube_id = :sube_id AND created_at >= :start_date
        GROUP BY 1
        ORDER BY 1 DESC
        """,
        {"sube_id": sube_id, "start_date": start_date},
    )

    orders_data = [dict(row) for row in orders]

    # Ödemeler
    payments = await db.fetch_all(
        """
        SELECT
            to_char(created_at, 'YYYY-MM-DD') AS tarih,
            yontem AS odeme_yontemi,
            COUNT(*) AS odeme_sayisi,
            SUM(tutar)::float AS toplam
        FROM odemeler
        WHERE sube_id = :sube_id AND created_at >= :start_date AND iptal = FALSE
        GROUP BY 1, 2
        ORDER BY 1 DESC, 2
        """,
        {"sube_id": sube_id, "start_date": start_date},
    )

    payments_data = [dict(row) for row in payments]

    # Giderler
    expenses = await db.fetch_all(
        """
        SELECT
            tarih::text,
            kategori,
            SUM(tutar)::float AS toplam
        FROM giderler
        WHERE sube_id = :sube_id AND tarih >= :start_date::date
        GROUP BY 1, 2
        ORDER BY 1 DESC, 2
        """,
        {"sube_id": sube_id, "start_date": start_date},
    )

    expenses_data = [dict(row) for row in expenses]

    # Özet veriler
    total_revenue = sum([row["toplam_tutar"] for row in orders_data])
    total_orders = sum([row["siparis_sayisi"] for row in orders_data])
    total_expenses = sum([row["toplam"] for row in expenses_data])
    avg_basket = total_revenue / total_orders if total_orders > 0 else 0
    net_profit = total_revenue - total_expenses

    report_data = {
        "total_revenue": total_revenue,
        "total_orders": total_orders,
        "avg_basket": avg_basket,
        "total_expenses": total_expenses,
        "net_profit": net_profit,
        "orders": orders_data,
        "payments": payments_data,
        "expenses": expenses_data,
    }

    # Export
    if format == "excel":
        file_bytes = export_service.create_daily_report_excel(report_data)
        filename = f"gunluk_rapor_{datetime.now().strftime('%Y%m%d')}.xlsx"
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:  # pdf
        # PDF için basit veri tablosu
        combined_data = []
        combined_data.append({"Metrik": "Toplam Ciro", "Değer": f"{total_revenue:.2f} ₺"})
        combined_data.append({"Metrik": "Toplam Sipariş", "Değer": total_orders})
        combined_data.append({"Metrik": "Ortalama Sepet", "Değer": f"{avg_basket:.2f} ₺"})
        combined_data.append({"Metrik": "Toplam Gider", "Değer": f"{total_expenses:.2f} ₺"})
        combined_data.append({"Metrik": "Net Kar", "Değer": f"{net_profit:.2f} ₺"})

        file_bytes = export_service.export_to_pdf(
            data=combined_data,
            title="Günlük Rapor",
            subtitle=f"Son {days} Gün - {datetime.now().strftime('%d.%m.%Y')}",
        )
        filename = f"gunluk_rapor_{datetime.now().strftime('%Y%m%d')}.pdf"
        media_type = "application/pdf"

    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get(
    "/export/stok",
    dependencies=[Depends(require_roles({"super_admin", "admin", "operator"}))],
)
async def export_stok_rapor(
    format: str = Query("excel", regex="^(excel|pdf)$"),
    user: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """
    Stok raporunu Excel veya PDF olarak indir

    **Yetkiler:** super_admin, admin, operator

    **Parametreler:**
    - format: 'excel' veya 'pdf'

    **Örnek:**
    ```
    GET /rapor/export/stok?format=excel
    ```
    """
    # Audit log
    await audit_service.log_action(
        action=f"report.export_stock_{format}",
        username=user.get("username"),
        user_id=user.get("id"),
        sube_id=sube_id,
        entity_type="report",
        success=True,
    )

    # Stok verilerini al
    stock_rows = await db.fetch_all(
        """
        SELECT
            ad AS stok_adi,
            kategori,
            mevcut::float AS mevcut_miktar,
            min::float AS min_miktar,
            birim,
            alis_fiyat::float AS alis_fiyati,
            (mevcut * alis_fiyat)::float AS toplam_deger,
            CASE
                WHEN mevcut <= 0 THEN 'Tükendi'
                WHEN mevcut <= min THEN 'Kritik'
                ELSE 'Normal'
            END AS durum
        FROM stok_kalemleri
        WHERE sube_id = :sube_id
        ORDER BY durum ASC, ad ASC
        """,
        {"sube_id": sube_id},
    )

    stock_data = [dict(row) for row in stock_rows]

    # Export
    if format == "excel":
        file_bytes = export_service.export_to_excel(
            data=stock_data,
            title="Stok Raporu",
            sheet_name="Stok",
        )
        filename = f"stok_rapor_{datetime.now().strftime('%Y%m%d')}.xlsx"
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:  # pdf
        file_bytes = export_service.export_to_pdf(
            data=stock_data,
            title="Stok Raporu",
            subtitle=f"{datetime.now().strftime('%d.%m.%Y %H:%M')}",
            orientation="landscape",
        )
        filename = f"stok_rapor_{datetime.now().strftime('%Y%m%d')}.pdf"
        media_type = "application/pdf"

    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
