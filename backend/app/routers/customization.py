from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from ..core.deps import require_roles, get_current_user
from ..db.database import db

router = APIRouter(
    prefix="/customization",
    tags=["Customization"],
)


# --------- Modeller ---------
class CustomizationIn(BaseModel):
    isletme_id: int = Field(gt=0)
    domain: Optional[str] = Field(None, description="Özel alan adı (örn: restoran1.neso.com)")
    app_name: Optional[str] = Field(None, description="Uygulama adı")
    logo_url: Optional[str] = None
    primary_color: Optional[str] = Field(default="#3b82f6", description="Ana renk (hex)")
    secondary_color: Optional[str] = Field(default="#1e40af", description="İkincil renk (hex)")
    footer_text: Optional[str] = None
    email: Optional[str] = None
    telefon: Optional[str] = None
    adres: Optional[str] = None
    openai_api_key: Optional[str] = Field(None, description="OpenAI API anahtarı (işletme bazında)")
    openai_model: Optional[str] = Field(default="gpt-4o-mini", description="OpenAI model (varsayılan: gpt-4o-mini)")
    meta_settings: Optional[Dict[str, Any]] = Field(default_factory=dict)


class CustomizationOut(CustomizationIn):
    id: int
    created_at: datetime
    updated_at: datetime


@router.get("/isletme/{isletme_id}", response_model=CustomizationOut)
async def get_customization(
    isletme_id: int,
    _: Dict[str, Any] = Depends(get_current_user),
):
    """İşletme özelleştirmelerini getir"""
    row = await db.fetch_one(
        """
        SELECT id, isletme_id, domain, app_name, logo_url, primary_color,
               secondary_color, footer_text, email, telefon, adres, 
               openai_api_key, openai_model, meta_settings,
               created_at, updated_at
        FROM tenant_customizations
        WHERE isletme_id = :id
        """,
        {"id": isletme_id},
    )
    if not row:
        # Varsayılan değerler döndür
        return {
            "id": 0,
            "isletme_id": isletme_id,
            "domain": None,
            "app_name": None,
            "logo_url": None,
            "primary_color": "#3b82f6",
            "secondary_color": "#1e40af",
            "footer_text": None,
            "email": None,
            "telefon": None,
            "adres": None,
            "openai_api_key": None,
            "openai_model": "gpt-4o-mini",
            "meta_settings": {},
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
    
    import json
    result = dict(row)
    if isinstance(result.get("meta_settings"), str):
        result["meta_settings"] = json.loads(result["meta_settings"])
    return result


@router.post("/create", response_model=CustomizationOut)
async def create_customization(
    payload: CustomizationIn,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """Yeni özelleştirme oluştur (super admin only)"""
    # Super admin kontrolü
    if user.get("role") != "super_admin":
        raise HTTPException(403, "Sadece super admin özelleştirme oluşturabilir")
    
    # İşletme kontrolü
    isletme = await db.fetch_one(
        "SELECT id FROM isletmeler WHERE id = :id",
        {"id": payload.isletme_id},
    )
    if not isletme:
        raise HTTPException(404, "İşletme bulunamadı")
    
    # Domain benzersizlik kontrolü
    if payload.domain:
        existing = await db.fetch_one(
            "SELECT id FROM tenant_customizations WHERE domain = :domain AND isletme_id != :id",
            {"domain": payload.domain, "id": payload.isletme_id},
        )
        if existing:
            raise HTTPException(400, "Bu domain zaten kullanılıyor")
    
    # Mevcut özelleştirme kontrolü
    existing = await db.fetch_one(
        "SELECT id FROM tenant_customizations WHERE isletme_id = :id",
        {"id": payload.isletme_id},
    )
    if existing:
        raise HTTPException(400, "Bu işletme için zaten özelleştirme mevcut. Güncelleme yapın.")
    
    import json
    data = payload.model_dump()
    data["meta_settings"] = json.dumps(data.get("meta_settings", {}))
    
    row = await db.fetch_one(
        """
        INSERT INTO tenant_customizations (
            isletme_id, domain, app_name, logo_url, primary_color,
            secondary_color, footer_text, email, telefon, adres, 
            openai_api_key, openai_model, meta_settings
        )
        VALUES (
            :isletme_id, :domain, :app_name, :logo_url, :primary_color,
            :secondary_color, :footer_text, :email, :telefon, :adres, 
            :openai_api_key, :openai_model, CAST(:meta_settings AS JSONB)
        )
        RETURNING id, isletme_id, domain, app_name, logo_url, primary_color,
                  secondary_color, footer_text, email, telefon, adres, 
                  openai_api_key, openai_model, meta_settings,
                  created_at, updated_at
        """,
        data,
    )
    
    result = dict(row)
    if isinstance(result.get("meta_settings"), str):
        result["meta_settings"] = json.loads(result["meta_settings"])
    return result


@router.patch("/isletme/{isletme_id}", response_model=CustomizationOut)
async def update_customization(
    isletme_id: int,
    payload: CustomizationIn,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """Özelleştirmeyi güncelle"""
    # Super admin kontrolü
    if user.get("role") != "super_admin":
        raise HTTPException(403, "Sadece super admin özelleştirme güncelleyebilir")
    
    existing = await db.fetch_one(
        "SELECT id FROM tenant_customizations WHERE isletme_id = :id",
        {"id": isletme_id},
    )
    if not existing:
        raise HTTPException(404, "Özelleştirme bulunamadı")
    
    # Domain benzersizlik kontrolü
    if payload.domain:
        existing_domain = await db.fetch_one(
            "SELECT id FROM tenant_customizations WHERE domain = :domain AND isletme_id != :id",
            {"domain": payload.domain, "id": isletme_id},
        )
        if existing_domain:
            raise HTTPException(400, "Bu domain zaten kullanılıyor")
    
    import json
    data = payload.model_dump(exclude={"isletme_id"}, exclude_unset=False)
    data["isletme_id"] = isletme_id
    data["meta_settings"] = json.dumps(data.get("meta_settings", {}))
    data["updated_at"] = datetime.utcnow()
    
    # Sadece verilen alanları güncelle (None olmayan ve boş string olmayan değerler)
    update_fields = []
    update_values = {"isletme_id": isletme_id, "updated_at": data["updated_at"]}
    
    for field in ["domain", "app_name", "logo_url", "primary_color", "secondary_color",
                  "footer_text", "email", "telefon", "adres", "openai_api_key", "openai_model", "meta_settings"]:
        if field in data and data[field] is not None:
            # Boş string'leri None'a çevir (opsiyonel alanlar için)
            if field in ["domain", "app_name", "logo_url", "footer_text", "email", "telefon", "adres", "openai_api_key"]:
                if data[field] == "":
                    update_fields.append(f"{field} = NULL")
                else:
                    update_fields.append(f"{field} = :{field}")
                    update_values[field] = data[field]
            else:
                # primary_color, secondary_color, openai_model, meta_settings her zaman güncellenmeli
                update_fields.append(f"{field} = :{field}")
                update_values[field] = data[field]
    
    if not update_fields:
        raise HTTPException(400, "Güncellenecek alan yok")
    
    query = f"""
        UPDATE tenant_customizations
        SET {', '.join(update_fields)}, updated_at = :updated_at
        WHERE isletme_id = :isletme_id
        RETURNING id, isletme_id, domain, app_name, logo_url, primary_color,
                  secondary_color, footer_text, email, telefon, adres, 
                  openai_api_key, openai_model, meta_settings,
                  created_at, updated_at
    """
    
    row = await db.fetch_one(query, update_values)
    
    result = dict(row)
    if isinstance(result.get("meta_settings"), str):
        result["meta_settings"] = json.loads(result["meta_settings"])
    return result


@router.get("/domain/{domain}", response_model=CustomizationOut)
async def get_customization_by_domain(
    domain: str,
):
    """Domain'e göre özelleştirmeyi getir (public endpoint)"""
    row = await db.fetch_one(
        """
        SELECT id, isletme_id, domain, app_name, logo_url, primary_color,
               secondary_color, footer_text, email, telefon, adres, 
               openai_api_key, openai_model, meta_settings,
               created_at, updated_at
        FROM tenant_customizations
        WHERE domain = :domain
        """,
        {"domain": domain},
    )
    if not row:
        raise HTTPException(404, "Özelleştirme bulunamadı")
    
    import json
    # Record objesini güvenli şekilde dict'e çevir
    if hasattr(row, 'keys'):
        result = dict(row)
    elif isinstance(row, dict):
        result = row
    else:
        result = dict(row) if row else {}
    
    if isinstance(result.get("meta_settings"), str):
        try:
            result["meta_settings"] = json.loads(result["meta_settings"])
        except (json.JSONDecodeError, TypeError):
            result["meta_settings"] = {}
    
    return result

