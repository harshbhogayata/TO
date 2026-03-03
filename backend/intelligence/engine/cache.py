"""
intelligence/engine/cache.py
Redis-backed recommendation cache layer.

Caches per-user recommendation results with intelligent invalidation.
Uses a global version counter so model retrains instantly bust all caches.
"""

import hashlib
import json
import logging

from django.core.cache import cache

from intelligence.constants import RECOMMENDATION_CACHE_TTL

logger = logging.getLogger(__name__)

_VERSION_KEY = 'intelligence:recs:version'


def _get_version() -> int:
    """Return the current global cache version (0 if unset)."""
    return cache.get(_VERSION_KEY) or 0


def _cache_key(user_id: int, params: dict | None = None) -> str:
    """Build a deterministic cache key for recommendation results."""
    version = _get_version()
    base = f'intelligence:recs:v{version}:{user_id}'
    if params:
        param_str = json.dumps(params, sort_keys=True)
        param_hash = hashlib.sha256(param_str.encode()).hexdigest()[:12]
        return f'{base}:{param_hash}'
    return base


def get_cached_recommendations(user_id: int, params: dict | None = None):
    """Return cached recommendation results or None."""
    key = _cache_key(user_id, params)
    return cache.get(key)


def set_cached_recommendations(
    user_id: int,
    data: dict,
    params: dict | None = None,
    ttl: int = RECOMMENDATION_CACHE_TTL,
):
    """Cache recommendation results."""
    key = _cache_key(user_id, params)
    cache.set(key, data, ttl)


def invalidate_user_recommendations(user_id: int):
    """
    Bust recommendation cache for a user.
    Called when a user applies, saves, or updates their profile.
    """
    # Delete the common (no-params) key.  Param-specific keys are
    # handled by TTL + version increment on model retrains.
    cache.delete(_cache_key(user_id))
    logger.debug('Busted recommendation cache for user %s', user_id)


def invalidate_all_recommendations():
    """
    Bust all recommendation caches (e.g. after model retrain).
    Increments a global version counter so every key becomes stale instantly.
    """
    try:
        cache.incr(_VERSION_KEY)
    except ValueError:
        # Key doesn't exist yet — initialise it
        cache.set(_VERSION_KEY, 1, timeout=None)
    logger.info('Incremented recommendation cache version — all prior caches invalidated')
