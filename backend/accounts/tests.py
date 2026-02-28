from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from .models import User


class AuthAPITestCase(TestCase):
    """Smoke tests for auth endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.talent = User.objects.create_user(
            email='talent@test.com',
            password='testpass123',
            full_name='Test Talent',
            role=User.Role.TALENT,
        )

    def test_login_returns_tokens(self):
        url = reverse('token_obtain_pair')
        resp = self.client.post(url, {'email': 'talent@test.com', 'password': 'testpass123'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('access', resp.data)
        self.assertIn('refresh', resp.data)

    def test_login_invalid_credentials(self):
        url = reverse('token_obtain_pair')
        resp = self.client.post(url, {'email': 'talent@test.com', 'password': 'wrong'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_requires_auth(self):
        url = reverse('me')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_returns_user(self):
        self.client.force_authenticate(user=self.talent)
        url = reverse('me')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data.get('email'), 'talent@test.com')
        self.assertEqual(resp.data.get('role'), 'TALENT')
