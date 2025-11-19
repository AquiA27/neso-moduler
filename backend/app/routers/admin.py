# backend/app/routers/admin.py
from fastapi import APIRouter, Depends, Query, Header, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Dict, Any
from starlette.responses import StreamingResponse
from datetime import datetime, timedelta
import io, csv

from ..core.deps import (
    get_current_user,
    require_roles,
    enforce_user_sube_access,  # şube yetki denetimi için kullanacağız
)
from ..db.database import db


# Tüm admin uçları sadece admin ve super_admin rolüne açık
router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(require_roles({"admin", "super_admin"}))],
)


async def resolve_sube_id_or_none(
    *,
    tum_subeler: bool,
    username: str,
    x_sube_id: Optional[int],
    sube_id_q: Optional[int],
) -> Optional[int]:
    """
    tum_subeler=True ise None döner (şube filtresi yok).
    Değilse: Header (X-Sube-Id) > query (?sube_id=) > 1
    + aktif şube kontrolü + kullanıcı şube yetkisi
    """
    import logging
    if tum_subeler:
        return None

    sube_id = x_sube_id if x_sube_id is not None else sube_id_q
    if sube_id is None:
        sube_id = 1  # DEMO varsayılanı (prod'da zorunlu yapmayı düşünebiliriz)

    logging.info(f"resolve_sube_id_or_none: checking sube_id={sube_id} for username={username}")
    
    # Şube aktif mi?
    try:
        row = await db.fetch_one(
            "SELECT id FROM subeler WHERE id = :id AND aktif = TRUE",
            {"id": sube_id},
        )
        if not row:
            logging.warning(f"Sube {sube_id} not found or not active")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Geçersiz veya pasif sube_id",
            )
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Database error checking sube: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )

    # Kullanıcının bu şubeye erişim izni var mı?
    try:
        await enforce_user_sube_access(username, sube_id)
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Access check error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Access check error: {str(e)}"
        )
    
    return sube_id


# --- 1) Günlük/Genel Özet ---
@router.get("/ozet")
async def admin_ozet(
    gun: Optional[str] = Query(None, description="YYYY-MM-DD (opsiyonel; boşsa bugün)"),
    start: Optional[str] = Query(None, description="Özel aralık başlangıcı (YYYY-MM-DD)"),
    end: Optional[str] = Query(None, description="Özel aralık bitişi (YYYY-MM-DD)"),
    tum_subeler: bool = Query(False, description="True=şube filtresi yok (ana admin görünümü)"),
    # X-Sube-Id ve ?sube_id, tum_subeler=False ise kullanılacak
    x_sube_id: Optional[int] = Header(None, alias="X-Sube-Id", convert_underscores=False),
    sube_id_q: Optional[int] = Query(None, alias="sube_id"),
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    KPI: siparis_sayisi, ciro, ortalama_siparis, iptal_sayisi
    """
    import logging
    try:
        logging.info(f"admin_ozet called: user={user['username']}, gun={gun}, tum_subeler={tum_subeler}")
        
        sube_id = await resolve_sube_id_or_none(
            tum_subeler=tum_subeler,
            username=user["username"],
            x_sube_id=x_sube_id,
            sube_id_q=sube_id_q,
        )

        params: Dict[str, Any] = {}
        siparis_flt = "TRUE"
        odeme_flt = "TRUE"

        if sube_id is not None:
            siparis_flt += " AND s.sube_id = :sid"
            odeme_flt += " AND o.sube_id = :sid"
            params["sid"] = sube_id

        start_date: Optional[datetime] = None
        end_date: Optional[datetime] = None

        if start and end:
            start_date = datetime.strptime(start, "%Y-%m-%d")
            end_date = datetime.strptime(end, "%Y-%m-%d")
            siparis_flt += " AND DATE(s.created_at) BETWEEN DATE(:start_date) AND DATE(:end_date)"
            odeme_flt += " AND DATE(o.created_at) BETWEEN DATE(:start_date) AND DATE(:end_date)"
            params["start_date"] = start_date.date()
            params["end_date"] = end_date.date()
        elif gun:
            siparis_flt += " AND DATE(s.created_at) = DATE(:gun)"
            odeme_flt += " AND DATE(o.created_at) = DATE(:gun)"
            # Convert string to date object for PostgreSQL
            params["gun"] = datetime.strptime(gun, "%Y-%m-%d").date()
        else:
            siparis_flt += " AND DATE(s.created_at) = CURRENT_DATE"
            odeme_flt += " AND DATE(o.created_at) = CURRENT_DATE"

        q = f"""
        WITH sp AS (
          SELECT COUNT(*) AS adet, COALESCE(SUM(tutar),0) AS ciro
          FROM siparisler s
          WHERE {siparis_flt} AND s.durum <> 'iptal'
        ),
        ip AS (
          SELECT COUNT(*) AS iptal
          FROM siparisler s
          WHERE {siparis_flt} AND s.durum = 'iptal'
        )
        SELECT sp.adet AS siparis_sayisi,
               sp.ciro AS ciro,
               CASE WHEN sp.adet>0 THEN sp.ciro/sp.adet ELSE 0 END AS ortalama_siparis,
               ip.iptal AS iptal_sayisi
        FROM sp, ip
        """
        logging.info(f"Executing query with params: {params}")
        row = await db.fetch_one(q, params) or {"siparis_sayisi": 0, "ciro": 0, "ortalama_siparis": 0, "iptal_sayisi": 0}

        result = {
            "kapsam": "tümü" if sube_id is None else f"sube:{sube_id}",
            "gun": gun or "bugün",
            **row
        }
        logging.info(f"admin_ozet result: {result}")
        if start and end:
            result["gun"] = f"{start} - {end}"
        return result
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in admin_ozet: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


# --- 2) Trend (son N gün) ---
@router.get("/trend")
async def admin_trend(
    gun_say: int = Query(7, ge=1, le=60),
    tum_subeler: bool = Query(False),
    x_sube_id: Optional[int] = Header(None, alias="X-Sube-Id", convert_underscores=False),
    sube_id_q: Optional[int] = Query(None, alias="sube_id"),
    start: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="YYYY-MM-DD"),
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Son N gün siparis_adedi ve ciro trendi
    """
    sube_id = await resolve_sube_id_or_none(
        tum_subeler=tum_subeler,
        username=user["username"],
        x_sube_id=x_sube_id,
        sube_id_q=sube_id_q,
    )

    # Tarih aralığı hesapla
    if (start and not end) or (end and not start):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start ve end parametreleri birlikte verilmelidir"
        )

    if start and end:
        try:
            start_date_obj = datetime.strptime(start, "%Y-%m-%d")
            end_date_obj = datetime.strptime(end, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Geçersiz tarih formatı. YYYY-MM-DD kullanın.")

        if start_date_obj > end_date_obj:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Başlangıç tarihi bitiş tarihinden büyük olamaz.")

        start_date = start_date_obj.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = end_date_obj.replace(hour=23, minute=59, second=59, microsecond=999999)
    else:
        end_date = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
        start_date = (end_date - timedelta(days=gun_say - 1)).replace(hour=0, minute=0, second=0, microsecond=0)

    params: Dict[str, Any] = {"start_date": start_date, "end_date": end_date}
    flt = "created_at >= :start_date AND created_at <= :end_date"
    if sube_id is not None:
        flt += " AND sube_id = :sid"
        params["sid"] = sube_id

    # Her gün için veri topla
    q = f"""
    SELECT 
        DATE(created_at) AS gun,
        COUNT(*) AS siparis_adedi,
        COALESCE(SUM(tutar), 0) AS ciro
    FROM siparisler
    WHERE {flt} AND durum <> 'iptal'
    GROUP BY DATE(created_at)
    ORDER BY gun
    """
    rows = await db.fetch_all(q, params)
    
    # Tarihleri string'e çevir
    result = []
    for row in rows:
        result.append({
            "gun": row["gun"].isoformat() if hasattr(row["gun"], 'isoformat') else str(row["gun"]),
            "siparis_adedi": int(row["siparis_adedi"]),
            "ciro": float(row["ciro"])
        })
    
    return result


# --- 3) Top Ürünler (sepet JSONB içinden) ---
@router.get("/top-urunler")
async def admin_top_urunler(
    gun_say: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=50),
    metrik: Literal["adet", "ciro"] = Query("adet"),
    tum_subeler: bool = Query(False),
    x_sube_id: Optional[int] = Header(None, alias="X-Sube-Id", convert_underscores=False),
    sube_id_q: Optional[int] = Query(None, alias="sube_id"),
    start: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="YYYY-MM-DD"),
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Son N günde en çok satan/ciro yapan ürünler.
    JSONB sepet -> ürün/adet/fiyat toplama.
    """
    sube_id = await resolve_sube_id_or_none(
        tum_subeler=tum_subeler,
        username=user["username"],
        x_sube_id=x_sube_id,
        sube_id_q=sube_id_q,
    )

    if (start and not end) or (end and not start):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start ve end parametreleri birlikte verilmelidir"
        )

    params: Dict[str, Any] = {"limit": limit}
    flt_clauses = ["s.durum <> 'iptal'"]
    if sube_id is not None:
        flt_clauses.append("s.sube_id = :sid")
        params["sid"] = sube_id

    try:
        if start and end:
            start_date_obj = datetime.strptime(start, "%Y-%m-%d")
            end_date_obj = datetime.strptime(end, "%Y-%m-%d")
            if start_date_obj > end_date_obj:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Başlangıç tarihi bitiş tarihinden büyük olamaz.")
            params["start_date"] = start_date_obj.replace(hour=0, minute=0, second=0, microsecond=0)
            params["end_date"] = end_date_obj.replace(hour=23, minute=59, second=59, microsecond=999999)
            date_filter = "s.created_at >= :start_date AND s.created_at <= :end_date"
        else:
            params["gun_say"] = gun_say
            date_filter = "s.created_at >= CURRENT_DATE - (:gun_say::int - 1)"
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Geçersiz tarih formatı. YYYY-MM-DD kullanın.")

    flt = " AND ".join(flt_clauses) if flt_clauses else "TRUE"

    # adet: SUM((item->>'adet')::numeric)
    # ciro: SUM((item->>'adet')::numeric * (item->>'fiyat')::numeric)
    order_column = "adet" if metrik == "adet" else "ciro"

    q = f"""
    WITH x AS (
      SELECT 
        unaccent(lower(item->>'urun')) AS ad_norm,
        MAX(item->>'urun') AS urun,
        SUM((item->>'adet')::numeric) AS adet,
        SUM((item->>'adet')::numeric * (item->>'fiyat')::numeric) AS ciro
      FROM siparisler s,
           LATERAL jsonb_array_elements(s.sepet) AS item
      WHERE {flt}
        AND {date_filter}
      GROUP BY unaccent(lower(item->>'urun'))
    )
    SELECT urun, adet, ciro
    FROM x
    ORDER BY {order_column} DESC
    LIMIT :limit
    """
    rows = await db.fetch_all(q, params)
    return {
        "metrik": metrik,
        "gun_say": gun_say,
        "kapsam": "tümü" if sube_id is None else f"sube:{sube_id}",
        "liste": rows,
        "start": start,
        "end": end,
    }


# --- 4) CSV Export: siparişler ---
@router.get("/export/siparisler.csv")
async def export_siparisler_csv(
    start: str = Query(..., description="YYYY-MM-DD"),
    end: str = Query(..., description="YYYY-MM-DD"),
    tum_subeler: bool = Query(False),
    x_sube_id: Optional[int] = Header(None, alias="X-Sube-Id", convert_underscores=False),
    sube_id_q: Optional[int] = Query(None, alias="sube_id"),
    user: Dict[str, Any] = Depends(get_current_user),
):
    sube_id = await resolve_sube_id_or_none(
        tum_subeler=tum_subeler,
        username=user["username"],
        x_sube_id=x_sube_id,
        sube_id_q=sube_id_q,
    )

    params: Dict[str, Any] = {"start": start, "end": end}
    flt = "DATE(created_at) BETWEEN DATE(:start) AND DATE(:end)"
    if sube_id is not None:
        flt += " AND sube_id = :sid"
        params["sid"] = sube_id

    q = f"""
    SELECT id, masa, durum, tutar, created_at, sube_id
    FROM siparisler
    WHERE {flt}
    ORDER BY created_at, id
    """
    rows = await db.fetch_all(q, params)

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "masa", "durum", "tutar", "created_at", "sube_id"])
    for r in rows:
        w.writerow([r["id"], r["masa"], r["durum"], r["tutar"], r["created_at"], r["sube_id"]])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="siparisler_{start}_{end}.csv"'},
    )


# --- 5) CSV Export: ödemeler ---
@router.get("/export/odemeler.csv")
async def export_odemeler_csv(
    start: str = Query(..., description="YYYY-MM-DD"),
    end: str = Query(..., description="YYYY-MM-DD"),
    tum_subeler: bool = Query(False),
    x_sube_id: Optional[int] = Header(None, alias="X-Sube-Id", convert_underscores=False),
    sube_id_q: Optional[int] = Query(None, alias="sube_id"),
    user: Dict[str, Any] = Depends(get_current_user),
):
    sube_id = await resolve_sube_id_or_none(
        tum_subeler=tum_subeler,
        username=user["username"],
        x_sube_id=x_sube_id,
        sube_id_q=sube_id_q,
    )

    params: Dict[str, Any] = {"start": start, "end": end}
    flt = "DATE(created_at) BETWEEN DATE(:start) AND DATE(:end)"
    if sube_id is not None:
        flt += " AND sube_id = :sid"
        params["sid"] = sube_id

    q = f"""
    SELECT id, masa, tutar, yontem, iptal, created_at, sube_id
    FROM odemeler
    WHERE {flt}
    ORDER BY created_at, id
    """
    rows = await db.fetch_all(q, params)

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "masa", "tutar", "yontem", "iptal", "created_at", "sube_id"])
    for r in rows:
        w.writerow([r["id"], r["masa"], r["tutar"], r["yontem"], r["iptal"], r["created_at"], r["sube_id"]])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="odemeler_{start}_{end}.csv"'},
    )


# ---- Personeller (Users) Yönetimi ----
class UserUpsertIn(BaseModel):
    username: str
    role: str
    aktif: bool = True
    password: Optional[str] = None


@router.get("/personeller")
async def personeller_list(
    limit: int = Query(50, ge=1, le=500, description="Sayfa başına kayıt sayısı"),
    offset: int = Query(0, ge=0, description="Atlanacak kayıt sayısı"),
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Personelleri listele
    - Super admin tenant switching yapıyorsa: Sadece seçili tenant'ın personellerini görür
    - Super admin "Tüm İşletmeler" modundaysa: Tüm personelleri görür
    - Admin: Sadece kendi işletmesine (tenant_id) ait personelleri görür
    """
    import logging
    user_role = user.get("role")
    user_tenant_id = user.get("tenant_id")

    # Super admin tenant switching yapıyorsa, effective_tenant_id'yi al
    switched_tenant_id = user.get("switched_tenant_id")
    effective_tenant_id = switched_tenant_id if switched_tenant_id else user_tenant_id

    # Super admin kontrolü
    is_super_admin = user_role == "super_admin"

    logging.info(f"[PERSONELLER_LIST] user_role={user_role}, user_tenant_id={user_tenant_id}, switched_tenant_id={switched_tenant_id}, effective_tenant_id={effective_tenant_id}")

    # Super admin tenant switching yapıyorsa (switched_tenant_id varsa), sadece o tenant'ın personellerini göster
    if is_super_admin and switched_tenant_id:
        # Önce tenant'ın var olduğunu ve aktif olduğunu kontrol et
        tenant_check = await db.fetch_one(
            "SELECT id, aktif FROM isletmeler WHERE id = :tid",
            {"tid": switched_tenant_id},
        )
        # tenant_check'ü dict'e çevir (Record objesi olabilir)
        tenant_check_dict = dict(tenant_check) if tenant_check and hasattr(tenant_check, 'keys') else (tenant_check if tenant_check else {})
        tenant_aktif = tenant_check_dict.get("aktif") if isinstance(tenant_check_dict, dict) else (getattr(tenant_check, "aktif", False) if tenant_check else False)
        
        if not tenant_check or not tenant_aktif:
            # Tenant yoksa veya pasifse, boş liste döndür
            logging.warning(f"[PERSONELLER_LIST] Tenant {switched_tenant_id} not found or inactive, returning empty list")
            return []

        logging.info(f"[PERSONELLER_LIST] Super admin tenant switching: fetching personeller for tenant_id={switched_tenant_id}")
        
        # Önce tenant_id ile eşleşen personelleri bul
        rows = await db.fetch_all(
            """
            SELECT id, username, role, aktif, tenant_id, created_at
            FROM users
            WHERE tenant_id = :tid AND role != 'super_admin'
            ORDER BY id DESC
            LIMIT :limit OFFSET :offset
            """,
            {"tid": switched_tenant_id, "limit": limit, "offset": offset}
        )
        logging.info(f"[PERSONELLER_LIST] Found {len(rows)} personeller for tenant_id={switched_tenant_id}")
        
        # Eğer hiç personel bulunamadıysa ve tenant_id=1 ise (Demo İşletme), NULL tenant_id'li personelleri de kontrol et
        if len(rows) == 0 and switched_tenant_id == 1:
            logging.info(f"[PERSONELLER_LIST] No personeller found for tenant_id=1, checking for NULL tenant_id personeller")
            rows_null = await db.fetch_all(
                """
                SELECT id, username, role, aktif, tenant_id, created_at
                FROM users
                WHERE tenant_id IS NULL AND role != 'super_admin'
                ORDER BY id DESC
                LIMIT :limit OFFSET :offset
                """,
                {"limit": limit, "offset": offset}
            )
            logging.info(f"[PERSONELLER_LIST] Found {len(rows_null)} personeller with NULL tenant_id")
            if len(rows_null) > 0:
                # NULL tenant_id'li personelleri Demo İşletme'ye atayalım
                logging.info(f"[PERSONELLER_LIST] Assigning {len(rows_null)} NULL tenant_id personeller to Demo İşletme (tenant_id=1)")
                for row in rows_null:
                    # row'u dict'e çevir
                    row_dict = dict(row) if hasattr(row, 'keys') else row
                    user_id = row_dict.get("id") if isinstance(row_dict, dict) else (getattr(row, "id", None) if row else None)
                    if user_id:
                        await db.execute(
                            "UPDATE users SET tenant_id = :tid WHERE id = :uid",
                            {"tid": 1, "uid": user_id}
                        )
                # Tekrar sorgula
                rows = await db.fetch_all(
                    """
                    SELECT id, username, role, aktif, tenant_id, created_at
                    FROM users
                    WHERE tenant_id = :tid AND role != 'super_admin'
                    ORDER BY id DESC
                    LIMIT :limit OFFSET :offset
                    """,
                    {"tid": switched_tenant_id, "limit": limit, "offset": offset}
                )
                logging.info(f"[PERSONELLER_LIST] After assignment: Found {len(rows)} personeller for tenant_id={switched_tenant_id}")
    elif is_super_admin:
        # Super admin "Tüm İşletmeler" modunda - tüm personelleri göster
        logging.info(f"[PERSONELLER_LIST] Super admin 'Tüm İşletmeler' mode: fetching all personeller")
        rows = await db.fetch_all(
            """
            SELECT id, username, role, aktif, tenant_id, created_at
            FROM users
            WHERE role != 'super_admin'
            ORDER BY id DESC
            LIMIT :limit OFFSET :offset
            """,
            {"limit": limit, "offset": offset}
        )
        logging.info(f"[PERSONELLER_LIST] Found {len(rows)} total personeller")
    else:
        # Admin sadece kendi tenant'ına ait personelleri görebilir (kendisi dahil)
        if user_tenant_id:
            logging.info(f"[PERSONELLER_LIST] Admin mode: fetching personeller for tenant_id={user_tenant_id}")
            rows = await db.fetch_all(
                """
                SELECT id, username, role, aktif, tenant_id, created_at
                FROM users
                WHERE tenant_id = :tid AND role != 'super_admin'
                ORDER BY id DESC
                LIMIT :limit OFFSET :offset
                """,
                {"tid": user_tenant_id, "limit": limit, "offset": offset}
            )
            logging.info(f"[PERSONELLER_LIST] Found {len(rows)} personeller for admin tenant_id={user_tenant_id} (including admin user)")
        else:
            # Tenant_id yoksa boş liste döndür
            logging.warning(f"[PERSONELLER_LIST] Admin has no tenant_id, returning empty list")
            rows = []

    result = [dict(r) if hasattr(r, 'keys') else r for r in rows]
    logging.info(f"[PERSONELLER_LIST] Returning {len(result)} personeller")
    return result


@router.post("/personeller/upsert")
async def personeller_upsert(payload: UserUpsertIn, user: Dict[str, Any] = Depends(get_current_user)):
    """
    Personel ekle/güncelle
    - Super admin: Herhangi bir tenant'a personel ekleyebilir
    - Admin: Sadece kendi işletmesine (tenant_id) personel ekleyebilir
    """
    from ..core.security import hash_password
    
    import logging
    user_role = user.get("role")
    user_tenant_id = user.get("tenant_id")
    
    # Super admin tenant switching yapıyorsa, effective_tenant_id'yi al
    switched_tenant_id = user.get("switched_tenant_id")
    effective_tenant_id = switched_tenant_id if switched_tenant_id else user_tenant_id
    
    # Admin sadece kendi tenant'ına personel ekleyebilir
    # Super admin için tenant_id None olabilir (isterse belirtir)
    # Ama super admin tenant switching yapıyorsa, switched_tenant_id kullanılmalı
    if user_role == "super_admin" and switched_tenant_id:
        tenant_id = switched_tenant_id
    elif user_role == "super_admin":
        tenant_id = None  # Super admin tüm işletmeler modunda
    else:
        tenant_id = effective_tenant_id  # Normal admin için effective_tenant_id
    
    logging.info(f"[PERSONELLER_UPSERT] user_role={user_role}, user_tenant_id={user_tenant_id}, switched_tenant_id={switched_tenant_id}, effective_tenant_id={effective_tenant_id}, tenant_id={tenant_id}")
    
    # Eğer mevcut kullanıcı varsa ve farklı tenant'a aitse, hata ver
    # Ancak, yeni kullanıcı eklenirken (password varsa veya kullanıcı yoksa) tenant_id atanabilir
    if user_role != "super_admin":
        existing_user = await db.fetch_one(
            "SELECT tenant_id FROM users WHERE username = :u",
            {"u": payload.username}
        )
        if existing_user:
            existing_tenant_dict = dict(existing_user) if hasattr(existing_user, 'keys') else existing_user
            existing_tenant_id = existing_tenant_dict.get("tenant_id") if isinstance(existing_tenant_dict, dict) else (getattr(existing_user, "tenant_id", None) if existing_user else None)
            
            logging.info(f"[PERSONELLER_UPSERT] Existing user found: username={payload.username}, existing_tenant_id={existing_tenant_id}, effective_tenant_id={effective_tenant_id}")
            
            # Eğer mevcut kullanıcı varsa:
            # 1. Eğer mevcut tenant_id NULL ise, yeni tenant'a atanabilir (zaten yukarıda tenant_id atanacak)
            # 2. Eğer mevcut tenant_id farklı bir tenant'a aitse VE password yoksa (güncelleme işlemi), hata ver
            # 3. Eğer password varsa (yeni kullanıcı ekleme), tenant_id güncellenebilir (admin kendi tenant'ına ekleyebilir)
            if existing_tenant_id is not None and existing_tenant_id != effective_tenant_id:
                # Password varsa (yeni kullanıcı ekleme), tenant_id'yi güncelle (admin kendi tenant'ına ekliyor)
                if payload.password:
                    logging.info(f"[PERSONELLER_UPSERT] Password provided, updating tenant_id from {existing_tenant_id} to {effective_tenant_id} for user {payload.username}")
                    # tenant_id zaten effective_tenant_id olarak ayarlandı, devam et
                else:
                    # Password yoksa (güncelleme işlemi), farklı tenant'a ait kullanıcıyı güncelleyemez
                    logging.warning(f"[PERSONELLER_UPSERT] User {payload.username} belongs to different tenant: {existing_tenant_id} != {effective_tenant_id} (no password provided)")
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Bu personel başka bir işletmeye ait. Sadece kendi işletmenize ait personelleri düzenleyebilirsiniz."
                    )
    
    params = {
        "u": payload.username,
        "r": payload.role,
        "a": payload.aktif,
        "tid": tenant_id,
    }
    
    # Super admin rolü atanmasını engelle
    if payload.role == "super_admin" and user_role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin rolü atanamaz"
        )
    
    if payload.password:
        params["h"] = hash_password(payload.password)
        await db.execute(
            """
            INSERT INTO users (username, sifre_hash, role, aktif, tenant_id)
            VALUES (:u, :h, :r, :a, :tid)
            ON CONFLICT (username) DO UPDATE
               SET role = EXCLUDED.role,
                   aktif = EXCLUDED.aktif,
                   sifre_hash = EXCLUDED.sifre_hash,
                   tenant_id = COALESCE(EXCLUDED.tenant_id, users.tenant_id)
            """,
            params,
        )
    else:
        await db.execute(
            """
            INSERT INTO users (username, role, aktif, tenant_id)
            VALUES (:u, :r, :a, :tid)
            ON CONFLICT (username) DO UPDATE
               SET role = EXCLUDED.role,
                   aktif = EXCLUDED.aktif,
                   tenant_id = COALESCE(EXCLUDED.tenant_id, users.tenant_id)
            """,
            params,
        )
    
    return {"ok": True}


# ---- Personel İzin Yönetimi ----
# Permission constants (superadmin'dan import et veya buraya kopyala)
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


@router.put("/users/{username}/permissions", response_model=UserPermissionOut)
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


@router.get("/permissions/available", response_model=Dict[str, str])
async def get_available_permissions(_: Dict[str, Any] = Depends(get_current_user)):
    """Tüm mevcut izin anahtarlarını listele"""
    return PERMISSION_KEYS


# ---- Personel Satış Analizi ----
@router.get("/personel-analiz")
async def personel_analiz(
    gun_say: int = Query(30, ge=1, le=365),
    limit: int = Query(20, ge=1, le=100),
    tum_subeler: bool = Query(False),
    x_sube_id: Optional[int] = Header(None, alias="X-Sube-Id", convert_underscores=False),
    sube_id_q: Optional[int] = Query(None, alias="sube_id"),
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Personel bazlı satış analizi
    - En fazla sipariş alan personeller
    - En fazla ciro yapan personeller
    - Ortalama sipariş tutarı
    """
    import logging
    user_role = user.get("role")
    user_tenant_id = user.get("tenant_id")
    switched_tenant_id = user.get("switched_tenant_id")
    effective_tenant_id = switched_tenant_id if switched_tenant_id else user_tenant_id
    
    is_super_admin = user_role == "super_admin"
    
    logging.info(f"personel_analiz called: user={user['username']}, gun_say={gun_say}, limit={limit}, effective_tenant_id={effective_tenant_id}")
    
    try:
        # Super admin tenant switching yapıyorsa ve sube_id belirtilmemişse, o tenant'ın ilk şubesini bul
        if effective_tenant_id and (not x_sube_id and not sube_id_q):
            # Önce tenant'ın şubelerini kontrol et
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
                tenant_sube_dict = dict(tenant_sube) if hasattr(tenant_sube, 'keys') else tenant_sube
                tenant_sube_id = tenant_sube_dict.get("id") if isinstance(tenant_sube_dict, dict) else (getattr(tenant_sube, "id", None) if tenant_sube else None)
                if tenant_sube_id:
                    # Tenant'ın şubesi varsa, otomatik olarak onu kullan
                    sube_id_q = tenant_sube_id
                    logging.info(f"[PERSONEL_ANALIZ] Using tenant {effective_tenant_id}'s first branch: {tenant_sube_id}")
        
        try:
            sube_id = await resolve_sube_id_or_none(
                tum_subeler=tum_subeler,
                username=user["username"],
                x_sube_id=x_sube_id,
                sube_id_q=sube_id_q,
            )
        except HTTPException as sube_error:
            # Şube bulunamadı veya pasif - sadece tenant filtresi ile devam et (sube_id olmadan)
            if effective_tenant_id:
                sube_id = None
                logging.warning(f"[PERSONEL_ANALIZ] Sube not found/active, continuing with tenant filter only (tenant_id={effective_tenant_id})")
            else:
                # Tenant ID de yoksa hata döndür
                logging.error(f"[PERSONEL_ANALIZ] Sube not found/active and no tenant_id available")
                raise
        
        # Tarih aralığı hesapla
        end_date = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
        start_date = (datetime.now() - timedelta(days=gun_say-1)).replace(hour=0, minute=0, second=0, microsecond=0)
        
        params: Dict[str, Any] = {"start_date": start_date, "end_date": end_date}
        flt = "s.created_at >= :start_date AND s.created_at <= :end_date"
        if sube_id is not None:
            flt += " AND s.sube_id = :sid"
            params["sid"] = sube_id
        
        # Tenant filtresi ekle (super admin tenant switching yapıyorsa veya normal admin ise)
        tenant_filter = ""
        if effective_tenant_id:
            # Super admin tenant switching yapıyorsa veya normal admin ise, sadece o tenant'ın personellerini göster
            tenant_filter = " AND u.tenant_id = :tid"
            params["tid"] = effective_tenant_id
            logging.info(f"[PERSONEL_ANALIZ] Filtering by tenant_id={effective_tenant_id}")
        elif is_super_admin:
            # Super admin "Tüm İşletmeler" modunda - tenant filtresi yok
            logging.info(f"[PERSONEL_ANALIZ] Super admin 'Tüm İşletmeler' mode - no tenant filter")
        
        logging.info(f"Executing personel query with params: {params}")
        
        # Personel bazlı analiz (kullanıcılar + yapay zeka)
        q_personel = f"""
        SELECT 
            u.id,
            u.username,
            u.role,
            COUNT(DISTINCT s.id) AS siparis_adedi,
            COALESCE(SUM(s.tutar), 0) AS toplam_ciro
        FROM users u
        LEFT JOIN siparisler s ON (
            ({flt})
            AND (
                s.created_by_user_id = u.id
                OR (s.created_by_user_id IS NULL AND s.created_by_username = u.username)
            )
        )
        WHERE u.role IN ('garson', 'barista', 'admin', 'operator'){tenant_filter}
        GROUP BY u.id, u.username, u.role
        HAVING COUNT(DISTINCT s.id) > 0
        """
        
        # AI sorgusu için tenant filtresi (siparişler üzerinden)
        ai_tenant_filter = ""
        ai_params = params.copy()
        if effective_tenant_id:
            # Siparişlerin şubeleri üzerinden tenant kontrolü yap
            ai_tenant_filter = """
            AND EXISTS (
                SELECT 1 FROM subeler sub 
                WHERE sub.id = s.sube_id AND sub.isletme_id = :tid
            )
            """
            ai_params["tid"] = effective_tenant_id
        
        q_ai = f"""
        SELECT 
            'Yapay Zeka' AS username,
            'ai' AS role,
            NULL AS id,
            COUNT(*) AS siparis_adedi,
            COALESCE(SUM(tutar), 0) AS toplam_ciro
        FROM siparisler s
        WHERE {flt} AND created_by_user_id IS NULL AND (s.created_by_username IS NULL OR s.created_by_username = ''){ai_tenant_filter}
        """
        
        personel_rows = await db.fetch_all(q_personel, params)
        ai_rows = await db.fetch_all(q_ai, ai_params)
        logging.info(f"personel_rows count: {len(personel_rows)}, ai_rows count: {len(ai_rows)}")
    except Exception as e:
        logging.error(f"Error in personel_analiz: {e}", exc_info=True)
        raise
    
    result = []
    
    # Personel verilerini ekle
    for row in personel_rows:
        result.append({
            "user_id": int(row["id"]) if row["id"] else None,
            "username": row["username"],
            "role": row["role"],
            "siparis_adedi": int(row["siparis_adedi"] or 0),
            "toplam_ciro": float(row["toplam_ciro"] or 0),
        })
    
    # Yapay Zeka verilerini ekle
    if ai_rows and len(ai_rows) > 0:
        ai_row = ai_rows[0]
        if ai_row["siparis_adedi"] and int(ai_row["siparis_adedi"]) > 0:
            result.append({
                "user_id": None,
                "username": "Yapay Zeka",
                "role": "ai",
                "siparis_adedi": int(ai_row["siparis_adedi"] or 0),
                "toplam_ciro": float(ai_row["toplam_ciro"] or 0),
            })
    
    # Sipariş adedine göre sırala ve limit uygula
    result = sorted(result, key=lambda x: x["toplam_ciro"], reverse=True)[:limit]
    
    return result
