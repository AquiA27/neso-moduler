from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from ..core.deps import get_current_user
from ..db.database import db

router = APIRouter(prefix="/sube", tags=["Sube"])

class SubeIn(BaseModel):
    isletme_id: int = Field(gt=0)
    ad: str = Field(min_length=1)
    adres: Optional[str] = None
    telefon: Optional[str] = None

class SubeOut(BaseModel):
    id: int
    isletme_id: int
    ad: str
    adres: Optional[str]
    telefon: Optional[str]

@router.get("/liste", response_model=List[SubeOut])
async def sube_liste(current_user: str = Depends(get_current_user)):
    q = """SELECT id, isletme_id, ad, adres, telefon
           FROM subeler ORDER BY id"""
    return await db.fetch_all(q)

@router.post("/ekle", response_model=SubeOut)
async def sube_ekle(data: SubeIn, current_user: str = Depends(get_current_user)):
    q = """INSERT INTO subeler (isletme_id, ad, adres, telefon)
           VALUES (:isletme_id, :ad, :adres, :telefon)
           RETURNING id, isletme_id, ad, adres, telefon"""
    return await db.fetch_one(q, data.model_dump())

@router.patch("/{id}", response_model=SubeOut)
async def sube_guncelle(id: int, data: SubeIn, current_user: str = Depends(get_current_user)):
    exists = await db.fetch_one("SELECT id FROM subeler WHERE id=:id", {"id": id})
    if not exists:
        raise HTTPException(404, "Şube bulunamadı")
    q = """UPDATE subeler
           SET isletme_id=:isletme_id, ad=:ad, adres=:adres, telefon=:telefon
           WHERE id=:id
           RETURNING id, isletme_id, ad, adres, telefon"""
    vals = {**data.model_dump(), "id": id}
    return await db.fetch_one(q, vals)

@router.delete("/{id}")
async def sube_sil(id: int, current_user: str = Depends(get_current_user)):
    await db.execute("DELETE FROM subeler WHERE id=:id", {"id": id})
    return {"ok": True}
