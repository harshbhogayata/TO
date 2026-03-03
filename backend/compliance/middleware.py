"""
compliance/middleware.py
Phase 6 — Trust & Compliance middleware.

AuditContextMiddleware:
    Attaches a unique request_id, client IP, and user-agent to every
    request via thread-local storage so that audit log entries created
    anywhere in the call stack can capture this context automatically.

ConsentEnforcementMiddleware:
    Checks whether the authenticated user has consented to all active
    policies that require re-consent. Returns HTTP 451 (Unavailable
    for Legal Reasons) if consent is outstanding.

    Enterprise upgrade: consent status is cached in Redis (or LocMemCache)
    to eliminate 2 DB queries per write request. Cache is invalidated on
    consent grant/withdraw via invalidate_consent_cache().
"""
import logging
import threading
import uuid

from django.core.cache import cache
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)

# Consent cache TTL (seconds). Short enough that policy changes propagate
# quickly, long enough to eliminate most DB queries.
_CONSENT_CACHE_TTL = 120  # 2 minutes

# Cache key prefix for consent status
_CONSENT_CACHE_PREFIX = 'compliance:consent_ok'

# ─── Thread-Local Audit Context ──────────────────────────────────────────────
_audit_context = threading.local()


def get_audit_context() -> dict:
    """
    Retrieve the current request's audit context from thread-local storage.

    Returns:
        dict with 'request_id', 'ip_address', 'user_agent', 'user'.
        All values may be None if called outside a request.
    """
    return {
        'request_id': getattr(_audit_context, 'request_id', None),
        'ip_address': getattr(_audit_context, 'ip_address', None),
        'user_agent': getattr(_audit_context, 'user_agent', None),
        'user': getattr(_audit_context, 'user', None),
    }


def set_audit_context(*, request_id=None, ip_address=None, user_agent=None, user=None):
    """Manually set audit context (useful in Celery tasks or management commands)."""
    if request_id is not None:
        _audit_context.request_id = request_id
    if ip_address is not None:
        _audit_context.ip_address = ip_address
    if user_agent is not None:
        _audit_context.user_agent = user_agent
    if user is not None:
        _audit_context.user = user


def clear_audit_context():
    """Remove all audit context from the current thread."""
    for attr in ('request_id', 'ip_address', 'user_agent', 'user'):
        try:
            delattr(_audit_context, attr)
        except AttributeError:
            pass


def _get_client_ip(request) -> str:
    """
    Extract the real client IP, respecting X-Forwarded-For from trusted proxies.

    In production behind Render/Vercel, the first IP in X-Forwarded-For
    is the client; subsequent IPs are intermediate proxies.
    """
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        # First IP in the chain is the original client
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


class AuditContextMiddleware(MiddlewareMixin):
    """
    Injects audit metadata into thread-local storage for every request.

    This allows signal handlers, decorators, and utility functions to
    access the request context without explicit parameter passing.

    Also sets the X-Request-ID response header for distributed tracing.
    """

    def process_request(self, request):
        request_id = uuid.uuid4()
        ip_address = _get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:1000]

        _audit_context.request_id = request_id
        _audit_context.ip_address = ip_address
        _audit_context.user_agent = user_agent
        _audit_context.user = None  # Set after authentication

        # Attach to the request object for easy access in views
        request.audit_request_id = request_id
        request.audit_ip_address = ip_address

    def process_view(self, request, view_func, view_args, view_kwargs):
        # By this point, authentication middleware has run
        if hasattr(request, 'user') and request.user.is_authenticated:
            _audit_context.user = request.user

    def process_response(self, request, response):
        # Add request ID to response headers for client-side correlation
        request_id = getattr(request, 'audit_request_id', None)
        if request_id:
            response['X-Request-ID'] = str(request_id)

        # Clean up thread-local to prevent leaks in connection pooling
        clear_audit_context()
        return response


# ─── Consent Enforcement ─────────────────────────────────────────────────────

# Paths exempt from consent enforcement (auth flow, consent endpoints, public)
_CONSENT_EXEMPT_PREFIXES = (
    '/api/v1/auth/login',
    '/api/v1/auth/logout',
    '/api/v1/auth/refresh',
    '/api/v1/auth/register',
    '/api/v1/auth/verify-email',
    '/api/v1/auth/password-reset',
    '/api/v1/auth/2fa',
    '/api/v1/compliance/consent',
    '/api/v1/compliance/policies',
    '/api/v1/compliance/gdpr',
    '/api/v1/admin-api/public-stats',
    '/health/',
    '/admin/',
)


def invalidate_consent_cache(user_id: int) -> None:
    """
    Clear the cached consent status for a specific user.
    Call this when consent is granted, withdrawn, or a new policy is published.
    """
    key = f'{_CONSENT_CACHE_PREFIX}:{user_id}'
    cache.delete(key)
    logger.debug('Consent cache invalidated for user %s', user_id)


def invalidate_consent_cache_all() -> None:
    """
    Invalidate consent cache for ALL users. Call when a new policy
    with requires_re_consent=True is published.
    Uses cache key version bump pattern.
    """
    cache.incr('compliance:consent_version', 1, ignore_key_check=True)
    logger.info('Global consent cache invalidated (new policy published)')


def _consent_cache_key(user_id: int) -> str:
    """Build a versioned cache key for consent status."""
    version = cache.get('compliance:consent_version', 0)
    return f'{_CONSENT_CACHE_PREFIX}:v{version}:{user_id}'


class ConsentEnforcementMiddleware(MiddlewareMixin):
    """
    Ensures authenticated users have accepted all active policies
    that require re-consent.

    Returns HTTP 451 (Unavailable for Legal Reasons) with a JSON body
    listing the outstanding policies if consent is missing.

    Exempt paths (login, register, consent endpoint itself) are skipped.

    Enterprise: consent check is cached in Redis/LocMemCache for
    _CONSENT_CACHE_TTL seconds. Cache is invalidated on consent
    grant/withdraw (see invalidate_consent_cache).
    """

    def process_view(self, request, view_func, view_args, view_kwargs):
        # Skip unauthenticated requests
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return None

        # Skip exempt paths
        path = request.path
        if any(path.startswith(prefix) for prefix in _CONSENT_EXEMPT_PREFIXES):
            return None

        # Skip safe methods (GET, HEAD, OPTIONS) — allow browsing
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return None

        # ── Check cache first ────────────────────────────────────────────
        cache_key = _consent_cache_key(request.user.pk)
        cached = cache.get(cache_key)
        if cached == 'ok':
            return None  # Consent is current — no DB query needed

        try:
            from compliance.models import PolicyVersion, ConsentRecord

            # Find active policies requiring consent
            active_policies = PolicyVersion.objects.filter(
                is_active=True,
                requires_re_consent=True,
            )

            if not active_policies.exists():
                # No policies require consent — cache and return
                cache.set(cache_key, 'ok', _CONSENT_CACHE_TTL)
                return None

            # Check which policies the user hasn't consented to
            consented_policy_ids = set(
                ConsentRecord.objects.filter(
                    user=request.user,
                    withdrawn_at__isnull=True,
                    policy_version__in=active_policies,
                ).values_list('policy_version_id', flat=True)
            )

            outstanding = active_policies.exclude(pk__in=consented_policy_ids)
            if not outstanding.exists():
                # All consented — cache the positive result
                cache.set(cache_key, 'ok', _CONSENT_CACHE_TTL)
                return None

            # Consent required — return 451 (do NOT cache negative results
            # so that immediate re-consent takes effect without delay)
            policies = [
                {
                    'id': p.pk,
                    'type': p.policy_type,
                    'version': p.version,
                    'title': p.title,
                    'effective_date': p.effective_date.isoformat(),
                }
                for p in outstanding
            ]

            return JsonResponse(
                {
                    'error': 'consent_required',
                    'message': (
                        'You must accept the updated policies before '
                        'performing write operations.'
                    ),
                    'outstanding_policies': policies,
                },
                status=451,
            )
        except Exception:
            # If consent check fails, don't block the request — log and pass
            logger.exception('ConsentEnforcementMiddleware: check failed')
            return None
