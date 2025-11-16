from fastapi import APIRouter, Depends
from ..core.deps import get_current_user
from ..db.database import db

router = APIRouter(prefix="/istatistik", tags=["Istatistik"])

@router.get("/gunluk")
async def gunluk_istatistik(current_user: str = Depends(get_current_user)):
    q = """
    SELECT 
      CAST(NOW() AT TIME ZONE 'UTC' AS DATE) AS gun,
      COUNT(*) AS siparis_adedi,
      COALESCE(SUM(tutar),0) AS ciro
    FROM siparisler
    WHERE created_at::date = (NOW() AT TIME ZONE 'UTC')::date;
    """
    row = await db.fetch_one(q)
    return {"gun": str(row["gun"]), "siparis_adedi": int(row["siparis_adedi"]), "ciro": float(row["ciro"])}

@router.get("/aylik")
async def aylik_istatistik(current_user: str = Depends(get_current_user)):
    q = """
    SELECT 
      to_char(date_trunc('day', created_at), 'YYYY-MM-DD') AS gun,
      COUNT(*) AS siparis_adedi,
      COALESCE(SUM(tutar),0) AS ciro
    FROM siparisler
    WHERE created_at >= date_trunc('month', NOW() AT TIME ZONE 'UTC')
    GROUP BY 1
    ORDER BY 1;
    """
    rows = await db.fetch_all(q)
    return [dict(r) for r in rows]

@router.get("/yillik")
async def yillik_istatistik(current_user: str = Depends(get_current_user)):
    q = """
    SELECT 
      to_char(date_trunc('month', created_at), 'YYYY-MM') AS ay,
      COUNT(*) AS siparis_adedi,
      COALESCE(SUM(tutar),0) AS ciro
    FROM siparisler
    WHERE created_at >= date_trunc('year', NOW() AT TIME ZONE 'UTC')
    GROUP BY 1
    ORDER BY 1;
    """
    rows = await db.fetch_all(q)
    return [dict(r) for r in rows]
