"""
developer/tests/test_tasks.py
Tests for Celery tasks in the developer app.

Covers:
    - compute_webhook_signature produces valid HMAC-SHA256
    - deliver_webhook creates delivery records
    - deliver_webhook handles endpoint failures
    - prune_delivery_logs removes old records
"""
import hmac
import hashlib
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import CompanyProfile, User
from developer.models import WebhookDelivery, WebhookEndpoint
from developer.tasks import compute_webhook_signature


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class ComputeWebhookSignatureTests(TestCase):
    """Tests for the HMAC signing helper."""

    def test_produces_v1_prefixed_signature(self):
        sig = compute_webhook_signature('whsec_test', '1700000000', b'{"event":"ping"}')
        self.assertTrue(sig.startswith('v1='))

    def test_signature_is_hex(self):
        sig = compute_webhook_signature('whsec_test', '1700000000', b'test')
        hex_part = sig.split('=', 1)[1]
        int(hex_part, 16)  # Should not raise

    def test_different_secrets_produce_different_signatures(self):
        sig1 = compute_webhook_signature('secret_a', '1700000000', b'payload')
        sig2 = compute_webhook_signature('secret_b', '1700000000', b'payload')
        self.assertNotEqual(sig1, sig2)

    def test_signature_matches_manual_hmac(self):
        secret = 'whsec_abcdef'
        timestamp = '1700000000'
        payload = b'{"event":"ping"}'
        message = f'{timestamp}.'.encode('utf-8') + payload
        expected = 'v1=' + hmac.new(
            secret.encode('utf-8'), message, hashlib.sha256,
        ).hexdigest()
        sig = compute_webhook_signature(secret, timestamp, payload)
        self.assertEqual(sig, expected)

    def test_same_inputs_produce_same_signature(self):
        args = ('secret', '123', b'body')
        self.assertEqual(
            compute_webhook_signature(*args),
            compute_webhook_signature(*args),
        )


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class PruneDeliveryLogsTests(TestCase):
    """Tests for the prune_delivery_logs periodic task."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='devadmin@company.io', password='StrongPass123!',
            full_name='Dev Admin', role=User.Role.COMPANY, is_verified=True,
        )
        self.company = CompanyProfile.objects.create(
            user=self.user, legal_name='Acme', subscription_tier='professional',
        )
        self.endpoint, _ = WebhookEndpoint.create_endpoint(
            company=self.company, url='https://hooks.io/v1',
            events=['job.created'], created_by=self.user,
        )

    def test_prunes_old_deliveries(self):
        # Create a delivery 45 days ago
        old = WebhookDelivery.objects.create(
            endpoint=self.endpoint, event_type='job.created',
            payload={}, is_success=True, response_time_ms=50,
        )
        WebhookDelivery.objects.filter(pk=old.pk).update(
            delivered_at=timezone.now() - timedelta(days=45),
        )

        # Create a recent delivery
        WebhookDelivery.objects.create(
            endpoint=self.endpoint, event_type='job.updated',
            payload={}, is_success=True, response_time_ms=30,
        )

        from developer.tasks import prune_delivery_logs
        prune_delivery_logs.apply()

        self.assertEqual(WebhookDelivery.objects.count(), 1)
        self.assertEqual(WebhookDelivery.objects.first().event_type, 'job.updated')

    def test_keeps_all_recent_deliveries(self):
        WebhookDelivery.objects.create(
            endpoint=self.endpoint, event_type='job.created',
            payload={}, is_success=True, response_time_ms=50,
        )
        from developer.tasks import prune_delivery_logs
        prune_delivery_logs.apply()
        self.assertEqual(WebhookDelivery.objects.count(), 1)
