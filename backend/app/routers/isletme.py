from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from ..core.deps import get_current_user
from ..db.database import db

router = APIRouter(prefix="/isletme", tags=["Isletme"])

class IsletmeIn(BaseModel):
    ad: str
    vergi_no: Optional[str] = None
    telefon: Optional[str] = None
    aktif: bool = True

class IsletmeOut(IsletmeIn):
    id: int

@router.post("/", response_model=IsletmeOut)
async def olustur(payload: IsletmeIn, user=Depends(get_current_user)):
    row = await db.fetch_one(
        """
        INSERT INTO isletmeler (ad, vergi_no, telefon, aktif)
        VALUES (:ad, :vergi_no, :telefon, :aktif)
        RETURNING id, ad, vergi_no, telefon, aktif
        """,
        payload.model_dump()
    )
    return row

@router.get("/", response_model=List[IsletmeOut])
async def listele(
    limit: int = Query(50, ge=1, le=500, description="Sayfa başına kayıt sayısı"),
    offset: int = Query(0, ge=0, description="Atlanacak kayıt sayısı"),
    user=Depends(get_current_user),
):
    rows = await db.fetch_all(
        """
        SELECT id, ad, vergi_no, telefon, aktif 
        FROM isletmeler 
        ORDER BY id DESC
        LIMIT :limit OFFSET :offset
        """,
        {"limit": limit, "offset": offset}
    )
    return rows

@router.get("/{id}", response_model=IsletmeOut)
async def getir(id: int, user=Depends(get_current_user)):
    row = await db.fetch_one(
        "SELECT id, ad, vergi_no, telefon, aktif FROM isletmeler WHERE id=:id",
        {"id": id}
    )
    if not row:
        raise HTTPException(404, "İşletme bulunamadı")
    return row

@router.patch("/{id}", response_model=IsletmeOut)
async def guncelle(id: int, payload: IsletmeIn, user=Depends(get_current_user)):
    existed = await db.fetch_one("SELECT id FROM isletmeler WHERE id=:id", {"id": id})
    if not existed:
        raise HTTPException(404, "İşletme bulunamadı")
    row = await db.fetch_one(
        """
        UPDATE isletmeler
        SET ad=:ad, vergi_no=:vergi_no, telefon=:telefon, aktif=:aktif
        WHERE id=:id
        RETURNING id, ad, vergi_no, telefon, aktif
        """,
        {**payload.model_dump(), "id": id}
    )
    return row

@router.delete("/{id}")
async def sil(id: int, user=Depends(get_current_user)):
    await db.execute("DELETE FROM isletmeler WHERE id=:id", {"id": id})
    return {"ok": True}
