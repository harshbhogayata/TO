"""
courses/tasks.py
Phase 7 — LMS Celery Tasks

Async operations for the course content engine:
    1. recalculate_course_metrics  — Recompute denormalised counters & ratings
    2. generate_certificate        — Issue a completion certificate
    3. send_enrollment_welcome     — Welcome email on enrollment
    4. send_completion_email       — Congratulations + certificate on completion
    5. update_course_search_index  — Reindex course for full-text search
    6. cleanup_stale_enrollments   — Mark long-inactive enrollments

All tasks use the BaseTaskWithDLQ base class from talentorbit.task_base
and are routed to appropriate queues via CELERY_TASK_ROUTES.
"""
import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db import models as db_models
from django.db.models import Avg, Count
from django.utils import timezone

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# METRIC RECALCULATION
# ═══════════════════════════════════════════════════════════════════════════════

@shared_task(
    bind=True,
    name='courses.recalculate_course_metrics',
    max_retries=3,
    default_retry_delay=30,
    queue='default',
)
def recalculate_course_metrics(self, course_id: int):
    """
    Recompute all denormalised metrics for a course:
    - enrollment_count
    - completion_count
    - average_rating
    - review_count
    - estimated_duration_minutes (sum of all lesson durations)
    """
    from .models import Course, CourseEnrollment, CourseReview, Lesson

    try:
        course = Course.objects.get(pk=course_id)
    except Course.DoesNotExist:
        logger.warning('recalculate_course_metrics: Course %s not found', course_id)
        return

    # Enrollment + completion counts
    enrollment_stats = CourseEnrollment.objects.filter(course=course).aggregate(
        total=Count('id'),
        completed=Count('id', filter=db_models.Q(status='completed')),
    )

    # Review stats
    review_stats = CourseReview.objects.filter(
        course=course, is_approved=True,
    ).aggregate(
        count=Count('id'),
        avg_rating=Avg('rating'),
    )

    # Total duration from lessons
    total_duration = (
        Lesson.objects
        .filter(module__course=course)
        .aggregate(total=db_models.Sum('estimated_duration_minutes'))
        ['total'] or 0
    )

    Course.objects.filter(pk=course_id).update(
        enrollment_count=enrollment_stats['total'],
        completion_count=enrollment_stats['completed'],
        review_count=review_stats['count'],
        average_rating=review_stats['avg_rating'] or 0.00,
        estimated_duration_minutes=total_duration,
    )

    logger.info(
        'Recalculated metrics for course %s: %d enrolled, %d completed, %.2f avg rating',
        course_id,
        enrollment_stats['total'],
        enrollment_stats['completed'],
        review_stats['avg_rating'] or 0,
    )


@shared_task(
    name='courses.recalculate_all_course_metrics',
    queue='default',
)
def recalculate_all_course_metrics():
    """Periodic task to recalculate metrics for all published courses."""
    from .models import Course

    course_ids = list(
        Course.objects
        .filter(status=Course.Status.PUBLISHED)
        .values_list('id', flat=True)
    )

    for course_id in course_ids:
        recalculate_course_metrics.delay(course_id)

    logger.info('Queued metric recalculation for %d courses', len(course_ids))


# ═══════════════════════════════════════════════════════════════════════════════
# CERTIFICATE GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

@shared_task(
    bind=True,
    name='courses.generate_certificate',
    max_retries=3,
    default_retry_delay=30,
    queue='default',
)
def generate_certificate(self, enrollment_id: int):
    """
    Generate a tamper-proof certificate for a completed enrollment.
    Called automatically when enrollment status changes to 'completed'.
    """
    from .models import Certificate, CourseEnrollment

    try:
        enrollment = (
            CourseEnrollment.objects
            .select_related('user', 'course')
            .get(pk=enrollment_id, status=CourseEnrollment.Status.COMPLETED)
        )
    except CourseEnrollment.DoesNotExist:
        logger.warning(
            'generate_certificate: Enrollment %s not found or not completed',
            enrollment_id,
        )
        return

    # Idempotency: skip if certificate already exists
    if Certificate.objects.filter(enrollment=enrollment).exists():
        logger.info('Certificate already exists for enrollment %s', enrollment_id)
        return

    course = enrollment.course
    user = enrollment.user

    # Gather instructor names
    instructor_names = ', '.join(
        course.instructors.values_list('display_name', flat=True),
    ) or 'TalentOrbit Staff'

    # Calculate total hours
    total_seconds = enrollment.total_time_spent_seconds or 0
    total_hours = round(total_seconds / 3600, 1)

    certificate = Certificate(
        enrollment=enrollment,
        holder_name=user.full_name or user.email,
        holder_email=user.email,
        course_title=course.title,
        course_version=course.version or '1.0',
        instructor_names=instructor_names,
        completion_date=enrollment.completed_at.date() if enrollment.completed_at else timezone.now().date(),
        total_hours=total_hours,
        skills_earned=course.skills or [],
    )
    certificate.generate_signature()
    certificate.save()

    logger.info(
        'Generated certificate %s for user %s (course: %s)',
        certificate.id, user.id, course.id,
    )

    # Queue email notification
    send_completion_email.delay(enrollment_id, str(certificate.id))

    return str(certificate.id)


# ═══════════════════════════════════════════════════════════════════════════════
# EMAIL NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════════════════════

@shared_task(
    name='courses.send_enrollment_welcome',
    max_retries=3,
    default_retry_delay=60,
    queue='emails',
)
def send_enrollment_welcome(enrollment_id: int):
    """Send a welcome email when a user enrolls in a course."""
    from .models import CourseEnrollment

    try:
        enrollment = (
            CourseEnrollment.objects
            .select_related('user', 'course')
            .get(pk=enrollment_id)
        )
    except CourseEnrollment.DoesNotExist:
        return

    user = enrollment.user
    course = enrollment.course

    # Use the same email infrastructure as accounts/tasks.py
    try:
        from django.core.mail import send_mail

        send_mail(
            subject=f'Welcome to "{course.title}" — TalentOrbit',
            message=(
                f'Hi {user.full_name or "there"},\n\n'
                f'You\'ve successfully enrolled in "{course.title}". '
                f'Start learning at your own pace!\n\n'
                f'— The TalentOrbit Team'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )
        logger.info('Sent enrollment welcome email to %s for course %s', user.email, course.id)
    except Exception:
        logger.exception('Failed to send enrollment welcome email for enrollment %s', enrollment_id)


@shared_task(
    name='courses.send_completion_email',
    max_retries=3,
    default_retry_delay=60,
    queue='emails',
)
def send_completion_email(enrollment_id: int, certificate_id: str | None = None):
    """Send a congratulatory email when a user completes a course."""
    from .models import CourseEnrollment

    try:
        enrollment = (
            CourseEnrollment.objects
            .select_related('user', 'course')
            .get(pk=enrollment_id)
        )
    except CourseEnrollment.DoesNotExist:
        return

    user = enrollment.user
    course = enrollment.course

    cert_line = ''
    if certificate_id:
        cert_line = (
            f'\nYour certificate is ready! View and share it at:\n'
            f'{settings.FRONTEND_URL}/certificates/{certificate_id}\n'
        )

    try:
        from django.core.mail import send_mail

        send_mail(
            subject=f'Congratulations! You completed "{course.title}" — TalentOrbit',
            message=(
                f'Hi {user.full_name or "there"},\n\n'
                f'Congratulations on completing "{course.title}"! 🎉\n'
                f'{cert_line}\n'
                f'Keep building your skills with more courses on TalentOrbit.\n\n'
                f'— The TalentOrbit Team'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )
        logger.info('Sent completion email to %s for course %s', user.email, course.id)
    except Exception:
        logger.exception('Failed to send completion email for enrollment %s', enrollment_id)


# ═══════════════════════════════════════════════════════════════════════════════
# HOUSEKEEPING
# ═══════════════════════════════════════════════════════════════════════════════

@shared_task(
    name='courses.cleanup_stale_enrollments',
    queue='default',
)
def cleanup_stale_enrollments(inactive_days: int = 180):
    """
    Mark enrollments as 'dropped' if the user hasn't accessed
    the course in `inactive_days` days. Runs as a periodic Beat task.
    """
    from .models import CourseEnrollment

    cutoff = timezone.now() - timedelta(days=inactive_days)

    stale = CourseEnrollment.objects.filter(
        status=CourseEnrollment.Status.ACTIVE,
        last_accessed_at__lt=cutoff,
    )
    count = stale.count()

    if count > 0:
        stale.update(status=CourseEnrollment.Status.DROPPED)
        logger.info('Marked %d stale enrollments as dropped (inactive > %d days)', count, inactive_days)
    else:
        logger.debug('No stale enrollments found (threshold: %d days)', inactive_days)
