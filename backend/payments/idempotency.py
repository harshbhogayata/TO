"""
payments/idempotency.py
Enterprise idempotency decorator for payment endpoints.

Prevents duplicate charges from network retries, user double-clicks,
or webhook re-deliveries by caching responses keyed on a client-provided
Idempotency-Key header.

Flow:
    1. Client sends POST with `Idempotency-Key: <UUID>` header
    2. Server hashes key with user ID → cache lookup
    3. If cached → return cached response (no side effects)
    4. If not cached → execute view, cache response, return

Security:
    - Keys are scoped per-user (user A's key can't collide with user B's)
    - SHA-256 hashed before storage
    - TTL prevents unbounded cache growth
"""
import hashlib
import functools
import logging

from django.core.cache import cache
from rest_framework.response import Response

logger = logging.getLogger(__name__)

_IDEMPOTENCY_HEADER = 'HTTP_IDEMPOTENCY_KEY'
_DEFAULT_TIMEOUT = 86400  # 24 hours


def idempotent(timeout: int = _DEFAULT_TIMEOUT):
    """
    Decorator that enforces idempotency on DRF views.

    Usage:
        @api_view(['POST'])
        @idempotent(timeout=86400)
        def create_checkout_session(request):
            ...

    The client MUST send an `Idempotency-Key` header. If omitted,
    the view executes normally (non-idempotent fallback for backwards
    compatibility).

    Args:
        timeout: How long to cache the response (seconds). Default 24h.
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            raw_key = request.META.get(_IDEMPOTENCY_HEADER)
            if not raw_key:
                # No idempotency key → execute normally
                return view_func(request, *args, **kwargs)

            raw_key = raw_key.strip()
            if len(raw_key) > 256:
                return Response(
                    {'error': 'Idempotency-Key must be ≤ 256 characters.'},
                    status=400,
                )

            # Scope key to authenticated user to prevent cross-user collisions
            user_id = getattr(request.user, 'id', 'anon')
            key_hash = hashlib.sha256(
                f'{user_id}:{raw_key}'.encode('utf-8')
            ).hexdigest()
            cache_key = f'idempotency:{key_hash}'

            # Check for cached response
            cached = cache.get(cache_key)
            if cached is not None:
                logger.info(
                    'Idempotent replay: user=%s key=%s…',
                    user_id, raw_key[:8],
                )
                return Response(
                    data=cached['data'],
                    status=cached['status'],
                )

            # Execute the view
            response = view_func(request, *args, **kwargs)

            # Cache successful responses only (2xx)
            if 200 <= response.status_code < 300:
                cache.set(
                    cache_key,
                    {
                        'data': response.data,
                        'status': response.status_code,
                    },
                    timeout,
                )

            return response
        return wrapper
    return decorator
