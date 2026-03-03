"""
realtime/presence.py
Redis-backed user presence tracking for TalentOrbit.

Tracks online/offline status and last-seen timestamps using the Django
cache framework (Redis in production, LocMem in development).

Architecture:
    - When a user connects to ANY WebSocket consumer (chat or notifications),
      they are marked as 'online'.
    - When all of a user's connections close, they are marked as 'offline'
      with a last_seen timestamp.
    - A per-user connection counter prevents premature offline marking
      when the user has multiple tabs/devices.
    - Presence changes are broadcast to relevant WebSocket groups so other
      users see real-time online/offline transitions.

Cache keys:
    ws:presence:{user_id}        → '1' (online) or missing (offline)
    ws:presence:conns:{user_id}  → int (connection count)
    ws:last_seen:{user_id}       → ISO timestamp string
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from django.core.cache import cache

logger = logging.getLogger(__name__)

# Cache TTL for presence keys (auto-expire if server crashes without cleanup)
_PRESENCE_TTL = 300  # 5 minutes — refreshed on heartbeat
_LAST_SEEN_TTL = 60 * 60 * 24 * 30  # 30 days

# Cache key prefixes
_CK_ONLINE = 'ws:presence:'
_CK_CONNS = 'ws:presence:conns:'
_CK_LAST_SEEN = 'ws:last_seen:'


def user_connected(user_id: int) -> bool:
    """
    Mark a user as online and increment their connection count.
    Call this when a WebSocket consumer's connect() succeeds.

    Returns True if the user just came online (was previously offline).
    """
    conns_key = f'{_CK_CONNS}{user_id}'
    online_key = f'{_CK_ONLINE}{user_id}'

    try:
        conn_count = cache.get(conns_key, 0)
        was_offline = conn_count == 0

        cache.set(conns_key, conn_count + 1, timeout=_PRESENCE_TTL)
        cache.set(online_key, '1', timeout=_PRESENCE_TTL)

        if was_offline:
            logger.info('User %s came online (first connection).', user_id)

        return was_offline
    except Exception:
        logger.debug('Presence tracking unavailable for connect (user %s).', user_id)
        return False


def user_disconnected(user_id: int) -> bool:
    """
    Decrement a user's connection count. Mark offline if count hits 0.
    Call this when a WebSocket consumer's disconnect() fires.

    Returns True if the user just went offline (last connection closed).
    """
    conns_key = f'{_CK_CONNS}{user_id}'
    online_key = f'{_CK_ONLINE}{user_id}'
    last_seen_key = f'{_CK_LAST_SEEN}{user_id}'

    try:
        conn_count = cache.get(conns_key, 0)
        new_count = max(0, conn_count - 1)

        if new_count == 0:
            # Last connection closed — user is offline
            cache.delete(conns_key)
            cache.delete(online_key)

            # Record last-seen timestamp
            now = datetime.now(timezone.utc).isoformat()
            cache.set(last_seen_key, now, timeout=_LAST_SEEN_TTL)

            logger.info('User %s went offline.', user_id)
            return True
        else:
            cache.set(conns_key, new_count, timeout=_PRESENCE_TTL)
            return False
    except Exception:
        logger.debug('Presence tracking unavailable for disconnect (user %s).', user_id)
        return False


def refresh_presence(user_id: int):
    """
    Refresh the TTL on a user's presence keys.
    Call this on heartbeat to prevent auto-expiry during long idle periods.
    """
    conns_key = f'{_CK_CONNS}{user_id}'
    online_key = f'{_CK_ONLINE}{user_id}'

    try:
        conn_count = cache.get(conns_key)
        if conn_count is not None and conn_count > 0:
            cache.set(conns_key, conn_count, timeout=_PRESENCE_TTL)
            cache.set(online_key, '1', timeout=_PRESENCE_TTL)
    except Exception:
        pass


def is_user_online(user_id: int) -> bool:
    """Check if a user is currently online."""
    try:
        return cache.get(f'{_CK_ONLINE}{user_id}') == '1'
    except Exception:
        return False


def get_last_seen(user_id: int) -> Optional[str]:
    """
    Get a user's last-seen timestamp (ISO format string).
    Returns None if the user is currently online or has no recorded last-seen.
    """
    try:
        return cache.get(f'{_CK_LAST_SEEN}{user_id}')
    except Exception:
        return None


def get_user_presence(user_id: int) -> dict:
    """
    Get complete presence info for a user.

    Returns:
        {
            'user_id': int,
            'is_online': bool,
            'last_seen': str | None,  # ISO timestamp, None if online
        }
    """
    online = is_user_online(user_id)
    return {
        'user_id': user_id,
        'is_online': online,
        'last_seen': None if online else get_last_seen(user_id),
    }


def get_bulk_presence(user_ids: list[int]) -> dict[int, dict]:
    """
    Get presence info for multiple users efficiently.
    Uses cache.get_many() for a single round-trip to Redis.

    Returns:
        { user_id: { 'is_online': bool, 'last_seen': str|None }, ... }
    """
    if not user_ids:
        return {}

    online_keys = {f'{_CK_ONLINE}{uid}': uid for uid in user_ids}
    last_seen_keys = {f'{_CK_LAST_SEEN}{uid}': uid for uid in user_ids}

    try:
        all_keys = list(online_keys.keys()) + list(last_seen_keys.keys())
        cached = cache.get_many(all_keys)
    except Exception:
        return {uid: {'is_online': False, 'last_seen': None} for uid in user_ids}

    result = {}
    for uid in user_ids:
        is_online = cached.get(f'{_CK_ONLINE}{uid}') == '1'
        last_seen = None if is_online else cached.get(f'{_CK_LAST_SEEN}{uid}')
        result[uid] = {
            'is_online': is_online,
            'last_seen': last_seen,
        }

    return result
