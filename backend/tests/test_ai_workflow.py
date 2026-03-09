from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import CompanyProfile, TalentProfile, User


_UNTHROTTLED_RATES = {
    'anon': '9999/minute',
    'user': '9999/minute',
    'resume_authenticated': '9999/minute',
    'resume_public': '9999/minute',
    'ai_resume_authenticated': '9999/minute',
    'ai_resume_public': '9999/minute',
    'ai_generate': '9999/minute',
}


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    DEFAULT_THROTTLE_RATES=_UNTHROTTLED_RATES,
    OPENAI_API_KEY='',
)
class AICompanyRoutePermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.company_user = User.objects.create_user(
            email='company@example.com',
            password='StrongPass123!',
            full_name='Company User',
            role=User.Role.COMPANY,
            is_verified=True,
        )
        CompanyProfile.objects.create(
            user=self.company_user,
            legal_name='Acme Corp',
            subscription_tier='professional',
        )
        self.talent_user = User.objects.create_user(
            email='talent@example.com',
            password='StrongPass123!',
            full_name='Talent User',
            role=User.Role.TALENT,
            is_verified=True,
        )
        TalentProfile.objects.create(
            user=self.talent_user,
            bio='',
            location='Remote',
            skills=['python'],
            is_open_to_work=True,
        )

    def test_talent_user_cannot_generate_job_description(self):
        self.client.force_authenticate(self.talent_user)
        response = self.client.post(
            '/api/v1/intelligence/ai/job-description/',
            {'title': 'Backend Engineer'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_talent_user_cannot_schedule_interviews(self):
        self.client.force_authenticate(self.talent_user)
        response = self.client.post(
            '/api/v1/intelligence/ai/schedule-interviews/',
            {'job_title': 'Backend Engineer', 'candidate_name': 'Jane Doe'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_company_user_reaches_job_description_handler(self):
        self.client.force_authenticate(self.company_user)
        response = self.client.post(
            '/api/v1/intelligence/ai/job-description/',
            {'title': 'Backend Engineer'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn('AI features are not configured', response.json()['error'])


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    DEFAULT_THROTTLE_RATES=_UNTHROTTLED_RATES,
)
class AnalyticsPermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.company_user = User.objects.create_user(
            email='company@example.com',
            password='StrongPass123!',
            full_name='Company User',
            role=User.Role.COMPANY,
            is_verified=True,
        )
        CompanyProfile.objects.create(
            user=self.company_user,
            legal_name='Acme Corp',
            subscription_tier='professional',
        )
        self.talent_user = User.objects.create_user(
            email='talent@example.com',
            password='StrongPass123!',
            full_name='Talent User',
            role=User.Role.TALENT,
            is_verified=True,
        )
        TalentProfile.objects.create(
            user=self.talent_user,
            bio='',
            location='Remote',
            skills=['python'],
            is_open_to_work=True,
        )
        self.admin_user = User.objects.create_user(
            email='admin@example.com',
            password='StrongPass123!',
            full_name='Admin User',
            role=User.Role.ADMIN,
            is_verified=True,
        )

    def test_talent_user_cannot_access_company_analytics_overview(self):
        self.client.force_authenticate(self.talent_user)
        response = self.client.get('/api/v1/intelligence/analytics/overview/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch('intelligence.analytics.aggregators.compute_overview_metrics')
    def test_company_user_can_access_company_analytics_overview(self, mock_compute):
        mock_compute.return_value = {
            'total_views': 10,
            'total_applications': 4,
            'application_change': 12.5,
            'active_jobs': 2,
            'total_jobs': 3,
        }

        self.client.force_authenticate(self.company_user)
        response = self.client.get('/api/v1/intelligence/analytics/overview/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['total_views'], 10)

    def test_company_user_cannot_access_platform_metrics(self):
        self.client.force_authenticate(self.company_user)
        response = self.client.get('/api/v1/intelligence/analytics/platform/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch('intelligence.analytics.materialized.get_platform_metrics_trend')
    def test_admin_user_can_access_platform_metrics(self, mock_trend):
        mock_trend.return_value = []

        self.client.force_authenticate(self.admin_user)
        response = self.client.get('/api/v1/intelligence/analytics/platform/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), [])