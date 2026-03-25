# backend/app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from typing import Annotated, Dict, Any, Optional
from ..core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    validate_password,
    decode_token,
    verify_token_type,
)
from ..core.deps import get_current_user, get_current_user_and_role, oauth2_scheme
from ..db.database import db
from ..services.cache import cache_service

router = APIRouter(prefix="/auth", tags=["Auth"])


# ========== Pydantic Models ==========

class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., description="Refresh token to exchange for new access token")


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Username (3-50 characters)")
    password: str = Field(..., min_length=8, description="Password (min 8 chars)")
    role: Optional[str] = Field("operator", description="User role: operator, admin, super_admin")
    tenant_id: Optional[int] = Field(None, description="Tenant ID (required for super_admin, auto-set for admin)")


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8, description="New password (min 8 chars)")


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    aktif: bool

class MFAVerifyRequest(BaseModel):
    temp_token: str = Field(..., description="Temporary token received after password verification")
    code: str = Field(..., description="6-digit MFA code")

class MFAEnableRequest(BaseModel):
    code: str = Field(..., description="6-digit MFA code to confirm setup")


# ========== Authentication Endpoints ==========

@router.post("/token", response_model=TokenOut)
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    """
    Login with username and password.
    Returns access token and refresh token.
    Includes brute-force protection and account lockout.
    """
    username = form_data.username
    lockout_key = f"lockout:{username}"
    attempts_key = f"login_attempts:{username}"

    # 1. Lockout Check
    if cache_service.is_enabled():
        is_locked = await cache_service.exists(lockout_key)
        if is_locked:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account temporarily locked due to multiple failed login attempts. Please try again in 15 minutes."
            )

    # Fetch user from database (tenant_id dahil)
    # mfa_enabled might not exist yet on older deployments, fallback gracefully
    try:
        user = await db.fetch_one(
            "SELECT id, username, sifre_hash, role, tenant_id, aktif, mfa_enabled FROM users WHERE username = :u",
            {"u": username}
        )
    except Exception:
        user = await db.fetch_one(
            "SELECT id, username, sifre_hash, role, tenant_id, aktif FROM users WHERE username = :u",
            {"u": username}
        )

    if not user:
        # Invalid username - Increment attempt to prevent username enumeration timing attacks easily
        if cache_service.is_enabled():
            attempts = await cache_service.get(attempts_key) or 0
            attempts += 1
            if attempts >= 5:
                await cache_service.set(lockout_key, "1", 900)
                await cache_service.delete(attempts_key)
            else:
                await cache_service.set(attempts_key, attempts, 3600)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Record objesini dictionary'ye çevir (PostgreSQL Record objesi .get() metoduna sahip değil)
    user_dict = dict(user) if hasattr(user, 'keys') else user

    # Check if user is active
    if not user_dict.get("aktif"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated"
        )

    # Verify password - guard against NULL sifre_hash (password-less accounts)
    pw_hash = user_dict.get("sifre_hash")
    if not pw_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not verify_password(form_data.password, pw_hash):
        if cache_service.is_enabled():
            attempts = await cache_service.get(attempts_key) or 0
            attempts += 1
            if attempts >= 5:
                # Lock for 15 minutes (900 seconds)
                await cache_service.set(lockout_key, "1", 900)
                await cache_service.delete(attempts_key)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Account locked for 15 minutes due to too many failed attempts."
                )
            else:
                # Remember attempt for 1 hour
                await cache_service.set(attempts_key, attempts, 3600)
                
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Successful login - Reset attempts
    if cache_service.is_enabled():
        await cache_service.delete(attempts_key)

    # Check if MFA is enabled
    mfa_enabled = user_dict.get("mfa_enabled", False)
    # Require MFA if enabled OR if super admin (and force setup if missing)
    # Actually, we will just honor the DB column here.
    if mfa_enabled:
        temp_token_data = {"sub": user_dict.get("username"), "type": "mfa_temp"}
        temp_token = create_access_token(temp_token_data, expires_minutes=5)
        # We return a specific 403 response so frontend knows to show MFA input
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "MFA code required",
                "mfa_required": True,
                "temp_token": temp_token
            }
        )

    # Create tokens (tenant_id dahil)
    token_data = {
        "sub": user_dict.get("username"),
        "role": user_dict.get("role"),
        "tenant_id": user_dict.get("tenant_id"),  # Super admin için None olabilir
    }
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token({"sub": user_dict.get("username")})

    return TokenOut(
        access_token=access_token,
        refresh_token=refresh_token
    )


@router.post("/refresh", response_model=TokenOut)
async def refresh_token(request: RefreshTokenRequest):
    """
    Exchange refresh token for new access token and refresh token.
    """
    try:
        # Verify it's a refresh token
        if not verify_token_type(request.refresh_token, "refresh"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )

        # Decode and validate
        payload = decode_token(request.refresh_token)
        username = payload.get("sub")

        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )

        # Fetch fresh user data
        user = await db.fetch_one(
            "SELECT username, role, aktif FROM users WHERE username = :u",
            {"u": username}
        )

        if not user or not user["aktif"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or deactivated"
            )

        # Create new tokens
        token_data = {"sub": user["username"], "role": user["role"]}
        access_token = create_access_token(token_data)
        new_refresh_token = create_refresh_token({"sub": user["username"]})

        return TokenOut(
            access_token=access_token,
            refresh_token=new_refresh_token
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token refresh failed: {str(e)}"
        )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    current_user: Dict[str, Any] = Depends(get_current_user_and_role)
):
    """
    Register a new user. Requires admin or super_admin role.
    """
    # Check permissions
    if current_user["role"] not in ["admin", "super_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can register new users"
        )

    # Validate password
    is_valid, error_msg = validate_password(request.password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )

    # Check if username already exists
    existing = await db.fetch_one(
        "SELECT id FROM users WHERE username = :u",
        {"u": request.username}
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists"
        )

    # Determine tenant_id:
    # - If current user is admin, use their tenant_id
    # - If current user is super_admin, use tenant_id from request (or None for super_admin users)
    tenant_id = None
    if current_user["role"] == "admin":
        # Admin users can only create users for their own tenant
        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin users must have a tenant_id"
            )
    elif current_user["role"] == "super_admin":
        # Super admin can specify tenant_id or create super_admin users (tenant_id=None)
        tenant_id = request.tenant_id
        # If creating a non-super_admin user, tenant_id is required
        if request.role != "super_admin" and not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="tenant_id is required when creating non-super_admin users"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can register new users"
        )

    # Hash password and insert user
    hashed = hash_password(request.password)
    user = await db.fetch_one(
        """
        INSERT INTO users (username, sifre_hash, role, tenant_id, aktif)
        VALUES (:u, :h, :r, :tid, TRUE)
        RETURNING id, username, role, aktif
        """,
        {"u": request.username, "h": hashed, "r": request.role, "tid": tenant_id}
    )

    return UserResponse(**user)


@router.post("/change-password")
async def change_password(
    request: PasswordChangeRequest,
    current_user: Dict[str, Any] = Depends(get_current_user_and_role)
):
    """
    Change current user's password.
    """
    # Fetch current user data
    user = await db.fetch_one(
        "SELECT sifre_hash FROM users WHERE username = :u",
        {"u": current_user["username"]}
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Verify old password
    if not verify_password(request.old_password, user["sifre_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect"
        )

    # Validate new password
    is_valid, error_msg = validate_password(request.new_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )

    # Update password
    hashed = hash_password(request.new_password)
    await db.execute(
        "UPDATE users SET sifre_hash = :h WHERE username = :u",
        {"h": hashed, "u": current_user["username"]}
    )

    return {"message": "Password changed successfully"}


# ========== User Info Endpoints ==========

@router.get("/me", response_model=UserResponse)
async def me(info: Dict[str, Any] = Depends(get_current_user_and_role)):
    """Get current user information"""
    user = await db.fetch_one(
        "SELECT id, username, role, aktif FROM users WHERE username = :u",
        {"u": info["username"]}
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Record objesini dictionary'ye çevir
    user_dict = dict(user) if hasattr(user, 'keys') else user
    
    return UserResponse(
        id=int(user_dict.get("id")),
        username=str(user_dict.get("username")),
        role=str(user_dict.get("role")),
        aktif=bool(user_dict.get("aktif")),
    )


@router.get("/pong")
async def pong(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Test endpoint to verify authentication"""
    return {"message": f"secure pong, {current_user['username']}"}


@router.post("/logout")
async def logout(token: str = Depends(oauth2_scheme)):
    """
    Logout the user by adding their access token to the Redis deny list.
    """
    from ..services.cache import cache_service
    import time
    
    if cache_service.is_enabled():
        try:
            payload = decode_token(token)
            exp = payload.get("exp")
            if exp:
                ttl = int(exp - time.time())
                if ttl > 0:
                    await cache_service.set(f"denylist:{token}", "1", ttl)
        except Exception:
            pass # Token invalid or already expired
            
    return {"message": "Successfully logged out"}


# ========== MFA Endpoints ==========

@router.post("/token/mfa", response_model=TokenOut)
async def verify_mfa_login(request: MFAVerifyRequest):
    """
    Verify MFA code and return real access/refresh tokens.
    """
    import pyotp
    payload = decode_token(request.temp_token)
    if payload.get("type") != "mfa_temp":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    username = payload.get("sub")

    user = await db.fetch_one(
        "SELECT username, role, tenant_id, mfa_secret, aktif FROM users WHERE username = :u", 
        {"u": username}
    )
    if not user or not user["aktif"]:
        raise HTTPException(status_code=401, detail="User not found or inactive")
        
    if not user["mfa_secret"]:
        raise HTTPException(status_code=400, detail="MFA is not configured for this user")

    totp = pyotp.TOTP(user["mfa_secret"])
    if not totp.verify(request.code):
        raise HTTPException(status_code=401, detail="Invalid MFA code")

    token_data = {
        "sub": user["username"],
        "role": user["role"],
        "tenant_id": user["tenant_id"],
    }
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token({"sub": user["username"]})

    return TokenOut(access_token=access_token, refresh_token=refresh_token)


@router.post("/mfa/setup")
async def mfa_setup(current_user: Dict[str, Any] = Depends(get_current_user_and_role)):
    """
    Generate a new MFA secret and provisioning URI. 
    User is required to verify it before it gets enabled.
    """
    import pyotp
    secret = pyotp.random_base32()
    
    # Store the secret but do NOT enable MFA yet
    await db.execute(
        "UPDATE users SET mfa_secret = :s, mfa_enabled = FALSE WHERE username = :u",
        {"s": secret, "u": current_user["username"]}
    )
    
    uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=current_user["username"], 
        issuer_name="Neso Moduler"
    )
    
    return {"secret": secret, "uri": uri}


@router.post("/mfa/enable")
async def mfa_enable(request: MFAEnableRequest, current_user: Dict[str, Any] = Depends(get_current_user_and_role)):
    """
    Confirm the generated MFA secret with a valid code to enable MFA permanently.
    """
    import pyotp
    user = await db.fetch_one(
        "SELECT mfa_secret FROM users WHERE username = :u", 
        {"u": current_user["username"]}
    )
    if not user or not user["mfa_secret"]:
        raise HTTPException(status_code=400, detail="MFA setup has not been initiated")
        
    totp = pyotp.TOTP(user["mfa_secret"])
    if not totp.verify(request.code):
        raise HTTPException(status_code=401, detail="Invalid MFA code. Cannot enable.")
        
    await db.execute(
        "UPDATE users SET mfa_enabled = TRUE WHERE username = :u", 
        {"u": current_user["username"]}
    )
    return {"message": "MFA clearly verified and enabled successfully"}

