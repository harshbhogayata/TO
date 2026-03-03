"""
developer/tests/test_models.py
Unit tests for developer app models.

Covers:
    - APIKey factory method and hash verification
    - APIKey lookup by raw key
    - APIKey expiry logic
    - APIKey usage recording
    - WebhookEndpoint factory and signing secret
    - WebhookEndpoint status labels
    - OAuthApplication factory and revocation
    - APIChangelog string representation
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import CompanyProfile, User
from developer.models import (
    APIChangelog,
    APIKey,
    OAuthApplication,
    WebhookEndpoint,
    _hash_secret,
)


class APIKeyModelTests(TestCase):
    """Unit tests for the APIKey model."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='dev@co.io', password='Pass123!',
            full_name='Dev', role=User.Role.COMPANY, is_verified=True,
        )
        self.company = CompanyProfile.objects.create(
            user=self.user, legal_name='TestCo',
        )

    def test_create_key_returns_tuple(self):
        key, raw = APIKey.create_key(
            company=self.company, name='Test', scopes=['read:jobs'],
        )
        self.assertIsInstance(key, APIKey)
        self.assertIsInstance(raw, str)
        self.assertTrue(raw.startswith('to_live_'))

    def test_key_hash_matches_raw(self):
        key, raw = APIKey.create_key(
            company=self.company, name='Hash', scopes=['admin'],
        )
        self.assertEqual(key.key_hash, _hash_secret(raw))

    def test_prefix_is_first_16_chars(self):
        key, raw = APIKey.create_key(
            company=self.company, name='Prefix', scopes=['admin'],
        )
        self.assertEqual(key.prefix, raw[:16])

    def test_lookup_by_raw_key(self):
        key, raw = APIKey.create_key(
            company=self.company, name='Lookup', scopes=['read:jobs'],
        )
        found = APIKey.lookup_by_raw_key(raw)
        self.assertEqual(found.pk, key.pk)

    def test_lookup_returns_none_for_inactive(self):
        key, raw = APIKey.create_key(
            company=self.company, name='Inactive', scopes=['admin'],
        )
        key.is_active = False
        key.save()
        self.assertIsNone(APIKey.lookup_by_raw_key(raw))

    def test_lookup_returns_none_for_expired(self):
        key, raw = APIKey.create_key(
            company=self.company, name='Expired', scopes=['admin'],
            expires_at=timezone.now() - timedelta(hours=1),
        )
        self.assertIsNone(APIKey.lookup_by_raw_key(raw))

    def test_is_expired_property(self):
        key, _ = APIKey.create_key(
            company=self.company, name='E1', scopes=['admin'],
            expires_at=timezone.now() - timedelta(hours=1),
        )
        self.assertTrue(key.is_expired)

    def test_not_expired(self):
        key, _ = APIKey.create_key(
            company=self.company, name='E2', scopes=['admin'],
            expires_at=timezone.now() + timedelta(hours=1),
        )
        self.assertFalse(key.is_expired)

    def test_never_expires(self):
        key, _ = APIKey.create_key(
            company=self.company, name='E3', scopes=['admin'],
        )
        self.assertFalse(key.is_expired)

    def test_record_usage_bumps_counters(self):
        key, _ = APIKey.create_key(
            company=self.company, name='Usage', scopes=['admin'],
        )
        key.record_usage(ip='10.0.0.1')
        key.refresh_from_db()
        self.assertEqual(key.usage_count, 1)
        self.assertEqual(key.last_used_ip, '10.0.0.1')
        self.assertIsNotNone(key.last_used_at)

    def test_daily_usage_initialized_to_7_zeros(self):
        key, _ = APIKey.create_key(
            company=self.company, name='Spark', scopes=['admin'],
        )
        self.assertEqual(key.daily_usage, [0] * 7)

    def test_str_representation(self):
        key, _ = APIKey.create_key(
            company=self.company, name='StrTest', scopes=['admin'],
        )
        self.assertIn('StrTest', str(key))


class WebhookEndpointModelTests(TestCase):
    """Unit tests for the WebhookEndpoint model."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='dev@co.io', password='Pass123!',
            full_name='Dev', role=User.Role.COMPANY, is_verified=True,
        )
        self.company = CompanyProfile.objects.create(
            user=self.user, legal_name='TestCo',
        )

    def test_create_endpoint_returns_tuple(self):
        ep, secret = WebhookEndpoint.create_endpoint(
            company=self.company, url='https://hooks.io/v1',
            events=['job.created'],
        )
        self.assertIsInstance(ep, WebhookEndpoint)
        self.assertTrue(secret.startswith('whsec_'))

    def test_get_signing_secret_roundtrip(self):
        ep, raw_secret = WebhookEndpoint.create_endpoint(
            company=self.company, url='https://hooks.io/v1',
            events=['job.created'],
        )
        self.assertEqual(ep.get_signing_secret(), raw_secret)

    def test_status_label_active(self):
        ep, _ = WebhookEndpoint.create_endpoint(
            company=self.company, url='https://hooks.io/v1',
            events=['job.created'],
        )
        self.assertEqual(ep.status_label, 'active')

    def test_status_label_disabled(self):
        ep, _ = WebhookEndpoint.create_endpoint(
            company=self.company, url='https://hooks.io/v1',
            events=['job.created'],
        )
        ep.is_active = False
        self.assertEqual(ep.status_label, 'disabled')

    def test_status_label_failing(self):
        ep, _ = WebhookEndpoint.create_endpoint(
            company=self.company, url='https://hooks.io/v1',
            events=['job.created'],
        )
        ep.failure_count = 5
        self.assertEqual(ep.status_label, 'failing')

    def test_signing_secret_prefix(self):
        ep, raw_secret = WebhookEndpoint.create_endpoint(
            company=self.company, url='https://hooks.io/v1',
            events=['job.created'],
        )
        self.assertEqual(ep.signing_secret_prefix, raw_secret[:16])


class OAuthApplicationModelTests(TestCase):
    """Unit tests for the OAuthApplication model."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='dev@co.io', password='Pass123!',
            full_name='Dev', role=User.Role.COMPANY, is_verified=True,
        )
        self.company = CompanyProfile.objects.create(
            user=self.user, legal_name='TestCo',
        )

    def test_create_application_returns_tuple(self):
        app, secret = OAuthApplication.create_application(
            company=self.company, name='TestApp',
            redirect_uris=['https://app.io/cb'], scopes=['user.read'],
        )
        self.assertIsInstance(app, OAuthApplication)
        self.assertIsInstance(secret, str)

    def test_client_id_prefix(self):
        app, _ = OAuthApplication.create_application(
            company=self.company, name='TestApp',
            redirect_uris=['https://app.io/cb'], scopes=['user.read'],
        )
        self.assertTrue(app.client_id.startswith('to_app_'))

    def test_secret_hash_stored_not_raw(self):
        app, raw_secret = OAuthApplication.create_application(
            company=self.company, name='TestApp',
            redirect_uris=['https://app.io/cb'], scopes=['user.read'],
        )
        self.assertNotEqual(app.client_secret_hash, raw_secret)
        self.assertEqual(app.client_secret_hash, _hash_secret(raw_secret))

    def test_logo_initials_generated(self):
        app, _ = OAuthApplication.create_application(
            company=self.company, name='My App',
            redirect_uris=[], scopes=['user.read'],
        )
        self.assertEqual(app.logo_initials, 'MA')

    def test_default_status_is_pending(self):
        app, _ = OAuthApplication.create_application(
            company=self.company, name='Pending',
            redirect_uris=[], scopes=['user.read'],
        )
        self.assertEqual(app.status, OAuthApplication.Status.PENDING)

    def test_revoke(self):
        app, _ = OAuthApplication.create_application(
            company=self.company, name='Revokable',
            redirect_uris=[], scopes=['user.read'],
        )
        app.revoke(user=self.user)
        app.refresh_from_db()
        self.assertEqual(app.status, OAuthApplication.Status.REVOKED)
        self.assertIsNotNone(app.revoked_at)
        self.assertEqual(app.revoked_by, self.user)


class APIChangelogModelTests(TestCase):
    """Unit tests for the APIChangelog model."""

    def test_str_representation(self):
        entry = APIChangelog.objects.create(
            version='v2.0.0', title='Big Update',
            description='Many changes.', is_published=True,
            published_at=timezone.now(),
        )
        self.assertIn('v2.0.0', str(entry))
        self.assertIn('Big Update', str(entry))
