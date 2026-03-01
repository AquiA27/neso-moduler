# backend/app/services/rate_limiter.py
"""
API Key Rate Limiting Service
Redis veya in-memory fallback ile rate limiting
"""
import time
import logging
from dataclasses import dataclass
from typing import Dict, Optional
from collections import defaultdict, deque

from .cache import cache_service

logger = logging.getLogger(__name__)


@dataclass
class RateLimitResult:
    """Rate limit kontrolÃ¼nÃ¼n detaylÄ± sonucunu temsil eder."""

    allowed: bool
    remaining: int
    retry_after: Optional[int] = None
    reset_after: Optional[int] = None


class RateLimiter:
    """API Key bazlÄ± rate limiting servisi."""

    def __init__(self):
        # In-memory fallback (Redis yoksa)
        self._in_memory_hits: Dict[int, deque] = defaultdict(deque)
        self._window_seconds = 60

    async def check_rate_limit(
        self,
        api_key_id: int,
        rate_limit_per_minute: int,
    ) -> RateLimitResult:
        """
        Rate limit kontrolÃ¼ yapar ve kalan hak / reset bilgilerini dÃ¶ner.
        """
        if rate_limit_per_minute <= 0:
            # Rate limit devre dÄ±ÅŸÄ±
            return RateLimitResult(True, remaining=rate_limit_per_minute)

        now = time.time()
        cache_key = f"rate_limit:api_key:{api_key_id}"

        # Redis kullanÄ±labilirse Redis ile yap
        if cache_service.is_enabled():
            try:
                return await self._check_redis_rate_limit(
                    cache_key,
                    rate_limit_per_minute,
                    now,
                )
            except Exception as e:
                logger.warning("Redis rate limit check failed: %s, falling back to in-memory", e)

        # In-memory fallback
        return self._check_in_memory_rate_limit(
            api_key_id,
            rate_limit_per_minute,
            now,
        )

    async def _check_redis_rate_limit(
        self,
        cache_key: str,
        rate_limit_per_minute: int,
        now: float,
    ) -> RateLimitResult:
        """Redis ile rate limit kontrolÃ¼ (sliding window)."""
        try:
            redis_client = cache_service.get_redis_client()

            if not redis_client:
                raise RuntimeError("Redis client not available")

            # Sliding window: son 60 saniyedeki istekleri say
            window_start = now - self._window_seconds

            # Eski kayÄ±tlarÄ± temizle
            await redis_client.zremrangebyscore(cache_key, 0, window_start)

            # Mevcut istek sayÄ±sÄ±
            current_count = await redis_client.zcard(cache_key)

            if current_count >= rate_limit_per_minute:
                # Rate limit aÅŸÄ±ldÄ±
                oldest = await redis_client.zrange(cache_key, 0, 0, withscores=True)
                oldest_timestamp = oldest[0][1] if oldest else None
                retry_after = self._seconds_until_reset(now, oldest_timestamp)
                return RateLimitResult(False, remaining=0, retry_after=retry_after, reset_after=retry_after)

            # Yeni isteÄŸi ekle
            await redis_client.zadd(cache_key, {str(now): now})
            # TTL ayarla (window_seconds + 10 saniye buffer)
            await redis_client.expire(cache_key, self._window_seconds + 10)

            remaining = max(rate_limit_per_minute - (current_count + 1), 0)
            oldest = await redis_client.zrange(cache_key, 0, 0, withscores=True)
            oldest_timestamp = oldest[0][1] if oldest else None
            reset_after = self._seconds_until_reset(now, oldest_timestamp)

            return RateLimitResult(True, remaining=remaining, reset_after=reset_after)

        except Exception as e:
            logger.error("Redis rate limit error: %s", e, exc_info=True)
            # Redis hatasÄ± durumunda in-memory'ye fallback yap
            raise

    def _check_in_memory_rate_limit(
        self,
        api_key_id: int,
        rate_limit_per_minute: int,
        now: float,
    ) -> RateLimitResult:
        """In-memory rate limit kontrolÃ¼ (fallback)."""
        q = self._in_memory_hits[api_key_id]

        # Pencere dÄ±ÅŸÄ±ndakileri temizle
        window_start = now - self._window_seconds
        while q and q[0] < window_start:
            q.popleft()

        # Rate limit kontrolÃ¼
        if len(q) >= rate_limit_per_minute:
            oldest_timestamp = q[0] if q else None
            retry_after = self._seconds_until_reset(now, oldest_timestamp)
            return RateLimitResult(False, remaining=0, retry_after=retry_after, reset_after=retry_after)

        # Yeni isteÄŸi ekle
        q.append(now)
        remaining = max(rate_limit_per_minute - len(q), 0)
        reset_after = self._seconds_until_reset(now, q[0] if q else None)

        return RateLimitResult(True, remaining=remaining, reset_after=reset_after)

    def clear_in_memory_cache(self):
        """In-memory cache'i temizle (test iÃ§in)."""
        self._in_memory_hits.clear()

    def _seconds_until_reset(self, now: float, oldest_timestamp: Optional[float]) -> int:
        """Rate limit penceresinin tekrar aÃ§Ä±lmasÄ±na kaÃ§ saniye kaldÄ±ÄŸÄ±nÄ± hesapla."""
        if oldest_timestamp is None:
            return self._window_seconds
        remaining = int((oldest_timestamp + self._window_seconds) - now)
        return max(1, remaining)


# Global rate limiter instance
rate_limiter = RateLimiter()
