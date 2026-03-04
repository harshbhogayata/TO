"""
talentorbit/cache_utils.py
Enterprise cache utilities with stampede prevention.

Provides cache_with_lock() — a thundering herd prevention pattern
that ensures only one process refreshes an expired cache key at a time.

Usage:
    from talentorbit.cache_utils import cache_with_lock

    def get_plans():
        return cache_with_lock(
            key='subscription_plans',
            timeout=3600,
            generator_fn=lambda: list(SubscriptionPlan.objects.filter(is_active=True).values()),
        )
"""
import logging
import time

from django.core.cache import cache

logger = logging.getLogger(__name__)


def cache_with_lock(key: str, timeout: int, generator_fn, lock_timeout: int = 30):
    """
    Cache-aside pattern with lock-based stampede prevention.

    When the cache key is missing:
        1. Try to acquire a lock (cache.add is atomic)
        2. If lock acquired → regenerate data, set cache, release lock
        3. If lock NOT acquired → wait briefly and retry cache read
        4. If still no data after retries → generate anyway (fallback)

    Args:
        key: Cache key.
        timeout: TTL for the cached value (seconds).
        generator_fn: Zero-argument callable that produces the value.
        lock_timeout: How long the lock is held before auto-release (seconds).

    Returns:
        The cached or freshly generated value.
    """
    # Fast path: cache hit
    result = cache.get(key)
    if result is not None:
        return result

    # Slow path: cache miss — try to acquire lock
    lock_key = f'lock:{key}'
    acquired = cache.add(lock_key, '1', timeout=lock_timeout)

    if acquired:
        try:
            result = generator_fn()
            cache.set(key, result, timeout)
            logger.debug('Cache refreshed: key=%s ttl=%d', key, timeout)
            return result
        finally:
            cache.delete(lock_key)
    else:
        # Another process is refreshing — poll for result
        for _ in range(10):
            time.sleep(0.5)
            result = cache.get(key)
            if result is not None:
                return result

        # Fallback: lock holder may have crashed — generate anyway
        logger.warning(
            'Cache lock timeout for key=%s — generating fallback',
            key,
        )
        return generator_fn()


def invalidate_cache(*keys: str) -> None:
    """
    Invalidate one or more cache keys.

    Args:
        *keys: Cache keys to delete.
    """
    for key in keys:
        cache.delete(key)
        logger.debug('Cache invalidated: key=%s', key)
