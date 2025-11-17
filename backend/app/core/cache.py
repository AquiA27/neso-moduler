# backend/app/core/cache.py
"""
Cache service - Redis veya in-memory fallback
"""
import json
import time
from typing import Optional, Any, Dict
from functools import wraps
import logging

from .config import settings

logger = logging.getLogger(__name__)

# Redis client (opsiyonel)
_redis_client: Optional[Any] = None


def _init_redis():
    """Redis client'ı initialize et"""
    global _redis_client
    if not settings.REDIS_ENABLED:
        return None
    
    try:
        import redis.asyncio as redis
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            max_connections=settings.REDIS_POOL_SIZE,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
            decode_responses=True,
        )
        logger.info("Redis cache initialized")
        return _redis_client
    except ImportError:
        logger.warning("Redis not installed, using in-memory cache")
        return None
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}, using in-memory cache")
        return None


# In-memory cache fallback
_in_memory_cache: Dict[str, Dict[str, Any]] = {}
_cache_ttl: Dict[str, float] = {}


class CacheService:
    """Cache service - Redis veya in-memory fallback"""
    
    def __init__(self):
        self.redis = None
        self.use_redis = False
        
        if settings.REDIS_ENABLED:
            self.redis = _init_redis()
            self.use_redis = self.redis is not None
    
    async def get(self, key: str) -> Optional[Any]:
        """Cache'den değer al"""
        if self.use_redis and self.redis:
            try:
                value = await self.redis.get(key)
                if value:
                    return json.loads(value)
            except Exception as e:
                logger.warning(f"Redis get error: {e}")
                # Fallback to in-memory
                self.use_redis = False
        
        # In-memory fallback
        if key in _in_memory_cache:
            cache_entry = _in_memory_cache[key]
            expire_time = cache_entry.get("expire_time", 0)
            if expire_time > time.time():
                return cache_entry.get("value")
            else:
                # Expired, remove
                del _in_memory_cache[key]
                if key in _cache_ttl:
                    del _cache_ttl[key]
        
        return None
    
    async def set(self, key: str, value: Any, ttl: int = settings.CACHE_TTL_MEDIUM):
        """Cache'e değer set et"""
        if self.use_redis and self.redis:
            try:
                await self.redis.setex(
                    key,
                    ttl,
                    json.dumps(value, default=str)
                )
                return
            except Exception as e:
                logger.warning(f"Redis set error: {e}")
                # Fallback to in-memory
                self.use_redis = False
        
        # In-memory fallback
        _in_memory_cache[key] = {
            "value": value,
            "expire_time": time.time() + ttl,
        }
        _cache_ttl[key] = ttl
    
    async def delete(self, key: str):
        """Cache'den değer sil"""
        if self.use_redis and self.redis:
            try:
                await self.redis.delete(key)
            except Exception as e:
                logger.warning(f"Redis delete error: {e}")
        
        # In-memory fallback
        if key in _in_memory_cache:
            del _in_memory_cache[key]
        if key in _cache_ttl:
            del _cache_ttl[key]
    
    async def delete_pattern(self, pattern: str):
        """Pattern'e uyan tüm cache key'lerini sil"""
        if self.use_redis and self.redis:
            try:
                keys = await self.redis.keys(pattern)
                if keys:
                    await self.redis.delete(*keys)
                return
            except Exception as e:
                logger.warning(f"Redis delete_pattern error: {e}")
        
        # In-memory fallback - simple prefix match
        keys_to_delete = [key for key in _in_memory_cache.keys() if pattern.replace("*", "") in key]
        for key in keys_to_delete:
            await self.delete(key)
    
    async def clear(self):
        """Tüm cache'i temizle"""
        if self.use_redis and self.redis:
            try:
                await self.redis.flushdb()
            except Exception as e:
                logger.warning(f"Redis clear error: {e}")
        
        # In-memory fallback
        _in_memory_cache.clear()
        _cache_ttl.clear()


# Global cache instance
cache = CacheService()


def cache_key(*args, **kwargs) -> str:
    """Cache key oluştur"""
    parts = []
    for arg in args:
        if arg is not None:
            parts.append(str(arg))
    for k, v in sorted(kwargs.items()):
        if v is not None:
            parts.append(f"{k}:{v}")
    return ":".join(parts)


def cached(ttl: int = settings.CACHE_TTL_MEDIUM, key_prefix: str = ""):
    """
    Decorator: Fonksiyon sonucunu cache'le
    
    Usage:
        @cached(ttl=300, key_prefix="menu")
        async def get_menu(sube_id: int):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Cache key oluştur
            func_name = func.__name__
            cache_key_parts = [key_prefix, func_name] if key_prefix else [func_name]
            
            # Positional args'ları ekle
            for arg in args:
                if isinstance(arg, (int, str, float, bool)):
                    cache_key_parts.append(str(arg))
            
            # Keyword args'ları ekle (sensitive olmayanlar)
            skip_kwargs = {"self", "_", "current_user", "user"}
            for k, v in sorted(kwargs.items()):
                if k not in skip_kwargs and isinstance(v, (int, str, float, bool)):
                    cache_key_parts.append(f"{k}:{v}")
            
            cache_key_str = ":".join(cache_key_parts)
            
            # Cache'den kontrol et
            cached_value = await cache.get(cache_key_str)
            if cached_value is not None:
                return cached_value
            
            # Cache'de yoksa fonksiyonu çalıştır
            result = await func(*args, **kwargs)
            
            # Sonucu cache'le
            await cache.set(cache_key_str, result, ttl=ttl)
            
            return result
        
        return wrapper
    return decorator

