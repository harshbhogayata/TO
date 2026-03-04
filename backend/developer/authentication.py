"""
developer/authentication.py
DRF Authentication backend for developer API keys.

Validates API keys passed via:
    Authorization: Bearer to_live_<key>
    X-API-Key: to_live_<key>

The key is hashed with SHA-256 and looked up against developer.APIKey.
IP allowlists and expiration are enforced.
"""
import hashlib
import logging

from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

logger = logging.getLogger(__name__)


class APIKeyAuthentication(BaseAuthentication):
    """
    DRF authentication class for developer API keys.

    Checks:
        1. Key prefix (to_live_ or to_test_)
        2. SHA-256 hash match against stored keys
        3. Key is active
        4. Key has not expired
        5. IP is on allowlist (if configured)
        6. Rate limit tracking (increments daily_usage)

    Usage in views:
        authentication_classes = [JWTAuthentication, APIKeyAuthentication]
    """

    keyword = 'Bearer'
    api_key_header = 'HTTP_X_API_KEY'
    key_prefixes = ('to_live_', 'to_test_')

    def authenticate(self, request):
        """
        Returns (user, api_key) if valid, None if not an API key request.
        Raises AuthenticationFailed on invalid key.
        """
        raw_key = self._extract_key(request)
        if raw_key is None:
            return None  # Not an API key auth attempt — let other backends try

        # Validate prefix
        if not any(raw_key.startswith(p) for p in self.key_prefixes):
            return None  # Not our format

        from developer.models import APIKey

        key_hash = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()

        try:
            api_key = APIKey.objects.select_related('company__user').get(
                key_hash=key_hash,
            )
        except APIKey.DoesNotExist:
            raise AuthenticationFailed('Invalid API key.')

        if not api_key.is_active:
            raise AuthenticationFailed('API key has been revoked.')

        if api_key.expires_at and api_key.expires_at < timezone.now():
            raise AuthenticationFailed('API key has expired.')

        # IP allowlist enforcement
        if api_key.ip_allowlist:
            client_ip = self._get_client_ip(request)
            if client_ip and client_ip not in api_key.ip_allowlist:
                logger.warning(
                    'API key %s: IP %s not in allowlist %s',
                    api_key.prefix, client_ip, api_key.ip_allowlist,
                )
                raise AuthenticationFailed('Request IP not in allowlist.')

        # Track usage: append or increment the last daily_usage entry
        self._track_usage(api_key)

        # Update last_used_at
        APIKey.objects.filter(pk=api_key.pk).update(last_used_at=timezone.now())

        # Return the company's user as the authenticated user
        user = api_key.company.user if hasattr(api_key.company, 'user') else None
        if user is None:
            raise AuthenticationFailed('API key not linked to a user account.')

        return (user, api_key)

    def authenticate_header(self, request):
        """Return string for WWW-Authenticate header on 401."""
        return 'Bearer realm="api", X-API-Key'

    def _extract_key(self, request):
        """Extract the API key from Authorization header or X-API-Key header."""
        # Try X-API-Key first
        x_api_key = request.META.get(self.api_key_header)
        if x_api_key:
            return x_api_key.strip()

        # Try Authorization: Bearer to_live_...
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == 'bearer':
                key = parts[1]
                if any(key.startswith(p) for p in self.key_prefixes):
                    return key

        return None

    def _get_client_ip(self, request):
        """Extract the real client IP, respecting X-Forwarded-For."""
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            return xff.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')

    def _track_usage(self, api_key):
        """Increment today's usage counter in the daily_usage JSON array."""
        today = timezone.now().date().isoformat()
        usage = api_key.daily_usage or []

        if usage and isinstance(usage[-1], dict) and usage[-1].get('date') == today:
            usage[-1]['count'] = usage[-1].get('count', 0) + 1
        else:
            # Trim old entries (keep last 30 days)
            if len(usage) >= 30:
                usage = usage[-29:]
            usage.append({'date': today, 'count': 1})

        from developer.models import APIKey as _AK
        _AK.objects.filter(pk=api_key.pk).update(daily_usage=usage)
