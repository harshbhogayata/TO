"""
developer/throttling.py
Per-endpoint rate limiting for Developer Platform security-sensitive operations.

These throttle classes supplement the global AnonRateThrottle / UserRateThrottle
with tighter, operation-specific limits on endpoints that create credentials,
rotate secrets, or perform outbound HTTP requests.

All classes extend SimpleRateThrottle and key on the authenticated user ID
(falling back to IP for unauthenticated callers where applicable).

Rate scopes are registered in settings.py → DEFAULT_THROTTLE_RATES.
"""
from rest_framework.throttling import SimpleRateThrottle


class _UserOrIPThrottle(SimpleRateThrottle):
    """
    Base mixin: throttle by user PK when authenticated, else by IP.
    Subclasses MUST define ``scope``.
    """

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = str(request.user.pk)
        else:
            ident = self.get_ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': ident}


# ── API Key Operations ───────────────────────────────────────────────────────

class APIKeyCreateThrottle(_UserOrIPThrottle):
    """10 API key creations per hour — prevents credential flood."""
    scope = 'developer_key_create'


class APIKeyRotateThrottle(_UserOrIPThrottle):
    """10 key rotations per hour — brute-force rotation prevention."""
    scope = 'developer_key_rotate'


# ── Webhook Operations ───────────────────────────────────────────────────────

class WebhookCreateThrottle(_UserOrIPThrottle):
    """10 webhook registrations per hour — prevents endpoint flood."""
    scope = 'developer_webhook_create'


class WebhookTestPingThrottle(_UserOrIPThrottle):
    """20 test pings per hour — outbound HTTP is expensive."""
    scope = 'developer_webhook_test'


# ── OAuth Application Operations ─────────────────────────────────────────────

class OAuthAppCreateThrottle(_UserOrIPThrottle):
    """5 OAuth app registrations per hour — credential issuance safety net."""
    scope = 'developer_oauth_create'


class OAuthAppRevokeThrottle(_UserOrIPThrottle):
    """10 revocations per hour — prevents mass-revoke abuse."""
    scope = 'developer_oauth_revoke'
