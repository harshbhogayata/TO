"""
Stricter throttling for auth endpoints (login, password-reset) to reduce brute-force risk.
"""
from rest_framework.throttling import SimpleRateThrottle


class AuthEndpointThrottle(SimpleRateThrottle):
    """
    Rate limit for unauthenticated auth endpoints (login, password-reset).
    Uses scope 'auth' and identifies by IP.
    """
    scope = 'auth'

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return None
        return self.cache_format % {
            'scope': self.scope,
            'ident': self.get_ident(request),
        }
