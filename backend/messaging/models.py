"""
messaging/models.py
Encrypted secure messaging between Talent and Company users.
"""
from django.db import models
from django.conf import settings


class Thread(models.Model):
    """
    A conversation thread between a Talent user and a Company user.
    Optionally linked to a job post for context.
    """
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='threads'
    )
    job = models.ForeignKey(
        'jobs.JobPost',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='threads',
        help_text='Optional: thread linked to a specific job application.'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        names = ', '.join(p.full_name or p.email for p in self.participants.all())
        return f'Thread [{self.id}] — {names}'

    @property
    def last_message(self):
        return self.messages.select_related('sender').last()

    @property
    def unread_count(self):
        """Convenience property — actual filtering done in views per-user."""
        return self.messages.filter(read=False).count()


class Message(models.Model):
    """
    A single message within a Thread.
    Tracks read status at the per-message level.
    """
    thread = models.ForeignKey(
        Thread, on_delete=models.CASCADE, related_name='messages'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages'
    )
    body = models.TextField(max_length=10000)
    attachment = models.FileField(
        upload_to='message_attachments/',
        null=True, blank=True
    )
    read = models.BooleanField(default=False)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sent_at']
        indexes = [
            models.Index(fields=['thread', 'read'], name='idx_msg_thread_read'),
            models.Index(fields=['thread', 'sent_at'], name='idx_msg_thread_sent'),
        ]

    def __str__(self):
        return f'[{self.thread_id}] {self.sender.full_name}: {self.body[:40]}'
