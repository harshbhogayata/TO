"""
compliance/constants.py
Canonical action types, categories, and configuration constants
for the TalentOrbit compliance subsystem.

These are referenced across models, signals, middleware, decorators,
and tasks — centralised here to eliminate magic strings.
"""

# ──────────────────────────────────────────────────────────────────────────────
# Audit Log — Action Types
# ──────────────────────────────────────────────────────────────────────────────

class AuditAction:
    """Enumeration of every auditable action on the platform."""

    # Authentication
    LOGIN = 'LOGIN'
    LOGIN_FAILED = 'LOGIN_FAILED'
    LOGOUT = 'LOGOUT'
    TOKEN_REFRESH = 'TOKEN_REFRESH'
    PASSWORD_CHANGE = 'PASSWORD_CHANGE'
    PASSWORD_RESET_REQUEST = 'PASSWORD_RESET_REQUEST'
    PASSWORD_RESET_CONFIRM = 'PASSWORD_RESET_CONFIRM'
    TWO_FACTOR_ENABLE = '2FA_ENABLE'
    TWO_FACTOR_DISABLE = '2FA_DISABLE'
    TWO_FACTOR_LOGIN = '2FA_LOGIN'
    EMAIL_VERIFY = 'EMAIL_VERIFY'

    # CRUD
    CREATE = 'CREATE'
    READ = 'READ'
    UPDATE = 'UPDATE'
    DELETE = 'DELETE'

    # Account lifecycle
    ACCOUNT_DEACTIVATE = 'ACCOUNT_DEACTIVATE'
    ACCOUNT_REACTIVATE = 'ACCOUNT_REACTIVATE'

    # Admin actions
    ADMIN_VERIFY_USER = 'ADMIN_VERIFY_USER'
    ADMIN_DEACTIVATE_USER = 'ADMIN_DEACTIVATE_USER'
    ADMIN_TOGGLE_JOB = 'ADMIN_TOGGLE_JOB'

    # Payments
    SUBSCRIPTION_CREATE = 'SUBSCRIPTION_CREATE'
    SUBSCRIPTION_UPDATE = 'SUBSCRIPTION_UPDATE'
    SUBSCRIPTION_CANCEL = 'SUBSCRIPTION_CANCEL'
    PAYMENT_FAILED = 'PAYMENT_FAILED'

    # Compliance
    DATA_EXPORT_REQUEST = 'DATA_EXPORT_REQUEST'
    DATA_EXPORT_DOWNLOAD = 'DATA_EXPORT_DOWNLOAD'
    DATA_DELETION_REQUEST = 'DATA_DELETION_REQUEST'
    DATA_DELETION_CANCEL = 'DATA_DELETION_CANCEL'
    DATA_DELETION_EXECUTE = 'DATA_DELETION_EXECUTE'
    CONSENT_GRANT = 'CONSENT_GRANT'
    CONSENT_WITHDRAW = 'CONSENT_WITHDRAW'

    # Team management
    TEAM_CREATE = 'TEAM_CREATE'
    TEAM_INVITE = 'TEAM_INVITE'
    TEAM_INVITE_ACCEPT = 'TEAM_INVITE_ACCEPT'
    TEAM_INVITE_DECLINE = 'TEAM_INVITE_DECLINE'
    TEAM_INVITE_REVOKE = 'TEAM_INVITE_REVOKE'
    TEAM_MEMBER_ROLE_CHANGE = 'TEAM_MEMBER_ROLE_CHANGE'
    TEAM_MEMBER_REMOVE = 'TEAM_MEMBER_REMOVE'

    # Application workflow
    APPLICATION_SUBMIT = 'APPLICATION_SUBMIT'
    APPLICATION_STATUS_CHANGE = 'APPLICATION_STATUS_CHANGE'
    APPLICATION_WITHDRAW = 'APPLICATION_WITHDRAW'

    # Messaging
    MESSAGE_SEND = 'MESSAGE_SEND'
    THREAD_CREATE = 'THREAD_CREATE'


# ──────────────────────────────────────────────────────────────────────────────
# Audit Log — Categories
# ──────────────────────────────────────────────────────────────────────────────

class AuditCategory:
    """Broad groupings for audit events (used for filtering & reporting)."""

    AUTH = 'AUTH'
    USER = 'USER'
    JOB = 'JOB'
    APPLICATION = 'APPLICATION'
    MESSAGE = 'MESSAGE'
    PAYMENT = 'PAYMENT'
    ADMIN = 'ADMIN'
    COMPLIANCE = 'COMPLIANCE'
    TEAM = 'TEAM'
    SYSTEM = 'SYSTEM'


# ──────────────────────────────────────────────────────────────────────────────
# GDPR Configuration
# ──────────────────────────────────────────────────────────────────────────────

# Cooling-off period before permanent deletion (in days).
# GDPR doesn't mandate one, but 14 days prevents accidental data loss
# and is standard practice among enterprise SaaS providers.
DELETION_COOLING_OFF_DAYS = 14

# How long a completed data export download link is valid (in hours).
DATA_EXPORT_LINK_TTL_HOURS = 48

# Maximum data export requests per user per month (prevent abuse).
MAX_EXPORT_REQUESTS_PER_MONTH = 3

# Maximum deletion requests per user per month (prevent abuse).
MAX_DELETION_REQUESTS_PER_MONTH = 1


# ──────────────────────────────────────────────────────────────────────────────
# Data Retention Defaults (in days) — configurable per entity
# ──────────────────────────────────────────────────────────────────────────────

DATA_RETENTION_DEFAULTS = {
    'audit_logs': 2555,          # 7 years (SOC 2 / financial regulations)
    'read_notifications': 90,    # Already implemented
    'search_analytics': 365,     # 1 year
    'inactive_accounts': 730,    # 2 years before auto-anonymisation
    'expired_invitations': 30,   # 30 days
    'completed_exports': 7,      # 7 days (files only; records persist)
}


# ──────────────────────────────────────────────────────────────────────────────
# Team Seat Limits per Subscription Tier
# ──────────────────────────────────────────────────────────────────────────────

TEAM_SEAT_LIMITS = {
    'free': 1,            # Owner only — no additional seats
    'starter': 3,         # Owner + 2 recruiters
    'professional': 10,   # Owner + 9 team members
    'enterprise': 50,     # Owner + 49 team members (custom available)
}


# ──────────────────────────────────────────────────────────────────────────────
# Team Invitation TTL (in days)
# ──────────────────────────────────────────────────────────────────────────────

TEAM_INVITATION_TTL_DAYS = 7


# ──────────────────────────────────────────────────────────────────────────────
# Security.txt / Bug Bounty
# ──────────────────────────────────────────────────────────────────────────────

SECURITY_CONTACT = 'mailto:security@talentorbit.com'
SECURITY_POLICY_URL = 'https://talentorbit.com/security-policy'
SECURITY_ACKNOWLEDGEMENTS_URL = 'https://talentorbit.com/security/thanks'
BUG_BOUNTY_URL = 'https://talentorbit.com/security/bug-bounty'
SECURITY_PREFERRED_LANGUAGES = 'en'
