from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field, EmailStr
from typing import Dict, Any, Optional
from datetime import datetime

from ..db.database import db
from ..core.security import hash_password, create_access_token, create_refresh_token, validate_password

router = APIRouter(prefix="/onboarding", tags=["Onboarding"])

class SignupRequest(BaseModel):
    # İşletme Bilgileri
    isletme_adi: str = Field(..., min_length=2, max_length=100)
    telefon: Optional[str] = None
    
    # Kullanıcı (Admin) Bilgileri
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    password: str = Field(..., min_length=8)
    
    # Hukuki Onaylar
    accepted_kvkk: bool = Field(..., description="KVKK Açık Rıza Metni onayı")
    accepted_terms: bool = Field(..., description="Mesafeli Satış Sözleşmesi onayı")

class SignupResponse(BaseModel):
    message: str
    access_token: str
    refresh_token: str
    isletme_id: int
    user_id: int


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
async def signup(request: Request, payload: SignupRequest):
    """
    SaaS Onboarding (Yeni İşletme Kaydı).
    """
    if not payload.accepted_kvkk or not payload.accepted_terms:
        raise HTTPException(
            status_code=400,
            detail="KVKK ve Mesafeli Satış Sözleşmesini kabul etmeniz zorunludur."
        )

    # Validate password
    is_valid, error_msg = validate_password(payload.password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    # Check if username exists
    existing_user = await db.fetch_one("SELECT id FROM users WHERE username = :u", {"u": payload.username})
    if existing_user:
        raise HTTPException(status_code=409, detail="Bu kullanıcı adı zaten alınmış.")

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    async with db.transaction():
        # 1. İşletmeyi oluştur
        isletme = await db.fetch_one(
            """
            INSERT INTO isletmeler (ad, telefon, aktif)
            VALUES (:ad, :tel, TRUE)
            RETURNING id
            """,
            {"ad": payload.isletme_adi, "tel": payload.telefon}
        )
        isletme_id = isletme["id"]

        # 2. Main şubeyi oluştur
        sube = await db.fetch_one(
            """
            INSERT INTO subeler (isletme_id, ad, aktif)
            VALUES (:iid, 'Merkez Şube', TRUE)
            RETURNING id
            """,
            {"iid": isletme_id}
        )

        # 3. Kullanıcıyı (admin) oluştur
        hashed_pw = hash_password(payload.password)
        user = await db.fetch_one(
            """
            INSERT INTO users (username, sifre_hash, role, tenant_id, aktif)
            VALUES (:u, :h, 'admin', :tid, TRUE)
            RETURNING id
            """,
            {"u": payload.username, "h": hashed_pw, "tid": isletme_id}
        )
        user_id = user["id"]

        # 4. Hukuki Onayları Kaydet (Audit)
        await db.execute(
            """
            INSERT INTO user_agreements (user_id, isletme_id, agreement_type, version, accepted, ip_address, user_agent)
            VALUES 
            (:uid, :iid, 'kvkk', '1.0', TRUE, :ip, :ua),
            (:uid, :iid, 'terms', '1.0', TRUE, :ip, :ua)
            """,
            {
                "uid": user_id, 
                "iid": isletme_id, 
                "ip": ip_address, 
                "ua": user_agent
            }
        )

        # 5. Abonelik başlat (Trial veya Basic)
        await db.execute(
            """
            INSERT INTO subscriptions (
                isletme_id, plan_type, status, 
                max_subeler, max_kullanicilar, max_menu_items
            )
            VALUES (:iid, 'free_trial', 'trial', 1, 2, 50)
            """,
            {"iid": isletme_id}
        )

        # Create tokens
        token_data = {
            "sub": payload.username,
            "role": "admin",
            "tenant_id": isletme_id,
        }
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token({"sub": payload.username})

    return SignupResponse(
        message="İşletme kaydınız başarıyla tamamlandı.",
        access_token=access_token,
        refresh_token=refresh_token,
        isletme_id=isletme_id,
        user_id=user_id
    )
