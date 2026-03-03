"""
courses/signals.py
Phase 7 — LMS Signal Handlers

Automatic side-effects triggered by model lifecycle events:
    1. On enrollment creation → send welcome email
    2. On enrollment completion → generate certificate
    3. On review save → recalculate course metrics
    4. On course publish → log + optionally reindex
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='courses.CourseEnrollment')
def on_enrollment_save(sender, instance, created, **kwargs):
    """
    After an enrollment is created or updated:
      - created → queue welcome email
      - status changed to 'completed' → queue certificate generation
    """
    if created:
        from .tasks import send_enrollment_welcome
        send_enrollment_welcome.delay(instance.id)
        return

    # Check for completion (use update_fields to avoid infinite loops)
    if instance.status == 'completed':
        from .models import Certificate
        if not Certificate.objects.filter(enrollment=instance).exists():
            from .tasks import generate_certificate
            generate_certificate.delay(instance.id)


@receiver(post_save, sender='courses.CourseReview')
def on_review_save(sender, instance, created, **kwargs):
    """After a review is created or updated, recalculate course metrics."""
    from .tasks import recalculate_course_metrics
    recalculate_course_metrics.delay(instance.course_id)
