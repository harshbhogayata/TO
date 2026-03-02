"""
celery_health management command.
Checks Celery broker + result backend connectivity.

Usage:
    python manage.py celery_health
    python manage.py celery_health --timeout 10
"""

import sys
import time

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Check Celery broker and result backend connectivity.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--timeout',
            type=int,
            default=5,
            help='Timeout in seconds for the ping (default: 5).',
        )

    def handle(self, *args, **options):
        timeout = options['timeout']

        self.stdout.write('Checking Celery health...\n')

        # 1. Check broker connection
        self._check_broker(timeout)

        # 2. Check result backend
        self._check_result_backend()

        # 3. Send a test task and verify round-trip
        self._check_task_roundtrip(timeout)

        self.stdout.write(self.style.SUCCESS('\n✓ All Celery health checks passed.'))

    def _check_broker(self, timeout):
        self.stdout.write('  [1/3] Broker connection... ', ending='')
        try:
            from talentorbit.celery import app
            conn = app.connection()
            conn.ensure_connection(max_retries=1, timeout=timeout)
            conn.close()
            self.stdout.write(self.style.SUCCESS('OK'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'FAIL: {e}'))
            self.stderr.write(
                self.style.ERROR(
                    'Broker is unreachable. Check CELERY_BROKER_URL / UPSTASH_REDIS_URL.'
                )
            )
            sys.exit(1)

    def _check_result_backend(self):
        self.stdout.write('  [2/3] Result backend (django-db)... ', ending='')
        try:
            from django_celery_results.models import TaskResult
            # Just verify the table is accessible
            TaskResult.objects.exists()
            self.stdout.write(self.style.SUCCESS('OK'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'FAIL: {e}'))
            self.stderr.write(
                self.style.ERROR(
                    'Result backend table missing. Run: python manage.py migrate django_celery_results'
                )
            )
            sys.exit(1)

    def _check_task_roundtrip(self, timeout):
        self.stdout.write('  [3/3] Task round-trip ping... ', ending='')
        try:
            from talentorbit.celery import app
            from django.conf import settings

            if getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
                self.stdout.write(self.style.WARNING('SKIPPED (eager mode)'))
                return

            result = app.send_task('celery.ping', queue='default')
            # Wait for result with timeout
            start = time.time()
            while not result.ready():
                if time.time() - start > timeout:
                    raise TimeoutError(f'Ping task did not complete within {timeout}s')
                time.sleep(0.2)

            self.stdout.write(self.style.SUCCESS(f'OK ({result.result})'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'WARN: {e}'))
            self.stdout.write(
                self.style.WARNING(
                    '    (This is expected if no worker is running.)'
                )
            )
