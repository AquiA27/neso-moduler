# backend/app/services/rate_limiter.py
"""
API Key Rate Limiting Service
Redis veya in-memory fallback ile rate limiting
"""
import time
import logging
from typing import Dict, Optional
from collections import defaultdict, deque
from datetime import datetime, timedelta

from ..core.config import settings
from .cache import cache_service

logger = logging.getLogger(__name__)


class RateLimiter:
    """API Key bazlı rate limiting servisi"""
    
    def __init__(self):
        # In-memory fallback (Redis yoksa)
        self._in_memory_hits: Dict[int, deque] = defaultdict(deque)
        self._window_seconds = 60
    
    async def check_rate_limit(
        self, 
        api_key_id: int, 
        rate_limit_per_minute: int
    ) -> tuple[bool, Optional[int]]:
        """
        Rate limit kontrolü yapar.
        
        Returns:
            (allowed: bool, retry_after_seconds: Optional[int])
            - allowed: True ise istek yapılabilir
            - retry_after_seconds: Rate limit aşıldıysa kaç saniye sonra tekrar deneyebilir
        """
        if rate_limit_per_minute <= 0:
            # Rate limit devre dışı
            return True, None
        
        now = time.time()
        cache_key = f"rate_limit:api_key:{api_key_id}"
        
        # Redis kullanılabilirse Redis ile yap
        if cache_service.is_enabled():
            try:
                return await self._check_redis_rate_limit(
                    cache_key, 
                    rate_limit_per_minute,
                    now
                )
            except Exception as e:
                logger.warning(f"Redis rate limit check failed: {e}, falling back to in-memory")
        
        # In-memory fallback
        return self._check_in_memory_rate_limit(
            api_key_id,
            rate_limit_per_minute,
            now
        )
    
    async def _check_redis_rate_limit(
        self,
        cache_key: str,
        rate_limit_per_minute: int,
        now: float
    ) -> tuple[bool, Optional[int]]:
        """Redis ile rate limit kontrolü (sliding window)"""
        try:
            # Redis'te sliding window için sorted set kullan
            # Key: rate_limit:api_key:{id}
            # Score: timestamp
            # Value: request_id (opsiyonel)
            
            # Cache service'in Redis client'ını kullan
            redis_client = cache_service.get_redis_client()
            
            if not redis_client:
                raise Exception("Redis client not available")
            
            # Sliding window: son 60 saniyedeki istekleri say
            window_start = now - self._window_seconds
            
            # Eski kayıtları temizle (score < window_start olanları sil)
            await redis_client.zremrangebyscore(cache_key, 0, window_start)
            
            # Mevcut istek sayısını al
            current_count = await redis_client.zcard(cache_key)
            
            if current_count >= rate_limit_per_minute:
                # Rate limit aşıldı
                # En eski isteğin ne zaman expire olacağını bul
                oldest = await redis_client.zrange(cache_key, 0, 0, withscores=True)
                if oldest:
                    oldest_timestamp = oldest[0][1]
                    retry_after = int(oldest_timestamp + self._window_seconds - now) + 1
                    return False, max(1, retry_after)
                return False, self._window_seconds
            
            # Yeni isteği ekle
            await redis_client.zadd(cache_key, {str(now): now})
            # TTL ayarla (window_seconds + 10 saniye buffer)
            await redis_client.expire(cache_key, self._window_seconds + 10)
            
            return True, None
            
        except Exception as e:
            logger.error(f"Redis rate limit error: {e}", exc_info=True)
            # Redis hatası durumunda in-memory'ye fallback yap
            raise
    
    def _check_in_memory_rate_limit(
        self,
        api_key_id: int,
        rate_limit_per_minute: int,
        now: float
    ) -> tuple[bool, Optional[int]]:
        """In-memory rate limit kontrolü (fallback)"""
        q = self._in_memory_hits[api_key_id]
        
        # Pencere dışındakileri temizle
        window_start = now - self._window_seconds
        while q and q[0] < window_start:
            q.popleft()
        
        # Rate limit kontrolü
        if len(q) >= rate_limit_per_minute:
            # Rate limit aşıldı
            # En eski isteğin ne zaman expire olacağını hesapla
            oldest_timestamp = q[0] if q else now
            retry_after = int(oldest_timestamp + self._window_seconds - now) + 1
            return False, max(1, retry_after)
        
        # Yeni isteği ekle
        q.append(now)
        
        return True, None
    
    def clear_in_memory_cache(self):
        """In-memory cache'i temizle (test için)"""
        self._in_memory_hits.clear()


# Global rate limiter instance
rate_limiter = RateLimiter()

