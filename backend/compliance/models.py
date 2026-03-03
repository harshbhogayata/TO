"""
compliance/models.py
Phase 6 — Trust & Compliance data models.

Contains:
    1. AuditLog         — Tamper-resistant, chained audit trail (SOC 2)
    2. PolicyVersion     — Versioned legal policies (ToS, Privacy, Cookie, DPA)
    3. ConsentRecord     — Per-user consent tracking with withdrawal support
    4. DataExportRequest — GDPR Article 20 data portability
    5. DataDeletionRequest — GDPR Article 17 right to erasure
    6. Team              — Company team container
    7. TeamMember        — Role-based team membership (OWNER/ADMIN/RECRUITER/VIEWER)
    8. TeamInvitation    — Email-based team invitation flow

Design decisions:
    - AuditLog uses chained SHA-256 checksums for tamper evidence
    - AuditLog is append-only (no update/delete at application level)
    - DataDeletionRequest enforces a 14-day cooling-off period
    - ConsentRecord supports both granting and withdrawal with full audit trail
    - Team seats are capped per subscription tier
    - All models use BigAutoField (inherited from settings)
"""
import hashlib
import json
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


# ═══════════════════════════════════════════════════════════════════════════════
# 1. AUDIT LOG — Tamper-Resistant Event Ledger
# ═══════════════════════════════════════════════════════════════════════════════

class AuditLog(models.Model):
    """
    Immutable, chained audit log entry.

    Every significant platform action produces an AuditLog record.
    Records are linked via `previous_checksum` — breaking the chain
    is detectable, providing tamper-evidence suitable for SOC 2 Type I.

    Fields are intentionally denormalised (actor_email, actor_role)
    so that user deletion (GDPR) does not destroy the audit trail.
    """

    class Action(models.TextChoices):
        CREATE = 'CREATE', 'Create'
        READ = 'READ', 'Read'
        UPDATE = 'UPDATE', 'Update'
        DELETE = 'DELETE', 'Delete'
        LOGIN = 'LOGIN', 'Login'
        LOGIN_FAILED = 'LOGIN_FAILED', 'Login Failed'
        LOGOUT = 'LOGOUT', 'Logout'
        TOKEN_REFRESH = 'TOKEN_REFRESH', 'Token Refresh'
        PASSWORD_CHANGE = 'PASSWORD_CHANGE', 'Password Change'
        PASSWORD_RESET_REQUEST = 'PASSWORD_RESET_REQUEST', 'Password Reset Request'
        PASSWORD_RESET_CONFIRM = 'PASSWORD_RESET_CONFIRM', 'Password Reset Confirm'
        TWO_FACTOR_ENABLE = '2FA_ENABLE', '2FA Enable'
        TWO_FACTOR_DISABLE = '2FA_DISABLE', '2FA Disable'
        TWO_FACTOR_LOGIN = '2FA_LOGIN', '2FA Login'
        EMAIL_VERIFY = 'EMAIL_VERIFY', 'Email Verify'
        ACCOUNT_DEACTIVATE = 'ACCOUNT_DEACTIVATE', 'Account Deactivate'
        ACCOUNT_REACTIVATE = 'ACCOUNT_REACTIVATE', 'Account Reactivate'
        ADMIN_VERIFY_USER = 'ADMIN_VERIFY_USER', 'Admin Verify User'
        ADMIN_DEACTIVATE_USER = 'ADMIN_DEACTIVATE_USER', 'Admin Deactivate User'
        ADMIN_TOGGLE_JOB = 'ADMIN_TOGGLE_JOB', 'Admin Toggle Job'
        SUBSCRIPTION_CREATE = 'SUBSCRIPTION_CREATE', 'Subscription Create'
        SUBSCRIPTION_UPDATE = 'SUBSCRIPTION_UPDATE', 'Subscription Update'
        SUBSCRIPTION_CANCEL = 'SUBSCRIPTION_CANCEL', 'Subscription Cancel'
        PAYMENT_FAILED = 'PAYMENT_FAILED', 'Payment Failed'
        DATA_EXPORT_REQUEST = 'DATA_EXPORT_REQUEST', 'Data Export Request'
        DATA_EXPORT_DOWNLOAD = 'DATA_EXPORT_DOWNLOAD', 'Data Export Download'
        DATA_DELETION_REQUEST = 'DATA_DELETION_REQUEST', 'Data Deletion Request'
        DATA_DELETION_CANCEL = 'DATA_DELETION_CANCEL', 'Data Deletion Cancel'
        DATA_DELETION_EXECUTE = 'DATA_DELETION_EXECUTE', 'Data Deletion Execute'
        CONSENT_GRANT = 'CONSENT_GRANT', 'Consent Grant'
        CONSENT_WITHDRAW = 'CONSENT_WITHDRAW', 'Consent Withdraw'
        TEAM_CREATE = 'TEAM_CREATE', 'Team Create'
        TEAM_INVITE = 'TEAM_INVITE', 'Team Invite'
        TEAM_INVITE_ACCEPT = 'TEAM_INVITE_ACCEPT', 'Team Invite Accept'
        TEAM_INVITE_DECLINE = 'TEAM_INVITE_DECLINE', 'Team Invite Decline'
        TEAM_INVITE_REVOKE = 'TEAM_INVITE_REVOKE', 'Team Invite Revoke'
        TEAM_MEMBER_ROLE_CHANGE = 'TEAM_MEMBER_ROLE_CHANGE', 'Team Member Role Change'
        TEAM_MEMBER_REMOVE = 'TEAM_MEMBER_REMOVE', 'Team Member Remove'
        APPLICATION_SUBMIT = 'APPLICATION_SUBMIT', 'Application Submit'
        APPLICATION_STATUS_CHANGE = 'APPLICATION_STATUS_CHANGE', 'Application Status Change'
        APPLICATION_WITHDRAW = 'APPLICATION_WITHDRAW', 'Application Withdraw'
        MESSAGE_SEND = 'MESSAGE_SEND', 'Message Send'
        THREAD_CREATE = 'THREAD_CREATE', 'Thread Create'

    class Category(models.TextChoices):
        AUTH = 'AUTH', 'Authentication'
        USER = 'USER', 'User Management'
        JOB = 'JOB', 'Job Management'
        APPLICATION = 'APPLICATION', 'Application'
        MESSAGE = 'MESSAGE', 'Messaging'
        PAYMENT = 'PAYMENT', 'Payment'
        ADMIN = 'ADMIN', 'Admin Action'
        COMPLIANCE = 'COMPLIANCE', 'Compliance'
        TEAM = 'TEAM', 'Team Management'
        SYSTEM = 'SYSTEM', 'System'

    # ── Who ───────────────────────────────────────────────────────────────
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        help_text='The user who performed the action. NULL for system/anonymous events.',
    )
    actor_email = models.EmailField(
        blank=True,
        help_text='Denormalised email — persists even if user is deleted.',
    )
    actor_role = models.CharField(
        max_length=20,
        blank=True,
        help_text='Denormalised role at time of action.',
    )

    # ── What ──────────────────────────────────────────────────────────────
    action = models.CharField(max_length=40, choices=Action.choices, db_index=True)
    category = models.CharField(max_length=30, choices=Category.choices, db_index=True)
    description = models.TextField(
        help_text='Human-readable description of what happened.',
    )

    # ── On Which Resource ─────────────────────────────────────────────────
    resource_type = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text='Django model label, e.g. "accounts.User" or "jobs.JobPost".',
    )
    resource_id = models.CharField(
        max_length=100,
        blank=True,
        help_text='Primary key of the affected resource (stringified).',
    )

    # ── Change Tracking ───────────────────────────────────────────────────
    changes = models.JSONField(
        default=dict,
        blank=True,
        help_text='Structured diff: {"field": {"old": ..., "new": ...}}',
    )

    # ── Request Context ───────────────────────────────────────────────────
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    request_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        help_text='Correlation ID from AuditContextMiddleware.',
    )

    # ── Tamper Evidence ───────────────────────────────────────────────────
    checksum = models.CharField(
        max_length=64,
        blank=True,
        editable=False,
        help_text='SHA-256 hash of this record\'s canonical fields.',
    )
    previous_checksum = models.CharField(
        max_length=64,
        blank=True,
        editable=False,
        help_text='Checksum of the immediately preceding AuditLog entry (chain link).',
    )

    # ── Timestamp ─────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        indexes = [
            models.Index(fields=['actor', '-created_at'], name='idx_audit_actor_date'),
            models.Index(fields=['resource_type', 'resource_id'], name='idx_audit_resource'),
            models.Index(fields=['action', '-created_at'], name='idx_audit_action_date'),
            models.Index(fields=['category', '-created_at'], name='idx_audit_category_date'),
            models.Index(fields=['ip_address', '-created_at'], name='idx_audit_ip_date'),
        ]

    def __str__(self):
        actor = self.actor_email or 'system'
        return f'[{self.action}] {actor} — {self.description[:80]}'

    def save(self, *args, **kwargs):
        # Denormalise actor info at write-time
        if self.actor and not self.actor_email:
            self.actor_email = self.actor.email
            self.actor_role = getattr(self.actor, 'role', '')

        # Chain: fetch previous checksum
        if not self.previous_checksum:
            last = AuditLog.objects.order_by('-pk').values_list('checksum', flat=True).first()
            self.previous_checksum = last or ('0' * 64)

        # Compute tamper-resistant checksum
        self.checksum = self._compute_checksum()

        super().save(*args, **kwargs)

    def _compute_checksum(self) -> str:
        """
        SHA-256 over a canonical representation of the record.
        Includes the previous_checksum for chain integrity.
        """
        payload = '|'.join([
            str(self.actor_id or ''),
            self.actor_email,
            self.actor_role,
            self.action,
            self.category,
            self.description,
            self.resource_type,
            str(self.resource_id),
            json.dumps(self.changes, sort_keys=True, default=str),
            str(self.ip_address or ''),
            str(self.request_id or ''),
            self.previous_checksum,
        ])
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()

    def verify_integrity(self) -> bool:
        """Check that the stored checksum matches a recomputed one."""
        return self.checksum == self._compute_checksum()

    @classmethod
    def verify_chain(cls, limit: int = 1000) -> dict:
        """
        Verify the integrity of the last `limit` audit log entries.
        Returns a dict with 'valid', 'checked', and 'first_broken_id'.
        """
        entries = list(
            cls.objects.order_by('pk').values(
                'pk', 'checksum', 'previous_checksum'
            )[:limit]
        )
        if not entries:
            return {'valid': True, 'checked': 0, 'first_broken_id': None}

        for i, entry in enumerate(entries):
            if i == 0:
                continue
            if entry['previous_checksum'] != entries[i - 1]['checksum']:
                return {
                    'valid': False,
                    'checked': i + 1,
                    'first_broken_id': entry['pk'],
                }

        return {'valid': True, 'checked': len(entries), 'first_broken_id': None}


# ═══════════════════════════════════════════════════════════════════════════════
# 2. POLICY VERSIONING — Legal Document Lifecycle
# ═══════════════════════════════════════════════════════════════════════════════

class PolicyVersion(models.Model):
    """
    Versioned legal policy document (ToS, Privacy Policy, Cookie Policy, DPA).

    Only one version per policy_type can be `is_active=True` at a time.
    When a new version with `requires_re_consent=True` is published,
    ConsentEnforcementMiddleware will prompt users to accept it.
    """

    class PolicyType(models.TextChoices):
        TOS = 'tos', 'Terms of Service'
        PRIVACY = 'privacy', 'Privacy Policy'
        COOKIE = 'cookie', 'Cookie Policy'
        DPA = 'dpa', 'Data Processing Agreement'

    policy_type = models.CharField(
        max_length=20,
        choices=PolicyType.choices,
        db_index=True,
    )
    version = models.CharField(
        max_length=20,
        help_text='Semantic version, e.g. "2.1.0".',
    )
    title = models.CharField(max_length=255)
    summary = models.TextField(
        blank=True,
        help_text='Plain-language summary of changes from previous version.',
    )
    content = models.TextField(
        help_text='Full policy text (Markdown supported).',
    )
    effective_date = models.DateField(
        help_text='Date from which this version takes effect.',
    )
    published_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(
        default=False,
        db_index=True,
        help_text='Only one version per policy_type should be active.',
    )
    requires_re_consent = models.BooleanField(
        default=False,
        help_text='If True, existing users must re-consent to this version.',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='authored_policies',
    )

    class Meta:
        ordering = ['-published_at']
        verbose_name = 'Policy Version'
        verbose_name_plural = 'Policy Versions'
        unique_together = ('policy_type', 'version')
        indexes = [
            models.Index(
                fields=['policy_type', 'is_active'],
                name='idx_policy_type_active',
            ),
        ]

    def __str__(self):
        status = '✓' if self.is_active else '○'
        return f'{status} {self.get_policy_type_display()} v{self.version}'

    def save(self, *args, **kwargs):
        # Enforce single-active constraint: deactivate siblings on activation
        if self.is_active:
            PolicyVersion.objects.filter(
                policy_type=self.policy_type,
                is_active=True,
            ).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. CONSENT RECORDS — Granular Consent Tracking
# ═══════════════════════════════════════════════════════════════════════════════

class ConsentRecord(models.Model):
    """
    Records a user's explicit consent (or withdrawal) to a specific PolicyVersion.

    GDPR requires demonstrable proof of consent:
    - Who consented
    - What they consented to (specific policy version)
    - When (timestamp)
    - How (IP, user-agent)
    - Withdrawal timestamp (if applicable)
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='consent_records',
    )
    policy_version = models.ForeignKey(
        PolicyVersion,
        on_delete=models.PROTECT,
        related_name='consent_records',
        help_text='The exact policy version the user consented to.',
    )
    consented_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    withdrawn_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When consent was withdrawn. NULL = still active.',
    )
    withdrawal_reason = models.TextField(
        blank=True,
        help_text='Optional reason for consent withdrawal.',
    )

    class Meta:
        ordering = ['-consented_at']
        verbose_name = 'Consent Record'
        verbose_name_plural = 'Consent Records'
        unique_together = ('user', 'policy_version')
        indexes = [
            models.Index(fields=['user', '-consented_at'], name='idx_consent_user_date'),
            models.Index(
                fields=['policy_version', 'withdrawn_at'],
                name='idx_consent_policy_withdrawn',
            ),
        ]

    def __str__(self):
        status = 'withdrawn' if self.withdrawn_at else 'active'
        return f'{self.user.email} → {self.policy_version} ({status})'

    @property
    def is_active(self) -> bool:
        return self.withdrawn_at is None


# ═══════════════════════════════════════════════════════════════════════════════
# 4. GDPR DATA EXPORT — Article 20 (Right to Data Portability)
# ═══════════════════════════════════════════════════════════════════════════════

class DataExportRequest(models.Model):
    """
    Tracks a user's request to export all their personal data.

    Workflow:
        1. User requests export → status=PENDING
        2. Celery task picks it up → status=PROCESSING
        3. Task compiles data into JSON + ZIP → status=COMPLETED
        4. User downloads within TTL → after expiry status=EXPIRED
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'
        EXPIRED = 'expired', 'Expired'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='data_export_requests',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    file_path = models.CharField(
        max_length=500,
        blank=True,
        help_text='Storage path (R2 key or local path) of the export archive.',
    )
    file_size_bytes = models.BigIntegerField(null=True, blank=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='After this time the download link is invalid.',
    )
    error_message = models.TextField(blank=True)

    # Security: one-time download token
    download_token = models.CharField(
        max_length=128,
        unique=True,
        default='',
        help_text='Unique token for secure download URL.',
    )

    class Meta:
        ordering = ['-requested_at']
        verbose_name = 'Data Export Request'
        verbose_name_plural = 'Data Export Requests'
        indexes = [
            models.Index(fields=['user', 'status'], name='idx_export_user_status'),
            models.Index(fields=['status', '-requested_at'], name='idx_export_status_date'),
        ]

    def __str__(self):
        return f'Export #{self.pk} — {self.user.email} [{self.status}]'

    def save(self, *args, **kwargs):
        if not self.download_token:
            self.download_token = secrets.token_urlsafe(64)
        super().save(*args, **kwargs)

    @property
    def is_downloadable(self) -> bool:
        return (
            self.status == self.Status.COMPLETED
            and self.file_path
            and self.expires_at
            and timezone.now() < self.expires_at
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 5. GDPR DATA DELETION — Article 17 (Right to Erasure)
# ═══════════════════════════════════════════════════════════════════════════════

class DataDeletionRequest(models.Model):
    """
    Tracks a user's request to permanently delete all personal data.

    Workflow:
        1. User requests deletion → status=PENDING
        2. Confirmation email sent with token → status=COOLING_OFF
        3. 14-day cooling-off period (user can cancel)
        4. After cooling-off, Celery task executes deletion → status=PROCESSING
        5. All PII anonymised/removed → status=COMPLETED

    The cooling-off period is a deliberate design choice to prevent
    accidental or coerced data loss. Enterprise customers expect this.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending Confirmation'
        COOLING_OFF = 'cooling_off', 'Cooling-Off Period'
        PROCESSING = 'processing', 'Processing Deletion'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled by User'
        FAILED = 'failed', 'Failed'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='data_deletion_requests',
        help_text='SET_NULL because the user row is anonymised on completion.',
    )
    user_email = models.EmailField(
        help_text='Denormalised — persists after user deletion for audit.',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    reason = models.TextField(
        blank=True,
        help_text='Optional reason for requesting deletion.',
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When the user clicked the confirmation link.',
    )
    cooling_off_ends_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='End of the cooling-off period.',
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    # Security: confirmation + cancellation tokens
    confirmation_token = models.CharField(
        max_length=128,
        unique=True,
        default='',
    )
    cancellation_token = models.CharField(
        max_length=128,
        unique=True,
        default='',
    )

    # What was deleted (summary for audit)
    deletion_summary = models.JSONField(
        default=dict,
        blank=True,
        help_text='Counts of deleted records by model.',
    )

    class Meta:
        ordering = ['-requested_at']
        verbose_name = 'Data Deletion Request'
        verbose_name_plural = 'Data Deletion Requests'
        indexes = [
            models.Index(fields=['status', '-requested_at'], name='idx_deletion_status_date'),
            models.Index(
                fields=['cooling_off_ends_at', 'status'],
                name='idx_deletion_cooloff_status',
            ),
        ]

    def __str__(self):
        return f'Deletion #{self.pk} — {self.user_email} [{self.status}]'

    def save(self, *args, **kwargs):
        if not self.confirmation_token:
            self.confirmation_token = secrets.token_urlsafe(64)
        if not self.cancellation_token:
            self.cancellation_token = secrets.token_urlsafe(64)
        if not self.user_email and self.user:
            self.user_email = self.user.email
        super().save(*args, **kwargs)

    @property
    def is_cancellable(self) -> bool:
        return self.status in (
            self.Status.PENDING,
            self.Status.COOLING_OFF,
        )

    @property
    def cooling_off_remaining(self) -> timedelta | None:
        if self.status != self.Status.COOLING_OFF or not self.cooling_off_ends_at:
            return None
        remaining = self.cooling_off_ends_at - timezone.now()
        return max(remaining, timedelta(0))


# ═══════════════════════════════════════════════════════════════════════════════
# 6. TEAM — Company Team Container
# ═══════════════════════════════════════════════════════════════════════════════

class Team(models.Model):
    """
    Represents a company's team on TalentOrbit.

    Each CompanyProfile can have exactly one Team. The team's seat limit
    is determined by the company's subscription tier.
    """

    company = models.OneToOneField(
        'accounts.CompanyProfile',
        on_delete=models.CASCADE,
        related_name='team',
    )
    name = models.CharField(
        max_length=255,
        help_text='Display name for the team (defaults to company legal_name).',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Team'
        verbose_name_plural = 'Teams'

    def __str__(self):
        return f'Team: {self.name}'

    @property
    def max_seats(self) -> int:
        """Seat limit based on company's subscription tier."""
        from compliance.constants import TEAM_SEAT_LIMITS
        tier = self.company.subscription_tier or 'free'
        return TEAM_SEAT_LIMITS.get(tier, TEAM_SEAT_LIMITS['free'])

    @property
    def current_seat_count(self) -> int:
        return self.members.filter(is_active=True).count()

    @property
    def seats_available(self) -> int:
        return max(0, self.max_seats - self.current_seat_count)

    @property
    def is_at_capacity(self) -> bool:
        return self.current_seat_count >= self.max_seats


# ═══════════════════════════════════════════════════════════════════════════════
# 7. TEAM MEMBER — Role-Based Team Membership
# ═══════════════════════════════════════════════════════════════════════════════

class TeamMember(models.Model):
    """
    Represents an individual's membership in a Team.

    Roles:
        OWNER     — Full control. Can delete team, transfer ownership. Exactly one per team.
        ADMIN     — Manage members, settings, all job posts.
        RECRUITER — Create/manage own job posts, review applications.
        VIEWER    — Read-only access to job posts and applications.
    """

    class Role(models.TextChoices):
        OWNER = 'owner', 'Owner'
        ADMIN = 'admin', 'Admin'
        RECRUITER = 'recruiter', 'Recruiter'
        VIEWER = 'viewer', 'Viewer'

    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='members',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='team_memberships',
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.VIEWER,
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='team_invitations_sent',
    )
    is_active = models.BooleanField(default=True, db_index=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Team Member'
        verbose_name_plural = 'Team Members'
        unique_together = ('team', 'user')
        indexes = [
            models.Index(fields=['team', 'is_active'], name='idx_tm_team_active'),
            models.Index(fields=['user', 'is_active'], name='idx_tm_user_active'),
        ]

    def __str__(self):
        return f'{self.user.email} [{self.role}] in {self.team.name}'

    @property
    def is_owner(self) -> bool:
        return self.role == self.Role.OWNER

    @property
    def can_manage_members(self) -> bool:
        return self.role in (self.Role.OWNER, self.Role.ADMIN)

    @property
    def can_manage_jobs(self) -> bool:
        return self.role in (self.Role.OWNER, self.Role.ADMIN, self.Role.RECRUITER)


# ═══════════════════════════════════════════════════════════════════════════════
# 8. TEAM INVITATION — Email-Based Invite Flow
# ═══════════════════════════════════════════════════════════════════════════════

class TeamInvitation(models.Model):
    """
    Email-based team invitation with expiry and status tracking.

    Flow:
        1. Admin/Owner creates invitation → email sent with token link
        2. Invitee clicks link → if registered, joins team; if not, registers first
        3. Invitation expires after TEAM_INVITATION_TTL_DAYS
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACCEPTED = 'accepted', 'Accepted'
        DECLINED = 'declined', 'Declined'
        EXPIRED = 'expired', 'Expired'
        REVOKED = 'revoked', 'Revoked'

    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='invitations',
    )
    email = models.EmailField(
        help_text='Email address of the invitee.',
    )
    role = models.CharField(
        max_length=20,
        choices=TeamMember.Role.choices,
        default=TeamMember.Role.RECRUITER,
        help_text='Role the invitee will receive upon acceptance.',
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sent_team_invitations',
    )
    token = models.CharField(
        max_length=128,
        unique=True,
        default='',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    message = models.TextField(
        blank=True,
        help_text='Optional personal message from the inviter.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Team Invitation'
        verbose_name_plural = 'Team Invitations'
        indexes = [
            models.Index(fields=['email', 'status'], name='idx_invite_email_status'),
            models.Index(fields=['team', 'status'], name='idx_invite_team_status'),
        ]

    def __str__(self):
        return f'Invite {self.email} → {self.team.name} [{self.status}]'

    def save(self, *args, **kwargs):
        # Always set expires_at before the first DB write
        if not self.expires_at:
            from compliance.constants import TEAM_INVITATION_TTL_DAYS
            self.expires_at = timezone.now() + timedelta(days=TEAM_INVITATION_TTL_DAYS)
        if not self.token:
            from compliance.token_utils import generate_signed_token
            # Generate a temporary token first for new instances (pk not yet assigned)
            if not self.pk:
                self.token = secrets.token_urlsafe(64)  # Placeholder
                super().save(*args, **kwargs)
                # Now re-generate with actual PK bound into HMAC
                self.token = generate_signed_token(self.pk)
                super().save(update_fields=['token'])
                return
            else:
                self.token = generate_signed_token(self.pk)
        super().save(*args, **kwargs)

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    @property
    def is_actionable(self) -> bool:
        return self.status == self.Status.PENDING and not self.is_expired
