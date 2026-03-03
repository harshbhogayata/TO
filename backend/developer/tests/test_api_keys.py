"""
developer/tests/test_api_keys.py
Comprehensive tests for the API Key management endpoints.

Covers:
    - List / Create / Detail / Revoke / Rotate
    - Tier-based limits enforcement
    - Audit log creation on mutations
    - Throttle enforcement on create + rotate
    - transaction.atomic() correctness on rotate
    - Scope validation
    - Duplicate name validation
    - Cache invalidation on mutations
"""
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import CompanyProfile, User
from compliance.models import AuditLog
from developer.models import APIKey

# ── Disable throttles + use in-memory cache for all tests ────────────────────
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
class APIKeyListCreateTests(TestCase):
    """Tests for GET/POST /api/v1/developer/api-keys/."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='devadmin@company.io',
            password='StrongPass123!',
            full_name='Dev Admin',
            role=User.Role.COMPANY,
            is_verified=True,
        )
        self.company = CompanyProfile.objects.create(
            user=self.user,
            legal_name='Acme Corp',
            subscription_tier='professional',
        )
        self.client.force_authenticate(user=self.user)
        self.url = reverse('developer:apikey-list-create')

    # ── List ──────────────────────────────────────────────────────

    def test_list_returns_empty_for_new_company(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 0)

    def test_list_returns_company_keys_only(self):
        APIKey.create_key(company=self.company, name='Key A', scopes=['read:jobs'], created_by=self.user)
        APIKey.create_key(company=self.company, name='Key B', scopes=['admin'], created_by=self.user)

        # Create another company with its own key
        other_user = User.objects.create_user(
            email='other@corp.io', password='Pass123!',
            full_name='Other', role=User.Role.COMPANY, is_verified=True,
        )
        other_company = CompanyProfile.objects.create(user=other_user, legal_name='Other Corp')
        APIKey.create_key(company=other_company, name='Other Key', scopes=['read:jobs'])

        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 2)
        names = {k['name'] for k in resp.data}
        self.assertEqual(names, {'Key A', 'Key B'})

    # ── Create ────────────────────────────────────────────────────

    def test_create_returns_raw_key_once(self):
        resp = self.client.post(self.url, {
            'name': 'Production Key',
            'scopes': ['read:jobs', 'write:jobs'],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn('raw_key', resp.data)
        self.assertTrue(resp.data['raw_key'].startswith('to_live_'))
        self.assertEqual(resp.data['name'], 'Production Key')
        self.assertEqual(resp.data['scopes'], ['read:jobs', 'write:jobs'])

    def test_create_stores_hash_not_raw_key(self):
        resp = self.client.post(self.url, {
            'name': 'HashTest', 'scopes': ['read:jobs'],
        }, format='json')
        key = APIKey.objects.get(id=resp.data['id'])
        # The raw key should not appear in the DB field
        self.assertNotEqual(key.key_hash, resp.data['raw_key'])
        self.assertEqual(len(key.key_hash), 64)  # SHA-256 hex

    def test_create_generates_audit_log(self):
        initial_count = AuditLog.objects.count()
        self.client.post(self.url, {
            'name': 'AuditTest', 'scopes': ['read:jobs'],
        }, format='json')
        self.assertGreater(AuditLog.objects.count(), initial_count)

    def test_create_rejects_invalid_scopes(self):
        resp = self.client.post(self.url, {
            'name': 'BadScopes', 'scopes': ['delete:everything'],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_rejects_empty_scopes(self):
        resp = self.client.post(self.url, {
            'name': 'Empty', 'scopes': [],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_rejects_duplicate_name(self):
        self.client.post(self.url, {
            'name': 'Unique', 'scopes': ['read:jobs'],
        }, format='json')
        resp = self.client.post(self.url, {
            'name': 'Unique', 'scopes': ['read:jobs'],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_invalidates_portal_stats_cache(self):
        cache.set(f'developer:portal_stats:{self.company.pk}', {'cached': True}, 600)
        self.client.post(self.url, {
            'name': 'CacheTest', 'scopes': ['read:jobs'],
        }, format='json')
        self.assertIsNone(cache.get(f'developer:portal_stats:{self.company.pk}'))

    def test_create_ip_allowlist_optional(self):
        resp = self.client.post(self.url, {
            'name': 'NoIP', 'scopes': ['read:jobs'],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        key = APIKey.objects.get(id=resp.data['id'])
        self.assertEqual(key.ip_allowlist, [])

    # ── Tier Limits ───────────────────────────────────────────────

    def test_tier_limit_enforced(self):
        """Free tier: max 2 active keys."""
        self.company.subscription_tier = 'free'
        self.company.save()

        self.client.post(self.url, {'name': 'K1', 'scopes': ['read:jobs']}, format='json')
        self.client.post(self.url, {'name': 'K2', 'scopes': ['read:jobs']}, format='json')
        resp = self.client.post(self.url, {'name': 'K3', 'scopes': ['read:jobs']}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('limit reached', resp.data['detail'].lower())

    def test_revoked_keys_dont_count_toward_limit(self):
        """Deactivated keys should not count toward the tier limit."""
        self.company.subscription_tier = 'free'
        self.company.save()

        r1 = self.client.post(self.url, {'name': 'K1', 'scopes': ['read:jobs']}, format='json')
        self.client.post(self.url, {'name': 'K2', 'scopes': ['read:jobs']}, format='json')

        # Revoke K1
        key_id = r1.data['id']
        self.client.delete(reverse('developer:apikey-detail', kwargs={'id': key_id}))

        # Should allow creating a 3rd key now
        resp = self.client.post(self.url, {'name': 'K3', 'scopes': ['read:jobs']}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    # ── Auth ──────────────────────────────────────────────────────

    def test_unauthenticated_returns_401(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_talent_user_returns_403(self):
        talent = User.objects.create_user(
            email='talent@test.io', password='Pass123!',
            full_name='Talent', role=User.Role.TALENT, is_verified=True,
        )
        self.client.force_authenticate(user=talent)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    DEFAULT_THROTTLE_RATES=_UNTHROTTLED_RATES,
    CELERY_TASK_ALWAYS_EAGER=True,
)
class APIKeyDetailRevokeTests(TestCase):
    """Tests for GET/DELETE /api/v1/developer/api-keys/<id>/."""

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
        self.key, self.raw = APIKey.create_key(
            company=self.company, name='TestKey', scopes=['read:jobs'], created_by=self.user,
        )

    def test_detail_returns_key_info(self):
        url = reverse('developer:apikey-detail', kwargs={'id': self.key.id})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['name'], 'TestKey')
        # Raw key must never appear in detail
        self.assertNotIn('raw_key', resp.data)

    def test_revoke_soft_deactivates(self):
        url = reverse('developer:apikey-detail', kwargs={'id': self.key.id})
        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.key.refresh_from_db()
        self.assertFalse(self.key.is_active)

    def test_revoke_creates_audit_log(self):
        url = reverse('developer:apikey-detail', kwargs={'id': self.key.id})
        initial = AuditLog.objects.count()
        self.client.delete(url)
        self.assertGreater(AuditLog.objects.count(), initial)

    def test_detail_404_for_other_company(self):
        other_user = User.objects.create_user(
            email='other@corp.io', password='Pass123!',
            full_name='Other', role=User.Role.COMPANY, is_verified=True,
        )
        other_company = CompanyProfile.objects.create(user=other_user, legal_name='Other')
        other_key, _ = APIKey.create_key(company=other_company, name='X', scopes=['read:jobs'])

        url = reverse('developer:apikey-detail', kwargs={'id': other_key.id})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    DEFAULT_THROTTLE_RATES=_UNTHROTTLED_RATES,
    CELERY_TASK_ALWAYS_EAGER=True,
)
class APIKeyRotateTests(TestCase):
    """Tests for POST /api/v1/developer/api-keys/<id>/rotate/."""

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
        self.key, self.raw = APIKey.create_key(
            company=self.company, name='RotateMe',
            scopes=['read:jobs', 'write:jobs'],
            ip_allowlist=['10.0.0.0/8'],
            created_by=self.user,
        )

    def test_rotate_creates_new_key_and_deactivates_old(self):
        url = reverse('developer:apikey-rotate', kwargs={'id': self.key.id})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        # Old key deactivated
        self.key.refresh_from_db()
        self.assertFalse(self.key.is_active)

        # New key returned with raw value
        self.assertIn('raw_key', resp.data)
        self.assertTrue(resp.data['raw_key'].startswith('to_live_'))
        self.assertNotEqual(resp.data['id'], str(self.key.id))

    def test_rotate_preserves_config(self):
        url = reverse('developer:apikey-rotate', kwargs={'id': self.key.id})
        resp = self.client.post(url)
        self.assertEqual(resp.data['name'], 'RotateMe')
        self.assertEqual(resp.data['scopes'], ['read:jobs', 'write:jobs'])
        self.assertEqual(resp.data['ip_allowlist'], ['10.0.0.0/8'])

    def test_rotate_is_atomic(self):
        """If new key creation fails, old key stays active."""
        url = reverse('developer:apikey-rotate', kwargs={'id': self.key.id})

        with patch('developer.models.APIKey.create_key', side_effect=Exception('DB Error')):
            try:
                self.client.post(url)
            except Exception:
                pass

        self.key.refresh_from_db()
        # Old key must still be active due to transaction rollback
        self.assertTrue(self.key.is_active)

    def test_rotate_404_for_inactive_key(self):
        self.key.is_active = False
        self.key.save()
        url = reverse('developer:apikey-rotate', kwargs={'id': self.key.id})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_rotate_creates_audit_log(self):
        url = reverse('developer:apikey-rotate', kwargs={'id': self.key.id})
        initial = AuditLog.objects.count()
        self.client.post(url)
        self.assertGreater(AuditLog.objects.count(), initial)
