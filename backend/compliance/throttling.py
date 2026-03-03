"""
compliance/throttling.py
Enterprise-grade per-endpoint rate limiting for compliance-sensitive operations.

These throttle classes supplement the global AnonRateThrottle / UserRateThrottle
with tighter, operation-specific limits on endpoints that are expensive
(data exports), irreversible (data deletion), or security-critical (team invites).

All classes extend SimpleRateThrottle and key on the authenticated user ID
(falling back to IP for unauthenticated callers where applicable).
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


# ── GDPR Endpoints ──────────────────────────────────────────────────────────

class DataExportThrottle(_UserOrIPThrottle):
    """5 export requests per day per user — prevents storage abuse."""
    scope = 'compliance_export'


class DataExportDownloadThrottle(_UserOrIPThrottle):
    """20 downloads per hour per user — protects bandwidth."""
    scope = 'compliance_export_download'


class DataDeletionThrottle(_UserOrIPThrottle):
    """3 deletion requests per day per user — irreversible, limit abuse."""
    scope = 'compliance_deletion'


class DeletionConfirmThrottle(_UserOrIPThrottle):
    """10 confirmation attempts per hour — brute-force protection for tokens."""
    scope = 'compliance_deletion_confirm'


# ── Consent Endpoints ────────────────────────────────────────────────────────

class ConsentWriteThrottle(_UserOrIPThrottle):
    """30 consent writes per hour per user — prevents scripted toggling."""
    scope = 'compliance_consent_write'


# ── Team Endpoints ───────────────────────────────────────────────────────────

class TeamInviteThrottle(_UserOrIPThrottle):
    """20 team invitations per hour per user — prevents invitation spam."""
    scope = 'compliance_team_invite'


class TeamInviteActionThrottle(_UserOrIPThrottle):
    """30 accept/decline actions per hour — token brute-force protection."""
    scope = 'compliance_team_invite_action'


# ── Audit Endpoints (Admin) ──────────────────────────────────────────────────

class AuditLogThrottle(_UserOrIPThrottle):
    """60 audit log queries per hour — expensive DB queries."""
    scope = 'compliance_audit'


class AuditIntegrityThrottle(_UserOrIPThrottle):
    """5 integrity checks per hour — very expensive chain verification."""
    scope = 'compliance_audit_integrity'


# ── Policy Admin ─────────────────────────────────────────────────────────────

class PolicyCreateThrottle(_UserOrIPThrottle):
    """10 policy creations per hour — admin safety net."""
    scope = 'compliance_policy_create'
