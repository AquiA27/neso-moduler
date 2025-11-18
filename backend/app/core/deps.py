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
    
    # Tenant_id'yi token'dan veya DB'den al
    tenant_id = user_dict.get("tenant_id") or token_tenant_id
    user_dict["tenant_id"] = tenant_id
    
    # Super admin için X-Tenant-Id header'ını veya tenant_id query parameter'ını kontrol et (tenant switching)
    switched_tenant_id = None
    if user_dict.get("role") == "super_admin" and request:
        # Önce query parameter'ı kontrol et (frontend'den gelen)
        query_params = dict(request.query_params) if hasattr(request, 'query_params') else {}
        tenant_id_param = query_params.get("tenant_id")
        
        # Sonra header'ı kontrol et (alternatif yöntem)
        x_tenant_id = request.headers.get("X-Tenant-Id")
        
        # Query parameter öncelikli, yoksa header
        tenant_id_value = tenant_id_param or x_tenant_id
        
        if tenant_id_value:
            try:
                switched_tenant_id = int(tenant_id_value)
                # Tenant'ın var olduğunu ve aktif olduğunu kontrol et
                tenant_check = await db.fetch_one(
                    "SELECT id, aktif FROM isletmeler WHERE id = :tid",
                    {"tid": switched_tenant_id},
                )
                if not tenant_check or not tenant_check.get("aktif"):
                    # Tenant yoksa veya pasifse, switched_tenant_id'yi None yap
                    switched_tenant_id = None
                else:
                    # Super admin'in bu tenant'ın context'inde çalışması için tenant_id'yi geçici olarak değiştir
                    user_dict["switched_tenant_id"] = switched_tenant_id
                    user_dict["tenant_id"] = switched_tenant_id  # Geçici olarak switched tenant'ın context'i
            except (ValueError, TypeError):
                # Geçersiz tenant_id, görmezden gel
                switched_tenant_id = None
    
    return user_dict


async def get_current_user_and_role(
    request: StarletteRequest,
    token: str = Depends(oauth2_scheme)
) -> Mapping[str, Any]:
    """
    Rolü token'dan **değil**, DB'den okur (güncel yetki için daha güvenli).
    """
    import logging
    user = await get_current_user(request, token)
    logging.info(f"get_current_user_and_role: user={user}")
    return {"username": user["username"], "role": user["role"], "id": user["id"]}


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
    - İkisi de yoksa: 1 (DEMO varsayılanı) — prod’da zorunlu yapacağız
    Ayrıca şubenin aktifliğini ve kullanıcının erişim iznini doğrular.
    """
    sube_id = x_sube_id if x_sube_id is not None else sube_id_q
    if sube_id is None:
        sube_id = 1  # DEMO varsayılanı

    # Şube aktif mi?
    row = await db.fetch_one(
        "SELECT id FROM subeler WHERE id = :id AND aktif = TRUE",
        {"id": sube_id},
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Geçersiz veya pasif sube_id",
        )

    # Şube erişim izni
    await enforce_user_sube_access(current["username"], sube_id)
    return sube_id
