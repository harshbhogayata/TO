"""
replay_dead_letters management command.
Lists and optionally replays tasks from the dead-letter queue (stored in
django-celery-results).

Usage:
    python manage.py replay_dead_letters --list
    python manage.py replay_dead_letters --replay --task-name accounts.send_verification_email
    python manage.py replay_dead_letters --purge --older-than 30
"""

import json
import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'List, replay, or purge dead-letter tasks from the Celery result backend.'

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--list', action='store_true', help='List all DLQ entries.')
        group.add_argument('--replay', action='store_true', help='Replay matching DLQ entries.')
        group.add_argument('--purge', action='store_true', help='Delete old DLQ entries.')

        parser.add_argument(
            '--task-name', type=str, default='',
            help='Filter by original task name (for --replay / --list).',
        )
        parser.add_argument(
            '--older-than', type=int, default=0,
            help='Purge DLQ entries older than N days (for --purge).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Show what would happen without actually executing.',
        )

    def handle(self, *args, **options):
        from django_celery_results.models import TaskResult

        dlq_results = TaskResult.objects.filter(
            task_name='talentorbit.dlq_handler.handle_dead_letter',
        ).order_by('-date_done')

        if options['task_name']:
            # Filter by original_task inside the JSON result
            dlq_results = [
                r for r in dlq_results
                if self._get_original_task(r) == options['task_name']
            ]

        if options['list']:
            self._list_entries(dlq_results)
        elif options['replay']:
            self._replay_entries(dlq_results, dry_run=options['dry_run'])
        elif options['purge']:
            self._purge_entries(dlq_results, options['older_than'], dry_run=options['dry_run'])

    def _get_original_task(self, result):
        try:
            data = json.loads(result.result) if isinstance(result.result, str) else result.result
            return data.get('original_task', 'unknown')
        except (json.JSONDecodeError, TypeError, AttributeError):
            return 'unknown'

    def _get_payload(self, result):
        try:
            return json.loads(result.result) if isinstance(result.result, str) else result.result
        except (json.JSONDecodeError, TypeError, AttributeError):
            return {}

    def _list_entries(self, results):
        if not results:
            self.stdout.write(self.style.SUCCESS('No dead-letter entries found.'))
            return

        self.stdout.write(f'\nFound {len(list(results))} dead-letter entries:\n')
        for r in results:
            payload = self._get_payload(r)
            self.stdout.write(
                f'  [{r.date_done}] task={payload.get("original_task", "?")} '
                f'id={payload.get("task_id", "?")} '
                f'exc={payload.get("exception", "?")[:80]}'
            )

    def _replay_entries(self, results, dry_run=False):
        from talentorbit.celery import app

        count = 0
        for r in results:
            payload = self._get_payload(r)
            original_task = payload.get('original_task')
            original_args = payload.get('args', [])
            original_kwargs = payload.get('kwargs', {})

            if not original_task:
                self.stdout.write(self.style.WARNING(f'  Skipping entry with no original_task: {r.task_id}'))
                continue

            if dry_run:
                self.stdout.write(
                    f'  [DRY RUN] Would replay: {original_task}(*{original_args}, **{original_kwargs})'
                )
            else:
                app.send_task(original_task, args=original_args, kwargs=original_kwargs)
                self.stdout.write(self.style.SUCCESS(f'  Replayed: {original_task}'))
                # Remove from DLQ results after replay
                r.delete()
            count += 1

        action = 'Would replay' if dry_run else 'Replayed'
        self.stdout.write(self.style.SUCCESS(f'\n{action} {count} tasks.'))

    def _purge_entries(self, results, older_than_days, dry_run=False):
        from django_celery_results.models import TaskResult

        qs = TaskResult.objects.filter(
            task_name='talentorbit.dlq_handler.handle_dead_letter',
        )

        if older_than_days > 0:
            cutoff = timezone.now() - timezone.timedelta(days=older_than_days)
            qs = qs.filter(date_done__lt=cutoff)

        count = qs.count()

        if dry_run:
            self.stdout.write(self.style.WARNING(f'[DRY RUN] Would purge {count} DLQ entries.'))
        else:
            deleted, _ = qs.delete()
            self.stdout.write(self.style.SUCCESS(f'Purged {deleted} DLQ entries.'))
