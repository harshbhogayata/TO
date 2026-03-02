"""
notifications/tasks.py
Async notification creation tasks.

Moves notification writes out of the request/response cycle and Django signal
handlers so the caller (views, signals) returns immediately.

Retry policy:
    - Max 3 attempts with exponential backoff (5s → 10s → 20s)
    - Database writes rarely fail transiently, so fewer retries than email.
"""

import logging
from typing import Optional

from celery import shared_task
from django.db import OperationalError, InterfaceError

logger = logging.getLogger(__name__)

# ─── Base retry parameters ───────────────────────────────────────────────────
_NOTIF_RETRY_KWARGS = {
    'bind': True,
    'autoretry_for': (OperationalError, InterfaceError),
    'retry_backoff': 5,
    'retry_backoff_max': 60,
    'retry_jitter': True,
    'max_retries': 3,
    'acks_late': True,
    'reject_on_worker_lost': True,
    'queue': 'notifications',
}


@shared_task(**_NOTIF_RETRY_KWARGS, name='notifications.create_notification')
def create_notification_task(
    self,
    user_id: int,
    category: str,
    title: str,
    description: str = '',
) -> dict:
    """
    Create a single notification for a user.

    Args:
        user_id: Primary key of the recipient User.
        category: Notification category (e.g. 'Application', 'Message', 'System').
        title: Short notification title.
        description: Optional longer description text.

    Returns:
        dict with 'status' and 'notification_id'.
    """
    from notifications.models import Notification
    from accounts.models import User

    if not User.objects.filter(pk=user_id, is_active=True).exists():
        logger.warning(
            'create_notification: user %s not found or inactive — skipping.', user_id
        )
        return {'status': 'skipped', 'reason': 'user_not_found'}

    notif = Notification.objects.create(
        user_id=user_id,
        category=category,
        title=title,
        description=description,
    )

    logger.info(
        'Notification created: id=%s user=%s category=%s title=%r',
        notif.pk, user_id, category, title,
    )

    # ── Broadcast to WebSocket in real time ──────────────────────────────
    from realtime.broadcast import broadcast_notification, broadcast_unread_count

    notification_data = {
        'id': notif.pk,
        'category': notif.category,
        'title': notif.title,
        'description': notif.description,
        'created_at': notif.created_at.isoformat(),
        'is_read': False,
    }
    broadcast_notification(user_id, notification_data)

    unread = Notification.objects.filter(user_id=user_id, is_read=False).count()
    broadcast_unread_count(user_id, unread)

    # ── Send FCM push notification ───────────────────────────────────────
    from realtime.push import send_push_notification
    try:
        send_push_notification(
            user_id=user_id,
            title=title,
            body=description or title,
        )
    except Exception:
        logger.exception('Push notification failed for user %s', user_id)

    return {'status': 'created', 'notification_id': notif.pk}


@shared_task(**_NOTIF_RETRY_KWARGS, name='notifications.create_bulk_notifications')
def create_bulk_notifications_task(
    self,
    user_ids: list[int],
    category: str,
    title: str,
    description: str = '',
) -> dict:
    """
    Create the same notification for multiple users (e.g. new message to
    all thread participants).

    Uses bulk_create for efficiency.

    Args:
        user_ids: List of recipient User primary keys.
        category: Notification category.
        title: Short notification title.
        description: Optional longer description text.

    Returns:
        dict with 'status' and 'created_count'.
    """
    from notifications.models import Notification
    from accounts.models import User

    # Filter to only active users
    valid_ids = set(
        User.objects.filter(pk__in=user_ids, is_active=True)
        .values_list('pk', flat=True)
    )

    if not valid_ids:
        return {'status': 'skipped', 'reason': 'no_valid_recipients'}

    notifications = [
        Notification(
            user_id=uid,
            category=category,
            title=title,
            description=description,
        )
        for uid in valid_ids
    ]

    created = Notification.objects.bulk_create(notifications)

    logger.info(
        'Bulk notifications created: count=%d category=%s title=%r',
        len(created), category, title,
    )
    return {'status': 'created', 'created_count': len(created)}


@shared_task(
    bind=True,
    max_retries=3,
    retry_backoff=5,
    acks_late=True,
    reject_on_worker_lost=True,
    queue='notifications',
    name='notifications.send_application_notification',
)
def send_application_notification_task(
    self,
    application_id: int,
    event_type: str,
    old_status: Optional[str] = None,
) -> dict:
    """
    Handle all application-related notifications asynchronously.

    This replaces the synchronous Django signal handlers with a single
    task that is dispatched from the signal.

    Args:
        application_id: Primary key of the Application.
        event_type: Either 'created' or 'status_changed'.
        old_status: The previous status (only for 'status_changed').

    Returns:
        dict with 'status' and details.
    """
    from jobs.models import Application

    try:
        application = Application.objects.select_related(
            'job', 'job__company', 'applicant'
        ).get(pk=application_id)
    except Application.DoesNotExist:
        logger.warning(
            'send_application_notification: application %s not found.', application_id
        )
        return {'status': 'skipped', 'reason': 'application_not_found'}

    if event_type == 'created':
        # Notify the company that owns the job
        create_notification_task.delay(
            user_id=application.job.company_id,
            category='Application',
            title=f'New application for "{application.job.title}"',
            description=(
                f'{application.applicant.full_name or application.applicant.email} '
                f'applied to your posting.'
            ),
        )
        return {'status': 'dispatched', 'type': 'new_application'}

    elif event_type == 'status_changed':
        if old_status and old_status != application.status:
            status_display = application.get_status_display()
            create_notification_task.delay(
                user_id=application.applicant_id,
                category='Application',
                title=f'Application update: {status_display}',
                description=(
                    f'Your application for "{application.job.title}" '
                    f'is now {status_display}.'
                ),
            )
            return {'status': 'dispatched', 'type': 'status_changed'}
        return {'status': 'skipped', 'reason': 'no_status_change'}

    return {'status': 'skipped', 'reason': f'unknown_event_type:{event_type}'}


@shared_task(
    bind=True,
    max_retries=3,
    retry_backoff=5,
    acks_late=True,
    reject_on_worker_lost=True,
    queue='notifications',
    name='notifications.send_message_notification',
)
def send_message_notification_task(self, message_id: int) -> dict:
    """
    Notify thread participants about a new message, asynchronously.

    Args:
        message_id: Primary key of the Message.

    Returns:
        dict with 'status' and details.
    """
    from messaging.models import Message

    try:
        message = Message.objects.select_related('sender', 'thread').get(pk=message_id)
    except Message.DoesNotExist:
        logger.warning(
            'send_message_notification: message %s not found.', message_id
        )
        return {'status': 'skipped', 'reason': 'message_not_found'}

    recipient_ids = list(
        message.thread.participants
        .exclude(pk=message.sender_id)
        .values_list('pk', flat=True)
    )

    if not recipient_ids:
        return {'status': 'skipped', 'reason': 'no_recipients'}

    sender_name = message.sender.full_name or message.sender.email
    body_preview = (message.body[:120] if message.body else '')

    create_bulk_notifications_task.delay(
        user_ids=recipient_ids,
        category='Message',
        title=f'New message from {sender_name}',
        description=body_preview,
    )

    return {'status': 'dispatched', 'recipient_count': len(recipient_ids)}


@shared_task(
    name='notifications.tasks.cleanup_old_notifications_task',
    bind=True,
    max_retries=0,
)
def cleanup_old_notifications_task(self):
    """
    Daily housekeeping: delete read notifications older than 90 days.
    Keeps the notifications table lean and queries fast.
    Scheduled via Celery Beat in settings.CELERY_BEAT_SCHEDULE.
    """
    from django.utils import timezone
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(days=90)
    qs = Notification.objects.filter(is_read=True, created_at__lt=cutoff)
    count, _ = qs.delete()
    logger.info('Cleanup: removed %d read notifications older than 90 days.', count)
    return {'deleted': count}
