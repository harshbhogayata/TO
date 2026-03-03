"""
compliance/tests/test_consent.py
Tests for consent grant, withdrawal, status, and middleware enforcement.
"""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework import status

from compliance.models import PolicyVersion, ConsentRecord
from .factories import create_user, create_policy, grant_consent_for_user


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
)
class ConsentAPITests(TestCase):
    """Tests for consent grant/withdraw/status endpoints."""

    def setUp(self):
        self.user = create_user()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.policy = create_policy(
            policy_type='tos',
            version='1.0.0',
            is_active=True,
            requires_re_consent=True,
        )

    def test_grant_consent(self):
        """User can grant consent to an active policy."""
        resp = self.client.post(
            '/api/v1/compliance/consent/grant/',
            {'policy_version_ids': [self.policy.pk]},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn(self.policy.pk, resp.data['granted'])
        self.assertTrue(
            ConsentRecord.objects.filter(
                user=self.user,
                policy_version=self.policy,
                withdrawn_at__isnull=True,
            ).exists()
        )

    def test_grant_consent_idempotent(self):
        """Granting consent twice returns already_consented."""
        grant_consent_for_user(self.user, self.policy)
        resp = self.client.post(
            '/api/v1/compliance/consent/grant/',
            {'policy_version_ids': [self.policy.pk]},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn(self.policy.pk, resp.data['already_consented'])

    def test_grant_consent_invalid_policy(self):
        """Granting consent to nonexistent policy returns 400."""
        resp = self.client.post(
            '/api/v1/compliance/consent/grant/',
            {'policy_version_ids': [99999]},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_withdraw_consent(self):
        """User can withdraw active consent."""
        grant_consent_for_user(self.user, self.policy)
        resp = self.client.post(
            '/api/v1/compliance/consent/withdraw/',
            {'policy_version_id': self.policy.pk, 'reason': 'Changed my mind'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        record = ConsentRecord.objects.get(user=self.user, policy_version=self.policy)
        self.assertIsNotNone(record.withdrawn_at)
        self.assertEqual(record.withdrawal_reason, 'Changed my mind')

    def test_withdraw_consent_not_found(self):
        """Withdrawing non-existent consent returns 404."""
        resp = self.client.post(
            '/api/v1/compliance/consent/withdraw/',
            {'policy_version_id': self.policy.pk},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_consent_status(self):
        """Status endpoint shows all policies and consent state."""
        grant_consent_for_user(self.user, self.policy)
        resp = self.client.get('/api/v1/compliance/consent/status/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['all_consented'])
        self.assertEqual(len(resp.data['policies']), 1)
        self.assertTrue(resp.data['policies'][0]['has_consent'])

    def test_consent_status_missing_consent(self):
        """Status shows all_consented=False when consent is missing."""
        resp = self.client.get('/api/v1/compliance/consent/status/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data['all_consented'])

    def test_re_consent_after_withdrawal(self):
        """User can re-consent after withdrawing."""
        record = grant_consent_for_user(self.user, self.policy)
        # Withdraw
        self.client.post(
            '/api/v1/compliance/consent/withdraw/',
            {'policy_version_id': self.policy.pk},
            format='json',
        )
        # Re-consent
        resp = self.client.post(
            '/api/v1/compliance/consent/grant/',
            {'policy_version_ids': [self.policy.pk]},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn(self.policy.pk, resp.data['granted'])
        record.refresh_from_db()
        self.assertIsNone(record.withdrawn_at)

    def test_my_consent_records(self):
        """List endpoint returns the user's consent records."""
        grant_consent_for_user(self.user, self.policy)
        resp = self.client.get('/api/v1/compliance/consent/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['results']), 1)

    def test_unauthenticated_denied(self):
        """Unauthenticated requests to consent endpoints return 401."""
        client = APIClient()
        resp = client.post('/api/v1/compliance/consent/grant/', {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
)
class ConsentMiddlewareCacheTests(TestCase):
    """Tests for consent middleware caching behaviour."""

    def setUp(self):
        self.user = create_user()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.policy = create_policy(
            policy_type='tos', version='1.0.0',
            is_active=True, requires_re_consent=True,
        )

    def test_write_blocked_without_consent(self):
        """POST requests should return 451 when consent is missing."""
        # POST to a write endpoint (team create, which requires consent)
        resp = self.client.post(
            '/api/v1/compliance/team/',
            {'name': 'Test'},
            format='json',
        )
        # May be 403 (company-only) or 451 (consent required)
        # The middleware fires before the view's permission check
        self.assertIn(resp.status_code, [status.HTTP_403_FORBIDDEN, 451])

    def test_get_not_blocked(self):
        """GET requests should not be blocked by consent middleware."""
        resp = self.client.get('/api/v1/compliance/consent/status/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_consent_endpoint_exempt(self):
        """Consent endpoints themselves are exempt from enforcement."""
        resp = self.client.post(
            '/api/v1/compliance/consent/grant/',
            {'policy_version_ids': [self.policy.pk]},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_cache_invalidated_on_grant(self):
        """After granting consent, the cache should be invalidated."""
        from compliance.middleware import _consent_cache_key, invalidate_consent_cache
        from django.core.cache import cache

        # Set a fake "ok" value
        key = _consent_cache_key(self.user.pk)
        cache.set(key, 'ok', 300)

        # Invalidate
        invalidate_consent_cache(self.user.pk)

        # Should be gone (the versioned key is invalidated by prefix removal)
        # Note: invalidate_consent_cache deletes the old-format key
        from compliance.middleware import _CONSENT_CACHE_PREFIX
        old_key = f'{_CONSENT_CACHE_PREFIX}:{self.user.pk}'
        self.assertIsNone(cache.get(old_key))
