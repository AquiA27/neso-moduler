# backend/app/routers/recete.py
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from ..core.deps import get_current_user, get_sube_id, require_roles
from ..db.database import db

router = APIRouter(prefix="/recete", tags=["Recete"])

# ---------- Modeller ----------
class ReceteItemIn(BaseModel):
    urun: str = Field(min_length=1)
    stok: str = Field(min_length=1)
    miktar: float = Field(gt=0)
    birim: str = Field(min_length=1)

class ReceteItemOut(BaseModel):
    id: int
    urun: str
    stok: str
    miktar: float
    birim: str

# ---------- Uçlar ----------
@router.post(
    "/ekle",
    response_model=ReceteItemOut,
    dependencies=[Depends(require_roles({"admin", "operator"}))]
)
async def recete_ekle(
    item: ReceteItemIn,
    _: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    params = {**item.model_dump(), "sid": sube_id}
    try:
        row = await db.fetch_one(
            """
            INSERT INTO receteler (sube_id, urun, stok, miktar, birim)
            VALUES (:sid, :urun, :stok, :miktar, :birim)
            RETURNING id, urun, stok, miktar, birim
            """,
            params,
        )
    except Exception:
        # Aynı reçete varsa UPDATE'e düş
        row = await db.fetch_one(
            """
            UPDATE receteler
               SET miktar = :miktar,
                   birim = :birim
             WHERE sube_id = :sid
               AND urun = :urun
               AND stok = :stok
         RETURNING id, urun, stok, miktar, birim
            """,
            params,
        )
        if not row:
            raise HTTPException(status_code=400, detail="Reçete ekleme/güncelleme başarısız")
    return {
        "id": row["id"],
        "urun": row["urun"],
        "stok": row["stok"],
        "miktar": float(row["miktar"]),
        "birim": row["birim"],
    }

@router.get("/liste", response_model=List[ReceteItemOut])
async def recete_liste(
    limit: int = Query(200, ge=1, le=2000),
    urun: Optional[str] = Query(None, description="Belirli bir ürün için reçeteleri filtrele"),
    _: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    if urun:
        rows = await db.fetch_all(
            """
            SELECT id, urun, stok, miktar, birim
            FROM receteler
            WHERE sube_id = :sid AND urun = :urun
            ORDER BY urun, stok
            LIMIT :lmt
            """,
            {"sid": sube_id, "urun": urun, "lmt": limit},
        )
    else:
        rows = await db.fetch_all(
            """
            SELECT id, urun, stok, miktar, birim
            FROM receteler
            WHERE sube_id = :sid
            ORDER BY urun, stok
            LIMIT :lmt
            """,
            {"sid": sube_id, "lmt": limit},
        )
    return [
        {
            "id": r["id"],
            "urun": r["urun"],
            "stok": r["stok"],
            "miktar": float(r["miktar"]),
            "birim": r["birim"] or "",
        }
        for r in rows
    ]

@router.delete(
    "/sil/{recete_id}",
    dependencies=[Depends(require_roles({"admin", "operator"}))]
)
async def recete_sil_by_id(
    recete_id: int = Path(..., description="Silinecek reçete ID'si"),
    _: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    result = await db.execute(
        """
        DELETE FROM receteler
        WHERE sube_id = :sid AND id = :id
        """,
        {"sid": sube_id, "id": recete_id},
    )
    return {"message": "Reçete silindi", "id": recete_id}

@router.delete(
    "/sil",
    dependencies=[Depends(require_roles({"admin", "operator"}))]
)
async def recete_sil(
    urun: str = Query(..., description="Silinecek reçetenin ürün adı"),
    stok: str = Query(..., description="Silinecek reçetenin stok adı"),
    _: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    result = await db.execute(
        """
        DELETE FROM receteler
        WHERE sube_id = :sid AND urun = :urun AND stok = :stok
        """,
        {"sid": sube_id, "urun": urun, "stok": stok},
    )
    return {"message": "Reçete silindi", "urun": urun, "stok": stok}
