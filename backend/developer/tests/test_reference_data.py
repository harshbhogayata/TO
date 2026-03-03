"""
developer/tests/test_reference_data.py
Tests for public reference data endpoints + portal stats + changelog.

Covers:
    - Available events (cached)
    - Available scopes (cached)
    - Rate limits (cached)
    - Endpoint catalogue (cached)
    - Portal stats with caching
    - Changelog listing
"""
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import CompanyProfile, User
from developer.models import (
    APIChangelog,
    APIKey,
    OAuthApplication,
    WebhookDelivery,
    WebhookEndpoint,
)

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
)
class AvailableEventsTests(TestCase):
    """Tests for GET /api/v1/developer/available-events/."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.url = reverse('developer:available-events')

    def test_returns_events(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        events = {e['event'] for e in resp.data}
        self.assertIn('job.created', events)
        self.assertIn('application.received', events)
        self.assertEqual(len(resp.data), len(WebhookEndpoint.AVAILABLE_EVENTS))

    def test_no_auth_required(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_response_is_cached(self):
        self.client.get(self.url)
        # Second call should hit cache
        cached = cache.get('developer:ref:available_events')
        self.assertIsNotNone(cached)
        self.assertEqual(len(cached), len(WebhookEndpoint.AVAILABLE_EVENTS))


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    DEFAULT_THROTTLE_RATES=_UNTHROTTLED_RATES,
)
class AvailableScopesTests(TestCase):
    """Tests for GET /api/v1/developer/available-scopes/."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.url = reverse('developer:available-scopes')

    def test_returns_both_scope_sets(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('api_key_scopes', resp.data)
        self.assertIn('oauth_scopes', resp.data)
        self.assertIn('read:jobs', resp.data['api_key_scopes'])
        self.assertIn('user.read', resp.data['oauth_scopes'])

    def test_scopes_are_sorted(self):
        resp = self.client.get(self.url)
        api_scopes = resp.data['api_key_scopes']
        self.assertEqual(api_scopes, sorted(api_scopes))

    def test_response_is_cached(self):
        self.client.get(self.url)
        cached = cache.get('developer:ref:available_scopes')
        self.assertIsNotNone(cached)


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    DEFAULT_THROTTLE_RATES=_UNTHROTTLED_RATES,
)
class RateLimitsTests(TestCase):
    """Tests for GET /api/v1/developer/rate-limits/."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.url = reverse('developer:rate-limits')

    def test_returns_all_tiers(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        tiers = {t['tier'] for t in resp.data}
        self.assertEqual(tiers, {'Free', 'Starter', 'Professional', 'Enterprise'})

    def test_response_is_cached(self):
        self.client.get(self.url)
        cached = cache.get('developer:ref:rate_limits')
        self.assertIsNotNone(cached)


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    DEFAULT_THROTTLE_RATES=_UNTHROTTLED_RATES,
)
class EndpointCatalogueTests(TestCase):
    """Tests for GET /api/v1/developer/endpoints/."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.url = reverse('developer:endpoint-catalogue')

    def test_returns_endpoints(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(len(resp.data) > 0)
        for ep in resp.data:
            self.assertIn('method', ep)
            self.assertIn('path', ep)
            self.assertIn('description', ep)

    def test_response_is_cached(self):
        self.client.get(self.url)
        cached = cache.get('developer:ref:endpoint_catalogue')
        self.assertIsNotNone(cached)


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    DEFAULT_THROTTLE_RATES=_UNTHROTTLED_RATES,
)
class PortalStatsTests(TestCase):
    """Tests for GET /api/v1/developer/portal/stats/."""

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
        self.url = reverse('developer:portal-stats')

    def test_returns_all_stat_fields(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        expected_fields = {
            'api_keys_count', 'active_api_keys',
            'webhooks_count', 'active_webhooks',
            'oauth_apps_count', 'active_oauth_apps',
            'total_api_calls_24h', 'webhook_delivery_rate',
        }
        self.assertTrue(expected_fields.issubset(set(resp.data.keys())))

    def test_stats_reflect_data(self):
        APIKey.create_key(company=self.company, name='K1', scopes=['read:jobs'])
        APIKey.create_key(company=self.company, name='K2', scopes=['admin'])
        key3, _ = APIKey.create_key(company=self.company, name='K3', scopes=['read:jobs'])
        key3.is_active = False
        key3.save()

        resp = self.client.get(self.url)
        self.assertEqual(resp.data['api_keys_count'], 3)
        self.assertEqual(resp.data['active_api_keys'], 2)

    def test_stats_are_cached(self):
        self.client.get(self.url)
        cached = cache.get(f'developer:portal_stats:{self.company.pk}')
        self.assertIsNotNone(cached)

    def test_cached_stats_returned_on_second_call(self):
        self.client.get(self.url)
        # Modify data
        APIKey.create_key(company=self.company, name='New', scopes=['admin'])
        # Second call should still return cached (0 keys)
        resp = self.client.get(self.url)
        self.assertEqual(resp.data['api_keys_count'], 0)  # from cache

    def test_unauthenticated_returns_401(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_delivery_rate_100_when_no_deliveries(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.data['webhook_delivery_rate'], 100.0)


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    DEFAULT_THROTTLE_RATES=_UNTHROTTLED_RATES,
)
class ChangelogTests(TestCase):
    """Tests for GET /api/v1/developer/changelog/."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.url = reverse('developer:changelog-list')

    def test_returns_published_only(self):
        APIChangelog.objects.create(
            version='v1.0.0', title='Launch',
            description='Initial release.', is_published=True,
            published_at=timezone.now(),
        )
        APIChangelog.objects.create(
            version='v1.1.0', title='Draft',
            description='Unpublished.', is_published=False,
        )
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['title'], 'Launch')

    def test_no_auth_required(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
