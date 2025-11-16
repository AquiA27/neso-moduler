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
    elif not settings.DATABASE_URL.startswith("postgresql+asyncpg://"):
        errors.append(
            f"DATABASE_URL must start with 'postgresql+asyncpg://' but got: "
            f"{settings.DATABASE_URL[:30]}..."
        )

    # Check SECRET_KEY
    if not settings.SECRET_KEY or settings.SECRET_KEY == "change-me":
        errors.append(
            "SECRET_KEY is not set or using default value. "
            "Generate a strong key with: openssl rand -hex 32"
        )

    # Check ENV
    if settings.ENV not in ["dev", "prod"]:
        warnings.append(f"ENV is '{settings.ENV}', expected 'dev' or 'prod'")

    # Check CORS
    if settings.ENV == "prod" and isinstance(settings.CORS_ORIGINS, list):
        if any("localhost" in origin for origin in settings.CORS_ORIGINS):
            warnings.append(
                "CORS_ORIGINS contains localhost URLs in production. "
                "Make sure to add your actual frontend domain."
            )

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
        logger.error("CONFIGURATION ERRORS - Application cannot start:")
        for error in errors:
            logger.error(f"  ❌ {error}")
        logger.error("=" * 60)
        logger.error("")
        logger.error("For Render deployment, set these in Dashboard > Environment:")
        logger.error("  1. DATABASE_URL=postgresql+asyncpg://user:pass@host/db")
        logger.error("  2. SECRET_KEY=your-random-secret-key")
        logger.error("  3. ENV=prod")
        logger.error("  4. CORS_ORIGINS=https://your-frontend.onrender.com")
        logger.error("")
        logger.error("See RENDER_DEPLOYMENT.md for detailed instructions.")
        logger.error("=" * 60)

    return len(errors) == 0, errors


def validate_startup():
    """
    Run all startup checks and exit if critical errors are found.
    """
    is_valid, errors = check_environment_variables()

    if not is_valid:
        logger.critical("Startup validation failed. Exiting.")
        sys.exit(1)

    logger.info("✅ Startup validation passed")
