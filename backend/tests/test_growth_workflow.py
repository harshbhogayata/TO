from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import CompanyProfile, TalentProfile, User
from jobs.models import JobPost
from payments.models import SponsoredJobCampaign, TalentPoolCandidate, TalentPoolPipeline


def create_company(email='company@growth.test', **extra):
    user = User.objects.create_user(
        email=email,
        password='TestPass123!',
        full_name='Growth Company',
        role=User.Role.COMPANY,
        is_verified=True,
        **extra,
    )
    CompanyProfile.objects.create(user=user, legal_name='Growth Company LLC')
    return user


def create_talent(email='talent@growth.test', **extra):
    user = User.objects.create_user(
        email=email,
        password='TestPass123!',
        full_name='Growth Talent',
        role=User.Role.TALENT,
        is_verified=True,
        **extra,
    )
    TalentProfile.objects.create(user=user)
    return user


def create_job(company, **overrides):
    defaults = {
        'title': 'Frontend Lead',
        'description': 'Lead the frontend team.',
        'requirements': 'React, Typescript',
        'location': 'Remote',
        'status': JobPost.Status.OPEN,
    }
    defaults.update(overrides)
    return JobPost.objects.create(company=company, **defaults)


def unwrap_results(data):
    if isinstance(data, dict) and 'results' in data:
        return data['results']
    return data


class GrowthWorkflowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.company = create_company()
        self.talent = create_talent()
        self.job = create_job(self.company)

    def test_talent_user_cannot_access_sponsored_campaigns(self):
        self.client.force_authenticate(user=self.talent)

        response = self.client.get('/api/v1/payments/sponsored/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_talent_user_cannot_create_crm_pipeline(self):
        self.client.force_authenticate(user=self.talent)

        response = self.client.post('/api/v1/payments/pipelines/', {'name': 'Hiring'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_company_pipeline_create_returns_default_stage_labels(self):
        self.client.force_authenticate(user=self.company)

        response = self.client.post('/api/v1/payments/pipelines/', {'name': 'Design Hiring'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['stages'][0]['label'], 'Sourced')
        self.assertEqual(response.data['stages'][0]['id'], 'sourced')

    def test_company_candidate_list_returns_display_name_contract(self):
        pipeline = TalentPoolPipeline.objects.create(
            company=self.company,
            name='Design Hiring',
            stages=[{'id': 'sourced', 'label': 'Sourced', 'color': '#94A3B8'}],
        )
        TalentPoolCandidate.objects.create(
            pipeline=pipeline,
            external_name='Alex Rivera',
            external_email='alex@example.com',
            stage_id='sourced',
            source='import',
            rating=4,
        )
        self.client.force_authenticate(user=self.company)

        response = self.client.get(f'/api/v1/payments/pipelines/{pipeline.id}/candidates/')
        rows = unwrap_results(response.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(rows[0]['display_name'], 'Alex Rivera')
        self.assertEqual(rows[0]['stage_id'], 'sourced')
        self.assertEqual(rows[0]['rating'], 4)

    def test_company_sponsored_list_returns_amount_spent_contract(self):
        SponsoredJobCampaign.objects.create(
            company=self.company,
            job=self.job,
            bid_type='cpc',
            bid_amount=Decimal('2.50'),
            daily_budget=Decimal('50.00'),
            total_budget=Decimal('350.00'),
            amount_spent=Decimal('125.75'),
            status='active',
            starts_at=timezone.now(),
            ends_at=timezone.now() + timedelta(days=7),
        )
        self.client.force_authenticate(user=self.company)

        response = self.client.get('/api/v1/payments/sponsored/')
        rows = unwrap_results(response.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(rows[0]['job_title'], 'Frontend Lead')
        self.assertEqual(str(rows[0]['amount_spent']), '125.75')

    @patch(
        'intelligence.analytics.aggregators.compute_overview_metrics',
        return_value={
            'total_views': 8100,
            'total_applications': 22,
            'application_change': 12.4,
            'active_jobs': 3,
            'total_jobs': 5,
        },
    )
    def test_company_can_access_company_analytics_overview(self, mock_compute):
        self.client.force_authenticate(user=self.company)

        response = self.client.get('/api/v1/intelligence/analytics/overview/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_applications'], 22)
        mock_compute.assert_called_once()
