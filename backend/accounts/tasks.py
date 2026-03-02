"""
accounts/tasks.py
Async email tasks for the accounts app.

All email sending is offloaded to Celery so that API responses remain fast
(<100 ms) even when the SMTP relay is slow or temporarily unreachable.

Retry policy:
    - Max 5 attempts with exponential backoff (10s → 20s → 40s → 80s → 160s)
    - On final failure the task is routed to the dead-letter queue for manual triage.
"""

import logging

from celery import shared_task
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

logger = logging.getLogger(__name__)

# ─── Base retry parameters (DRY across all email tasks) ──────────────────────
_EMAIL_RETRY_KWARGS = {
    'bind': True,
    'autoretry_for': (Exception,),
    'retry_backoff': 10,          # Initial backoff: 10 seconds
    'retry_backoff_max': 300,     # Cap at 5 minutes
    'retry_jitter': True,         # Randomise to avoid thundering herd
    'max_retries': 5,
    'acks_late': True,            # Re-deliver if worker dies mid-execution
    'reject_on_worker_lost': True,
    'queue': 'emails',
}


@shared_task(**_EMAIL_RETRY_KWARGS, name='accounts.send_verification_email')
def send_verification_email_task(self, user_id: int) -> dict:
    """
    Send email-verification link to a newly registered user.

    Args:
        user_id: Primary key of the User record.

    Returns:
        dict with 'status' and 'email' on success.
    """
    from accounts.models import User

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning('send_verification_email: user %s not found — skipping.', user_id)
        return {'status': 'skipped', 'reason': 'user_not_found'}

    if user.is_verified:
        return {'status': 'skipped', 'reason': 'already_verified'}

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    verify_url = f"{settings.FRONTEND_URL}/verify-email?uid={uid}&token={token}"

    send_mail(
        subject='TalentOrbit — Verify Your Email',
        message=(
            f'Hi {user.full_name or "there"},\n\n'
            f'Welcome to TalentOrbit! Please verify your email address '
            f'by clicking the link below:\n\n'
            f'{verify_url}\n\n'
            f'This link will expire in approximately 15 minutes.\n\n'
            f'If you didn\'t create this account, you can safely ignore this email.\n\n'
            f'— TalentOrbit'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )

    logger.info('Verification email queued for user %s (%s).', user_id, user.email)
    return {'status': 'sent', 'email': user.email}


@shared_task(**_EMAIL_RETRY_KWARGS, name='accounts.send_password_reset_email')
def send_password_reset_email_task(self, user_id: int) -> dict:
    """
    Send password-reset link to a user.

    Args:
        user_id: Primary key of the User record.

    Returns:
        dict with 'status' and 'email' on success.
    """
    from accounts.models import User

    try:
        user = User.objects.get(pk=user_id, is_active=True)
    except User.DoesNotExist:
        logger.warning('send_password_reset_email: user %s not found — skipping.', user_id)
        return {'status': 'skipped', 'reason': 'user_not_found'}

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    reset_url = f"{settings.FRONTEND_URL}/recovery?uid={uid}&token={token}"

    send_mail(
        subject='TalentOrbit — Password Reset',
        message=(
            f'Hi {user.full_name or "there"},\n\n'
            f'We received a request to reset your password.\n'
            f'Click the link below (valid for ~15 minutes):\n\n'
            f'{reset_url}\n\n'
            f'If you didn\'t request this, you can safely ignore this email.\n\n'
            f'— TalentOrbit'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )

    logger.info('Password reset email queued for user %s (%s).', user_id, user.email)
    return {'status': 'sent', 'email': user.email}


@shared_task(**_EMAIL_RETRY_KWARGS, name='accounts.send_generic_email')
def send_generic_email_task(self, subject: str, message: str,
                            recipient_list: list[str],
                            from_email: str | None = None) -> dict:
    """
    General-purpose async email sender.

    Use this for transactional emails that don't warrant their own task
    (e.g. contact-form auto-replies, admin alerts).

    Args:
        subject: Email subject line.
        message: Plain-text body.
        recipient_list: List of email addresses.
        from_email: Sender address (defaults to DEFAULT_FROM_EMAIL).

    Returns:
        dict with 'status' and 'recipients'.
    """
    if not recipient_list:
        return {'status': 'skipped', 'reason': 'no_recipients'}

    send_mail(
        subject=subject,
        message=message,
        from_email=from_email or settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipient_list,
        fail_silently=False,
    )

    logger.info('Generic email sent: subject=%r recipients=%s', subject, recipient_list)
    return {'status': 'sent', 'recipients': recipient_list}
