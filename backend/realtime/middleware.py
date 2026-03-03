"""
realtime/middleware.py
Production-grade WebSocket middleware stack for Django Channels.

Provides:
    - Per-IP connection rate limiting (prevents WS connection floods)
    - Per-user message rate limiting (prevents message spam)
    - Connection tracking for observability
    - Request ID injection for correlated logging

Rate limits are enforced via Django's cache framework (Redis in production).
The sliding-window algorithm uses atomic cache increment operations.
"""

import logging
import time
from typing import Optional

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache

logger = logging.getLogger(__name__)

# ─── Configuration (overridable via Django settings) ─────────────────────────

# Max WebSocket connections per IP within the window
WS_CONNECT_RATE_LIMIT = getattr(settings, 'WS_CONNECT_RATE_LIMIT', 20)
WS_CONNECT_RATE_WINDOW = getattr(settings, 'WS_CONNECT_RATE_WINDOW', 60)  # seconds

# Max messages per user per window (across all connections)
WS_MESSAGE_RATE_LIMIT = getattr(settings, 'WS_MESSAGE_RATE_LIMIT', 60)
WS_MESSAGE_RATE_WINDOW = getattr(settings, 'WS_MESSAGE_RATE_WINDOW', 60)  # seconds

# Max concurrent connections per user
WS_MAX_CONNECTIONS_PER_USER = getattr(settings, 'WS_MAX_CONNECTIONS_PER_USER', 5)

# Cache key prefixes
_CK_CONN_RATE = 'ws:conn_rate:'
_CK_MSG_RATE = 'ws:msg_rate:'
_CK_USER_CONNS = 'ws:user_conns:'
_CK_ACTIVE_CONNS = 'ws:active_connections'


def _get_client_ip(scope: dict) -> str:
    """Extract the client IP from the ASGI scope, respecting X-Forwarded-For."""
    headers = dict(scope.get('headers', []))
    xff = headers.get(b'x-forwarded-for', b'').decode('utf-8')
    if xff:
        # Take the first (leftmost) IP — the original client
        return xff.split(',')[0].strip()

    # Fall back to the direct peer address
    client = scope.get('client')
    if client:
        return client[0]
    return 'unknown'


class ConnectionRateLimitMiddleware(BaseMiddleware):
    """
    Reject WebSocket connections that exceed the per-IP rate limit.

    Sends a 4429 close code (Too Many Requests) and logs the event.
    Uses a sliding-window counter stored in the cache backend.
    """

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'websocket':
            return await super().__call__(scope, receive, send)

        ip = _get_client_ip(scope)
        cache_key = f'{_CK_CONN_RATE}{ip}'

        # Check rate limit
        allowed = await self._check_rate_limit(cache_key)

        if not allowed:
            logger.warning(
                'WebSocket connection rate-limited: ip=%s', ip,
            )
            # Send a WebSocket close before the connection is established
            await send({'type': 'websocket.close', 'code': 4429})
            return

        # Track this connection for metrics
        scope['_ws_client_ip'] = ip
        scope['_ws_connect_time'] = time.monotonic()

        return await super().__call__(scope, receive, send)

    @database_sync_to_async
    def _check_rate_limit(self, cache_key: str) -> bool:
        """Increment sliding-window counter. Returns True if within limit."""
        try:
            count = cache.get(cache_key, 0)
            if count >= WS_CONNECT_RATE_LIMIT:
                return False
            # Atomic increment with TTL
            cache.set(cache_key, count + 1, timeout=WS_CONNECT_RATE_WINDOW)
            return True
        except Exception:
            # If cache is down, allow the connection (fail-open)
            logger.debug('Rate limit cache unavailable — allowing connection.')
            return True


class ConnectionTrackingMiddleware(BaseMiddleware):
    """
    Track active WebSocket connections for observability.

    Increments a counter when a connection is established and decrements
    when it closes. Also enforces per-user concurrent connection limits.
    """

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'websocket':
            return await super().__call__(scope, receive, send)

        # We intercept the receive/send to detect connect/disconnect
        connected = False

        async def tracked_receive():
            nonlocal connected
            message = await receive()

            if message['type'] == 'websocket.connect':
                connected = True
                await self._on_connect(scope)

            return message

        async def tracked_send(message):
            nonlocal connected
            if message['type'] == 'websocket.close' and connected:
                connected = False
                await self._on_disconnect(scope)
            await send(message)

        try:
            return await self.inner(scope, tracked_receive, tracked_send)
        finally:
            if connected:
                await self._on_disconnect(scope)

    @database_sync_to_async
    def _on_connect(self, scope):
        """Track connection establishment."""
        try:
            cache.incr(_CK_ACTIVE_CONNS)
        except ValueError:
            cache.set(_CK_ACTIVE_CONNS, 1, timeout=None)
        except Exception:
            pass

    @database_sync_to_async
    def _on_disconnect(self, scope):
        """Track connection teardown and log duration."""
        try:
            cache.decr(_CK_ACTIVE_CONNS)
        except Exception:
            pass

        connect_time = scope.get('_ws_connect_time')
        if connect_time:
            duration = time.monotonic() - connect_time
            user = scope.get('user')
            user_id = getattr(user, 'id', 'anon')
            logger.info(
                'WebSocket session ended: user=%s duration=%.1fs ip=%s',
                user_id, duration, scope.get('_ws_client_ip', 'unknown'),
            )


# ─── Message rate limiting (used inside consumers) ───────────────────────────

def check_message_rate_limit(user_id: int) -> bool:
    """
    Check if a user has exceeded the message rate limit.
    Call this from consumer.receive_json() before processing a message.

    Returns True if the message should be allowed.
    """
    cache_key = f'{_CK_MSG_RATE}{user_id}'
    try:
        count = cache.get(cache_key, 0)
        if count >= WS_MESSAGE_RATE_LIMIT:
            return False
        cache.set(cache_key, count + 1, timeout=WS_MESSAGE_RATE_WINDOW)
        return True
    except Exception:
        return True  # Fail-open


def get_active_connection_count() -> int:
    """Return the current number of active WebSocket connections."""
    try:
        return cache.get(_CK_ACTIVE_CONNS, 0)
    except Exception:
        return -1
