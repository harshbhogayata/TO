"""
Management command to verify Sentry integration is working.
Usage: python manage.py sentry_test
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Send a test error to Sentry to verify the integration is working.'

    def handle(self, *args, **options):
        import sentry_sdk

        if not sentry_sdk.get_client().is_active():
            self.stderr.write(self.style.ERROR(
                'Sentry is not initialized. Make sure SENTRY_DSN is set.'
            ))
            return

        try:
            sentry_sdk.capture_message('TalentOrbit Sentry test — this is a verification message.')
            self.stdout.write(self.style.SUCCESS(
                'Test message sent to Sentry. Check your Sentry dashboard to confirm.'
            ))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Failed to send to Sentry: {e}'))
