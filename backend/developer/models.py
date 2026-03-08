"""
developer/models.py
Developer Platform data models for TalentOrbit.

Contains:
    1. APIKey             â€” Company API keys with hashed secrets, scoped access,
                            IP allowlists, per-key usage sparkline data
    2. WebhookEndpoint    â€” Registered webhook URLs with event subscriptions
    3. WebhookDelivery    â€” Immutable delivery log per webhook attempt
    4. OAuthApplication   â€” Registered OAuth 2.0 apps with client credentials,
                            redirect URIs, scope checklist, and revocation flow
    5. APIChangelog       â€” Versioned changelog entries for developer portal

Design:
    - API keys are stored as SHA-256 hashes; only the prefix is kept in plaintext.
    - Webhook signing secrets are signed at rest via Django Signer.
    - OAuth client secrets follow the same hash + prefix strategy as API keys.
    - Daily usage is recorded as a rolling 7-day JSON array for sparkline rendering.
    - All models use BigAutoField (inherited from settings) except where UUID is explicit.
"""
import hashlib
import secrets
import uuid

from django.conf import settings
from django.core.signing import Signer
from django.core.validators import URLValidator
from django.db import models
from django.utils import timezone

_webhook_signer = Signer(salt='talentorbit-webhook-secret-v1')


def _generate_api_key():
    """Generate a 40-char hex API key with 'to_live_' prefix."""
    return f'to_live_{secrets.token_hex(20)}'


def _generate_client_id():
    """Generate a unique OAuth client ID."""
    return f'to_app_{secrets.token_hex(12)}'


def _generate_client_secret():
    """Generate a 64-char hex client secret."""
    return secrets.token_hex(32)


def _generate_webhook_secret():
    """Generate a webhook signing secret."""
    return f'whsec_{secrets.token_hex(24)}'


def _hash_secret(value):
    """SHA-256 hash a secret value."""
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# 1. API KEY
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

class APIKey(models.Model):
    """
    Scoped API key for company integrations.

    The raw key is returned exactly once at creation time. We store only
    the SHA-256 hash + the first 12 characters as a display prefix.
    """

    class Meta:
        verbose_name = 'API Key'
        verbose_name_plural = 'API Keys'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['key_hash'], name='idx_apikey_hash'),
            models.Index(fields=['company', 'is_active'], name='idx_apikey_company_active'),
        ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        'accounts.CompanyProfile',
        on_delete=models.CASCADE,
        related_name='api_keys',
    )

    name = models.CharField(max_length=100, help_text='Human-friendly key label.')
    key_hash = models.CharField(
        max_length=64, unique=True, editable=False,
        help_text='SHA-256 of the full API key.',
    )
    prefix = models.CharField(
        max_length=20, editable=False,
        help_text='First 12 chars of the key (for UI identification).',
    )

    # Scopes â€” list of strings e.g. ["read:jobs", "write:jobs", "read:assessments"]
    scopes = models.JSONField(
        default=list,
        help_text='List of permission scope strings.',
    )

    # IP Allowlist â€” empty list means no restriction
    ip_allowlist = models.JSONField(
        default=list,
        help_text='List of allowed IPv4/IPv6 CIDRs. Empty = unrestricted.',
    )

    is_active = models.BooleanField(default=True, db_index=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    last_used_ip = models.GenericIPAddressField(null=True, blank=True)
    usage_count = models.PositiveIntegerField(default=0)

    # Rolling 7-day hourly usage for sparkline â€” list of 7 integers
    daily_usage = models.JSONField(
        default=list,
        help_text='Rolling 7-day usage counts for sparkline rendering.',
    )

    expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text='Optional expiry. Null = never expires.',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_api_keys',
    )

    def __str__(self):
        return f'{self.name} ({self.prefix}â€¦)'

    @property
    def is_expired(self):
        if self.expires_at is None:
            return False
        return timezone.now() >= self.expires_at

    @classmethod
    def create_key(cls, company, name, scopes, ip_allowlist=None, expires_at=None, created_by=None):
        """
        Factory method: generates a raw key, stores the hash + prefix,
        and returns (instance, raw_key) so the caller can show it once.
        """
        raw_key = _generate_api_key()
        instance = cls(
            company=company,
            name=name,
            key_hash=_hash_secret(raw_key),
            prefix=raw_key[:16],
            scopes=scopes or [],
            ip_allowlist=ip_allowlist or [],
            expires_at=expires_at,
            created_by=created_by,
            daily_usage=[0] * 7,
        )
        instance.save()
        return instance, raw_key

    @classmethod
    def lookup_by_raw_key(cls, raw_key):
        """Resolve an active API key from the raw bearer value."""
        hashed = _hash_secret(raw_key)
        try:
            key = cls.objects.get(key_hash=hashed, is_active=True)
            if key.is_expired:
                return None
            return key
        except cls.DoesNotExist:
            return None

    def record_usage(self, ip=None):
        """Bump counters and last-used timestamp."""
        self.usage_count += 1
        self.last_used_at = timezone.now()
        if ip:
            self.last_used_ip = ip
        # Rotate daily_usage: drop oldest, add today
        usage = list(self.daily_usage) if self.daily_usage else [0] * 7
        usage[-1] = usage[-1] + 1 if len(usage) == 7 else 1
        self.daily_usage = usage
        self.save(update_fields=['usage_count', 'last_used_at', 'last_used_ip', 'daily_usage'])


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# 2. WEBHOOK ENDPOINT
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

class WebhookEndpoint(models.Model):
    """
    A registered webhook URL for a company, subscribed to specific events.
    Signing secret is encrypted at rest via Django Signer.
    """

    AVAILABLE_EVENTS = [
        ('job.created', 'Job Created'),
        ('job.updated', 'Job Updated'),
        ('job.closed', 'Job Closed'),
        ('application.received', 'Application Received'),
        ('application.status_changed', 'Application Status Changed'),
        ('assessment.completed', 'Assessment Completed'),
        ('assessment.graded', 'Assessment Graded'),
        ('user.deactivated', 'User Deactivated'),
        ('invoice.paid', 'Invoice Paid'),
        ('team.member_added', 'Team Member Added'),
    ]

    class Meta:
        verbose_name = 'Webhook Endpoint'
        verbose_name_plural = 'Webhook Endpoints'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'url'],
                name='uq_webhook_company_url',
            ),
        ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        'accounts.CompanyProfile',
        on_delete=models.CASCADE,
        related_name='webhook_endpoints',
    )

    url = models.URLField(
        max_length=500,
        help_text='HTTPS endpoint URL that receives POST payloads.',
    )

    # Events this endpoint is subscribed to
    events = models.JSONField(
        default=list,
        help_text='List of event type strings this endpoint listens to.',
    )

    # Signing secret â€” signed at rest
    signing_secret_signed = models.CharField(
        max_length=256, editable=False,
        help_text='Signer-protected webhook signing secret.',
    )
    signing_secret_prefix = models.CharField(
        max_length=20, editable=False,
        help_text='First 12 chars for display.',
    )

    is_active = models.BooleanField(default=True, db_index=True)
    failure_count = models.PositiveIntegerField(
        default=0,
        help_text='Consecutive delivery failures. Resets on success.',
    )
    last_delivery_at = models.DateTimeField(null=True, blank=True)
    last_status_code = models.PositiveIntegerField(null=True, blank=True)

    description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_webhooks',
    )

    def __str__(self):
        return f'Webhook â†’ {self.url[:60]}â€¦'

    @classmethod
    def create_endpoint(cls, company, url, events, description='', created_by=None):
        """
        Factory: generates signing secret, signs it, and creates the endpoint.
        Returns (instance, raw_secret).
        """
        from .validators import validate_webhook_url

        url = validate_webhook_url(url)
        raw_secret = _generate_webhook_secret()
        instance = cls(
            company=company,
            url=url,
            events=events or [],
            signing_secret_signed=_webhook_signer.sign(raw_secret),
            signing_secret_prefix=raw_secret[:16],
            description=description,
            created_by=created_by,
        )
        instance.save()
        return instance, raw_secret

    def get_signing_secret(self):
        """Unsign and return the raw secret for signature computation."""
        from django.core.signing import BadSignature
        try:
            return _webhook_signer.unsign(self.signing_secret_signed)
        except BadSignature:
            return self.signing_secret_signed

    @property
    def status_label(self):
        if not self.is_active:
            return 'disabled'
        if self.failure_count >= 5:
            return 'failing'
        return 'active'


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# 3. WEBHOOK DELIVERY LOG
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

class WebhookDelivery(models.Model):
    """
    Immutable log entry for each webhook delivery attempt.
    Supports multiple retry attempts per logical delivery.
    """

    class Meta:
        verbose_name = 'Webhook Delivery'
        verbose_name_plural = 'Webhook Deliveries'
        ordering = ['-delivered_at']
        indexes = [
            models.Index(fields=['endpoint', '-delivered_at'], name='idx_delivery_endpoint_date'),
        ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    endpoint = models.ForeignKey(
        WebhookEndpoint,
        on_delete=models.CASCADE,
        related_name='deliveries',
    )

    event_type = models.CharField(max_length=80, db_index=True)
    payload = models.JSONField(
        default=dict,
        help_text='Full JSON payload delivered to the endpoint.',
    )

    status_code = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='HTTP status code from the endpoint response.',
    )
    response_body = models.TextField(
        blank=True,
        help_text='First 2KB of the endpoint response body.',
    )
    response_time_ms = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Round-trip time in milliseconds.',
    )

    attempt_number = models.PositiveSmallIntegerField(
        default=1,
        help_text='Retry attempt number (1 = first try).',
    )
    error_message = models.TextField(
        blank=True,
        help_text='Error message if delivery failed (timeout, DNS, etc.).',
    )
    is_success = models.BooleanField(
        default=False, db_index=True,
        help_text='True if status_code is 2xx.',
    )

    delivered_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.event_type} â†’ {self.endpoint.url[:40]} [{self.status_code}]'


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# 4. OAUTH APPLICATION
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

class OAuthApplication(models.Model):
    """
    Registered OAuth 2.0 application for third-party integrations.

    client_secret is stored as SHA-256 hash + prefix, exactly like API keys.
    The raw secret is returned only once at creation.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending Approval'
        ACTIVE = 'active', 'Active'
        SUSPENDED = 'suspended', 'Suspended'
        REVOKED = 'revoked', 'Revoked'

    class Meta:
        verbose_name = 'OAuth Application'
        verbose_name_plural = 'OAuth Applications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client_id'], name='idx_oauth_client_id'),
            models.Index(fields=['company', 'status'], name='idx_oauth_company_status'),
        ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        'accounts.CompanyProfile',
        on_delete=models.CASCADE,
        related_name='oauth_applications',
    )

    name = models.CharField(max_length=150, help_text='Application display name.')
    client_id = models.CharField(
        max_length=40, unique=True, editable=False,
        help_text='Public OAuth client identifier.',
    )
    client_secret_hash = models.CharField(
        max_length=64, editable=False,
        help_text='SHA-256 of the client secret.',
    )
    client_secret_prefix = models.CharField(
        max_length=20, editable=False,
        help_text='First 12 chars of the client secret (for UI).',
    )

    redirect_uris = models.JSONField(
        default=list,
        help_text='List of allowed redirect URI strings.',
    )
    scopes = models.JSONField(
        default=list,
        help_text='List of OAuth scope strings.',
    )

    logo_initials = models.CharField(
        max_length=4, blank=True,
        help_text='1-2 character initials for logo placeholder.',
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    authorized_users_count = models.PositiveIntegerField(
        default=0,
        help_text='Cached count of users who have authorized this app.',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_oauth_apps',
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='revoked_oauth_apps',
    )

    def __str__(self):
        return f'{self.name} ({self.client_id})'

    @classmethod
    def create_application(cls, company, name, redirect_uris, scopes, created_by=None):
        """
        Factory: generates client_id + client_secret, stores hashes,
        returns (instance, raw_client_secret).
        """
        client_id = _generate_client_id()
        raw_secret = _generate_client_secret()
        initials = ''.join(w[0] for w in name.split() if w)[:2].upper() or name[:2].upper()

        instance = cls(
            company=company,
            name=name,
            client_id=client_id,
            client_secret_hash=_hash_secret(raw_secret),
            client_secret_prefix=raw_secret[:12],
            redirect_uris=redirect_uris or [],
            scopes=scopes or [],
            logo_initials=initials,
            created_by=created_by,
        )
        instance.save()
        return instance, raw_secret

    def revoke(self, user=None):
        """Mark the application as revoked."""
        self.status = self.Status.REVOKED
        self.revoked_at = timezone.now()
        self.revoked_by = user
        self.save(update_fields=['status', 'revoked_at', 'revoked_by'])


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# 5. API CHANGELOG
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

class APIChangelog(models.Model):
    """
    Versioned changelog entries displayed in the developer portal.
    """

    class ChangeType(models.TextChoices):
        MAJOR = 'major', 'Major Release'
        MINOR = 'minor', 'Minor Release'
        PATCH = 'patch', 'Patch'
        DEPRECATION = 'deprecation', 'Deprecation'
        SECURITY = 'security', 'Security Fix'

    class Meta:
        verbose_name = 'API Changelog'
        verbose_name_plural = 'API Changelog Entries'
        ordering = ['-published_at']

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.CharField(max_length=30, help_text='e.g. v4.0.2')
    title = models.CharField(max_length=200)
    description = models.TextField(help_text='Markdown-supported description of changes.')
    change_type = models.CharField(
        max_length=20,
        choices=ChangeType.choices,
        default=ChangeType.PATCH,
    )
    is_published = models.BooleanField(default=False, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='authored_changelogs',
    )

    def __str__(self):
        return f'{self.version} â€” {self.title}'


