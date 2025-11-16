// Frontend cache hook with localStorage and in-memory cache
import { useState, useEffect, useCallback } from 'react';

interface CacheOptions {
  ttl?: number; // Time to live in milliseconds (default: 5 minutes)
  storage?: 'memory' | 'localStorage'; // Storage type (default: memory)
}

interface CacheEntry<T> {
  data: T;
  timestamp: number;
  ttl: number;
}

// In-memory cache
const memoryCache = new Map<string, CacheEntry<any>>();

// Cache utilities
const getCacheKey = (key: string): string => `neso_cache_${key}`;

const isExpired = (entry: CacheEntry<any>): boolean => {
  return Date.now() - entry.timestamp > entry.ttl;
};

const getFromCache = <T>(key: string, storage: 'memory' | 'localStorage'): T | null => {
  const cacheKey = getCacheKey(key);

  if (storage === 'memory') {
    const entry = memoryCache.get(cacheKey);
    if (entry && !isExpired(entry)) {
      return entry.data as T;
    }
    if (entry) {
      memoryCache.delete(cacheKey); // Clean up expired entry
    }
    return null;
  }

  // localStorage
  try {
    const item = localStorage.getItem(cacheKey);
    if (!item) return null;

    const entry: CacheEntry<T> = JSON.parse(item);
    if (isExpired(entry)) {
      localStorage.removeItem(cacheKey);
      return null;
    }
    return entry.data;
  } catch (error) {
    console.warn('Cache read error:', error);
    return null;
  }
};

const setToCache = <T>(
  key: string,
  data: T,
  storage: 'memory' | 'localStorage',
  ttl: number
): void => {
  const cacheKey = getCacheKey(key);
  const entry: CacheEntry<T> = {
    data,
    timestamp: Date.now(),
    ttl,
  };

  if (storage === 'memory') {
    memoryCache.set(cacheKey, entry);
    return;
  }

  // localStorage
  try {
    localStorage.setItem(cacheKey, JSON.stringify(entry));
  } catch (error) {
    console.warn('Cache write error:', error);
  }
};

const clearCache = (pattern?: string): void => {
  if (pattern) {
    // Clear specific pattern
    const prefix = getCacheKey(pattern);

    // Memory cache
    for (const key of memoryCache.keys()) {
      if (key.startsWith(prefix)) {
        memoryCache.delete(key);
      }
    }

    // localStorage
    try {
      const keys = Object.keys(localStorage);
      keys.forEach((key) => {
        if (key.startsWith(prefix)) {
          localStorage.removeItem(key);
        }
      });
    } catch (error) {
      console.warn('Cache clear error:', error);
    }
  } else {
    // Clear all cache
    memoryCache.clear();
    try {
      const keys = Object.keys(localStorage);
      keys.forEach((key) => {
        if (key.startsWith('neso_cache_')) {
          localStorage.removeItem(key);
        }
      });
    } catch (error) {
      console.warn('Cache clear error:', error);
    }
  }
};

// Main hook
export function useCache<T>(
  key: string,
  fetcher: () => Promise<T>,
  options: CacheOptions = {}
) {
  const { ttl = 5 * 60 * 1000, storage = 'memory' } = options;

  const [data, setData] = useState<T | null>(() => {
    // Try to get from cache on mount
    return getFromCache<T>(key, storage);
  });
  const [loading, setLoading] = useState<boolean>(!data);
  const [error, setError] = useState<Error | null>(null);

  const fetchData = useCallback(async (force = false) => {
    // Check cache first (unless forced)
    if (!force) {
      const cached = getFromCache<T>(key, storage);
      if (cached) {
        setData(cached);
        setLoading(false);
        return;
      }
    }

    // Fetch fresh data
    setLoading(true);
    setError(null);

    try {
      const result = await fetcher();
      setData(result);
      setToCache(key, result, storage, ttl);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Unknown error'));
      console.error('Fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, [key, fetcher, storage, ttl]);

  const invalidate = useCallback(() => {
    const cacheKey = getCacheKey(key);
    if (storage === 'memory') {
      memoryCache.delete(cacheKey);
    } else {
      try {
        localStorage.removeItem(cacheKey);
      } catch (error) {
        console.warn('Cache invalidation error:', error);
      }
    }
  }, [key, storage]);

  const refresh = useCallback(() => {
    invalidate();
    return fetchData(true);
  }, [fetchData, invalidate]);

  // Auto-fetch on mount if no cache
  useEffect(() => {
    if (!data) {
      fetchData();
    }
  }, []);

  return {
    data,
    loading,
    error,
    refresh,
    invalidate,
  };
}

// Export utilities for manual cache management
export const cacheUtils = {
  get: getFromCache,
  set: setToCache,
  clear: clearCache,
};
