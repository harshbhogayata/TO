"""
compliance/tests/test_policies.py
Tests for policy versioning endpoints.
"""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework import status

from compliance.models import PolicyVersion
from .factories import create_user, create_admin_user, create_policy


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
)
class PolicyAPITests(TestCase):
    """Tests for policy CRUD endpoints."""

    def setUp(self):
        self.admin = create_admin_user()
        self.user = create_user(email='user@test.com')
        self.client = APIClient()

    def test_list_active_policies_public(self):
        """Anyone can list active policies (AllowAny)."""
        create_policy(is_active=True, version='1.0.0')
        create_policy(is_active=False, version='0.9.0')
        client = APIClient()
        resp = client.get('/api/v1/compliance/policies/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['results']), 1)

    def test_policy_detail_public(self):
        """Anyone can view a specific policy."""
        policy = create_policy()
        client = APIClient()
        resp = client.get(f'/api/v1/compliance/policies/{policy.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['version'], '1.0.0')
        self.assertIn('content', resp.data)

    def test_create_policy_admin_only(self):
        """Only admins can create policies."""
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(
            '/api/v1/compliance/policies/create/',
            {
                'policy_type': 'privacy',
                'version': '1.0.0',
                'title': 'Privacy Policy',
                'content': 'Privacy...',
                'effective_date': '2024-01-01',
                'is_active': True,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_creates_policy(self):
        """Admin can create a new policy version."""
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            '/api/v1/compliance/policies/create/',
            {
                'policy_type': 'privacy',
                'version': '1.0.0',
                'title': 'Privacy Policy v1',
                'summary': 'Initial release',
                'content': '# Privacy\nContent here.',
                'effective_date': '2024-01-01',
                'is_active': True,
                'requires_re_consent': False,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(PolicyVersion.objects.filter(version='1.0.0').exists())

    def test_duplicate_version_rejected(self):
        """Can't create two policies with same type+version."""
        create_policy(policy_type='tos', version='1.0.0')
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            '/api/v1/compliance/policies/create/',
            {
                'policy_type': 'tos',
                'version': '1.0.0',
                'title': 'Duplicate',
                'content': 'Content',
                'effective_date': '2024-01-01',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_single_active_constraint(self):
        """Activating a new version deactivates the previous one."""
        p1 = create_policy(policy_type='tos', version='1.0.0', is_active=True)
        _p2 = create_policy(policy_type='tos', version='2.0.0', is_active=True)
        p1.refresh_from_db()
        self.assertFalse(p1.is_active)

    def test_filter_by_type(self):
        """Policies can be filtered by type."""
        create_policy(policy_type='tos', version='1.0.0')
        create_policy(policy_type='privacy', version='1.0.0')
        client = APIClient()
        resp = client.get('/api/v1/compliance/policies/?type=tos')
        self.assertEqual(len(resp.data['results']), 1)
        self.assertEqual(resp.data['results'][0]['policy_type'], 'tos')
