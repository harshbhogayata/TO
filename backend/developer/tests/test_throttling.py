"""
developer/tests/test_throttling.py
Tests for developer-specific throttle classes.

Verifies that sensitive mutation endpoints are rate-limited
when throttle rates are set to restrictive values.
"""
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import CompanyProfile, User
from developer.models import APIKey


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    DEFAULT_THROTTLE_RATES={
        'anon': '9999/min',
        'user': '9999/min',
        'developer_key_create': '1/hour',
        'developer_key_rotate': '1/hour',
        'developer_webhook_create': '9999/min',
        'developer_webhook_test': '9999/min',
        'developer_oauth_create': '9999/min',
        'developer_oauth_revoke': '9999/min',
    },
)
class APIKeyCreateThrottleTests(TestCase):
    """Verify API key create endpoint is throttled."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='dev@co.io', password='Pass123!',
            full_name='Dev', role=User.Role.COMPANY, is_verified=True,
        )
        self.company = CompanyProfile.objects.create(
            user=self.user, legal_name='Acme', subscription_tier='enterprise',
        )
        self.client.force_authenticate(user=self.user)
        self.url = reverse('developer:apikey-list-create')

    def test_second_create_is_throttled(self):
        resp1 = self.client.post(self.url, {
            'name': 'K1', 'scopes': ['read:jobs'],
        }, format='json')
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)

        resp2 = self.client.post(self.url, {
            'name': 'K2', 'scopes': ['read:jobs'],
        }, format='json')
        self.assertEqual(resp2.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_list_is_not_throttled(self):
        """GET on the same endpoint should not be throttled."""
        # Exhaust the POST throttle
        self.client.post(self.url, {'name': 'K1', 'scopes': ['read:jobs']}, format='json')
        self.client.post(self.url, {'name': 'K2', 'scopes': ['read:jobs']}, format='json')
        # GET should still work
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    DEFAULT_THROTTLE_RATES={
        'anon': '9999/min',
        'user': '9999/min',
        'developer_key_create': '9999/min',
        'developer_key_rotate': '1/hour',
        'developer_webhook_create': '9999/min',
        'developer_webhook_test': '9999/min',
        'developer_oauth_create': '9999/min',
        'developer_oauth_revoke': '9999/min',
    },
)
class APIKeyRotateThrottleTests(TestCase):
    """Verify API key rotation endpoint is throttled."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='dev@co.io', password='Pass123!',
            full_name='Dev', role=User.Role.COMPANY, is_verified=True,
        )
        self.company = CompanyProfile.objects.create(
            user=self.user, legal_name='Acme', subscription_tier='enterprise',
        )
        self.client.force_authenticate(user=self.user)

    def test_second_rotate_is_throttled(self):
        key1, _ = APIKey.create_key(
            company=self.company, name='R1', scopes=['admin'], created_by=self.user,
        )
        url = reverse('developer:apikey-rotate', kwargs={'id': key1.id})
        resp1 = self.client.post(url)
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)

        # Create another key to rotate
        key2, _ = APIKey.create_key(
            company=self.company, name='R2', scopes=['admin'], created_by=self.user,
        )
        url2 = reverse('developer:apikey-rotate', kwargs={'id': key2.id})
        resp2 = self.client.post(url2)
        self.assertEqual(resp2.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
