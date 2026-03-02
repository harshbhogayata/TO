"""
talentorbit/dlq_handler.py
Dead-letter queue consumer.

Receives payloads from permanently-failed tasks, persists them to the
database for operator review, and emits structured log entries that
feed into Sentry / log aggregation dashboards.

Operators can:
    - View failed tasks in Django Admin → Celery Results → Task Results
    - Replay them via ``python manage.py replay_dead_letters``
    - Purge acknowledged entries after root-cause is resolved
"""

import json
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name='talentorbit.dlq_handler.handle_dead_letter',
    queue='dlq',
    max_retries=0,          # Never retry the DLQ handler itself
    acks_late=False,         # Ack immediately — we don't want DLQ messages re-delivered
    reject_on_worker_lost=False,
)
def handle_dead_letter(self, payload: dict) -> dict:
    """
    Persist a dead-letter record and emit an alert-level log.

    The payload is also stored as the Celery task result (via
    django-celery-results) so it shows up in the admin panel.

    Args:
        payload: Dict containing original_task, task_id, args, kwargs,
                 exception, traceback, failed_at.

    Returns:
        dict echoing the payload with an added 'dlq_status'.
    """
    task_name = payload.get('original_task', 'unknown')
    task_id = payload.get('task_id', 'unknown')
    exception = payload.get('exception', '')
    failed_at = payload.get('failed_at', '')

    logger.error(
        'DLQ received permanently-failed task: '
        'original_task=%s original_id=%s exception=%s failed_at=%s',
        task_name, task_id, exception, failed_at,
    )

    # Optionally: persist to a dedicated DeadLetter model for richer querying.
    # For now the django-celery-results TaskResult table captures this via the
    # task return value + the CELERY_RESULT_EXTENDED setting.

    # Emit Sentry alert (if Sentry is configured, structured logging → Sentry)
    try:
        import sentry_sdk
        sentry_sdk.capture_message(
            f'Dead-letter task: {task_name} (id={task_id})',
            level='error',
            extras=payload,
        )
    except ImportError:
        pass

    return {
        'dlq_status': 'received',
        **payload,
    }
