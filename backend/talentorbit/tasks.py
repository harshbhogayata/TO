"""
talentorbit/tasks.py
Global periodic tasks for platform health monitoring.
Registered by Celery Beat in settings.CELERY_BEAT_SCHEDULE.
"""
import logging

from celery import shared_task
from django.core.cache import cache

logger = logging.getLogger(__name__)


@shared_task(name='talentorbit.tasks.celery_health_heartbeat', bind=True, max_retries=0)
def celery_health_heartbeat(self):
    """
    Lightweight heartbeat task executed every 5 minutes via Celery Beat.
    Writes a timestamp to the cache so external monitors (e.g. the
    celery_health management command) can verify worker liveness.
    """
    from django.utils import timezone

    now = timezone.now().isoformat()
    cache.set('celery_heartbeat', now, timeout=600)  # 10 min TTL
    logger.debug('Celery heartbeat: %s', now)
    return now
