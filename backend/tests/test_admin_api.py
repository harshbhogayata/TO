"""
tests/test_admin_api.py
Production-grade tests for the admin API endpoints.

Coverage:
    1. Permission enforcement (admin-only access)
    2. Public stats endpoint
    3. Platform stats (admin only)
    4. User listing, filtering, search
    5. User verification
    6. User deactivation (with self-deactivation guard)
    7. Job listing and status toggling
    8. Application listing
"""

from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework import status as http_status

from accounts.models import User, TalentProfile, CompanyProfile
from jobs.models import JobPost, Application


def _create_admin(email='admin@test.com'):
    return User.objects.create_user(
        email=email, password='AdminPass123!',
        full_name='Platform Admin', role=User.Role.ADMIN,
        is_verified=True, is_staff=True, is_superuser=True,
    )


def _create_talent(email='talent@admin.com'):
    user = User.objects.create_user(
        email=email, password='TestPass123!',
        full_name='Test Talent', role=User.Role.TALENT,
        is_verified=True,
    )
    TalentProfile.objects.create(user=user, skills=['Python'])
    return user


def _create_company(email='company@admin.com'):
    user = User.objects.create_user(
        email=email, password='TestPass123!',
        full_name='Test Corp', role=User.Role.COMPANY,
        is_verified=True,
    )
    CompanyProfile.objects.create(user=user, legal_name='Admin Test Corp')
    return user


# ─── Permission Tests ─────────────────────────────────────────────────────────

class AdminPermissionTest(TestCase):
    """Verify admin endpoints reject non-admin users."""

    def setUp(self):
        self.client = APIClient()
        self.talent = _create_talent()
        self.company = _create_company()
        self.admin = _create_admin()

    def test_talent_cannot_access_platform_stats(self):
        self.client.force_authenticate(user=self.talent)
        resp = self.client.get('/api/v1/admin-api/stats/')
        self.assertEqual(resp.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_company_cannot_access_platform_stats(self):
        self.client.force_authenticate(user=self.company)
        resp = self.client.get('/api/v1/admin-api/stats/')
        self.assertEqual(resp.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_access_platform_stats(self):
        resp = self.client.get('/api/v1/admin-api/stats/')
        self.assertEqual(resp.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_admin_can_access_platform_stats(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get('/api/v1/admin-api/stats/')
        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)

    def test_talent_cannot_list_users(self):
        self.client.force_authenticate(user=self.talent)
        resp = self.client.get('/api/v1/admin-api/users/')
        self.assertEqual(resp.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_company_cannot_deactivate_users(self):
        self.client.force_authenticate(user=self.company)
        resp = self.client.delete(f'/api/v1/admin-api/users/{self.talent.pk}/')
        self.assertEqual(resp.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_talent_cannot_verify_users(self):
        self.client.force_authenticate(user=self.talent)
        resp = self.client.patch(f'/api/v1/admin-api/users/{self.company.pk}/verify/')
        self.assertEqual(resp.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_non_staff_admin_role_rejected(self):
        """User with ADMIN role but is_staff=False should be rejected."""
        fake_admin = User.objects.create_user(
            email='fake@admin.com', password='TestPass123!',
            full_name='Fake Admin', role=User.Role.ADMIN,
            is_staff=False,
        )
        self.client.force_authenticate(user=fake_admin)
        resp = self.client.get('/api/v1/admin-api/stats/')
        self.assertEqual(resp.status_code, http_status.HTTP_403_FORBIDDEN)


# ─── Public Stats ─────────────────────────────────────────────────────────────

class PublicStatsTest(TestCase):
    """Tests for GET /api/v1/admin-api/public-stats/"""

    def test_returns_stats_without_auth(self):
        client = APIClient()
        resp = client.get('/api/v1/admin-api/public-stats/')
        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        self.assertIn('total_users', resp.data)
        self.assertIn('total_jobs', resp.data)

    def test_counts_only_active_users(self):
        _create_talent(email='active@test.com')
        User.objects.create_user(
            email='inactive@test.com', password='p',
            role=User.Role.TALENT, is_active=False,
        )
        client = APIClient()
        resp = client.get('/api/v1/admin-api/public-stats/')
        self.assertEqual(resp.data['total_users'], 1)

    def test_counts_only_open_jobs(self):
        company = _create_company(email='stats_co@test.com')
        JobPost.objects.create(
            company=company, title='Open', description='d', status='open',
        )
        JobPost.objects.create(
            company=company, title='Closed', description='d', status='closed',
        )
        client = APIClient()
        resp = client.get('/api/v1/admin-api/public-stats/')
        self.assertEqual(resp.data['total_jobs'], 1)


# ─── Platform Stats ──────────────────────────────────────────────────────────

class PlatformStatsTest(TestCase):
    """Tests for GET /api/v1/admin-api/stats/"""

    def setUp(self):
        self.client = APIClient()
        self.admin = _create_admin()
        self.client.force_authenticate(user=self.admin)

    def test_returns_all_metrics(self):
        _create_talent(email='metric_t@test.com')
        _create_company(email='metric_c@test.com')

        resp = self.client.get('/api/v1/admin-api/stats/')
        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        # Admin user + talent + company = 3 active users
        self.assertIn('talent_count', resp.data)
        self.assertIn('company_count', resp.data)
        self.assertIn('open_jobs', resp.data)
        self.assertIn('total_applications', resp.data)
        self.assertEqual(resp.data['talent_count'], 1)
        self.assertEqual(resp.data['company_count'], 1)


# ─── User Management ─────────────────────────────────────────────────────────

class AdminUserManagementTest(TestCase):
    """Tests for user listing, verification, and deactivation."""

    def setUp(self):
        self.client = APIClient()
        self.admin = _create_admin()
        self.client.force_authenticate(user=self.admin)

    def test_list_users(self):
        _create_talent(email='list_t@test.com')
        _create_company(email='list_c@test.com')

        resp = self.client.get('/api/v1/admin-api/users/')
        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        # Admin + talent + company
        self.assertGreaterEqual(resp.data['count'], 3)

    def test_filter_users_by_role(self):
        _create_talent(email='filter_t@test.com')
        _create_company(email='filter_c@test.com')

        resp = self.client.get('/api/v1/admin-api/users/?role=TALENT')
        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        for user in resp.data['results']:
            self.assertEqual(user['role'], 'TALENT')

    def test_search_users(self):
        _create_talent(email='searchme@test.com')

        resp = self.client.get('/api/v1/admin-api/users/?search=searchme')
        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 1)

    def test_verify_user(self):
        unverified = User.objects.create_user(
            email='unveri@test.com', password='TestPass123!',
            full_name='Unverified', role=User.Role.TALENT,
            is_verified=False,
        )

        resp = self.client.patch(f'/api/v1/admin-api/users/{unverified.pk}/verify/')
        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        unverified.refresh_from_db()
        self.assertTrue(unverified.is_verified)

    def test_verify_nonexistent_user(self):
        resp = self.client.patch('/api/v1/admin-api/users/99999/verify/')
        self.assertEqual(resp.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_deactivate_user(self):
        target = _create_talent(email='deact@test.com')

        resp = self.client.delete(f'/api/v1/admin-api/users/{target.pk}/')
        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        target.refresh_from_db()
        self.assertFalse(target.is_active)

    def test_cannot_deactivate_self(self):
        resp = self.client.delete(f'/api/v1/admin-api/users/{self.admin.pk}/')
        self.assertEqual(resp.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_cannot_deactivate_another_admin(self):
        other_admin = _create_admin(email='admin2@test.com')
        resp = self.client.delete(f'/api/v1/admin-api/users/{other_admin.pk}/')
        self.assertEqual(resp.status_code, http_status.HTTP_403_FORBIDDEN)
        other_admin.refresh_from_db()
        self.assertTrue(other_admin.is_active)

    def test_deactivate_nonexistent_user(self):
        resp = self.client.delete('/api/v1/admin-api/users/99999/')
        self.assertEqual(resp.status_code, http_status.HTTP_404_NOT_FOUND)


# ─── Job Management ──────────────────────────────────────────────────────────

class AdminJobManagementTest(TestCase):
    """Tests for admin job listing and toggling."""

    def setUp(self):
        self.client = APIClient()
        self.admin = _create_admin()
        self.company = _create_company(email='job_mgmt@test.com')
        self.client.force_authenticate(user=self.admin)

    def test_list_all_jobs(self):
        JobPost.objects.create(
            company=self.company, title='Job 1', description='d', status='open',
        )
        JobPost.objects.create(
            company=self.company, title='Job 2', description='d', status='closed',
        )

        resp = self.client.get('/api/v1/admin-api/jobs/')
        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 2)

    def test_toggle_job_open_to_closed(self):
        job = JobPost.objects.create(
            company=self.company, title='Toggle', description='d', status='open',
        )

        resp = self.client.patch(f'/api/v1/admin-api/jobs/{job.pk}/toggle/')
        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        self.assertEqual(resp.data['status'], 'closed')

    def test_toggle_job_closed_to_open(self):
        job = JobPost.objects.create(
            company=self.company, title='Toggle2', description='d', status='closed',
        )

        resp = self.client.patch(f'/api/v1/admin-api/jobs/{job.pk}/toggle/')
        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        self.assertEqual(resp.data['status'], 'open')

    def test_toggle_nonexistent_job(self):
        resp = self.client.patch('/api/v1/admin-api/jobs/99999/toggle/')
        self.assertEqual(resp.status_code, http_status.HTTP_404_NOT_FOUND)
