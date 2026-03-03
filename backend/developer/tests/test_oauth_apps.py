"""
developer/tests/test_oauth_apps.py
Comprehensive tests for the OAuth Application management endpoints.

Covers:
    - List / Create / Detail / Revoke
    - Tier-based limits enforcement
    - Audit log creation on mutations
    - Scope validation
    - Status filter on list
    - Already-revoked guard
"""
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import CompanyProfile, User
from compliance.models import AuditLog
from developer.models import OAuthApplication

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
class OAuthAppListCreateTests(TestCase):
    """Tests for GET/POST /api/v1/developer/oauth-apps/."""

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
        self.url = reverse('developer:oauth-list-create')

    # ── List ──────────────────────────────────────────────────────

    def test_list_empty(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 0)

    def test_list_shows_company_apps_only(self):
        OAuthApplication.create_application(
            company=self.company, name='App1',
            redirect_uris=['https://app.io/cb'], scopes=['user.read'],
            created_by=self.user,
        )
        other_user = User.objects.create_user(
            email='other@corp.io', password='Pass123!',
            full_name='Other', role=User.Role.COMPANY, is_verified=True,
        )
        other_co = CompanyProfile.objects.create(user=other_user, legal_name='Other')
        OAuthApplication.create_application(
            company=other_co, name='OtherApp',
            redirect_uris=['https://other.io/cb'], scopes=['user.read'],
        )

        resp = self.client.get(self.url)
        self.assertEqual(len(resp.data), 1)

    def test_list_status_filter(self):
        app1, _ = OAuthApplication.create_application(
            company=self.company, name='Active1',
            redirect_uris=['https://a.io/cb'], scopes=['user.read'],
            created_by=self.user,
        )
        app1.status = OAuthApplication.Status.ACTIVE
        app1.save()

        app2, _ = OAuthApplication.create_application(
            company=self.company, name='Revoked1',
            redirect_uris=['https://b.io/cb'], scopes=['user.read'],
            created_by=self.user,
        )
        app2.revoke(user=self.user)

        resp = self.client.get(self.url, {'status': 'active'})
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['name'], 'Active1')

    # ── Create ────────────────────────────────────────────────────

    def test_create_success(self):
        resp = self.client.post(self.url, {
            'name': 'My OAuth App',
            'redirect_uris': ['https://myapp.io/callback'],
            'scopes': ['user.read', 'job.read'],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn('client_secret', resp.data)
        self.assertIn('client_id', resp.data)
        self.assertTrue(resp.data['client_id'].startswith('to_app_'))

    def test_create_stores_hash_not_raw_secret(self):
        resp = self.client.post(self.url, {
            'name': 'HashTest',
            'redirect_uris': ['https://myapp.io/cb'],
            'scopes': ['user.read'],
        }, format='json')
        app = OAuthApplication.objects.get(id=resp.data['id'])
        self.assertNotEqual(app.client_secret_hash, resp.data['client_secret'])
        self.assertEqual(len(app.client_secret_hash), 64)

    def test_create_rejects_invalid_scopes(self):
        resp = self.client.post(self.url, {
            'name': 'BadScopes',
            'redirect_uris': ['https://app.io/cb'],
            'scopes': ['destroy.everything'],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_generates_audit_log(self):
        initial = AuditLog.objects.count()
        self.client.post(self.url, {
            'name': 'AuditApp',
            'redirect_uris': ['https://audit.io/cb'],
            'scopes': ['user.read'],
        }, format='json')
        self.assertGreater(AuditLog.objects.count(), initial)

    def test_create_invalidates_portal_stats_cache(self):
        cache.set(f'developer:portal_stats:{self.company.pk}', {'cached': True}, 600)
        self.client.post(self.url, {
            'name': 'CacheApp',
            'redirect_uris': ['https://cache.io/cb'],
            'scopes': ['user.read'],
        }, format='json')
        self.assertIsNone(cache.get(f'developer:portal_stats:{self.company.pk}'))

    # ── Tier limits ───────────────────────────────────────────────

    def test_tier_limit_enforced(self):
        self.company.subscription_tier = 'free'
        self.company.save()

        self.client.post(self.url, {
            'name': 'App1',
            'redirect_uris': ['https://a.io/cb'],
            'scopes': ['user.read'],
        }, format='json')
        resp = self.client.post(self.url, {
            'name': 'App2',
            'redirect_uris': ['https://b.io/cb'],
            'scopes': ['user.read'],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_revoked_apps_dont_count_toward_limit(self):
        self.company.subscription_tier = 'free'
        self.company.save()

        r1 = self.client.post(self.url, {
            'name': 'App1',
            'redirect_uris': ['https://a.io/cb'],
            'scopes': ['user.read'],
        }, format='json')
        app = OAuthApplication.objects.get(id=r1.data['id'])
        app.revoke(user=self.user)

        resp = self.client.post(self.url, {
            'name': 'App2',
            'redirect_uris': ['https://b.io/cb'],
            'scopes': ['user.read'],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    # ── Auth ──────────────────────────────────────────────────────

    def test_unauthenticated_returns_401(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    DEFAULT_THROTTLE_RATES=_UNTHROTTLED_RATES,
    CELERY_TASK_ALWAYS_EAGER=True,
)
class OAuthAppDetailTests(TestCase):
    """Tests for GET /api/v1/developer/oauth-apps/<id>/."""

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
        self.app, self.raw_secret = OAuthApplication.create_application(
            company=self.company, name='DetailApp',
            redirect_uris=['https://app.io/cb'], scopes=['user.read'],
            created_by=self.user,
        )

    def test_detail_returns_app_info(self):
        url = reverse('developer:oauth-detail', kwargs={'id': self.app.id})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['name'], 'DetailApp')
        # Raw secret must never appear in detail
        self.assertNotIn('client_secret', resp.data)

    def test_detail_404_for_other_company(self):
        other_user = User.objects.create_user(
            email='other@corp.io', password='Pass123!',
            full_name='Other', role=User.Role.COMPANY, is_verified=True,
        )
        other_co = CompanyProfile.objects.create(user=other_user, legal_name='Other')
        other_app, _ = OAuthApplication.create_application(
            company=other_co, name='OtherApp',
            redirect_uris=['https://other.io/cb'], scopes=['user.read'],
        )
        url = reverse('developer:oauth-detail', kwargs={'id': other_app.id})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    DEFAULT_THROTTLE_RATES=_UNTHROTTLED_RATES,
    CELERY_TASK_ALWAYS_EAGER=True,
)
class OAuthAppRevokeTests(TestCase):
    """Tests for POST /api/v1/developer/oauth-apps/<id>/revoke/."""

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
        self.app, _ = OAuthApplication.create_application(
            company=self.company, name='RevokeApp',
            redirect_uris=['https://app.io/cb'], scopes=['user.read'],
            created_by=self.user,
        )

    def test_revoke_success(self):
        url = reverse('developer:oauth-revoke', kwargs={'id': self.app.id})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, OAuthApplication.Status.REVOKED)
        self.assertIsNotNone(self.app.revoked_at)
        self.assertEqual(self.app.revoked_by, self.user)

    def test_revoke_already_revoked_returns_400(self):
        self.app.revoke(user=self.user)
        url = reverse('developer:oauth-revoke', kwargs={'id': self.app.id})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_revoke_creates_audit_log(self):
        url = reverse('developer:oauth-revoke', kwargs={'id': self.app.id})
        initial = AuditLog.objects.count()
        self.client.post(url)
        self.assertGreater(AuditLog.objects.count(), initial)

    def test_revoke_invalidates_portal_stats_cache(self):
        cache.set(f'developer:portal_stats:{self.company.pk}', {'cached': True}, 600)
        url = reverse('developer:oauth-revoke', kwargs={'id': self.app.id})
        self.client.post(url)
        self.assertIsNone(cache.get(f'developer:portal_stats:{self.company.pk}'))

    def test_revoke_404_for_other_company(self):
        other_user = User.objects.create_user(
            email='other@corp.io', password='Pass123!',
            full_name='Other', role=User.Role.COMPANY, is_verified=True,
        )
        other_co = CompanyProfile.objects.create(user=other_user, legal_name='Other')
        other_app, _ = OAuthApplication.create_application(
            company=other_co, name='OtherApp',
            redirect_uris=['https://other.io/cb'], scopes=['user.read'],
        )
        url = reverse('developer:oauth-revoke', kwargs={'id': other_app.id})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
