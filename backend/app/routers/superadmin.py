from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from ..core.deps import require_roles, get_current_user
from ..db.database import db


router = APIRouter(
    prefix="/superadmin",
    tags=["SuperAdmin"],
    dependencies=[Depends(require_roles({"super_admin"}))],
)


# --------- Modeller ---------
class TenantIn(BaseModel):
    ad: str = Field(min_length=1)
    vergi_no: Optional[str] = None
    telefon: Optional[str] = None
    aktif: bool = True

class TenantOut(TenantIn):
    id: int


@router.get("/tenants", response_model=List[TenantOut])
async def tenants_list(_: Dict[str, Any] = Depends(get_current_user)):
    q = """
    SELECT id, ad, vergi_no, telefon, aktif
    FROM isletmeler
    ORDER BY id DESC
    """
    return await db.fetch_all(q)


@router.post("/tenants", response_model=TenantOut)
async def tenant_create(payload: TenantIn, _: Dict[str, Any] = Depends(get_current_user)):
    row = await db.fetch_one(
        """
        INSERT INTO isletmeler (ad, vergi_no, telefon, aktif)
        VALUES (:ad, :vergi_no, :telefon, :aktif)
        RETURNING id, ad, vergi_no, telefon, aktif
        """,
        payload.model_dump(),
    )
    return row


@router.patch("/tenants/{id}", response_model=TenantOut)
async def tenant_update(id: int, payload: TenantIn, _: Dict[str, Any] = Depends(get_current_user)):
    exists = await db.fetch_one("SELECT id FROM isletmeler WHERE id = :id", {"id": id})
    if not exists:
        raise HTTPException(404, "İşletme bulunamadı")
    row = await db.fetch_one(
        """
        UPDATE isletmeler
           SET ad=:ad, vergi_no=:vergi_no, telefon=:telefon, aktif=:aktif
         WHERE id=:id
     RETURNING id, ad, vergi_no, telefon, aktif
        """,
        {**payload.model_dump(), "id": id},
    )
    return row


@router.delete("/tenants/{id}")
async def tenant_delete(id: int, _: Dict[str, Any] = Depends(get_current_user)):
    await db.execute("DELETE FROM isletmeler WHERE id = :id", {"id": id})
    return {"ok": True}


# ---- Kullanıcılar ----
class UserUpsertIn(BaseModel):
    username: str = Field(min_length=1)
    role: str = Field(min_length=1)
    aktif: bool = True
    password: Optional[str] = None


@router.get("/users")
async def users_list(
    include_passive: bool = Query(False, alias="include_passive"),
    _: Dict[str, Any] = Depends(get_current_user),
):
    base_query = "SELECT id, username, role, aktif, created_at FROM users"
    if not include_passive:
        base_query += " WHERE aktif = TRUE"
    base_query += " ORDER BY id DESC"
    rows = await db.fetch_all(base_query)
    return [dict(r) for r in rows]


@router.post("/users/upsert")
async def users_upsert(payload: UserUpsertIn, _: Dict[str, Any] = Depends(get_current_user)):
    # Şifre hash sütunu varsa kullan, yoksa geç
    params = {
        "u": payload.username,
        "r": payload.role,
        "a": payload.aktif,
    }
    if payload.password:
        try:
            from ..core.security import hash_password
            params["h"] = hash_password(payload.password)
            await db.execute(
                """
                INSERT INTO users (username, sifre_hash, role, aktif)
                VALUES (:u, :h, :r, :a)
                ON CONFLICT (username) DO UPDATE
                   SET role = EXCLUDED.role,
                       aktif = EXCLUDED.aktif,
                       sifre_hash = EXCLUDED.sifre_hash
                """,
                params,
            )
            return {"ok": True}
        except Exception:
            # Şema sifre_hash içermiyorsa ikinci deneme
            pass

    await db.execute(
        """
        INSERT INTO users (username, role, aktif)
        VALUES (:u, :r, :a)
        ON CONFLICT (username) DO UPDATE
           SET role = EXCLUDED.role,
               aktif = EXCLUDED.aktif
        """,
        params,
    )
    return {"ok": True}


class UserSubeIzinIn(BaseModel):
    username: str
    sube_ids: List[int] = Field(default_factory=list)


@router.post("/users/sube-izin")
async def set_user_sube_permissions(payload: UserSubeIzinIn, _: Dict[str, Any] = Depends(get_current_user)):
    # Mevcut izinleri sil ve yeniden yaz
    await db.execute("DELETE FROM user_sube_izinleri WHERE username = :u", {"u": payload.username})
    if payload.sube_ids:
        for sid in payload.sube_ids:
            try:
                await db.execute(
                    "INSERT INTO user_sube_izinleri (username, sube_id) VALUES (:u, :sid)",
                    {"u": payload.username, "sid": int(sid)},
                )
            except Exception:
                pass
    return {"ok": True, "username": payload.username, "sube_ids": payload.sube_ids}


# ---- Uygulama Ayarları (global KV) ----
class SettingsUpsertIn(BaseModel):
    values: Dict[str, Any]


@router.get("/settings")
async def app_settings_get(_: Dict[str, Any] = Depends(get_current_user)):
    rows = await db.fetch_all("SELECT key, value, updated_at FROM app_settings ORDER BY key")
    return {r["key"]: r["value"] for r in rows}


@router.put("/settings")
async def app_settings_put(payload: SettingsUpsertIn, _: Dict[str, Any] = Depends(get_current_user)):
    async with db.transaction():
        for k, v in payload.values.items():
            try:
                await db.execute(
                    """
                    INSERT INTO app_settings (key, value, updated_at)
                    VALUES (:k, CAST(:v AS JSONB), NOW())
                    ON CONFLICT (key) DO UPDATE
                       SET value = EXCLUDED.value,
                           updated_at = EXCLUDED.updated_at
                    """,
                    {"k": k, "v": json_dumps(v)},
                )
            except Exception:
                # JSONB cast başarısızsa alternatif
                await db.execute(
                    """
                    INSERT INTO app_settings (key, value, updated_at)
                    VALUES (:k, to_jsonb(:v::text), NOW())
                    ON CONFLICT (key) DO UPDATE
                       SET value = EXCLUDED.value,
                           updated_at = EXCLUDED.updated_at
                    """,
                    {"k": k, "v": json_dumps(v)},
                )
    return {"ok": True}


def json_dumps(v: Any) -> str:
    import json
    return json.dumps(v, ensure_ascii=False)


# ---- Kullanıcı İzinleri Yönetimi ----
# Tüm mevcut izin anahtarları
PERMISSION_KEYS = {
    "menu_ekle": "Menü Ekleme",
    "menu_guncelle": "Menü Güncelleme",
    "menu_sil": "Menü Silme",
    "menu_varyasyon_yonet": "Menü Varyasyon Yönetimi",
    "stok_ekle": "Stok Ekleme",
    "stok_guncelle": "Stok Güncelleme",
    "stok_sil": "Stok Silme",
    "stok_goruntule": "Stok Görüntüleme",
    "siparis_ekle": "Sipariş Ekleme",
    "siparis_guncelle": "Sipariş Güncelleme",
    "siparis_sil": "Sipariş Silme",
    "siparis_goruntule": "Sipariş Görüntüleme",
    "odeme_ekle": "Ödeme Ekleme",
    "odeme_iptal": "Ödeme İptal",
    "odeme_goruntule": "Ödeme Görüntüleme",
    "hesap_kapat": "Hesap Kapatma",
    "adisyon_yonet": "Adisyon Yönetimi",
    "mutfak_yonet": "Mutfak Yönetimi",
    "masa_yonet": "Masa Yönetimi",
    "gider_ekle": "Gider Ekleme",
    "gider_guncelle": "Gider Güncelleme",
    "gider_sil": "Gider Silme",
    "gider_goruntule": "Gider Görüntüleme",
    "rapor_goruntule": "Rapor Görüntüleme",
    "rapor_export": "Rapor Export (Excel/PDF)",
    "personel_yonet": "Personel Yönetimi",
    "personel_goruntule": "Personel Görüntüleme",
    "analytics_goruntule": "Analitik Görüntüleme",
    "bi_assistant": "İşletme Asistanı",
    "ayarlar_yonet": "Ayarlar Yönetimi",
}

# Rol bazlı varsayılan izinler
DEFAULT_PERMISSIONS_BY_ROLE = {
    "admin": [
        "menu_ekle", "menu_guncelle", "menu_sil", "menu_varyasyon_yonet",
        "stok_ekle", "stok_guncelle", "stok_sil", "stok_goruntule",
        "siparis_ekle", "siparis_guncelle", "siparis_goruntule",
        "odeme_ekle", "odeme_goruntule", "hesap_kapat", "adisyon_yonet",
        "mutfak_yonet", "masa_yonet",
        "gider_ekle", "gider_guncelle", "gider_sil", "gider_goruntule",
        "rapor_goruntule", "rapor_export",
        "personel_goruntule", "analytics_goruntule", "bi_assistant",
    ],
    "operator": [
        "menu_goruntule", "stok_goruntule",
        "siparis_ekle", "siparis_guncelle", "siparis_goruntule",
        "odeme_ekle", "odeme_goruntule", "hesap_kapat", "adisyon_yonet",
        "mutfak_yonet", "masa_yonet",
        "rapor_goruntule",
    ],
    "barista": [
        "menu_goruntule", "stok_goruntule",
        "siparis_ekle", "siparis_goruntule",
        "odeme_ekle", "odeme_goruntule",
        "mutfak_yonet",
    ],
    "waiter": [
        "menu_goruntule",
        "siparis_ekle", "siparis_goruntule",
        "masa_yonet",
    ],
}


class UserPermissionIn(BaseModel):
    username: str
    permissions: Dict[str, bool] = Field(
        default_factory=dict,
        description="İzin anahtarları ve aktif/pasif durumları"
    )


class UserPermissionOut(BaseModel):
    username: str
    permissions: Dict[str, bool]
    available_permissions: Dict[str, str]


@router.get("/users/{username}/permissions", response_model=UserPermissionOut)
async def get_user_permissions(
    username: str,
    _: Dict[str, Any] = Depends(get_current_user)
):
    """Kullanıcının mevcut izinlerini getir"""
    # Kullanıcının mevcut izinlerini al
    rows = await db.fetch_all(
        """
        SELECT permission_key, enabled
        FROM user_permissions
        WHERE username = :u
        """,
        {"u": username},
    )
    
    permissions = {r["permission_key"]: r["enabled"] for r in rows}
    
    # Eğer kullanıcının hiç izni yoksa, rolüne göre varsayılan izinleri kontrol et
    if not permissions:
        user_row = await db.fetch_one(
            "SELECT role FROM users WHERE username = :u",
            {"u": username},
        )
        if user_row:
            role = user_row["role"]
            default_perms = DEFAULT_PERMISSIONS_BY_ROLE.get(role, [])
            permissions = {perm: True for perm in default_perms}
    
    return {
        "username": username,
        "permissions": permissions,
        "available_permissions": PERMISSION_KEYS,
    }


@router.put("/users/{username}/permissions", response_model=UserPermissionOut)
async def update_user_permissions(
    username: str,
    payload: UserPermissionIn,
    _: Dict[str, Any] = Depends(get_current_user)
):
    """Kullanıcının izinlerini güncelle"""
    # Kullanıcının var olduğunu kontrol et
    user_row = await db.fetch_one(
        "SELECT id, role FROM users WHERE username = :u",
        {"u": username},
    )
    if not user_row:
        raise HTTPException(status_code=404, detail=f"Kullanıcı bulunamadı: {username}")
    
    # Mevcut izinleri sil
    await db.execute(
        "DELETE FROM user_permissions WHERE username = :u",
        {"u": username},
    )
    
    # Yeni izinleri ekle (sadece enabled=True olanları ekle)
    if payload.permissions:
        for perm_key, enabled in payload.permissions.items():
            if perm_key in PERMISSION_KEYS and enabled:
                await db.execute(
                    """
                    INSERT INTO user_permissions (username, permission_key, enabled)
                    VALUES (:u, :key, :enabled)
                    ON CONFLICT (username, permission_key) DO UPDATE
                       SET enabled = EXCLUDED.enabled
                    """,
                    {"u": username, "key": perm_key, "enabled": True},
                )
    
    # Güncellenmiş izinleri döndür
    rows = await db.fetch_all(
        """
        SELECT permission_key, enabled
        FROM user_permissions
        WHERE username = :u
        """,
        {"u": username},
    )
    
    permissions = {r["permission_key"]: r["enabled"] for r in rows}
    
    return {
        "username": username,
        "permissions": permissions,
        "available_permissions": PERMISSION_KEYS,
    }


@router.get("/permissions/available", response_model=Dict[str, str])
async def get_available_permissions(_: Dict[str, Any] = Depends(get_current_user)):
    """Tüm mevcut izin anahtarlarını listele"""
    return PERMISSION_KEYS


@router.get("/permissions/role-defaults/{role}", response_model=List[str])
async def get_role_default_permissions(
    role: str,
    _: Dict[str, Any] = Depends(get_current_user)
):
    """Rol için varsayılan izinleri getir"""
    return DEFAULT_PERMISSIONS_BY_ROLE.get(role, [])


# ---- Hızlı İşletme Kurulumu ----
class QuickSetupIn(BaseModel):
    isletme_ad: str = Field(min_length=1)
    isletme_vergi_no: Optional[str] = None
    isletme_telefon: Optional[str] = None
    sube_ad: str = Field(min_length=1, default="Merkez Şube")
    admin_username: str = Field(min_length=1)
    admin_password: str = Field(min_length=6)
    plan_type: str = Field(default="basic")  # basic, pro, enterprise
    ayllik_fiyat: float = Field(default=0.0, ge=0)
    domain: Optional[str] = None
    app_name: Optional[str] = None
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None


@router.post("/quick-setup")
async def quick_setup(
    payload: QuickSetupIn,
    _: Dict[str, Any] = Depends(get_current_user)
):
    """
    Hızlı işletme kurulumu: İşletme + Şube + Admin kullanıcı + Abonelik + Özelleştirme
    """
    from datetime import datetime, timedelta
    from ..core.security import hash_password
    import json
    
    async with db.transaction():
        # 1. İşletme oluştur
        isletme = await db.fetch_one(
            """
            INSERT INTO isletmeler (ad, vergi_no, telefon, aktif)
            VALUES (:ad, :vergi_no, :telefon, TRUE)
            RETURNING id
            """,
            {
                "ad": payload.isletme_ad,
                "vergi_no": payload.isletme_vergi_no,
                "telefon": payload.isletme_telefon,
            },
        )
        isletme_id = isletme["id"]
        
        # 2. Şube oluştur
        sube = await db.fetch_one(
            """
            INSERT INTO subeler (isletme_id, ad, aktif)
            VALUES (:isletme_id, :ad, TRUE)
            RETURNING id
            """,
            {
                "isletme_id": isletme_id,
                "ad": payload.sube_ad,
            },
        )
        sube_id = sube["id"]
        
        # 3. Admin kullanıcı oluştur
        sifre_hash = hash_password(payload.admin_password)
        await db.execute(
            """
            INSERT INTO users (username, sifre_hash, role, aktif)
            VALUES (:username, :sifre_hash, 'admin', TRUE)
            ON CONFLICT (username) DO UPDATE
               SET sifre_hash = EXCLUDED.sifre_hash,
                   role = EXCLUDED.role,
                   aktif = TRUE
            """,
            {
                "username": payload.admin_username,
                "sifre_hash": sifre_hash,
            },
        )
        
        # 4. Abonelik oluştur
        subscription = await db.fetch_one(
            """
            INSERT INTO subscriptions (
                isletme_id, plan_type, status, max_subeler, max_kullanicilar,
                max_menu_items, ayllik_fiyat, trial_baslangic, trial_bitis,
                baslangic_tarihi, otomatik_yenileme
            )
            VALUES (
                :isletme_id, :plan_type, 'active', 
                CASE WHEN :plan_type = 'basic' THEN 1 WHEN :plan_type = 'pro' THEN 5 ELSE 999 END,
                CASE WHEN :plan_type = 'basic' THEN 5 WHEN :plan_type = 'pro' THEN 20 ELSE 999 END,
                CASE WHEN :plan_type = 'basic' THEN 100 WHEN :plan_type = 'pro' THEN 500 ELSE 9999 END,
                :ayllik_fiyat,
                CASE WHEN :plan_type = 'basic' THEN NOW() ELSE NULL END,
                CASE WHEN :plan_type = 'basic' THEN NOW() + INTERVAL '14 days' ELSE NULL END,
                NOW(), TRUE
            )
            RETURNING id
            """,
            {
                "isletme_id": isletme_id,
                "plan_type": payload.plan_type,
                "ayllik_fiyat": payload.ayllik_fiyat,
            },
        )
        
        # 5. Özelleştirme oluştur (varsa)
        if payload.domain or payload.app_name or payload.logo_url or payload.primary_color:
            await db.execute(
                """
                INSERT INTO tenant_customizations (
                    isletme_id, domain, app_name, logo_url, primary_color
                )
                VALUES (:isletme_id, :domain, :app_name, :logo_url, :primary_color)
                ON CONFLICT (isletme_id) DO UPDATE
                   SET domain = EXCLUDED.domain,
                       app_name = EXCLUDED.app_name,
                       logo_url = EXCLUDED.logo_url,
                       primary_color = EXCLUDED.primary_color,
                       updated_at = NOW()
                """,
                {
                    "isletme_id": isletme_id,
                    "domain": payload.domain,
                    "app_name": payload.app_name,
                    "logo_url": payload.logo_url,
                    "primary_color": payload.primary_color or "#3b82f6",
                },
            )
    
    return {
        "ok": True,
        "isletme_id": isletme_id,
        "sube_id": sube_id,
        "subscription_id": subscription["id"],
        "admin_username": payload.admin_username,
        "message": "İşletme başarıyla kuruldu",
    }


@router.get("/dashboard/stats")
async def dashboard_stats(_: Dict[str, Any] = Depends(get_current_user)):
    """Super admin dashboard istatistikleri"""
    # Toplam işletme sayısı
    total_isletme = await db.fetch_one("SELECT COUNT(*) as count FROM isletmeler")
    
    # Aktif işletme sayısı
    active_isletme = await db.fetch_one("SELECT COUNT(*) as count FROM isletmeler WHERE aktif = TRUE")
    
    # Toplam şube sayısı
    total_sube = await db.fetch_one("SELECT COUNT(*) as count FROM subeler")
    
    # Toplam kullanıcı sayısı
    total_user = await db.fetch_one("SELECT COUNT(*) as count FROM users")
    
    # Aktif abonelik sayısı
    active_subscription = await db.fetch_one(
        "SELECT COUNT(*) as count FROM subscriptions WHERE status = 'active'"
    )
    
    # Bu ay toplam gelir
    this_month_revenue = await db.fetch_one(
        """
        SELECT COALESCE(SUM(tutar), 0) as total
        FROM payments
        WHERE durum = 'completed'
          AND DATE_TRUNC('month', odeme_tarihi) = DATE_TRUNC('month', CURRENT_DATE)
        """
    )
    
    # Bekleyen ödemeler
    pending_payments = await db.fetch_one(
        """
        SELECT COALESCE(SUM(tutar), 0) as total, COUNT(*) as count
        FROM payments
        WHERE durum = 'pending'
        """
    )
    
    # Plan dağılımı
    plan_distribution = await db.fetch_all(
        """
        SELECT plan_type, COUNT(*) as count
        FROM subscriptions
        WHERE status = 'active'
        GROUP BY plan_type
        """
    )
    
    return {
        "isletmeler": {
            "total": total_isletme["count"] if total_isletme else 0,
            "active": active_isletme["count"] if active_isletme else 0,
        },
        "subeler": {
            "total": total_sube["count"] if total_sube else 0,
        },
        "kullanicilar": {
            "total": total_user["count"] if total_user else 0,
        },
        "abonelikler": {
            "active": active_subscription["count"] if active_subscription else 0,
            "plan_distribution": [dict(r) for r in plan_distribution],
        },
        "finansal": {
            "this_month_revenue": float(this_month_revenue["total"]) if this_month_revenue else 0.0,
            "pending_payments": {
                "total": float(pending_payments["total"]) if pending_payments else 0.0,
                "count": pending_payments["count"] if pending_payments else 0,
            },
        },
    }

