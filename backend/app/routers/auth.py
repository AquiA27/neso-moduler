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
from ..core.deps import get_current_user, get_current_user_and_role
from ..db.database import db

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


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8, description="New password (min 8 chars)")


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    aktif: bool


# ========== Authentication Endpoints ==========

@router.post("/token", response_model=TokenOut)
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    """
    Login with username and password.
    Returns access token and refresh token.
    """
    # Fetch user from database (tenant_id dahil)
    user = await db.fetch_one(
        "SELECT id, username, sifre_hash, role, tenant_id, aktif FROM users WHERE username = :u",
        {"u": form_data.username}
    )

    if not user:
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

    # Verify password
    if not verify_password(form_data.password, user_dict.get("sifre_hash", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
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

    # Hash password and insert user
    hashed = hash_password(request.password)
    user = await db.fetch_one(
        """
        INSERT INTO users (username, sifre_hash, role, aktif)
        VALUES (:u, :h, :r, TRUE)
        RETURNING id, username, role, aktif
        """,
        {"u": request.username, "h": hashed, "r": request.role}
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

    return UserResponse(**user)


@router.get("/pong")
async def pong(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Test endpoint to verify authentication"""
    return {"message": f"secure pong, {current_user['username']}"}
