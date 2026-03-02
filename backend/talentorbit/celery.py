"""
talentorbit/celery.py
Celery application factory for TalentOrbit.

Initialises the Celery app with Django settings, auto-discovers tasks in every
installed app, and configures production-grade defaults (serialiser, result
backend, broker connection parameters, retry policies, and dead-letter routing).

Usage:
    # Worker (production)
    celery -A talentorbit worker -l info -Q default,emails,notifications,dlq

    # Beat scheduler (periodic tasks — cron-like)
    celery -A talentorbit beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
"""

import os
import logging

from celery import Celery
from celery.signals import task_failure, task_retry, task_revoked

logger = logging.getLogger(__name__)

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'talentorbit.settings')

app = Celery('talentorbit')

# Pull all CELERY_* keys from Django settings (namespace='CELERY')
app.config_from_object('django.conf:settings', namespace='CELERY')

# Set BaseTaskWithDLQ as the default base for all tasks
# (tasks can still override with base=OtherBase)
from talentorbit.task_base import BaseTaskWithDLQ  # noqa: E402
app.Task = BaseTaskWithDLQ

# Auto-discover tasks.py in every INSTALLED_APPS app
app.autodiscover_tasks()


# ─── Signal Handlers (observability) ─────────────────────────────────────────

@task_failure.connect
def _on_task_failure(sender=None, task_id=None, exception=None,
                     args=None, kwargs=None, traceback=None, **kw):
    """Log every final task failure to structured logging + Sentry."""
    logger.error(
        'Celery task FAILED: task=%s id=%s args=%s kwargs=%s exc=%r',
        sender.name if sender else '?', task_id, args, kwargs, exception,
        exc_info=True,
    )


@task_retry.connect
def _on_task_retry(sender=None, request=None, reason=None, **kw):
    """Log retries so we can monitor flapping tasks."""
    logger.warning(
        'Celery task RETRY: task=%s id=%s reason=%s',
        sender.name if sender else '?',
        request.id if request else '?',
        reason,
    )


@task_revoked.connect
def _on_task_revoked(sender=None, request=None, terminated=None,
                     signum=None, expired=None, **kw):
    """Log revoked/expired tasks."""
    logger.warning(
        'Celery task REVOKED: task=%s id=%s terminated=%s expired=%s',
        sender.name if sender else '?',
        request.id if request else '?',
        terminated, expired,
    )
