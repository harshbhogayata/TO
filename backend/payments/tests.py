from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import User, TalentProfile, CompanyProfile
from payments.views import PLANS, _update_user_tier


class PaymentsAPITestCase(TestCase):
    """Tests for payments endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='user@test.com',
            password='testpass123',
            full_name='Test User',
            role=User.Role.TALENT,
        )
        TalentProfile.objects.create(user=self.user, subscription_tier='free')

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


class PlanDefinitionTests(TestCase):
    """Tests for plan definition integrity."""

    def test_all_plans_have_required_keys(self):
        required_keys = {'amount', 'currency', 'name', 'description', 'tier', 'interval'}
        for plan_name, plan in PLANS.items():
            for key in required_keys:
                self.assertIn(key, plan, f'Plan "{plan_name}" missing key "{key}"')

    def test_tier_codes_are_unique(self):
        tiers = [p['tier'] for p in PLANS.values()]
        self.assertEqual(len(tiers), len(set(tiers)), 'Tier codes must be unique')

    def test_paid_plans_have_positive_amounts(self):
        for name, plan in PLANS.items():
            if name not in ('Free Agent', 'Enterprise'):
                self.assertGreater(plan['amount'], 0, f'Plan "{name}" should have positive amount')

    def test_all_plans_use_monthly_interval(self):
        for name, plan in PLANS.items():
            self.assertEqual(plan['interval'], 'month', f'Plan "{name}" should be monthly')


class TierUpdateHelperTests(TestCase):
    """Tests for the _update_user_tier webhook helper."""

    def test_update_talent_tier(self):
        user = User.objects.create_user(
            email='tier_talent@test.com', password='p', role=User.Role.TALENT,
        )
        TalentProfile.objects.create(user=user, subscription_tier='free')

        _update_user_tier(str(user.id), 'Premium Pro')
        user.talent_profile.refresh_from_db()
        self.assertEqual(user.talent_profile.subscription_tier, 'premium')

    def test_update_company_tier(self):
        user = User.objects.create_user(
            email='tier_co@test.com', password='p', role=User.Role.COMPANY,
        )
        CompanyProfile.objects.create(user=user, legal_name='Test', subscription_tier='free')

        _update_user_tier(str(user.id), 'Professional')
        user.company_profile.refresh_from_db()
        self.assertEqual(user.company_profile.subscription_tier, 'professional')

    def test_update_reverts_to_free_on_cancellation(self):
        user = User.objects.create_user(
            email='cancel@test.com', password='p', role=User.Role.TALENT,
        )
        TalentProfile.objects.create(user=user, subscription_tier='premium')

        _update_user_tier(str(user.id), 'Free Agent')
        user.talent_profile.refresh_from_db()
        self.assertEqual(user.talent_profile.subscription_tier, 'free')

    def test_update_nonexistent_user_does_not_raise(self):
        """Webhook helper should log but not crash for missing users."""
        _update_user_tier('99999', 'Premium Pro')  # Should not raise
