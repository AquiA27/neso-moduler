# backend/app/routers/menu.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Mapping
import csv, io, unicodedata, secrets
from pathlib import Path

from ..core.config import settings
from ..core.deps import get_current_user, get_sube_id, require_roles
from ..core.cache import cache, cache_key
from ..db.database import db

router = APIRouter(prefix="/menu", tags=["Menu"])

# ---------- Yardımcı: güvenli normalizasyon (maketrans YOK) ----------
def normalize_name(s: str) -> str:
    if s is None:
        return ""
    s = s.casefold().strip()
    repl = {
        "ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u",
        "â": "a", "ê": "e", "î": "i", "ô": "o", "û": "u"
    }
    for k, v in repl.items():
        s = s.replace(k, v)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(s.split())

def row_to_menu_out(row: Mapping[str, Any]) -> Dict[str, Any]:
    data = dict(row)
    return {
        "id": data["id"],
        "ad": data["ad"],
        "fiyat": float(data["fiyat"]) if data.get("fiyat") is not None else 0.0,
        "kategori": data.get("kategori"),
        "aktif": data["aktif"],
        "aciklama": data.get("aciklama"),
        "gorsel_url": data.get("gorsel_url"),
    }

def resolve_media_path(url: Optional[str]) -> Optional[Path]:
    if not url:
        return None
    media_url = settings.MEDIA_URL.rstrip("/")
    cleaned = url.strip()
    if cleaned.startswith("http://") or cleaned.startswith("https://"):
        # Sadece kendi servisimize ait relatif yolu destekliyoruz
        if media_url in cleaned:
            cleaned = cleaned.split(media_url, 1)[-1]
        else:
            return None
    if cleaned.startswith(media_url):
        cleaned = cleaned[len(media_url):]
    cleaned = cleaned.lstrip("/\\")
    return (Path(settings.MEDIA_ROOT) / cleaned).resolve()

# ---------- Modeller ----------
class MenuItemIn(BaseModel):
    ad: str = Field(min_length=1)
    fiyat: float = Field(ge=0)
    kategori: str = Field(min_length=1)
    aktif: bool = True
    aciklama: Optional[str] = None

class VaryasyonOut(BaseModel):
    id: int
    ad: str
    ek_fiyat: float
    sira: int

class MenuItemOut(BaseModel):
    id: int
    ad: str
    fiyat: float
    kategori: Optional[str] = None
    aktif: bool
    aciklama: Optional[str] = None
    gorsel_url: Optional[str] = None
    varyasyonlar: Optional[List["VaryasyonOut"]] = None

class MenuUpdateIn(BaseModel):
    # Hedef kaydı bulmak için (id veya ad kullanılabilir, id önceliklidir)
    id: Optional[int] = Field(default=None, description="Güncellenecek ürün ID'si")
    ad: Optional[str] = Field(default=None, min_length=1, description="Güncellenecek mevcut ürün adı (id yoksa kullanılır)")
    # Güncellenecek alanlar (opsiyonel)
    yeni_ad: Optional[str] = None
    fiyat: Optional[float] = Field(default=None, ge=0)
    kategori: Optional[str] = None
    aktif: Optional[bool] = None
    aciklama: Optional[str] = None

# ---------- Uçlar ----------
@router.post(
    "/ekle",
    response_model=MenuItemOut,
    dependencies=[Depends(require_roles({"admin", "operator", "super_admin"}))]
)
async def menu_ekle(
    item: MenuItemIn,
    current_user: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    # Super admin tenant switching yapıyorsa, tenant_id'yi al
    switched_tenant_id = current_user.get("switched_tenant_id")
    tenant_id = current_user.get("tenant_id")
    effective_tenant_id = switched_tenant_id if switched_tenant_id else tenant_id
    
    import logging
    logging.info(f"[MENU_EKLE] sube_id={sube_id}, effective_tenant_id={effective_tenant_id}, item={item.model_dump()}")
    
    # UNIQUE (sube_id, unaccent(lower(ad))) nedeniyle kopya yazımlar hata verebilir -> INSERT dene, patlarsa UPDATE
    params = {**item.model_dump(), "sid": sube_id}
    try:
        row = await db.fetch_one(
            """
            INSERT INTO menu (sube_id, ad, fiyat, kategori, aktif, aciklama)
            VALUES (:sid, :ad, :fiyat, :kategori, :aktif, :aciklama)
            RETURNING id, ad, fiyat, kategori, aktif, aciklama, gorsel_url
            """,
            params,
        )
        logging.info(f"[MENU_EKLE] Menü eklendi: id={row['id']}, ad={row['ad']}, sube_id={sube_id}")
    except Exception as e:
        # Aynı ürün farklı yazımla varsa (aynı şubede) UPDATE'e düş
        logging.warning(f"[MENU_EKLE] INSERT başarısız, UPDATE deneniyor: {e}")
        row = await db.fetch_one(
            """
            UPDATE menu
               SET fiyat = :fiyat,
                   kategori = :kategori,
                   aktif = :aktif,
                   aciklama = COALESCE(:aciklama, aciklama)
             WHERE sube_id = :sid
               AND unaccent(lower(ad)) = unaccent(lower(:ad))
         RETURNING id, ad, fiyat, kategori, aktif, aciklama, gorsel_url
            """,
            params,
        )
        if not row:
            logging.error(f"[MENU_EKLE] UPDATE başarısız: sube_id={sube_id}, ad={params.get('ad')}")
            raise HTTPException(status_code=400, detail="Menü ekleme/güncelleme başarısız")
        logging.info(f"[MENU_EKLE] Menü güncellendi: id={row['id']}, ad={row['ad']}, sube_id={sube_id}")
    
    # Cache'i temizle (menu listesi değişti) - TÜM tenant'lar ve sube'ler için
    await cache.delete_pattern("menu:liste:*")
    logging.info(f"[MENU_EKLE] Cache temizlendi: pattern=menu:liste:*")
    
    return row_to_menu_out(row)

@router.get("/liste", response_model=List[MenuItemOut])
async def menu_liste(
    sadece_aktif: bool = Query(False, description="true ise sadece aktif ürünler"),
    limit: int = Query(100, ge=1, le=500, description="Sayfa başına kayıt sayısı"),
    offset: int = Query(0, ge=0, description="Atlanacak kayıt sayısı"),
    varyasyonlar_dahil: bool = Query(False, description="true ise varyasyonları da getir"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    # Super admin tenant switching yapıyorsa, tenant_id'yi al
    switched_tenant_id = current_user.get("switched_tenant_id")
    tenant_id = current_user.get("tenant_id")
    effective_tenant_id = switched_tenant_id if switched_tenant_id else tenant_id
    
    # Cache key oluştur (tenant_id ve sube_id dahil - her tenant için ayrı cache)
    cache_key_str = cache_key("menu:liste", effective_tenant_id, sube_id, sadece_aktif, varyasyonlar_dahil, limit, offset)
    
    # Cache'den kontrol et
    cached_result = await cache.get(cache_key_str)
    if cached_result is not None:
        import logging
        logging.info(f"[MENU_LISTE] Cache hit: sube_id={sube_id}, effective_tenant_id={effective_tenant_id}")
        return cached_result
    
    # Super admin tenant switching yapıyorsa (effective_tenant_id varsa), şubenin o tenant'a ait olduğunu doğrula
    # Ama "Tüm İşletmeler" seçildiğinde (effective_tenant_id null) tenant kontrolü yapma
    if effective_tenant_id:
        role = (current_user.get("role") or "").lower()
        if role == "super_admin":
            # Şubenin tenant'a ait olduğunu kontrol et
            sube_check = await db.fetch_one(
                "SELECT id, isletme_id FROM subeler WHERE id = :sid",
                {"sid": sube_id},
            )
            if sube_check:
                # sube_check'ü dict'e çevir (Record objesi olabilir)
                sube_check_dict = dict(sube_check) if hasattr(sube_check, 'keys') else sube_check
                sube_isletme_id = sube_check_dict.get("isletme_id") if isinstance(sube_check_dict, dict) else (getattr(sube_check, "isletme_id", None) if sube_check else None)
                
                # Şube var, tenant'a ait mi kontrol et
                if sube_isletme_id != effective_tenant_id:
                    # Şube başka tenant'a ait - o tenant'ın şubelerini kontrol et
                    tenant_sube = await db.fetch_one(
                        """
                        SELECT id FROM subeler 
                        WHERE isletme_id = :tid AND aktif = TRUE 
                        ORDER BY id ASC 
                        LIMIT 1
                        """,
                        {"tid": effective_tenant_id},
                    )
                    if tenant_sube:
                        # tenant_sube'yi dict'e çevir
                        tenant_sube_dict = dict(tenant_sube) if hasattr(tenant_sube, 'keys') else tenant_sube
                        new_sube_id = tenant_sube_dict.get("id") if isinstance(tenant_sube_dict, dict) else (getattr(tenant_sube, "id", None) if tenant_sube else None)
                        if new_sube_id:
                            # Tenant'ın şubesi var, sube_id'yi güncelle
                            sube_id = new_sube_id
                            import logging
                            logging.info(f"[MENU_LISTE] Tenant {effective_tenant_id} için şube güncellendi: {sube_id}")
                    else:
                        # Tenant'ın şubesi yok - boş menu dönecek (hata verme)
                        import logging
                        logging.warning(f"[MENU_LISTE] Tenant {effective_tenant_id} için şube bulunamadı, boş menu dönecek")
                        return []  # Boş menu döndür
            else:
                # Şube yok - tenant'ın şubesini kontrol et
                tenant_sube = await db.fetch_one(
                    """
                    SELECT id FROM subeler 
                    WHERE isletme_id = :tid AND aktif = TRUE 
                    ORDER BY id ASC 
                    LIMIT 1
                    """,
                    {"tid": effective_tenant_id},
                )
                if tenant_sube:
                    sube_id = tenant_sube["id"]
                    import logging
                    logging.info(f"[MENU_LISTE] Tenant {effective_tenant_id} için şube bulundu: {sube_id}")
                else:
                    # Tenant'ın şubesi yok - boş menu dönecek
                    import logging
                    logging.warning(f"[MENU_LISTE] Tenant {effective_tenant_id} için şube bulunamadı, boş menu dönecek")
                    return []  # Boş menu döndür
    if varyasyonlar_dahil:
        # N+1 query düzeltmesi: Tek JOIN sorgusu ile tüm varyasyonları getir
        # Önce menu'leri pagination ile al, sonra varyasyonları JOIN ile getir
        rows = await db.fetch_all(
            """
            SELECT 
                m.id, m.ad, m.fiyat, m.kategori, m.aktif, m.aciklama, m.gorsel_url,
                mv.id as var_id, mv.ad as var_ad, mv.ek_fiyat as var_ek_fiyat, mv.sira as var_sira
            FROM (
                SELECT id, ad, fiyat, kategori, aktif, aciklama, gorsel_url
                FROM menu
                WHERE sube_id = :sid
                """ + (" AND aktif = TRUE" if sadece_aktif else "") + """
                ORDER BY kategori NULLS LAST, ad ASC
                LIMIT :limit OFFSET :offset
            ) m
            LEFT JOIN menu_varyasyonlar mv ON m.id = mv.menu_id AND mv.aktif = TRUE
            ORDER BY m.kategori NULLS LAST, m.ad ASC, mv.sira ASC, mv.ad ASC
            """,
            {"sid": sube_id, "limit": limit, "offset": offset},
        )
        
        # Grupla: menu_id -> variations list
        items_dict: Dict[int, Dict[str, Any]] = {}
        for r in rows:
            menu_id = r["id"]
            if menu_id not in items_dict:
                items_dict[menu_id] = {
                    **row_to_menu_out(r),
                    "varyasyonlar": [],
                }
            if r["var_id"]:
                items_dict[menu_id]["varyasyonlar"].append({
                    "id": r["var_id"],
                    "ad": r["var_ad"],
                    "ek_fiyat": float(r["var_ek_fiyat"] or 0),
                    "sira": r["var_sira"],
                })
        result = list(items_dict.values())
    else:
        base = """
        SELECT id, ad, fiyat, kategori, aktif, aciklama, gorsel_url 
        FROM menu 
        WHERE sube_id = :sid
        """
        params: Dict[str, Any] = {"limit": limit, "offset": offset, "sid": sube_id}
        if sadece_aktif:
            base += " AND aktif = TRUE"
        base += " ORDER BY ad ASC LIMIT :limit OFFSET :offset"
        rows = await db.fetch_all(base, params)
        result = [row_to_menu_out(r) for r in rows]
    
    # Cache'e kaydet (5 dakika TTL)
    await cache.set(cache_key_str, result, ttl=300)
    
    # Debug log (production'da da yararlı - sorun giderme için)
    import logging
    logging.info(f"[MENU_LISTE] sube_id={sube_id}, effective_tenant_id={effective_tenant_id}, items_count={len(result)}, sadece_aktif={sadece_aktif}")
    
    # Eğer sonuç boşsa ve tenant var ise, şube kontrolü yap
    if len(result) == 0 and effective_tenant_id:
        # Tenant'ın şubelerini kontrol et
        subeler_check = await db.fetch_all(
            "SELECT id, ad, aktif FROM subeler WHERE isletme_id = :tid ORDER BY id",
            {"tid": effective_tenant_id},
        )
        logging.warning(f"[MENU_LISTE] Boş sonuç - Tenant {effective_tenant_id} şubeleri: {[dict(s) for s in subeler_check] if subeler_check else 'yok'}")
    
    return result

@router.patch(
    "/guncelle",
    response_model=MenuItemOut,
    dependencies=[Depends(require_roles({"admin", "operator", "super_admin"}))]
)
async def menu_guncelle(
    payload: MenuUpdateIn,
    _: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    # id veya ad ile ürünü bul (id önceliklidir)
    if not payload.id and not payload.ad:
        raise HTTPException(status_code=400, detail="id veya ad belirtilmelidir")
    
    if payload.id:
        # id ile bul
        mevcut = await db.fetch_one(
            """
            SELECT id, ad FROM menu
             WHERE id = :id AND sube_id = :sid
             LIMIT 1
            """,
            {"id": payload.id, "sid": sube_id},
        )
        if not mevcut:
            raise HTTPException(
                status_code=404, 
                detail=f"Ürün bulunamadı: ID={payload.id} (Şube ID: {sube_id})"
            )
        mevcut_ad = mevcut["ad"]
        where_clause = "id = :id AND sube_id = :sid"
        where_params = {"id": payload.id, "sid": sube_id}
        
        # Eğer id varsa ve payload.ad mevcut ad'dan farklıysa, bu yeni_ad olarak kabul edilir
        if payload.ad and payload.ad.strip() and normalize_name(payload.ad) != normalize_name(mevcut_ad):
            # Frontend'den gelen ad, mevcut ad'dan farklı -> yeni_ad olarak kullan
            if payload.yeni_ad is None:
                payload.yeni_ad = payload.ad
    else:
        # ad ile bul
        mevcut = await db.fetch_one(
            """
            SELECT id, ad FROM menu
             WHERE sube_id = :sid
               AND unaccent(lower(ad)) = unaccent(lower(:ad))
             LIMIT 1
            """,
            {"sid": sube_id, "ad": payload.ad},
        )
        if not mevcut:
            # Şubede mevcut ürünleri kontrol et (daha iyi hata mesajı için)
            mevcut_urunler = await db.fetch_all(
                """
                SELECT ad FROM menu
                 WHERE sube_id = :sid
                 ORDER BY ad
                 LIMIT 10
                """,
                {"sid": sube_id},
            )
            urun_listesi = ", ".join([r["ad"] for r in mevcut_urunler]) if mevcut_urunler else "Henüz ürün yok"
            raise HTTPException(
                status_code=404, 
                detail=f"Ürün bulunamadı: '{payload.ad}' (Şube ID: {sube_id}). Mevcut ürünler: {urun_listesi}"
            )
        mevcut_ad = mevcut["ad"]
        where_clause = "sube_id = :sid AND unaccent(lower(ad)) = unaccent(lower(:ad))"
        where_params = {"sid": sube_id, "ad": payload.ad}

    fields = []
    values: Dict[str, Any] = where_params.copy()
    if payload.yeni_ad is not None:
        fields.append("ad = :yeni_ad")
        values["yeni_ad"] = payload.yeni_ad
    if payload.fiyat is not None:
        fields.append("fiyat = :fiyat")
        values["fiyat"] = payload.fiyat
    if payload.kategori is not None:
        fields.append("kategori = :kategori")
        values["kategori"] = payload.kategori
    if payload.aktif is not None:
        fields.append("aktif = :aktif")
        values["aktif"] = payload.aktif
    if payload.aciklama is not None:
        fields.append("aciklama = :aciklama")
        values["aciklama"] = payload.aciklama

    if not fields:
        raise HTTPException(status_code=400, detail="Güncellenecek alan yok")

    sql = f"""
        UPDATE menu
           SET {', '.join(fields)}
         WHERE {where_clause}
    """
    await db.execute(sql, values)
    
    # Cache'i temizle (menu listesi değişti)
    await cache.delete_pattern("menu:liste:*")

    # Güncellenmiş kaydı getir
    if payload.id:
        # id ile getir
        row = await db.fetch_one(
            """
            SELECT id, ad, fiyat, kategori, aktif, aciklama, gorsel_url
              FROM menu
             WHERE id = :id AND sube_id = :sid
             LIMIT 1
            """,
            {"id": payload.id, "sid": sube_id},
        )
    else:
        # yeni_ad varsa onu kullan, yoksa eski ad'ı kullan
        target_ad = payload.yeni_ad or mevcut_ad
        row = await db.fetch_one(
            """
            SELECT id, ad, fiyat, kategori, aktif, aciklama, gorsel_url
              FROM menu
             WHERE sube_id = :sid
               AND unaccent(lower(ad)) = unaccent(lower(:target))
             LIMIT 1
            """,
            {"sid": sube_id, "target": target_ad},
        )
    
    if not row:
        raise HTTPException(status_code=500, detail="Güncellenmiş kayıt bulunamadı")
    
    return row_to_menu_out(row)

@router.post(
    "/{menu_id}/gorsel",
    response_model=MenuItemOut,
    dependencies=[Depends(require_roles({"admin", "operator", "super_admin"}))]
)
async def menu_gorsel_yukle(
    menu_id: int,
    file: UploadFile = File(...),
    _: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    allowed_types = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }
    content_type = (file.content_type or "").lower()
    extension = allowed_types.get(content_type)
    original_suffix = Path(file.filename or "").suffix.lower()
    if not extension:
        if original_suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
            extension = ".jpg" if original_suffix in {".jpg", ".jpeg"} else original_suffix
        else:
            raise HTTPException(status_code=400, detail="Desteklenmeyen dosya türü")

    content = await file.read()
    max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"Dosya boyutu çok büyük. Maksimum {settings.MAX_UPLOAD_SIZE_MB}MB yükleyebilirsiniz.",
        )

    existing = await db.fetch_one(
        """
        SELECT id, gorsel_url
          FROM menu
         WHERE id = :id AND sube_id = :sid
         LIMIT 1
        """,
        {"id": menu_id, "sid": sube_id},
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Menü ürünü bulunamadı")

    media_dir = Path(settings.MEDIA_ROOT) / "menu"
    media_dir.mkdir(parents=True, exist_ok=True)
    filename = f"menu_{menu_id}_{secrets.token_hex(8)}{extension}"
    file_path = (media_dir / filename).resolve()

    try:
        with open(file_path, "wb") as out_file:
            out_file.write(content)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Görsel kaydedilemedi: {exc}") from exc

    # Eski görseli sil
    old_path = resolve_media_path(existing["gorsel_url"])
    if old_path and old_path.exists():
        try:
            if old_path.is_file():
                old_path.unlink()
        except Exception:
            pass

    relative_url = f"{settings.MEDIA_URL.rstrip('/')}/menu/{filename}"
    row = await db.fetch_one(
        """
        UPDATE menu
           SET gorsel_url = :url
         WHERE id = :id AND sube_id = :sid
     RETURNING id, ad, fiyat, kategori, aktif, aciklama, gorsel_url
        """,
        {"id": menu_id, "sid": sube_id, "url": relative_url},
    )
    if not row:
        raise HTTPException(status_code=404, detail="Menü ürünü güncellenemedi")

    # Cache'i temizle (menü listesi değişti - görsel eklendi)
    await cache.delete_pattern("menu:liste:*")
    import logging
    logging.info(f"[MENU_GORSEL_YUKLE] Görsel yüklendi: menu_id={menu_id}, sube_id={sube_id}, cache temizlendi")

    return row_to_menu_out(row)

@router.delete(
    "/{menu_id}/gorsel",
    response_model=MenuItemOut,
    dependencies=[Depends(require_roles({"admin", "operator", "super_admin"}))]
)
async def menu_gorsel_sil(
    menu_id: int,
    _: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    row = await db.fetch_one(
        """
        SELECT gorsel_url
          FROM menu
         WHERE id = :id AND sube_id = :sid
         LIMIT 1
        """,
        {"id": menu_id, "sid": sube_id},
    )
    if not row:
        raise HTTPException(status_code=404, detail="Menü ürünü bulunamadı")

    file_path = resolve_media_path(row["gorsel_url"])
    if file_path and file_path.exists():
        try:
            if file_path.is_file():
                file_path.unlink()
        except Exception:
            pass

    updated = await db.fetch_one(
        """
        UPDATE menu
           SET gorsel_url = NULL
         WHERE id = :id AND sube_id = :sid
     RETURNING id, ad, fiyat, kategori, aktif, aciklama, gorsel_url
        """,
        {"id": menu_id, "sid": sube_id},
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Menü ürünü güncellenemedi")

    # Cache'i temizle (menü listesi değişti - görsel silindi)
    await cache.delete_pattern("menu:liste:*")
    import logging
    logging.info(f"[MENU_GORSEL_SIL] Görsel silindi: menu_id={menu_id}, sube_id={sube_id}, cache temizlendi")

    return row_to_menu_out(updated)

@router.delete(
    "/sil",
    dependencies=[Depends(require_roles({"admin", "operator", "super_admin"}))]
)
async def menu_sil(
    id: Optional[int] = Query(None, description="Silinecek ürün ID'si"),
    ad: Optional[str] = Query(None, min_length=1, description="Silinecek ürün adı (id yoksa kullanılır)"),
    _: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    if not id and not ad:
        raise HTTPException(status_code=400, detail="id veya ad belirtilmelidir")
    
    if id:
        # id ile bul ve sil
        row = await db.fetch_one(
            """
            SELECT id, ad FROM menu
             WHERE id = :id AND sube_id = :sid
             LIMIT 1
            """,
            {"id": id, "sid": sube_id},
        )
        if not row:
            raise HTTPException(status_code=404, detail=f"Ürün bulunamadı: ID={id} (Şube ID: {sube_id})")
        urun_ad = row["ad"]
        await db.execute(
            """
            DELETE FROM menu
             WHERE id = :id AND sube_id = :sid
            """,
            {"id": id, "sid": sube_id},
        )
        # Cache'i temizle (menu listesi değişti)
        await cache.delete_pattern("menu:liste:*")
        return {"message": f"Silindi: {urun_ad} (ID: {id})"}
    else:
        # ad ile bul ve sil
        row = await db.fetch_one(
            """
            SELECT id, ad FROM menu
             WHERE sube_id = :sid
               AND unaccent(lower(ad)) = unaccent(lower(:ad))
             LIMIT 1
            """,
            {"sid": sube_id, "ad": ad},
        )
        if not row:
            raise HTTPException(status_code=404, detail=f"Ürün bulunamadı: {ad}")
        await db.execute(
            """
            DELETE FROM menu
             WHERE sube_id = :sid
               AND unaccent(lower(ad)) = unaccent(lower(:ad))
            """,
            {"sid": sube_id, "ad": ad},
        )
        # Cache'i temizle (menu listesi değişti)
        await cache.delete_pattern("menu:liste:*")
        return {"message": f"Silindi: {ad}"}

@router.post(
    "/yukle-csv",
    dependencies=[Depends(require_roles({"admin", "operator", "super_admin"}))]
)
async def menu_yukle_csv(
    file: UploadFile = File(...),
    _: Dict[str, Any] = Depends(get_current_user),
    sube_id: int = Depends(get_sube_id),
):
    """
    CSV başlıkları: ad,fiyat,kategori,aktif
    aktif: true/false (boşsa true kabul edilir)
    """
    content = await file.read()
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    items: List[Dict[str, Any]] = []
    for row in reader:
        ad_raw = (row.get("ad") or "").strip()
        kat = (row.get("kategori") or "").strip()
        if not ad_raw or not kat:
            continue
        # rakamsal fiyat
        try:
            fiyat = float((row.get("fiyat") or "0").strip())
        except ValueError:
            continue
        aktif_raw = (row.get("aktif") or "").strip().lower()
        aktif = True if aktif_raw in ("", "1", "true", "t", "evet", "yes") else False
        items.append({"ad": ad_raw, "fiyat": fiyat, "kategori": kat, "aktif": aktif})

    if not items:
        raise HTTPException(status_code=400, detail="CSV içeriği boş veya hatalı")

    # DB'deki mevcut ürün isimlerini normalize ederek map'le (bu şubeye ait)
    mevcut_rows = await db.fetch_all(
        "SELECT ad FROM menu WHERE sube_id = :sid;",
        {"sid": sube_id},
    )
    mevcut_map = {normalize_name(r["ad"]): r["ad"] for r in mevcut_rows}

    insert_count = 0
    update_count = 0

    async with db.transaction():
        for it in items:
            key = normalize_name(it["ad"])
            it_sube = {**it, "sid": sube_id}

            # 1) Aynı ürün (normalize) bu şubede varsa doğrudan UPDATE
            if key in mevcut_map:
                it2 = it.copy()
                it2.update({"ad": mevcut_map[key], "sid": sube_id})
                await db.execute(
                    """
                    UPDATE menu
                       SET fiyat = :fiyat,
                           kategori = :kategori,
                           aktif = :aktif
                     WHERE sube_id = :sid
                       AND ad = :ad
                    """,
                    it2,
                )
                update_count += 1
                continue

            # 2) Yoksa INSERT dene; UNIQUE çakışırsa (aynı şubede) UPDATE'e düş
            try:
                await db.execute(
                    """
                    INSERT INTO menu (sube_id, ad, fiyat, kategori, aktif)
                    VALUES (:sid, :ad, :fiyat, :kategori, :aktif)
                    """,
                    it_sube,
                )
                insert_count += 1
                mevcut_map[key] = it["ad"]
            except Exception:
                await db.execute(
                    """
                    UPDATE menu
                       SET fiyat = :fiyat,
                           kategori = :kategori,
                           aktif = :aktif
                     WHERE sube_id = :sid
                       AND unaccent(lower(ad)) = unaccent(lower(:ad))
                    """,
                    it_sube,
                )
                update_count += 1

    return {
        "ok": True,
        "toplam_kayit": len(items),
        "eklenen": insert_count,
        "guncellenen": update_count,
    }
