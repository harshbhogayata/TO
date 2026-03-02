"""
Periodic cleanup of old read notifications.
Run via: python manage.py cleanup_notifications
Schedule via cron or Render/Heroku scheduler.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from notifications.models import Notification


class Command(BaseCommand):
    help = 'Delete read notifications older than 90 days to prevent unbounded table growth.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Delete read notifications older than this many days (default: 90).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show how many would be deleted without actually deleting.',
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        cutoff = timezone.now() - timezone.timedelta(days=days)

        qs = Notification.objects.filter(is_read=True, created_at__lt=cutoff)
        count = qs.count()

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'[DRY RUN] Would delete {count} read notifications older than {days} days.'
            ))
        else:
            deleted, _ = qs.delete()
            self.stdout.write(self.style.SUCCESS(
                f'Deleted {deleted} read notifications older than {days} days.'
            ))
