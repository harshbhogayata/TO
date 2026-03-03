"""
compliance/signals.py
Phase 6 — Automatic audit logging via Django signals.

Listens to model lifecycle events and creates AuditLog entries
for security-critical and compliance-relevant actions.

Signal handlers are kept lightweight — they read context from
the AuditContextMiddleware thread-local and create a single
AuditLog record. No external calls, no heavy computation.
"""
import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver

from compliance.constants import AuditAction, AuditCategory
from compliance.middleware import get_audit_context

logger = logging.getLogger(__name__)

User = get_user_model()


# ═══════════════════════════════════════════════════════════════════════════════
# AUTHENTICATION SIGNALS
# ═══════════════════════════════════════════════════════════════════════════════

@receiver(user_logged_in)
def audit_user_login(sender, request, user, **kwargs):
    """Audit successful login and record the IP as known for anomaly detection."""
    ctx = get_audit_context()

    # Record IP as known for this user (anomaly detection)
    ip_address = ctx.get('ip_address')
    if ip_address and user:
        try:
            from compliance.anomaly import record_known_ip
            record_known_ip(user.pk, ip_address)
        except Exception:
            pass  # Never let anomaly tracking break login

    _create_log(
        actor=user,
        action=AuditAction.LOGIN,
        category=AuditCategory.AUTH,
        description=f'User logged in: {user.email}',
        resource_type='accounts.User',
        resource_id=str(user.pk),
        ctx=ctx,
    )


@receiver(user_logged_out)
def audit_user_logout(sender, request, user, **kwargs):
    """Audit logout."""
    if not user:
        return
    ctx = get_audit_context()
    _create_log(
        actor=user,
        action=AuditAction.LOGOUT,
        category=AuditCategory.AUTH,
        description=f'User logged out: {user.email}',
        resource_type='accounts.User',
        resource_id=str(user.pk),
        ctx=ctx,
    )


@receiver(user_login_failed)
def audit_login_failed(sender, credentials, request, **kwargs):
    """Audit failed login attempts (for brute-force detection)."""
    ctx = get_audit_context()
    email = credentials.get('email', credentials.get('username', ''))
    _create_log(
        actor=None,
        action=AuditAction.LOGIN_FAILED,
        category=AuditCategory.AUTH,
        description=f'Failed login attempt for: {email}',
        resource_type='accounts.User',
        resource_id='',
        ctx=ctx,
        extra_email=email,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# USER LIFECYCLE SIGNALS
# ═══════════════════════════════════════════════════════════════════════════════

@receiver(post_save, sender=User)
def audit_user_save(sender, instance, created, **kwargs):
    """Audit user creation and significant field changes."""
    ctx = get_audit_context()

    if created:
        _create_log(
            actor=instance,
            action=AuditAction.CREATE,
            category=AuditCategory.USER,
            description=f'New {instance.role} account created: {instance.email}',
            resource_type='accounts.User',
            resource_id=str(instance.pk),
            ctx=ctx,
        )
        return

    # Detect significant field changes from pre_save cache
    changes = getattr(instance, '_audit_changes', None)
    if changes:
        _create_log(
            actor=ctx.get('user') or instance,
            action=AuditAction.UPDATE,
            category=AuditCategory.USER,
            description=f'User account updated: {instance.email}',
            resource_type='accounts.User',
            resource_id=str(instance.pk),
            changes=changes,
            ctx=ctx,
        )
        # Clean up
        instance._audit_changes = None


@receiver(pre_save, sender=User)
def cache_user_changes(sender, instance, **kwargs):
    """Cache old field values before save for change detection."""
    if not instance.pk:
        return

    try:
        old = User.objects.get(pk=instance.pk)
    except User.DoesNotExist:
        return

    changes = {}
    tracked_fields = [
        'email', 'full_name', 'role', 'is_active',
        'is_verified', 'is_staff', 'is_2fa_enabled',
    ]
    for field in tracked_fields:
        old_val = getattr(old, field)
        new_val = getattr(instance, field)
        if old_val != new_val:
            changes[field] = {
                'old': str(old_val),
                'new': str(new_val),
            }

    if changes:
        instance._audit_changes = changes


# ═══════════════════════════════════════════════════════════════════════════════
# APPLICATION SIGNALS
# ═══════════════════════════════════════════════════════════════════════════════

def _setup_application_signals():
    """Lazy import to avoid circular imports."""
    from jobs.models import Application

    @receiver(post_save, sender=Application)
    def audit_application_save(sender, instance, created, **kwargs):
        ctx = get_audit_context()

        if created:
            _create_log(
                actor=instance.applicant,
                action=AuditAction.APPLICATION_SUBMIT,
                category=AuditCategory.APPLICATION,
                description=(
                    f'{instance.applicant.email} applied to '
                    f'"{instance.job.title}" (job #{instance.job.pk})'
                ),
                resource_type='jobs.Application',
                resource_id=str(instance.pk),
                ctx=ctx,
            )
            return

        old_status = getattr(instance, '_old_status', None)
        if old_status and old_status != instance.status:
            actor = ctx.get('user')
            _create_log(
                actor=actor,
                action=AuditAction.APPLICATION_STATUS_CHANGE,
                category=AuditCategory.APPLICATION,
                description=(
                    f'Application #{instance.pk} status changed: '
                    f'{old_status} → {instance.status}'
                ),
                resource_type='jobs.Application',
                resource_id=str(instance.pk),
                changes={'status': {'old': old_status, 'new': instance.status}},
                ctx=ctx,
            )


# ═══════════════════════════════════════════════════════════════════════════════
# JOB POST SIGNALS
# ═══════════════════════════════════════════════════════════════════════════════

def _setup_jobpost_signals():
    """Lazy import to avoid circular imports."""
    from jobs.models import JobPost

    @receiver(post_save, sender=JobPost)
    def audit_jobpost_save(sender, instance, created, **kwargs):
        ctx = get_audit_context()

        if created:
            _create_log(
                actor=instance.company,
                action=AuditAction.CREATE,
                category=AuditCategory.JOB,
                description=f'Job post created: "{instance.title}"',
                resource_type='jobs.JobPost',
                resource_id=str(instance.pk),
                ctx=ctx,
            )
        else:
            changes = getattr(instance, '_audit_changes', None)
            if changes:
                _create_log(
                    actor=ctx.get('user') or instance.company,
                    action=AuditAction.UPDATE,
                    category=AuditCategory.JOB,
                    description=f'Job post updated: "{instance.title}"',
                    resource_type='jobs.JobPost',
                    resource_id=str(instance.pk),
                    changes=changes,
                    ctx=ctx,
                )
                instance._audit_changes = None

    @receiver(pre_save, sender=JobPost)
    def cache_jobpost_changes(sender, instance, **kwargs):
        if not instance.pk:
            return
        try:
            old = JobPost.objects.get(pk=instance.pk)
        except JobPost.DoesNotExist:
            return

        changes = {}
        tracked_fields = ['title', 'status', 'job_type', 'work_mode', 'location']
        for field in tracked_fields:
            old_val = getattr(old, field)
            new_val = getattr(instance, field)
            if old_val != new_val:
                changes[field] = {'old': str(old_val), 'new': str(new_val)}
        if changes:
            instance._audit_changes = changes

    @receiver(post_delete, sender=JobPost)
    def audit_jobpost_delete(sender, instance, **kwargs):
        ctx = get_audit_context()
        _create_log(
            actor=ctx.get('user'),
            action=AuditAction.DELETE,
            category=AuditCategory.JOB,
            description=f'Job post deleted: "{instance.title}" (was #{instance.pk})',
            resource_type='jobs.JobPost',
            resource_id=str(instance.pk),
            ctx=ctx,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TEAM SIGNALS
# ═══════════════════════════════════════════════════════════════════════════════

def _setup_team_signals():
    """Lazy import to avoid circular imports."""
    from compliance.models import Team, TeamMember, TeamInvitation

    @receiver(post_save, sender=Team)
    def audit_team_created(sender, instance, created, **kwargs):
        if not created:
            return
        ctx = get_audit_context()
        _create_log(
            actor=ctx.get('user'),
            action=AuditAction.TEAM_CREATE,
            category=AuditCategory.TEAM,
            description=f'Team created: "{instance.name}"',
            resource_type='compliance.Team',
            resource_id=str(instance.pk),
            ctx=ctx,
        )

    @receiver(post_save, sender=TeamMember)
    def audit_team_member_change(sender, instance, created, **kwargs):
        # NOTE: Do NOT log created=True here — the accept_team_invitation view
        # and _create_team view already handle creation audit with richer context
        # (invitation reference, actor info). Logging here would create duplicates.
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _create_log(
    *,
    actor,
    action,
    category,
    description,
    resource_type='',
    resource_id='',
    changes=None,
    ctx=None,
    extra_email='',
):
    """
    Create an AuditLog entry. Defensive — never raises.
    """
    try:
        from compliance.models import AuditLog

        if ctx is None:
            ctx = get_audit_context()

        log = AuditLog(
            actor=actor if actor and hasattr(actor, 'pk') else None,
            action=action,
            category=category,
            description=description,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else '',
            changes=changes or {},
            ip_address=ctx.get('ip_address') or None,
            user_agent=(ctx.get('user_agent') or '')[:1000],
            request_id=ctx.get('request_id') or None,
        )

        # Override email for failed logins where actor is None
        if extra_email and not log.actor_email:
            log.actor_email = extra_email

        log.save()

    except Exception:
        # Audit logging must NEVER crash the application
        logger.exception(
            'Failed to create audit log: action=%s resource=%s:%s',
            action, resource_type, resource_id,
        )


# ─── Register lazy signal handlers ───────────────────────────────────────────
# Called at module import time (from apps.py ready())
_setup_application_signals()
_setup_jobpost_signals()
_setup_team_signals()
