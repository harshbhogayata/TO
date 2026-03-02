"""
notifications/signals.py
Auto-create notifications from real platform events via async Celery tasks.

  - Application submitted → notify company (async)
  - Application status changed → notify talent (async)
  - New message received → notify recipient(s) (async)

All notification creation is now offloaded to Celery tasks so that the
database write happens outside the request/response cycle. The signal
handlers dispatch tasks and return immediately.
"""
import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from jobs.models import Application
from messaging.models import Message

logger = logging.getLogger(__name__)


# ─── Application submitted → notify company (async) ─────────────────────────
@receiver(post_save, sender=Application)
def notify_on_new_application(sender, instance, created, **kwargs):
    """When a talent applies, dispatch async notification to the company."""
    if not created:
        return

    from notifications.tasks import send_application_notification_task

    try:
        send_application_notification_task.delay(
            application_id=instance.pk,
            event_type='created',
        )
    except Exception:
        logger.exception(
            'Failed to dispatch new-application notification for application %s',
            instance.pk,
        )


# ─── Application status changed → notify talent (async) ─────────────────────
@receiver(pre_save, sender=Application)
def cache_old_application_status(sender, instance, **kwargs):
    """Store old status before save so post_save can detect changes."""
    if instance.pk:
        try:
            instance._old_status = Application.objects.get(pk=instance.pk).status
        except Application.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None


@receiver(post_save, sender=Application)
def notify_on_application_status_change(sender, instance, created, **kwargs):
    """When a company changes application status, dispatch async notification."""
    if created:
        return

    old = getattr(instance, '_old_status', None)
    if old and old != instance.status:
        from notifications.tasks import send_application_notification_task

        try:
            send_application_notification_task.delay(
                application_id=instance.pk,
                event_type='status_changed',
                old_status=old,
            )
        except Exception:
            logger.exception(
                'Failed to dispatch status-change notification for application %s',
                instance.pk,
            )


# ─── New message → notify recipient(s) (async) ──────────────────────────────
@receiver(post_save, sender=Message)
def notify_on_new_message(sender, instance, created, **kwargs):
    """When a message is sent, dispatch async notification to participants."""
    if not created:
        return

    from notifications.tasks import send_message_notification_task

    try:
        send_message_notification_task.delay(message_id=instance.pk)
    except Exception:
        logger.exception(
            'Failed to dispatch message notification for message %s',
            instance.pk,
        )
