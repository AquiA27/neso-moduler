"""
Startup validation checks for environment variables and configuration.
"""
import sys
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)


def check_environment_variables() -> Tuple[bool, List[str]]:
    """
    Check if all required environment variables are set.
    Returns (is_valid, error_messages)
    """
    from .config import settings

    errors = []
    warnings = []

    # Check DATABASE_URL
    if not settings.DATABASE_URL:
        errors.append("DATABASE_URL is not set")
    elif settings.DATABASE_URL == "postgresql+asyncpg://neso:neso123@localhost:5432/neso":
        errors.append(
            "DATABASE_URL is using default value. "
            "Please set it to your actual database connection string."
        )
    elif "localhost" in settings.DATABASE_URL:
        warnings.append(
            "DATABASE_URL contains 'localhost'. "
            "Make sure this is intentional for production deployment."
        )
    elif not (settings.DATABASE_URL.startswith("postgresql+asyncpg://") or
              settings.DATABASE_URL.startswith("postgresql://")):
        errors.append(
            f"DATABASE_URL must start with 'postgresql+asyncpg://' or 'postgresql://' but got: "
            f"{settings.DATABASE_URL[:30]}..."
        )

    # Check SECRET_KEY
    if not settings.SECRET_KEY or settings.SECRET_KEY in ("change-me", "dev-secret-key-change-me-INSECURE"):
        if settings.ENV == "prod":
            errors.append(
                "SECRET_KEY is not set or using default value in PRODUCTION! "
                "Generate: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        else:
            warnings.append(
                "SECRET_KEY is using default insecure value. "
                "Set SECRET_KEY in .env for development too."
            )
    elif len(settings.SECRET_KEY) < 32:
        warnings.append(
            f"SECRET_KEY is only {len(settings.SECRET_KEY)} chars. "
            "Recommend at least 32 chars for security."
        )

    # Check DEFAULT_ADMIN_PASSWORD
    if settings.DEFAULT_ADMIN_PASSWORD in ("admin123", "admin", "password", "123456"):
        if settings.ENV == "prod":
            errors.append(
                "DEFAULT_ADMIN_PASSWORD is using a weak default value in PRODUCTION! "
                "Set DEFAULT_ADMIN_PASSWORD in .env with a strong password."
            )
        else:
            warnings.append(
                "DEFAULT_ADMIN_PASSWORD is weak ('admin123'). "
                "For production, set a strong password in .env."
            )

    # Check RATE_LIMIT in production
    if settings.ENV == "prod" and settings.RATE_LIMIT_PER_MINUTE == 0:
        errors.append(
            "RATE_LIMIT_PER_MINUTE is 0 (disabled) in PRODUCTION. "
            "Set RATE_LIMIT_PER_MINUTE=60 in .env to prevent abuse."
        )

    # Check CORS in production
    if settings.ENV == "prod" and isinstance(settings.CORS_ORIGINS, list):
        if any("localhost" in origin for origin in settings.CORS_ORIGINS):
            warnings.append(
                "CORS_ORIGINS contains localhost URLs in production. "
                "Set CORS_ORIGINS to your actual frontend domain in .env."
            )

    # Check ENV value
    if settings.ENV not in ["dev", "prod"]:
        warnings.append(f"ENV is '{settings.ENV}', expected 'dev' or 'prod'")

    # Print warnings
    if warnings:
        logger.warning("=" * 60)
        logger.warning("CONFIGURATION WARNINGS:")
        for warning in warnings:
            logger.warning(f"  ⚠️  {warning}")
        logger.warning("=" * 60)

    # Print errors
    if errors:
        logger.error("=" * 60)
        logger.error("CONFIGURATION ERRORS - Application cannot start in production:")
        for error in errors:
            logger.error(f"  ❌ {error}")
        logger.error("=" * 60)
        logger.error("")
        logger.error("Production checklist (.env veya Render Dashboard > Environment):")
        logger.error("  1. DATABASE_URL=postgresql+asyncpg://user:pass@host/db")
        logger.error("  2. SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')")
        logger.error("  3. ENV=prod")
        logger.error("  4. CORS_ORIGINS=https://your-frontend.vercel.app")
        logger.error("  5. RATE_LIMIT_PER_MINUTE=60")
        logger.error("  6. DEFAULT_ADMIN_PASSWORD=<strong-password>")
        logger.error("=" * 60)

    return len(errors) == 0, errors


def validate_startup():
    """
    Run all startup checks.
    - In production (ENV=prod): exits on any error.
    - In development (ENV=dev): logs warnings, does NOT block startup.
    """
    from .config import settings
    is_valid, errors = check_environment_variables()

    if not is_valid:
        if settings.ENV == "prod":
            logger.critical("Startup validation FAILED in production mode. Exiting.")
            raise RuntimeError("Startup validation failed: " + "; ".join(errors))
        else:
            logger.warning(
                "⚠️ Startup validation found issues in dev mode. "
                "Fix before deploying to production."
            )
    else:
        logger.info("✅ Startup validation passed")
