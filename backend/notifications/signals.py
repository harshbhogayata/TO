"""
notifications/signals.py
Auto-create notifications from real platform events:
  - Application submitted (notify company)
  - Application status changed (notify talent)
  - New message received (notify recipient)
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from jobs.models import Application
from messaging.models import Message
from notifications.models import Notification


# ─── Application submitted → notify company ────────────────────────────────
@receiver(post_save, sender=Application)
def notify_on_new_application(sender, instance, created, **kwargs):
    """When a talent applies, notify the company that owns the job."""
    if not created:
        return
    Notification.objects.create(
        user=instance.job.company,
        category='Application',
        title=f'New application for "{instance.job.title}"',
        description=f'{instance.applicant.full_name or instance.applicant.email} applied to your posting.',
    )


# ─── Application status changed → notify talent ────────────────────────────
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
    """When a company changes application status, notify the applicant."""
    if created:
        return
    old = getattr(instance, '_old_status', None)
    if old and old != instance.status:
        status_display = instance.get_status_display()
        Notification.objects.create(
            user=instance.applicant,
            category='Application',
            title=f'Application update: {status_display}',
            description=f'Your application for "{instance.job.title}" is now {status_display}.',
        )


# ─── New message → notify recipient(s) ─────────────────────────────────────
@receiver(post_save, sender=Message)
def notify_on_new_message(sender, instance, created, **kwargs):
    """When a message is sent, notify the other thread participants."""
    if not created:
        return
    recipients = instance.thread.participants.exclude(pk=instance.sender_id)
    sender_name = instance.sender.full_name or instance.sender.email
    for user in recipients:
        Notification.objects.create(
            user=user,
            category='Message',
            title=f'New message from {sender_name}',
            description=instance.body[:120] if instance.body else '',
        )
