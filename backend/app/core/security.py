# backend/app/core/security.py
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple
from jose import jwt, JWTError
import bcrypt
import re

# Güvenlik ayarları: config'den al, fallback olarak env var kullan
import os as _os

# SECRET_KEY: Önce config, yoksa env var
try:
    from .config import settings as _settings
    SECRET_KEY = _settings.SECRET_KEY
except Exception:
    SECRET_KEY = _os.getenv("SECRET_KEY", "dev-secret-key-INSECURE-change-me")

ALGORITHM = _os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(_os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "720"))
REFRESH_TOKEN_EXPIRE_DAYS = int(_os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Password Policy: ENV=prod'da special karakter de zorunlu
_env = _os.getenv("ENV", "dev")
PASSWORD_MIN_LENGTH = int(_os.getenv("PASSWORD_MIN_LENGTH", "12"))
PASSWORD_REQUIRE_UPPERCASE = _os.getenv("PASSWORD_REQUIRE_UPPERCASE", "true").lower() == "true"
PASSWORD_REQUIRE_LOWERCASE = _os.getenv("PASSWORD_REQUIRE_LOWERCASE", "true").lower() == "true"
PASSWORD_REQUIRE_DIGIT = _os.getenv("PASSWORD_REQUIRE_DIGIT", "true").lower() == "true"
# Production'da özel karakter varsayılan olarak zorunlu; dev'de opsiyonel
_special_default = "true" if _env == "prod" else "false"
PASSWORD_REQUIRE_SPECIAL = _os.getenv("PASSWORD_REQUIRE_SPECIAL", _special_default).lower() == "true"

BCRYPT_ROUNDS = int(_os.getenv("BCRYPT_ROUNDS", "12"))



# ========== API Key Encryption ==========
from cryptography.fernet import Fernet
import base64
import hashlib

def _get_fernet_key() -> bytes:
    # Derive a valid url-safe 32-byte key from our SECRET_KEY
    hasher = hashlib.sha256()
    hasher.update(SECRET_KEY.encode('utf-8'))
    return base64.urlsafe_b64encode(hasher.digest())

_fernet = Fernet(_get_fernet_key())

def encrypt_string(plain_text: str) -> str:
    """Encrypt a string at rest securely using Fernet symmetric encryption"""
    return _fernet.encrypt(plain_text.encode('utf-8')).decode('utf-8')

def decrypt_string(encrypted_text: str) -> str:
    """Decrypt a Fernet encrypted string"""
    try:
        return _fernet.decrypt(encrypted_text.encode('utf-8')).decode('utf-8')
    except Exception:
        return ""


class PasswordValidationError(Exception):
    """Raised when password doesn't meet policy requirements"""
    pass


def validate_password(password: str) -> Tuple[bool, Optional[str]]:
    """
    Validate password against security policy.

    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    if len(password) < PASSWORD_MIN_LENGTH:
        return False, f"Password must be at least {PASSWORD_MIN_LENGTH} characters long"

    if PASSWORD_REQUIRE_UPPERCASE and not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"

    if PASSWORD_REQUIRE_LOWERCASE and not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"

    if PASSWORD_REQUIRE_DIGIT and not re.search(r'\d', password):
        return False, "Password must contain at least one digit"

    if PASSWORD_REQUIRE_SPECIAL and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"

    return True, None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password"""
    if not hashed_password:
        return False

    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except ValueError:
        # Invalid hash format in DB
        return False


def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def create_access_token(data: Dict[str, Any], expires_minutes: Optional[int] = None) -> str:
    """
    Create a JWT access token.

    Args:
        data: Payload to encode in the token
        expires_minutes: Token expiration time in minutes

    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: Dict[str, Any], expires_days: Optional[int] = None) -> str:
    """
    Create a JWT refresh token with longer expiration.

    Args:
        data: Payload to encode in the token
        expires_days: Token expiration time in days

    Returns:
        Encoded JWT refresh token
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        days=expires_days or REFRESH_TOKEN_EXPIRE_DAYS
    )
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode and verify a JWT token.

    Args:
        token: JWT token to decode

    Returns:
        Decoded token payload

    Raises:
        JWTError: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        raise JWTError(f"Invalid token: {str(e)}")


def verify_token_type(token: str, expected_type: str = "access") -> bool:
    """
    Verify that token is of expected type (access or refresh).

    Args:
        token: JWT token to verify
        expected_type: Expected token type ("access" or "refresh")

    Returns:
        True if token type matches, False otherwise
    """
    try:
        payload = decode_token(token)
        return payload.get("type") == expected_type
    except JWTError:
        return False
