# Temporary debug endpoint
from typing import Annotated
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from ..core.security import verify_password
from ..db.database import db

router = APIRouter(prefix="/debug", tags=["Debug"])

@router.post("/test-login")
async def test_login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    """Debug endpoint to test login"""
    result = {"step": "start", "username": form_data.username}

    # Step 1: Fetch user
    user = await db.fetch_one(
        "SELECT id, username, sifre_hash, role, aktif FROM users WHERE username = :u",
        {"u": form_data.username}
    )

    if not user:
        result["step"] = "user_not_found"
        return result

    result["step"] = "user_found"
    result["user_id"] = user["id"]
    result["role"] = user["role"]
    result["aktif"] = user["aktif"]
    result["has_hash"] = bool(user["sifre_hash"])

    # Step 2: Check active
    if not user["aktif"]:
        result["step"] = "user_inactive"
        return result

    # Step 3: Verify password
    try:
        pwd_valid = verify_password(form_data.password, user["sifre_hash"])
        result["step"] = "password_verified"
        result["password_valid"] = pwd_valid
    except Exception as e:
        result["step"] = "password_error"
        result["error"] = str(e)

    return result
