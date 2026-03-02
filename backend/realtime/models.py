"""
realtime/models.py
Models for push notification device registration.
"""

from django.conf import settings
from django.db import models


class PushSubscription(models.Model):
    """
    Stores FCM device tokens for web push notifications.
    Each user can have multiple active subscriptions (multiple browsers/devices).
    """

    class Platform(models.TextChoices):
        WEB = 'web', 'Web Browser'
        ANDROID = 'android', 'Android'
        IOS = 'ios', 'iOS'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='push_subscriptions',
    )
    token = models.TextField(
        unique=True,
        help_text='FCM registration token / device token.',
    )
    platform = models.CharField(
        max_length=10,
        choices=Platform.choices,
        default=Platform.WEB,
    )
    user_agent = models.TextField(
        blank=True,
        help_text='Browser/device user-agent string for debugging.',
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text='Deactivated when FCM reports the token as unregistered.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-last_used_at']
        indexes = [
            models.Index(fields=['user', 'is_active'], name='idx_push_user_active'),
        ]

    def __str__(self):
        return f'PushSub({self.user.email}, {self.platform}, active={self.is_active})'
