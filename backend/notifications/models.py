from django.db import models
from django.conf import settings

class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    category = models.CharField(max_length=50, default='System')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read'], name='idx_notif_user_read'),
            models.Index(fields=['user', '-created_at'], name='idx_notif_user_created'),
        ]

    def __str__(self):
        return f"[{self.category}] {self.title} to {self.user.email}"
