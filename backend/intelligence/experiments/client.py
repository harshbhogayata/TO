"""
intelligence/experiments/client.py
Server-side PostHog client wrapper for feature flag evaluation and event tracking.
Caches flag evaluations in Redis to avoid API latency on every request.
"""

import logging
import os
import threading

from django.core.cache import cache

from intelligence.constants import FEATURE_FLAG_CACHE_TTL

logger = logging.getLogger(__name__)

_posthog_client = None
_client_lock = threading.Lock()


def _get_client():
    """Lazy-initialise the PostHog client (thread-safe)."""
    global _posthog_client

    if _posthog_client is not None:
        return _posthog_client

    with _client_lock:
        # Double-check after acquiring lock
        if _posthog_client is not None:
            return _posthog_client

        api_key = os.environ.get('POSTHOG_API_KEY', '')
        host = os.environ.get('POSTHOG_HOST', 'https://us.i.posthog.com')

        if not api_key:
            logger.debug('PostHog API key not configured, feature flags will use defaults')
            return None

        try:
            import posthog
            posthog.project_api_key = api_key
            posthog.host = host
            posthog.debug = False
            posthog.on_error = lambda e, _: logger.warning('PostHog error: %s', e)
            _posthog_client = posthog
            return posthog
        except ImportError:
            logger.warning('posthog package not installed')
            return None
        except Exception:
            logger.warning('Failed to initialise PostHog client', exc_info=True)
            return None


def get_feature_flag(flag_key: str, user_id, default=False):
    """
    Get a feature flag value for a user.
    Returns the variant string, True/False, or the default.
    Cached per-user for FEATURE_FLAG_CACHE_TTL seconds.
    """
    cache_key = f'intelligence:ff:{user_id}:{flag_key}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    client = _get_client()
    if client is None:
        return default

    try:
        result = client.get_feature_flag(
            flag_key,
            distinct_id=str(user_id),
        )
        if result is None:
            result = default

        cache.set(cache_key, result, FEATURE_FLAG_CACHE_TTL)
        return result
    except Exception:
        logger.warning('Failed to evaluate feature flag %s', flag_key, exc_info=True)
        return default


def get_all_flags(user_id) -> dict:
    """
    Get all active feature flags for a user.
    Returns dict of {flag_key: value}.
    """
    cache_key = f'intelligence:ff:all:{user_id}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    client = _get_client()
    if client is None:
        return {}

    try:
        flags = client.get_all_flags(distinct_id=str(user_id))
        result = flags or {}
        cache.set(cache_key, result, FEATURE_FLAG_CACHE_TTL)
        return result
    except Exception:
        logger.warning('Failed to fetch all feature flags', exc_info=True)
        return {}


def capture_event(user_id, event_name: str, properties: dict | None = None):
    """Send an event to PostHog for analytics/experiment tracking."""
    client = _get_client()
    if client is None:
        return

    try:
        client.capture(
            distinct_id=str(user_id),
            event=event_name,
            properties=properties or {},
        )
    except Exception:
        logger.warning('Failed to capture PostHog event %s', event_name, exc_info=True)


def is_feature_enabled(flag_key: str, user_id) -> bool:
    """Simple boolean feature flag check."""
    result = get_feature_flag(flag_key, user_id, default=False)
    return bool(result)
