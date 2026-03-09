"""
search/cache.py
Redis-backed caching layer for search results and autocomplete suggestions.

Strategy:
  - Search results:  cached 5 min, keyed by entity:hash(query+filters+page)
  - Autocomplete:    cached 15 min, keyed by prefix
  - Trending:        cached 1 hour, keyed by entity type
  - Invalidation:    on model save, bust all keys for that entity type

Uses Django's cache framework, which is backed by Upstash Redis in production
and LocMemCache in development — same API, zero config changes.
"""
import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

# ─── TTLs (seconds) ──────────────────────────────────────────────────────────
SEARCH_RESULTS_TTL = 300       # 5 minutes
AUTOCOMPLETE_TTL = 900         # 15 minutes
TRENDING_TTL = 3600            # 1 hour
ENTITY_VERSION_TTL = 86400     # 24 hours (version counter for invalidation)


# ─── Version-based cache invalidation ────────────────────────────────────────
# Instead of scanning Redis for keys to delete (expensive), we use a version
# counter per entity type. When a model saves, we bump the version, which
# makes all existing cache keys stale (they include the old version).

def _entity_version_key(entity_type):
    return f'search:version:{entity_type}'


def get_entity_version(entity_type):
    """Get the current cache version for an entity type."""
    version = cache.get(_entity_version_key(entity_type))
    if version is None:
        version = 1
        cache.set(_entity_version_key(entity_type), version, ENTITY_VERSION_TTL)
    return version


def bump_entity_version(entity_type):
    """
    Increment the version counter for an entity type.
    All cached results for this entity become stale.
    """
    key = _entity_version_key(entity_type)
    try:
        new_version = cache.incr(key)
    except ValueError:
        # Key doesn't exist (expired or never set)
        new_version = 1
        cache.set(key, new_version, ENTITY_VERSION_TTL)

    logger.info('Bumped search cache version for %s to %d', entity_type, new_version)
    return new_version


def _versioned_key(base_key, entity_type):
    """Prefix a cache key with the entity version for automatic invalidation."""
    version = get_entity_version(entity_type)
    return f'v{version}:{base_key}'


# ─── Search result caching ───────────────────────────────────────────────────

def get_cached_results(cache_key, entity_type):
    """Retrieve cached search results. Returns None on miss."""
    full_key = _versioned_key(cache_key, entity_type)
    result = cache.get(full_key)
    if result is not None:
        logger.debug('Cache HIT: %s', full_key)
    return result


def set_cached_results(cache_key, entity_type, data, ttl=SEARCH_RESULTS_TTL):
    """Store search results in cache."""
    full_key = _versioned_key(cache_key, entity_type)
    cache.set(full_key, data, ttl)
    logger.debug('Cache SET: %s (TTL=%ds)', full_key, ttl)


# ─── Autocomplete caching ────────────────────────────────────────────────────

def get_cached_suggestions(prefix, entity_type):
    """Retrieve cached autocomplete suggestions."""
    key = _versioned_key(f'autocomplete:{entity_type}:{prefix.lower()[:20]}', entity_type)
    return cache.get(key)


def set_cached_suggestions(prefix, entity_type, suggestions, ttl=AUTOCOMPLETE_TTL):
    """Store autocomplete suggestions."""
    key = _versioned_key(f'autocomplete:{entity_type}:{prefix.lower()[:20]}', entity_type)
    cache.set(key, suggestions, ttl)


# ─── Trending searches ───────────────────────────────────────────────────────

def get_cached_trending(entity_type='all'):
    """Retrieve cached trending searches."""
    key = f'search:trending:{entity_type}'
    return cache.get(key)


def set_cached_trending(entity_type, data, ttl=TRENDING_TTL):
    """Store trending search data."""
    key = f'search:trending:{entity_type}'
    cache.set(key, data, ttl)


def invalidate_trending_cache(entity_type):
    """Invalidate cached trending queries for an entity type and the global feed."""
    cache.delete(f'search:trending:{entity_type}')
    cache.delete('search:trending:all')


# ─── Bulk invalidation ───────────────────────────────────────────────────────

def invalidate_entity_cache(entity_type):
    """
    Invalidate all cached search results for an entity type.
    Uses version bumping — O(1) operation regardless of cache size.
    """
    bump_entity_version(entity_type)
    # Also clear trending since results changed
    invalidate_trending_cache(entity_type)
