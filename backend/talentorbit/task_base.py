"""
talentorbit/task_base.py
Production-grade base task class with dead-letter queue routing.

When a task exhausts all retries, the on_failure callback re-publishes the
failed payload to the 'dlq' queue with full context (original args, kwargs,
exception info, timestamp) so that an operator can:
    1. Inspect failures in the Django admin (via django-celery-results).
    2. Replay the task after fixing the root cause.
    3. Discard poison messages that can never succeed.
"""

import json
import logging
from datetime import datetime, timezone

from celery import Task

logger = logging.getLogger(__name__)


class BaseTaskWithDLQ(Task):
    """
    Custom Celery Task subclass that routes permanently-failed tasks to a
    dead-letter queue instead of silently dropping them.

    Usage:
        @shared_task(base=BaseTaskWithDLQ, ...)
        def my_task(...): ...

    Or set as the global default via CELERY_TASK_BASE in settings (we do
    this in celery.py after the app is created).
    """

    abstract = True  # Celery won't register this as a runnable task

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called when the task fails permanently (all retries exhausted)."""
        payload = {
            'original_task': self.name,
            'task_id': task_id,
            'args': args,
            'kwargs': kwargs,
            'exception': str(exc),
            'exception_type': type(exc).__qualname__,
            'traceback': str(einfo) if einfo else None,
            'failed_at': datetime.now(timezone.utc).isoformat(),
        }

        logger.error(
            'Task permanently failed — routing to DLQ: task=%s id=%s exc=%r',
            self.name, task_id, exc,
        )

        try:
            # Publish to the DLQ for manual inspection / replay
            self.app.send_task(
                'talentorbit.dlq_handler.handle_dead_letter',
                args=[payload],
                queue='dlq',
                # No retries for the DLQ handler itself — it must not loop
                retry=False,
            )
        except Exception:
            # Last resort: if even the DLQ publish fails, log the full payload
            # so it can be recovered from structured logs.
            logger.critical(
                'CRITICAL: Failed to publish to DLQ. Payload: %s',
                json.dumps(payload, default=str),
            )

        super().on_failure(exc, task_id, args, kwargs, einfo)
