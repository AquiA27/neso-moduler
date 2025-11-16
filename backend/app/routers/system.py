from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from ..core.config import settings
from ..db.database import db
from ..core.deps import get_current_user
from ..services.cache import cache_service

router = APIRouter(prefix="", tags=["Sistem"])

@router.get("/health")
async def health():
    """
    Production-ready health check endpoint.
    Returns 200 if healthy, 503 if unhealthy.
    """
    checks = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": settings.APP_NAME,
        "version": settings.VERSION,
        "env": settings.ENV,
        "database": "unknown",
        "redis": "unknown"
    }
    
    # Database check
    try:
        await db.fetch_one("SELECT 1;")
        checks["database"] = "connected"
    except Exception as e:
        checks["database"] = "disconnected"
        checks["status"] = "unhealthy"
        checks["database_error"] = str(e)
    
    # Redis check (optional)
    try:
        if cache_service and hasattr(cache_service, 'redis') and cache_service.redis:
            await cache_service.get("health_check_test")
            checks["redis"] = "connected"
        else:
            checks["redis"] = "optional"
    except Exception:
        checks["redis"] = "optional"  # Redis is optional, don't fail if disconnected
    
    # Return 503 if unhealthy
    if checks["status"] == "unhealthy":
        raise HTTPException(status_code=503, detail=checks)
    
    return checks

@router.get("/version")
async def version():
    return {"app": settings.APP_NAME, "version": settings.VERSION, "env": settings.ENV}

@router.get("/me")
async def me(current_user: str = Depends(get_current_user)):
    # get_current_user şu an username döndürüyor
    return {"user": current_user}
