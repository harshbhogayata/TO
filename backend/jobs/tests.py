from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import User, CompanyProfile


class JobsAPITestCase(TestCase):
    """Smoke tests for jobs endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.talent = User.objects.create_user(
            email='talent@test.com',
            password='testpass123',
            full_name='Test Talent',
            role=User.Role.TALENT,
        )
        self.company = User.objects.create_user(
            email='company@test.com',
            password='testpass123',
            full_name='Test Company',
            role=User.Role.COMPANY,
        )
        CompanyProfile.objects.get_or_create(user=self.company, defaults={'legal_name': 'Test Company'})

    def test_list_jobs_public(self):
        url = reverse('job_list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('results', resp.data)

    def test_company_jobs_requires_auth(self):
        url = reverse('company_jobs')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_company_can_create_job(self):
        self.client.force_authenticate(user=self.company)
        url = reverse('company_jobs')
        data = {
            'title': 'Backend Developer',
            'description': 'Python/Django role',
            'job_type': 'full_time',
            'work_mode': 'remote',
        }
        resp = self.client.post(url, data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data.get('title'), 'Backend Developer')
