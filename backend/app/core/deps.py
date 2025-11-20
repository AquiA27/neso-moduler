# backend/app/core/deps.py
from typing import Dict, Any, Mapping, Optional, Set

from fastapi import Depends, HTTPException, status, Header, Query, Request
from fastapi.security import OAuth2PasswordBearer
from starlette.requests import Request as StarletteRequest
from jose import jwt, JWTError

from ..db.database import db
from .security import ALGORITHM, SECRET_KEY

# OAuth2 Password Bearer (token alma ucu: /auth/token)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


# ---------------------------
# JWT Yardımcıları
# ---------------------------
def decode_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


# ---------------------------
# Kimlik ve Rol
# ---------------------------
async def get_current_user(
    request: StarletteRequest,
    token: str = Depends(oauth2_scheme),
) -> Mapping[str, Any]:
    """
    JWT 'sub' içinden kullanıcıyı DB'den çeker ve aktifliğini doğrular.
    Domain-based tenant routing: request.state.tenant_id varsa (DomainTenantMiddleware'den gelmişse) öncelik verir.
    Super admin için X-Tenant-Id header'ını veya tenant_id query parameter'ını kontrol eder (tenant switching).
    Dönüş: {"id": ..., "username": ..., "role": ..., "aktif": ..., "tenant_id": ..., "switched_tenant_id": ...}
    """
    payload = decode_token(token)
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token (no sub)",
        )

    # Token'dan tenant_id al (super_admin için None olabilir)
    token_tenant_id = payload.get("tenant_id")

    # sub'u senin yapına göre yorumla:
    # - eğer 'sub' username ise username ile çek
    # - eğer 'sub' user_id ise id ile çek
    # Burada username varsaydım. Gerekirse id tabanlı sorguya çeviririz.
    row = await db.fetch_one(
        "SELECT id, username, role, aktif, tenant_id FROM users WHERE username = :u",
        {"u": sub},
    )
    if not row or row["aktif"] is False:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    user_dict = dict(row) if hasattr(row, 'keys') else row
    
    # Domain-based tenant routing: request.state.tenant_id varsa öncelik ver (DomainTenantMiddleware'den gelmişse)
    domain_tenant_id = None
    if hasattr(request.state, 'tenant_id') and request.state.tenant_id:
        domain_tenant_id = request.state.tenant_id
        import logging
        logging.info(f"[get_current_user] Domain-based tenant detected: tenant_id={domain_tenant_id}")
    
    # Tenant_id'yi domain > token > DB sırasıyla al
    tenant_id = domain_tenant_id or user_dict.get("tenant_id") or token_tenant_id
    user_dict["tenant_id"] = tenant_id
    
    # Super admin için X-Tenant-Id header'ını veya tenant_id query parameter'ını kontrol et (tenant switching)
    switched_tenant_id = None
    if user_dict.get("role") == "super_admin" and request:
        import logging
        # Önce query parameter'ı kontrol et (frontend'den gelen)
        # Starlette'de query_params bir QueryParams objesi, dict'e çevirirken dikkatli ol
        tenant_id_param = None
        if hasattr(request, 'query_params'):
            # QueryParams objesi üzerinden direkt erişim
            if "tenant_id" in request.query_params:
                tenant_id_param = request.query_params.get("tenant_id")
                # Eğer liste dönerse, ilk elemanı al
                if isinstance(tenant_id_param, list):
                    tenant_id_param = tenant_id_param[0] if tenant_id_param else None
        
        # Sonra header'ı kontrol et (alternatif yöntem)
        x_tenant_id = request.headers.get("X-Tenant-Id")
        
        logging.info(f"[get_current_user] Super admin tenant switching check: query_param={tenant_id_param}, header={x_tenant_id}")
        
        # Query parameter öncelikli, yoksa header
        tenant_id_value = tenant_id_param or x_tenant_id
        
        if tenant_id_value:
            try:
                # String'i int'e çevir - manuel parse (int() fonksiyonu sorunlu olabilir)
                tenant_id_str = str(tenant_id_value).strip()
                if not tenant_id_str or not tenant_id_str.isdigit():
                    logging.warning(f"[get_current_user] Invalid tenant_id format: {tenant_id_str}")
                    switched_tenant_id = None
                else:
                    # Manuel olarak string'i int'e çevir
                    switched_tenant_id = 0
                    for char in tenant_id_str:
                        if char.isdigit():
                            switched_tenant_id = switched_tenant_id * 10 + (ord(char) - ord('0'))
                        else:
                            logging.warning(f"[get_current_user] Invalid character in tenant_id: {char}")
                            switched_tenant_id = None
                            break
                    
                    if switched_tenant_id is not None:
                        logging.info(f"[get_current_user] Parsed tenant_id: {switched_tenant_id}")

                        # Tenant'ın var olduğunu ve aktif olduğunu kontrol et
                        try:
                            tenant_check = await db.fetch_one(
                                "SELECT id, aktif FROM isletmeler WHERE id = :tid",
                                {"tid": switched_tenant_id},
                            )
                            # tenant_check'ü dict'e çevir
                            tenant_check_dict = dict(tenant_check) if tenant_check and hasattr(tenant_check, 'keys') else (tenant_check if tenant_check else {})
                            tenant_aktif = tenant_check_dict.get("aktif") if isinstance(tenant_check_dict, dict) else (getattr(tenant_check, "aktif", False) if tenant_check else False)
                            
                            if not tenant_check or not tenant_aktif:
                                # Tenant yoksa veya pasifse, switched_tenant_id'yi None yap
                                logging.warning(f"[get_current_user] Tenant {switched_tenant_id} not found or inactive")
                                switched_tenant_id = None
                            else:
                                # Super admin'in bu tenant'ın context'inde çalışması için tenant_id'yi geçici olarak değiştir
                                user_dict["switched_tenant_id"] = switched_tenant_id
                                user_dict["tenant_id"] = switched_tenant_id  # Geçici olarak switched tenant'ın context'i
                                logging.info(f"[get_current_user] Tenant switching active: switched_tenant_id={switched_tenant_id}, user_dict={user_dict}")
                        except Exception as db_error:
                            logging.warning(f"[get_current_user] Error checking tenant {switched_tenant_id}: {db_error}")
                            switched_tenant_id = None
            except Exception as e:
                # Geçersiz tenant_id, görmezden gel
                logging.warning(f"[get_current_user] Invalid tenant_id value: {tenant_id_value} (type: {type(tenant_id_value)}), error: {e}, error_type: {type(e)}")
                switched_tenant_id = None
        else:
            logging.info(f"[get_current_user] No tenant_id provided for super admin")
    
    return user_dict


async def get_current_user_and_role(
    request: StarletteRequest,
    token: str = Depends(oauth2_scheme)
) -> Mapping[str, Any]:
    """
    Rolü token'dan **değil**, DB'den okur (güncel yetki için daha güvenli).
    Super admin tenant switching için switched_tenant_id ve tenant_id bilgilerini de döndürür.
    """
    import logging
    user = await get_current_user(request, token)
    logging.info(f"get_current_user_and_role: user={user}")
    result = {
        "username": user["username"], 
        "role": user["role"], 
        "id": user["id"],
        "tenant_id": user.get("tenant_id"),
        "switched_tenant_id": user.get("switched_tenant_id"),
    }
    return result


def require_roles(allowed: Set[str]):
    """
    Kullanım: dependencies=[Depends(require_roles({'admin'}))]
    veya:     dependencies=[Depends(require_roles({'admin','operator'}))]
    """
    async def _dep(info: Mapping[str, Any] = Depends(get_current_user_and_role)) -> Mapping[str, Any]:
        import logging
        role = (info.get("role") or "").lower()
        logging.info(f"require_roles check: role={role}, allowed={allowed}")
        # Super admin her yeri görebilir
        if role == "super_admin":
            return info
        if role not in {r.lower() for r in allowed}:
            logging.warning(f"Access denied: role={role} not in allowed={allowed}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden (role: {role})",
            )
        return info
    return _dep


async def check_user_permission(username: str, permission_key: str) -> bool:
    """
    Kullanıcının belirli bir izne sahip olup olmadığını kontrol et.
    Super admin her zaman True döner.
    """
    from ..db.database import db
    
    # Kullanıcının rolünü kontrol et
    user_row = await db.fetch_one(
        "SELECT role FROM users WHERE username = :u",
        {"u": username},
    )
    if not user_row:
        return False
    
    role = (user_row.get("role") or "").lower()
    # Super admin her zaman izinlidir
    if role == "super_admin":
        return True
    
    # Kullanıcının özel izinlerini kontrol et
    perm_row = await db.fetch_one(
        """
        SELECT enabled FROM user_permissions
        WHERE username = :u AND permission_key = :key
        """,
        {"u": username, "key": permission_key},
    )
    
    if perm_row:
        return perm_row["enabled"] is True
    
    # Özel izin yoksa, rol bazlı varsayılan izinleri kontrol et
    try:
        from ..routers.superadmin import DEFAULT_PERMISSIONS_BY_ROLE
        default_perms = DEFAULT_PERMISSIONS_BY_ROLE.get(role, [])
        return permission_key in default_perms
    except ImportError:
        # Eğer superadmin modülü yüklenemezse, varsayılan olarak False döndür
        return False


def require_permission(permission_key: str):
    """
    Kullanım: dependencies=[Depends(require_permission('menu_ekle'))]
    Belirli bir izin gerektiren endpoint'ler için kullanılır.
    """
    async def _dep(current_user: Mapping[str, Any] = Depends(get_current_user)) -> Mapping[str, Any]:
        import logging
        username = current_user.get("username")
        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized",
            )
        
        has_permission = await check_user_permission(username, permission_key)
        if not has_permission:
            logging.warning(f"Permission denied: user={username}, permission={permission_key}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: {permission_key} permission required",
            )
        return current_user
    return _dep


# ---------------------------
# Şube Erişim Kontrolü
# ---------------------------
async def enforce_user_sube_access(username: str, sube_id: int) -> None:
    """
    Kullanıcıya tanımlı şube izinleri varsa sadece o şubelere erişsin.
    Hiç izin kaydı yoksa (tablo boşsa) gevşek mod: tüm şubelere izin.
    """
    # Super admin için bypass
    try:
        role_row = await db.fetch_one(
            "SELECT role FROM users WHERE username = :u",
            {"u": username},
        )
        if role_row and str(role_row["role"] or "").lower() == "super_admin":
            return
    except Exception:
        # users tablosu yoksa/uyumsuzsa, mevcut gevşek davranışa düş
        pass

    try:
        rows = await db.fetch_all(
            "SELECT sube_id FROM user_sube_izinleri WHERE username = :u",
            {"u": username},
        )
    except Exception:
        # Tablo yoksa mevcut gevşek davranışı koru
        return
    if not rows:
        # Gevşek mod: kayıt yoksa tüm şubeler serbest (mevcut davranış)
        return
    allowed = {r["sube_id"] for r in rows}
    if sube_id not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu şubeye erişim yetkiniz yok",
        )


async def get_sube_id(
    x_sube_id: Optional[int] = Header(
        None, alias="X-Sube-Id", convert_underscores=False
    ),
    sube_id_q: Optional[int] = Query(None, alias="sube_id"),
    current: Mapping[str, Any] = Depends(get_current_user),  # username/role/id içeriyor
) -> int:
    """
    Şube belirleme:
    - Header (X-Sube-Id) öncelikli
    - Yoksa query (?sube_id=)
    - İkisi de yoksa: Super admin tenant switching yapıyorsa o tenant'ın ilk şubesini, yoksa 1 (DEMO varsayılanı)
    Ayrıca şubenin aktifliğini ve kullanıcının erişim iznini doğrular.
    Super admin tenant switching yapıyorsa, sadece o tenant'ın şubelerine erişebilir.
    """
    sube_id = x_sube_id if x_sube_id is not None else sube_id_q
    
    # Super admin tenant switching yapıyorsa, tenant_id'yi al
    switched_tenant_id = current.get("switched_tenant_id")
    tenant_id = current.get("tenant_id")
    effective_tenant_id = switched_tenant_id if switched_tenant_id else tenant_id
    
    role = (current.get("role") or "").lower()
    is_super_admin = role == "super_admin"
    
    # Super admin tenant switching yapıyorsa, şubenin o tenant'a ait olduğunu kontrol et
    if is_super_admin and effective_tenant_id and sube_id is not None:
        # Gönderilen sube_id'nin o tenant'a ait olup olmadığını kontrol et
        sube_check = await db.fetch_one(
            "SELECT id FROM subeler WHERE id = :sid AND isletme_id = :tid AND aktif = TRUE",
            {"sid": sube_id, "tid": effective_tenant_id},
        )
        if not sube_check:
            # Gönderilen sube_id o tenant'a ait değil, o tenant'ın ilk şubesini bul
            row = await db.fetch_one(
                """
                SELECT id FROM subeler 
                WHERE isletme_id = :tid AND aktif = TRUE 
                ORDER BY id ASC 
                LIMIT 1
                """,
                {"tid": effective_tenant_id},
            )
            if row:
                sube_id = row["id"]
                import logging
                logging.info(f"[get_sube_id] Tenant {effective_tenant_id} için şube bulundu: {sube_id}")
            else:
                # Tenant'ın şubesi yoksa, hata verme - backend'de varsayılan şube kullanılacak
                # Ama bu durumda menu boş dönecek (normal davranış)
                import logging
                logging.warning(f"[get_sube_id] Tenant {effective_tenant_id} için aktif şube bulunamadı")
                # sube_id'yi None yap, aşağıda varsayılan şube atanacak ama tenant kontrolü yapılmayacak
                sube_id = None
    
    # Super admin tenant switching yapıyorsa ve sube_id belirtilmemişse, o tenant'ın ilk şubesini bul
    if sube_id is None and is_super_admin and effective_tenant_id:
        row = await db.fetch_one(
            """
            SELECT id FROM subeler 
            WHERE isletme_id = :tid AND aktif = TRUE 
            ORDER BY id ASC 
            LIMIT 1
            """,
            {"tid": effective_tenant_id},
        )
        if row:
            sube_id = row["id"]
            import logging
            logging.info(f"[get_sube_id] Tenant {effective_tenant_id} için otomatik şube bulundu: {sube_id}")
        else:
            # Tenant'ın şubesi yoksa, varsayılan şube kullan ama tenant kontrolü yapma
            import logging
            logging.warning(f"[get_sube_id] Tenant {effective_tenant_id} için şube bulunamadı, varsayılan şube kullanılacak")
            sube_id = 1  # DEMO varsayılanı - ama aşağıda tenant kontrolü yapılmayacak
    
    if sube_id is None:
        sube_id = 1  # DEMO varsayılanı

    # Şube aktif mi ve tenant_id kontrolü
    query = "SELECT id, isletme_id FROM subeler WHERE id = :id AND aktif = TRUE"
    params = {"id": sube_id}
    
    # Super admin tenant switching yapıyorsa (effective_tenant_id varsa), şubenin o tenant'a ait olduğunu kontrol et
    # Ama "Tüm İşletmeler" seçildiğinde (effective_tenant_id null) tenant kontrolü yapma
    # Ayrıca, eğer tenant'ın şubesi yoksa (yukarıda bulunamadıysa), tenant kontrolü yapma
    tenant_check_needed = is_super_admin and effective_tenant_id
    
    # Önce şubenin var olup olmadığını kontrol et
    row = await db.fetch_one(query, params)
    if not row:
        # Şube yok veya pasif
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Geçersiz veya pasif sube_id",
        )
    
    # row'u dict'e çevir (Record objesi olabilir)
    row_dict = dict(row) if hasattr(row, 'keys') else row
    
    # Şube var, şimdi tenant kontrolü yap (eğer gerekliyse)
    if tenant_check_needed:
        # Şubenin tenant'a ait olduğunu kontrol et
        row_isletme_id = row_dict.get("isletme_id") if isinstance(row_dict, dict) else (getattr(row, "isletme_id", None) if row else None)
        if row_isletme_id != effective_tenant_id:
            # Şube başka bir tenant'a ait - o tenant'ın ilk şubesini tekrar bul
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
                sube_id = tenant_sube_dict.get("id") if isinstance(tenant_sube_dict, dict) else (getattr(tenant_sube, "id", None) if tenant_sube else None)
                if sube_id:
                    # Yeni şube ID'si ile tekrar kontrol et
                    row = await db.fetch_one(
                        "SELECT id, isletme_id FROM subeler WHERE id = :id AND aktif = TRUE",
                        {"id": sube_id},
                    )
                    if not row:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Geçersiz veya pasif sube_id",
                        )
                    # row'u tekrar dict'e çevir
                    row_dict = dict(row) if hasattr(row, 'keys') else row
            else:
                # Tenant'ın şubesi yok - bu durumda hata verme, sadece boş sonuç dönecek
                import logging
                logging.warning(f"[get_sube_id] Tenant {effective_tenant_id} için şube bulunamadı, varsayılan şube kullanılacak")
                # sube_id'yi olduğu gibi bırak, menu endpoint'i boş sonuç dönecek

    # Şube erişim izni
    await enforce_user_sube_access(current["username"], sube_id)
    return sube_id
