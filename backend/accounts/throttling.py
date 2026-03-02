"""
Stricter throttling for auth and contact endpoints.
Applies to both anonymous AND authenticated users to prevent brute-force.
"""
from rest_framework.throttling import SimpleRateThrottle


class AuthEndpointThrottle(SimpleRateThrottle):
    """
    Rate limit for auth endpoints (login, password-reset, change-password).
    Uses scope 'auth'. Throttles by user ID if authenticated, else by IP.
    """
    scope = 'auth'

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = str(request.user.pk)
        else:
            ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident,
        }


class ContactEndpointThrottle(SimpleRateThrottle):
    """
    Rate limit for the contact form to prevent spam.
    Uses scope 'contact'. Throttles by user ID if authenticated, else by IP.
    """
    scope = 'contact'

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = str(request.user.pk)
        else:
            ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident,
        }
