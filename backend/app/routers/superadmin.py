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
async def tenants_list(
    limit: int = Query(50, ge=1, le=500, description="Sayfa başına kayıt sayısı"),
    offset: int = Query(0, ge=0, description="Atlanacak kayıt sayısı"),
    _: Dict[str, Any] = Depends(get_current_user),
):
    import logging
    q = """
    SELECT id, ad, vergi_no, telefon, aktif
    FROM isletmeler
    ORDER BY id DESC
    LIMIT :limit OFFSET :offset
    """
    results = await db.fetch_all(q, {"limit": limit, "offset": offset})
    logging.info(f"[TENANTS_LIST] Query returned {len(results)} tenants")
    for r in results:
        logging.info(f"[TENANTS_LIST] Tenant: id={r['id']}, ad={r['ad']}, aktif={r['aktif']}")
    return results


@router.get("/tenants/{id}")
async def tenant_detail(id: int, _: Dict[str, Any] = Depends(get_current_user)):
    """Tenant (işletme) detay bilgileri: genel bilgiler, abonelik, kullanıcılar, şubeler, customization, istatistikler"""
    import logging
    import traceback
    
    try:
        # 1. İşletme bilgileri
        isletme = await db.fetch_one(
            """
            SELECT id, ad, vergi_no, telefon, aktif, created_at
            FROM isletmeler
            WHERE id = :id
            """,
            {"id": id}
        )
        
        if not isletme:
            raise HTTPException(404, "İşletme bulunamadı")
        
        # 2. Abonelik bilgileri
        subscription = await db.fetch_one(
            """
            SELECT 
                id, plan_type, status, max_subeler, max_kullanicilar, max_menu_items,
                ayllik_fiyat, trial_baslangic, trial_bitis, baslangic_tarihi, bitis_tarihi,
                otomatik_yenileme
            FROM subscriptions
            WHERE isletme_id = :id
            ORDER BY id DESC
            LIMIT 1
            """,
            {"id": id}
        )
        
        # 3. Şubeler
        subeler = await db.fetch_all(
            """
            SELECT id, ad, adres, telefon, aktif, created_at
            FROM subeler
            WHERE isletme_id = :id
            ORDER BY id
            """,
            {"id": id}
        )
        
        # 4. Kullanıcılar (bu işletmeye ait)
        users = await db.fetch_all(
            """
            SELECT id, username, role, aktif, created_at
            FROM users
            WHERE tenant_id = :id
            ORDER BY created_at DESC
            """,
            {"id": id}
        )
        
        # 5. Customization
        # Önce kolonların varlığını kontrol et
        column_check = await db.fetch_one(
            """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'tenant_customizations' 
            AND column_name IN ('openai_api_key', 'openai_model')
            """
        )
        
        has_openai_columns = column_check is not None
        
        # Kolonlar varsa dahil et, yoksa sadece mevcut kolonları çek
        if has_openai_columns:
            customization = await db.fetch_one(
                """
                SELECT domain, app_name, logo_url, primary_color, secondary_color,
                       openai_api_key, openai_model
                FROM tenant_customizations
                WHERE isletme_id = :id
                """,
                {"id": id}
            )
        else:
            customization = await db.fetch_one(
                """
                SELECT domain, app_name, logo_url, primary_color, secondary_color
                FROM tenant_customizations
                WHERE isletme_id = :id
                """,
                {"id": id}
            )
            # Kolonlar yoksa None olarak ekle
            if customization:
                customization_dict = dict(customization) if hasattr(customization, 'keys') else customization
                customization_dict["openai_api_key"] = None
                customization_dict["openai_model"] = None
                customization = customization_dict
        
        # API key'i kısalt (güvenlik için sadece ilk 8 ve son 4 karakteri göster)
        if customization:
            customization_dict = dict(customization) if hasattr(customization, 'keys') else customization
            if customization_dict.get("openai_api_key"):
                api_key = str(customization_dict["openai_api_key"])
                if api_key and api_key != "None" and len(api_key) > 12:
                    customization_dict["openai_api_key"] = f"{api_key[:8]}...{api_key[-4:]}"
                elif api_key and api_key != "None":
                    customization_dict["openai_api_key"] = "***"
            customization = customization_dict
        
        # 6. İstatistikler
        # Toplam sipariş sayısı
        siparis_count = await db.fetch_one(
            """
            SELECT COUNT(*) as count
            FROM siparisler s
            JOIN subeler sub ON s.sube_id = sub.id
            WHERE sub.isletme_id = :id
            """,
            {"id": id}
        )
        
        # Toplam gelir
        revenue = await db.fetch_one(
            """
            SELECT COALESCE(SUM(o.tutar), 0) as total
            FROM odemeler o
            JOIN adisyons a ON o.adisyon_id = a.id
            JOIN subeler sub ON a.sube_id = sub.id
            WHERE sub.isletme_id = :id
              AND o.iptal = FALSE
            """,
            {"id": id}
        )
        
        # Toplam menu item sayısı
        menu_count = await db.fetch_one(
            """
            SELECT COUNT(*) as count
            FROM menu m
            JOIN subeler sub ON m.sube_id = sub.id
            WHERE sub.isletme_id = :id AND m.aktif = TRUE
            """,
            {"id": id}
        )
        
        # Son sipariş tarihi
        last_order = await db.fetch_one(
            """
            SELECT MAX(s.created_at) as last_order_date
            FROM siparisler s
            JOIN subeler sub ON s.sube_id = sub.id
            WHERE sub.isletme_id = :id
            """,
            {"id": id}
        )
        
        # Result hazırla - Record objelerini güvenli şekilde dict'e çevir
        def safe_dict(obj):
            if not obj:
                return None
            if isinstance(obj, dict):
                return obj
            if hasattr(obj, 'keys'):
                return dict(obj)
            return obj
        
        def safe_get(obj, key, default=None):
            if not obj:
                return default
            obj_dict = safe_dict(obj)
            if isinstance(obj_dict, dict):
                return obj_dict.get(key, default)
            return getattr(obj, key, default)
        
        # İstatistikleri güvenli şekilde hesapla
        siparis_sayisi = 0
        if siparis_count:
            count_val = safe_get(siparis_count, "count") or safe_get(siparis_count, "count", 0)
            try:
                siparis_sayisi = int(count_val) if count_val is not None else 0
            except (ValueError, TypeError):
                siparis_sayisi = 0
        
        toplam_gelir = 0.0
        if revenue:
            total_val = safe_get(revenue, "total") or safe_get(revenue, "total", 0.0)
            try:
                toplam_gelir = float(total_val) if total_val is not None else 0.0
            except (ValueError, TypeError):
                toplam_gelir = 0.0
        
        menu_item_sayisi = 0
        if menu_count:
            count_val = safe_get(menu_count, "count") or safe_get(menu_count, "count", 0)
            try:
                menu_item_sayisi = int(count_val) if count_val is not None else 0
            except (ValueError, TypeError):
                menu_item_sayisi = 0
        
        son_siparis_tarihi = None
        if last_order:
            last_order_date = safe_get(last_order, "last_order_date")
            if last_order_date:
                try:
                    if hasattr(last_order_date, 'isoformat'):
                        son_siparis_tarihi = last_order_date.isoformat()
                    else:
                        son_siparis_tarihi = str(last_order_date)
                except (AttributeError, TypeError):
                    son_siparis_tarihi = None
        
        result = {
            "isletme": safe_dict(isletme),
            "subscription": safe_dict(subscription),
            "subeler": [safe_dict(s) for s in subeler] if subeler else [],
            "kullanicilar": [safe_dict(u) for u in users] if users else [],
            "customization": customization if customization else None,
            "istatistikler": {
                "siparis_sayisi": siparis_sayisi,
                "toplam_gelir": toplam_gelir,
                "menu_item_sayisi": menu_item_sayisi,
                "kullanici_sayisi": len(users) if users else 0,
                "sube_sayisi": len(subeler) if subeler else 0,
                "son_siparis_tarihi": son_siparis_tarihi,
            }
        }
        
        return result
    except Exception as e:
        error_msg = f"Tenant detail error for id={id}: {str(e)}"
        error_trace = traceback.format_exc()
        logging.error(f"[TENANT_DETAIL] {error_msg}\n{error_trace}")
        raise HTTPException(status_code=500, detail=f"İşletme detayı yüklenirken hata oluştu: {str(e)}")


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
    """İşletmeyi ve tüm ilişkili verilerini sil (cascade delete)"""
    import logging
    
    # İşletme var mı kontrol et
    isletme = await db.fetch_one(
        "SELECT id, ad FROM isletmeler WHERE id = :id",
        {"id": id}
    )
    if not isletme:
        raise HTTPException(status_code=404, detail="İşletme bulunamadı")
    
    # Record objesini dictionary'ye çevir
    isletme_dict = dict(isletme) if hasattr(isletme, 'keys') else isletme
    isletme_ad = isletme_dict.get('ad') if isinstance(isletme_dict, dict) else getattr(isletme, 'ad', 'Bilinmeyen')
    
    logging.info(f"[TENANT_DELETE] İşletme siliniyor: id={id}, ad={isletme_ad}")
    
    # Transaction içinde cascade delete
    # Foreign key'ler ON DELETE CASCADE olduğu için otomatik silinir:
    # - subeler (ve altındaki menu, siparisler, odemeler, adisyons)
    # - subscriptions
    # - payments
    # - tenant_customizations
    # users tablosunda tenant_id NULL olur (ON DELETE SET NULL)
    
    await db.execute("DELETE FROM isletmeler WHERE id = :id", {"id": id})
    
    logging.info(f"[TENANT_DELETE] İşletme ve ilişkili veriler silindi: id={id}")
    return {"ok": True, "message": f"İşletme '{isletme_ad}' ve tüm ilişkili veriler silindi"}


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


@router.get("/users/{username}/permissions", response_model=UserPermissionOut, dependencies=[Depends(require_roles({"admin", "super_admin"}))])
async def get_user_permissions(
    username: str,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Kullanıcının mevcut izinlerini getir"""
    import logging
    
    user_role = user.get("role")
    user_tenant_id = user.get("tenant_id")
    switched_tenant_id = user.get("switched_tenant_id")
    effective_tenant_id = switched_tenant_id if switched_tenant_id else user_tenant_id
    
    # Normal admin sadece kendi tenant'ındaki kullanıcıların yetkilerini görebilir
    if user_role != "super_admin":
        # Hedef kullanıcının tenant_id'sini kontrol et
        target_user = await db.fetch_one(
            "SELECT tenant_id FROM users WHERE username = :u",
            {"u": username},
        )
        if not target_user:
            raise HTTPException(status_code=404, detail=f"Kullanıcı bulunamadı: {username}")
        
        target_user_dict = dict(target_user) if hasattr(target_user, 'keys') else target_user
        target_tenant_id = target_user_dict.get("tenant_id") if isinstance(target_user_dict, dict) else (getattr(target_user, "tenant_id", None) if target_user else None)
        
        # Normal admin sadece kendi tenant'ındaki kullanıcıları görebilir
        if target_tenant_id != effective_tenant_id:
            logging.warning(f"[GET_USER_PERMISSIONS] Admin {user.get('username')} tried to access permissions for user {username} from different tenant: {target_tenant_id} != {effective_tenant_id}")
            raise HTTPException(
                status_code=403,
                detail="Bu kullanıcının yetkilerini görüntüleyemezsiniz. Sadece kendi işletmenizdeki kullanıcıların yetkilerini görebilirsiniz."
            )
    
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


@router.put("/users/{username}/permissions", response_model=UserPermissionOut, dependencies=[Depends(require_roles({"admin", "super_admin"}))])
async def update_user_permissions(
    username: str,
    payload: UserPermissionIn,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Kullanıcının izinlerini güncelle"""
    import logging
    
    user_role = user.get("role")
    user_tenant_id = user.get("tenant_id")
    switched_tenant_id = user.get("switched_tenant_id")
    effective_tenant_id = switched_tenant_id if switched_tenant_id else user_tenant_id
    
    # Kullanıcının var olduğunu kontrol et
    user_row = await db.fetch_one(
        "SELECT id, role, tenant_id FROM users WHERE username = :u",
        {"u": username},
    )
    if not user_row:
        raise HTTPException(status_code=404, detail=f"Kullanıcı bulunamadı: {username}")
    
    # Normal admin sadece kendi tenant'ındaki kullanıcıların yetkilerini güncelleyebilir
    if user_role != "super_admin":
        user_row_dict = dict(user_row) if hasattr(user_row, 'keys') else user_row
        target_tenant_id = user_row_dict.get("tenant_id") if isinstance(user_row_dict, dict) else (getattr(user_row, "tenant_id", None) if user_row else None)
        
        # Normal admin sadece kendi tenant'ındaki kullanıcıları güncelleyebilir
        if target_tenant_id != effective_tenant_id:
            logging.warning(f"[UPDATE_USER_PERMISSIONS] Admin {user.get('username')} tried to update permissions for user {username} from different tenant: {target_tenant_id} != {effective_tenant_id}")
            raise HTTPException(
                status_code=403,
                detail="Bu kullanıcının yetkilerini güncelleyemezsiniz. Sadece kendi işletmenizdeki kullanıcıların yetkilerini güncelleyebilirsiniz."
            )
    
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


@router.get("/permissions/available", response_model=Dict[str, str], dependencies=[Depends(require_roles({"admin", "super_admin"}))])
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


# ---- API Kullanım İstatistikleri ----
@router.get("/api-usage")
async def get_api_usage_stats(
    isletme_id: Optional[int] = Query(None, description="İşletme ID (opsiyonel, belirtilmezse tüm işletmeler)"),
    days: int = Query(30, ge=1, le=365, description="Gün sayısı (varsayılan: 30)"),
    api_type: Optional[str] = Query(None, description="API türü (örn: 'openai')"),
    _: Dict[str, Any] = Depends(get_current_user),
):
    """API kullanım istatistiklerini getir"""
    from ..services.api_usage_tracker import get_api_usage_stats as get_stats
    
    stats = await get_stats(
        isletme_id=isletme_id,
        days=days,
        api_type=api_type,
    )
    
    # İşletme adlarını ekle
    for stat in stats:
        if stat.get("isletme_id"):
            isletme_row = await db.fetch_one(
                "SELECT ad FROM isletmeler WHERE id = :id",
                {"id": stat["isletme_id"]}
            )
            if isletme_row:
                isletme_dict = dict(isletme_row) if hasattr(isletme_row, 'keys') else isletme_row
                stat["isletme_ad"] = isletme_dict.get("ad")
    
    return stats


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
    theme: Optional[str] = Field(default="green")  # green, blue, purple, rose
    odeme_turu: Optional[str] = Field(default="odeme_sistemi")  # odeme_sistemi, nakit, havale, kredi_karti
    openai_api_key: Optional[str] = Field(None, description="OpenAI API anahtarı (işletme bazında)")
    openai_model: Optional[str] = Field(default="gpt-4o-mini", description="OpenAI model")


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
        
        # 3. Admin kullanıcı oluştur (tenant_id ile)
        sifre_hash = hash_password(payload.admin_password)
        await db.execute(
            """
            INSERT INTO users (username, sifre_hash, role, tenant_id, aktif)
            VALUES (:username, :sifre_hash, 'admin', :tenant_id, TRUE)
            ON CONFLICT (username) DO UPDATE
               SET sifre_hash = EXCLUDED.sifre_hash,
                   role = EXCLUDED.role,
                   tenant_id = EXCLUDED.tenant_id,
                   aktif = TRUE
            """,
            {
                "username": payload.admin_username,
                "sifre_hash": sifre_hash,
                "tenant_id": isletme_id,
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
        # Tema paketleri
        theme_colors = {
            "green": {"primary": "#00c67f", "secondary": "#00e699"},
            "blue": {"primary": "#2563eb", "secondary": "#3b82f6"},
            "purple": {"primary": "#7c3aed", "secondary": "#8b5cf6"},
            "rose": {"primary": "#e11d48", "secondary": "#f43f5e"},
        }
        
        theme = payload.theme or "green"
        theme_color = theme_colors.get(theme, theme_colors["green"])
        
        if payload.domain or payload.app_name or payload.logo_url or theme or payload.openai_api_key:
            # Kolonların varlığını kontrol et
            column_check = await db.fetch_one(
                """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'tenant_customizations' 
                AND column_name IN ('openai_api_key', 'openai_model')
                """
            )
            
            has_openai_columns = column_check is not None
            
            # Kolonlar varsa dahil et, yoksa sadece mevcut kolonları kullan
            if has_openai_columns:
                await db.execute(
                    """
                    INSERT INTO tenant_customizations (
                        isletme_id, domain, app_name, logo_url, primary_color, secondary_color,
                        openai_api_key, openai_model
                    )
                    VALUES (:isletme_id, :domain, :app_name, :logo_url, :primary_color, :secondary_color,
                            :openai_api_key, :openai_model)
                    ON CONFLICT (isletme_id) DO UPDATE
                       SET domain = EXCLUDED.domain,
                           app_name = EXCLUDED.app_name,
                           logo_url = EXCLUDED.logo_url,
                           primary_color = EXCLUDED.primary_color,
                           secondary_color = EXCLUDED.secondary_color,
                           openai_api_key = EXCLUDED.openai_api_key,
                           openai_model = EXCLUDED.openai_model,
                           updated_at = NOW()
                    """,
                    {
                        "isletme_id": isletme_id,
                        "domain": payload.domain,
                        "app_name": payload.app_name,
                        "logo_url": payload.logo_url,
                        "primary_color": theme_color["primary"],
                        "secondary_color": theme_color["secondary"],
                        "openai_api_key": payload.openai_api_key,
                        "openai_model": payload.openai_model or "gpt-4o-mini",
                    },
                )
            else:
                # Kolonlar yoksa sadece mevcut kolonları kullan
                await db.execute(
                    """
                    INSERT INTO tenant_customizations (
                        isletme_id, domain, app_name, logo_url, primary_color, secondary_color
                    )
                    VALUES (:isletme_id, :domain, :app_name, :logo_url, :primary_color, :secondary_color)
                    ON CONFLICT (isletme_id) DO UPDATE
                       SET domain = EXCLUDED.domain,
                           app_name = EXCLUDED.app_name,
                           logo_url = EXCLUDED.logo_url,
                           primary_color = EXCLUDED.primary_color,
                           secondary_color = EXCLUDED.secondary_color,
                           updated_at = NOW()
                    """,
                    {
                        "isletme_id": isletme_id,
                        "domain": payload.domain,
                        "app_name": payload.app_name,
                        "logo_url": payload.logo_url,
                        "primary_color": theme_color["primary"],
                        "secondary_color": theme_color["secondary"],
                    },
                )
        
        # 6. Ödeme kaydı oluştur (aylık fiyat > 0 ise)
        if payload.ayllik_fiyat > 0:
            odeme_turu = payload.odeme_turu or "odeme_sistemi"
            await db.execute(
                """
                INSERT INTO payments (
                    isletme_id, subscription_id, tutar, odeme_turu, durum,
                    aciklama, odeme_tarihi
                )
                VALUES (
                    :isletme_id, :subscription_id, :tutar, :odeme_turu, 'completed',
                    :aciklama, NOW()
                )
                """,
                {
                    "isletme_id": isletme_id,
                    "subscription_id": subscription["id"],
                    "tutar": payload.ayllik_fiyat,
                    "odeme_turu": odeme_turu,
                    "aciklama": f"İlk kurulum - Aylık abonelik ücreti ({payload.plan_type})",
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
    
    # Pasif işletme sayısı
    passive_isletme = await db.fetch_one("SELECT COUNT(*) as count FROM isletmeler WHERE aktif = FALSE")
    
    # Toplam şube sayısı
    total_sube = await db.fetch_one("SELECT COUNT(*) as count FROM subeler")
    
    # Toplam kullanıcı sayısı
    total_user = await db.fetch_one("SELECT COUNT(*) as count FROM users")
    
    # Arıza ve servis talepleri sayısı (şimdilik 0, gelecekte ticket/support tablosu eklendiğinde güncellenecek)
    # TODO: Arıza ve servis talepleri için bir tablo oluşturulduğunda bu sorgu güncellenecek
    ariza_servis_talepleri = 0  # Gelecekte: SELECT COUNT(*) FROM support_tickets WHERE durum IN ('pending', 'in_progress')
    
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
            "passive": passive_isletme["count"] if passive_isletme else 0,
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
        "ariza_servis_talepleri": ariza_servis_talepleri,
        "finansal": {
            "this_month_revenue": float(this_month_revenue["total"]) if this_month_revenue else 0.0,
            "pending_payments": {
                "total": float(pending_payments["total"]) if pending_payments else 0.0,
                "count": pending_payments["count"] if pending_payments else 0,
            },
        },
    }

