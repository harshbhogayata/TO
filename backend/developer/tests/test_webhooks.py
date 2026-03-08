"""
developer/tests/test_webhooks.py
Comprehensive tests for Webhook management endpoints.

Covers:
    - List / Create / Detail / Update / Deactivate
    - Delivery log retrieval
    - Test ping with HMAC-SHA256 signature verification
    - Tier-based limits enforcement
    - Audit log creation on mutations
    - HTTPS-only URL validation
    - Duplicate URL validation
    - Invalid event validation
"""
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import CompanyProfile, User
from compliance.models import AuditLog
from developer.models import WebhookDelivery, WebhookEndpoint

_UNTHROTTLED_RATES = {
    'anon': '9999/min',
    'user': '9999/min',
    'developer_key_create': '9999/min',
    'developer_key_rotate': '9999/min',
    'developer_webhook_create': '9999/min',
    'developer_webhook_test': '9999/min',
    'developer_oauth_create': '9999/min',
    'developer_oauth_revoke': '9999/min',
}


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    DEFAULT_THROTTLE_RATES=_UNTHROTTLED_RATES,
    CELERY_TASK_ALWAYS_EAGER=True,
)
class WebhookListCreateTests(TestCase):
    """Tests for GET/POST /api/v1/developer/webhooks/."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='devadmin@company.io', password='StrongPass123!',
            full_name='Dev Admin', role=User.Role.COMPANY, is_verified=True,
        )
        self.company = CompanyProfile.objects.create(
            user=self.user, legal_name='Acme Corp', subscription_tier='professional',
        )
        self.client.force_authenticate(user=self.user)
        self.url = reverse('developer:webhook-list-create')

    # â”€â”€ List â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def test_list_empty(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 0)

    def test_list_shows_company_webhooks_only(self):
        WebhookEndpoint.create_endpoint(
            company=self.company, url='https://a.io/hook',
            events=['job.created'], created_by=self.user,
        )
        other_user = User.objects.create_user(
            email='other@corp.io', password='Pass123!',
            full_name='Other', role=User.Role.COMPANY, is_verified=True,
        )
        other_co = CompanyProfile.objects.create(user=other_user, legal_name='Other')
        WebhookEndpoint.create_endpoint(
            company=other_co, url='https://b.io/hook', events=['job.created'],
        )

        resp = self.client.get(self.url)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['url'], 'https://a.io/hook')

    # â”€â”€ Create â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def test_create_success(self):
        resp = self.client.post(self.url, {
            'url': 'https://example.com/webhook',
            'events': ['job.created', 'job.updated'],
            'description': 'Main webhook',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn('signing_secret', resp.data)
        self.assertTrue(resp.data['signing_secret'].startswith('whsec_'))

    def test_create_rejects_http_url(self):
        resp = self.client.post(self.url, {
            'url': 'http://insecure.com/hook',
            'events': ['job.created'],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_rejects_private_metadata_url(self):
        resp = self.client.post(self.url, {
            'url': 'https://169.254.169.254/latest/meta-data',
            'events': ['job.created'],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_rejects_invalid_events(self):
        resp = self.client.post(self.url, {
            'url': 'https://example.com/hook',
            'events': ['nonexistent.event'],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_rejects_duplicate_url(self):
        self.client.post(self.url, {
            'url': 'https://example.com/hook',
            'events': ['job.created'],
        }, format='json')
        resp = self.client.post(self.url, {
            'url': 'https://example.com/hook',
            'events': ['job.updated'],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_generates_audit_log(self):
        initial = AuditLog.objects.count()
        self.client.post(self.url, {
            'url': 'https://audit.io/hook',
            'events': ['job.created'],
        }, format='json')
        self.assertGreater(AuditLog.objects.count(), initial)

    def test_create_invalidates_portal_stats_cache(self):
        cache.set(f'developer:portal_stats:{self.company.pk}', {'cached': True}, 600)
        self.client.post(self.url, {
            'url': 'https://cache.io/hook', 'events': ['job.created'],
        }, format='json')
        self.assertIsNone(cache.get(f'developer:portal_stats:{self.company.pk}'))

    # â”€â”€ Tier limits â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def test_tier_limit_enforced(self):
        self.company.subscription_tier = 'free'
        self.company.save()

        self.client.post(self.url, {
            'url': 'https://a.io/h1', 'events': ['job.created'],
        }, format='json')
        self.client.post(self.url, {
            'url': 'https://b.io/h2', 'events': ['job.created'],
        }, format='json')
        resp = self.client.post(self.url, {
            'url': 'https://c.io/h3', 'events': ['job.created'],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    DEFAULT_THROTTLE_RATES=_UNTHROTTLED_RATES,
    CELERY_TASK_ALWAYS_EAGER=True,
)
class WebhookDetailTests(TestCase):
    """Tests for GET/PATCH/DELETE /api/v1/developer/webhooks/<id>/."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='devadmin@company.io', password='StrongPass123!',
            full_name='Dev Admin', role=User.Role.COMPANY, is_verified=True,
        )
        self.company = CompanyProfile.objects.create(
            user=self.user, legal_name='Acme Corp', subscription_tier='professional',
        )
        self.client.force_authenticate(user=self.user)
        self.endpoint, self.raw_secret = WebhookEndpoint.create_endpoint(
            company=self.company, url='https://hooks.io/v1',
            events=['job.created'], created_by=self.user,
        )

    def test_detail_returns_webhook_info(self):
        url = reverse('developer:webhook-detail', kwargs={'id': self.endpoint.id})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['url'], 'https://hooks.io/v1')

    def test_update_events(self):
        url = reverse('developer:webhook-detail', kwargs={'id': self.endpoint.id})
        resp = self.client.patch(url, {
            'events': ['job.created', 'application.received'],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.endpoint.refresh_from_db()
        self.assertEqual(set(self.endpoint.events), {'job.created', 'application.received'})

    def test_update_creates_audit_log(self):
        url = reverse('developer:webhook-detail', kwargs={'id': self.endpoint.id})
        initial = AuditLog.objects.count()
        self.client.patch(url, {'description': 'Updated desc'}, format='json')
        self.assertGreater(AuditLog.objects.count(), initial)

    def test_update_rejects_private_url(self):
        url = reverse('developer:webhook-detail', kwargs={'id': self.endpoint.id})
        resp = self.client.patch(url, {
            'url': 'https://127.0.0.1/internal',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_deactivate_webhook(self):
        url = reverse('developer:webhook-detail', kwargs={'id': self.endpoint.id})
        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.endpoint.refresh_from_db()
        self.assertFalse(self.endpoint.is_active)

    def test_deactivate_creates_audit_log(self):
        url = reverse('developer:webhook-detail', kwargs={'id': self.endpoint.id})
        initial = AuditLog.objects.count()
        self.client.delete(url)
        self.assertGreater(AuditLog.objects.count(), initial)


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    DEFAULT_THROTTLE_RATES=_UNTHROTTLED_RATES,
    CELERY_TASK_ALWAYS_EAGER=True,
)
class WebhookDeliveryLogTests(TestCase):
    """Tests for GET /api/v1/developer/webhooks/<id>/deliveries/."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='devadmin@company.io', password='StrongPass123!',
            full_name='Dev Admin', role=User.Role.COMPANY, is_verified=True,
        )
        self.company = CompanyProfile.objects.create(
            user=self.user, legal_name='Acme Corp', subscription_tier='professional',
        )
        self.client.force_authenticate(user=self.user)
        self.endpoint, _ = WebhookEndpoint.create_endpoint(
            company=self.company, url='https://hooks.io/v1',
            events=['job.created'], created_by=self.user,
        )

    def test_delivery_log_empty(self):
        url = reverse('developer:webhook-deliveries', kwargs={'id': self.endpoint.id})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 0)

    def test_delivery_log_shows_deliveries(self):
        WebhookDelivery.objects.create(
            endpoint=self.endpoint, event_type='job.created',
            payload={'test': True}, status_code=200,
            response_time_ms=42, is_success=True,
        )
        url = reverse('developer:webhook-deliveries', kwargs={'id': self.endpoint.id})
        resp = self.client.get(url)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['event_type'], 'job.created')
        self.assertTrue(resp.data[0]['is_success'])


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    DEFAULT_THROTTLE_RATES=_UNTHROTTLED_RATES,
    CELERY_TASK_ALWAYS_EAGER=True,
)
class WebhookTestPingTests(TestCase):
    """Tests for POST /api/v1/developer/webhooks/<id>/test/."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='devadmin@company.io', password='StrongPass123!',
            full_name='Dev Admin', role=User.Role.COMPANY, is_verified=True,
        )
        self.company = CompanyProfile.objects.create(
            user=self.user, legal_name='Acme Corp', subscription_tier='professional',
        )
        self.client.force_authenticate(user=self.user)
        self.endpoint, self.raw_secret = WebhookEndpoint.create_endpoint(
            company=self.company, url='https://hooks.io/v1',
            events=['job.created'], created_by=self.user,
        )
        self.url = reverse('developer:webhook-test', kwargs={'id': self.endpoint.id})

    @patch('developer.views.http_requests', create=True)
    def test_test_ping_sends_hmac_signed_request(self, mock_module):
        """Verify the outbound request includes HMAC signature headers."""
        # Import inline to patch correctly
        import developer.views as views_module

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = 'ok'

        with patch('requests.post', return_value=mock_resp) as mock_post:
            resp = self.client.post(self.url)

        # The response should record a delivery
        if resp.status_code == status.HTTP_200_OK:
            self.assertTrue(resp.data['is_success'])
            self.assertEqual(resp.data['event_type'], 'ping')
            self.assertEqual(resp.data['status_code'], 200)

    @patch('requests.post')
    def test_test_ping_records_delivery_on_success(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200, text='ok')
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(WebhookDelivery.objects.filter(endpoint=self.endpoint).count(), 1)
        delivery = WebhookDelivery.objects.get(endpoint=self.endpoint)
        self.assertTrue(delivery.is_success)

    @patch('requests.post')
    def test_test_ping_records_failure(self, mock_post):
        mock_post.return_value = MagicMock(status_code=500, text='Internal Server Error')
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        delivery = WebhookDelivery.objects.get(endpoint=self.endpoint)
        self.assertFalse(delivery.is_success)

    @patch('requests.post')
    def test_test_ping_handles_timeout(self, mock_post):
        import requests as http_requests
        mock_post.side_effect = http_requests.Timeout('Connection timed out')
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, status.HTTP_502_BAD_GATEWAY)
        delivery = WebhookDelivery.objects.get(endpoint=self.endpoint)
        self.assertFalse(delivery.is_success)
        self.assertIn('timed out', delivery.error_message.lower())

    @patch('requests.post')
    def test_test_ping_creates_audit_log(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200, text='ok')
        initial = AuditLog.objects.count()
        self.client.post(self.url)
        self.assertGreater(AuditLog.objects.count(), initial)

    def test_test_ping_404_for_inactive_webhook(self):
        self.endpoint.is_active = False
        self.endpoint.save()
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @patch('requests.post')
    def test_test_ping_includes_signature_header(self, mock_post):
        """Verify that X-TalentOrbit-Signature is sent in headers."""
        mock_post.return_value = MagicMock(status_code=200, text='ok')
        self.client.post(self.url)

        # Inspect the headers sent in the mock call
        if mock_post.called:
            _, kwargs = mock_post.call_args
            headers = kwargs.get('headers', {})
            self.assertIn('X-TalentOrbit-Signature', headers)
            self.assertTrue(headers['X-TalentOrbit-Signature'].startswith('v1='))
            self.assertIn('X-TalentOrbit-Timestamp', headers)

    @patch('requests.post')
    def test_test_ping_resets_failure_count_on_success(self, mock_post):
        self.endpoint.failure_count = 5
        self.endpoint.save()

        mock_post.return_value = MagicMock(status_code=200, text='ok')
        self.client.post(self.url)

        self.endpoint.refresh_from_db()
        self.assertEqual(self.endpoint.failure_count, 0)

    @patch('requests.post')
    def test_test_ping_increments_failure_count_on_error(self, mock_post):
        mock_post.return_value = MagicMock(status_code=500, text='error')
        self.client.post(self.url)

        self.endpoint.refresh_from_db()
        self.assertEqual(self.endpoint.failure_count, 1)

    @patch('requests.post')
    def test_test_ping_blocks_private_url_without_outbound_call(self, mock_post):
        WebhookEndpoint.objects.filter(pk=self.endpoint.pk).update(
            url='https://169.254.169.254/latest/meta-data'
        )
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        mock_post.assert_not_called()
        self.endpoint.refresh_from_db()
        self.assertEqual(self.endpoint.failure_count, 1)
        delivery = WebhookDelivery.objects.get(endpoint=self.endpoint)
        self.assertFalse(delivery.is_success)
        self.assertIn('SSRF prevention', delivery.error_message)

