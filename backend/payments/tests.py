from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import User


class PaymentsAPITestCase(TestCase):
    """Smoke tests for payments endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='user@test.com',
            password='testpass123',
            full_name='Test User',
            role=User.Role.TALENT,
        )

    def test_create_checkout_session_requires_auth(self):
        url = reverse('create-checkout-session')
        resp = self.client.post(url, {'plan': 'Premium Pro'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_checkout_session_enterprise_returns_support_url(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('create-checkout-session')
        resp = self.client.post(url, {'plan': 'Enterprise'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('url', resp.data)
        self.assertIn('/support', resp.data['url'])

    def test_create_checkout_session_free_returns_success_url(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('create-checkout-session')
        resp = self.client.post(url, {'plan': 'Free Agent'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('url', resp.data)
        self.assertIn('payment/success', resp.data['url'])

    def test_create_checkout_session_unknown_plan_returns_400(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('create-checkout-session')
        resp = self.client.post(url, {'plan': 'Invalid Plan'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
