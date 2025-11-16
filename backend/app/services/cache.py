# backend/app/services/cache.py
"""
Redis Cache Service
Performans iyileştirmesi için Redis tabanlı caching katmanı
"""
import json
import hashlib
from typing import Optional, Any, Callable
from functools import wraps
import redis.asyncio as aioredis
from redis.asyncio import Redis
from redis.exceptions import RedisError

from ..core.config import settings
import logging
import asyncio

logger = logging.getLogger(__name__)


class CacheService:
    """Redis Cache servisi - Singleton pattern"""

    _instance: Optional['CacheService'] = None
    _redis: Optional[Redis] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def connect(self):
        """Redis bağlantısını başlat"""
        if not settings.REDIS_ENABLED:
            logger.info("Redis cache disabled in settings")
            return

        try:
            self._redis = await aioredis.from_url(
                settings.REDIS_URL,
                max_connections=settings.REDIS_POOL_SIZE,
                socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
                decode_responses=True,
                encoding="utf-8"
            )
            # Connection test
            await self._redis.ping()
            logger.info(f"Redis cache connected: {settings.REDIS_URL}")
        except RedisError as e:
            logger.warning(f"Redis connection failed: {e}. Caching disabled.")
            self._redis = None
        except Exception as e:
            logger.error(f"Unexpected error connecting to Redis: {e}")
            self._redis = None

    async def disconnect(self):
        """Redis bağlantısını kapat"""
        if self._redis:
            await self._redis.close()
            logger.info("Redis cache disconnected")

    def is_enabled(self) -> bool:
        """Cache aktif mi?"""
        return settings.REDIS_ENABLED and self._redis is not None

    async def get(self, key: str) -> Optional[Any]:
        """Cache'den veri çek"""
        if not self.is_enabled():
            return None

        try:
            value = await self._redis.get(key)
            if value:
                return json.loads(value)
            return None
        except (RedisError, json.JSONDecodeError) as e:
            logger.warning(f"Cache get error for key '{key}': {e}")
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Cache'e veri yaz"""
        if not self.is_enabled():
            return False

        try:
            serialized = json.dumps(value, ensure_ascii=False, default=str)
            if ttl:
                await self._redis.setex(key, ttl, serialized)
            else:
                await self._redis.set(key, serialized)
            return True
        except (RedisError, TypeError, ValueError) as e:
            logger.warning(f"Cache set error for key '{key}': {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Cache'den veri sil"""
        if not self.is_enabled():
            return False

        try:
            await self._redis.delete(key)
            return True
        except RedisError as e:
            logger.warning(f"Cache delete error for key '{key}': {e}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Pattern ile eşleşen tüm anahtarları sil"""
        if not self.is_enabled():
            return 0

        try:
            keys = []
            async for key in self._redis.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                return await self._redis.delete(*keys)
            return 0
        except RedisError as e:
            logger.warning(f"Cache delete pattern error for '{pattern}': {e}")
            return 0

    async def clear_all(self) -> bool:
        """Tüm cache'i temizle"""
        if not self.is_enabled():
            return False

        try:
            await self._redis.flushdb()
            logger.info("Cache cleared completely")
            return True
        except RedisError as e:
            logger.error(f"Cache clear error: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Key var mı kontrol et"""
        if not self.is_enabled():
            return False

        try:
            return await self._redis.exists(key) > 0
        except RedisError:
            return False

    async def get_stats(self) -> dict:
        """Cache istatistiklerini getir"""
        if not self.is_enabled():
            return {"enabled": False}

        try:
            info = await self._redis.info()
            return {
                "enabled": True,
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "total_keys": await self._redis.dbsize(),
                "hit_rate": info.get("keyspace_hits", 0) /
                           (info.get("keyspace_hits", 0) + info.get("keyspace_misses", 1))
            }
        except RedisError as e:
            logger.warning(f"Cache stats error: {e}")
            return {"enabled": True, "error": str(e)}


# Global cache instance
cache_service = CacheService()


def cache_key(*args, **kwargs) -> str:
    """Cache key oluştur (fonksiyon parametrelerinden)"""
    key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    return hashlib.md5(key_data.encode()).hexdigest()


def cached(
    ttl: int = settings.CACHE_TTL_MEDIUM,
    key_prefix: str = "",
    key_builder: Optional[Callable] = None
):
    """
    Cache decorator - Fonksiyon sonucunu cache'ler

    Usage:
        @cached(ttl=300, key_prefix="menu")
        async def get_menu_items(tenant_id: int, sube_id: int):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Cache key oluştur
            if key_builder:
                cache_k = key_builder(*args, **kwargs)
            else:
                params_key = cache_key(*args, **kwargs)
                cache_k = f"{key_prefix}:{func.__name__}:{params_key}"

            # Cache'den dene
            cached_value = await cache_service.get(cache_k)
            if cached_value is not None:
                logger.debug(f"Cache HIT: {cache_k}")
                return cached_value

            # Cache miss - fonksiyonu çalıştır
            logger.debug(f"Cache MISS: {cache_k}")
            result = await func(*args, **kwargs)

            # Sonucu cache'e kaydet
            await cache_service.set(cache_k, result, ttl)

            return result

        return wrapper
    return decorator


def invalidate_cache_pattern(pattern: str):
    """
    Cache invalidation decorator - Fonksiyon çalıştıktan sonra pattern ile eşleşen cache'leri sil

    Usage:
        @invalidate_cache_pattern("menu:*")
        async def update_menu_item(item_id: int, ...):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            # Fonksiyon başarılı olduysa cache'i temizle
            deleted = await cache_service.delete_pattern(pattern)
            if deleted > 0:
                logger.info(f"Invalidated {deleted} cache entries with pattern: {pattern}")
            return result
        return wrapper
    return decorator

AI_CACHE_PREFIX = "ai_data-*"
AI_CACHE_TTL_MS = 60_000

def _sanitize_pattern(pattern: str) -> str:
    return pattern if pattern.endswith("*") else f"{pattern}*"


def invalidate(pattern: str) -> None:
    if not cache_service.is_enabled():
        return
    sanitized_pattern = _sanitize_pattern(pattern)
    logger.info("Cache invalidate: pattern=%s", sanitized_pattern)
    asyncio.create_task(cache_service.delete_pattern(sanitized_pattern))


def invalidate_ai_cache_sync() -> None:
    invalidate(AI_CACHE_PREFIX)