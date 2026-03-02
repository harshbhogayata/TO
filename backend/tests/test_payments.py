"""
tests/test_payments.py
Production-grade tests for the Stripe payment/subscription lifecycle.

Coverage:
    1. Checkout session creation (valid plans, invalid plans, free, enterprise)
    2. Webhook signature verification
    3. Subscription lifecycle events (checkout.completed, updated, deleted, payment_failed)
    4. Idempotent tier updates
    5. Invoice PDF generation
    6. Edge cases (missing metadata, unknown events, malformed payloads)
"""

import json
import hmac
import hashlib
import time
import uuid
from unittest.mock import patch, MagicMock

from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework import status as http_status

from accounts.models import User, TalentProfile, CompanyProfile


def _create_talent(email='talent@pay.com', tier='free', **kw):
    user = User.objects.create_user(
        email=email, password='TestPass123!',
        full_name='Pay Talent', role=User.Role.TALENT,
        is_verified=True, **kw,
    )
    TalentProfile.objects.create(user=user, subscription_tier=tier)
    return user


def _create_company(email='company@pay.com', tier='free', **kw):
    user = User.objects.create_user(
        email=email, password='TestPass123!',
        full_name='Pay Corp', role=User.Role.COMPANY,
        is_verified=True, **kw,
    )
    CompanyProfile.objects.create(user=user, legal_name='Pay Corp Inc', subscription_tier=tier)
    return user


def _build_stripe_event(event_type, data_object, webhook_secret='whsec_test'):
    """Build a fake Stripe event payload with a valid-looking signature."""
    event = {
        'id': f'evt_test_{uuid.uuid4().hex[:16]}',
        'type': event_type,
        'data': {'object': data_object},
    }
    return event


# ─── Checkout Session Tests ──────────────────────────────────────────────────

@override_settings(
    STRIPE_SECRET_KEY='sk_test_fake',
    STRIPE_WEBHOOK_SECRET='whsec_test',
    FRONTEND_URL='http://localhost:5173',
)
class CreateCheckoutSessionTest(TestCase):
    """Tests for POST /api/v1/payments/create-checkout-session/"""

    def setUp(self):
        self.client = APIClient()
        self.talent = _create_talent()
        self.company = _create_company()

    @patch('payments.views.stripe.checkout.Session.create')
    def test_valid_subscription_plan(self, mock_create):
        """Should create a Stripe Checkout session for Premium Pro."""
        mock_create.return_value = MagicMock(url='https://checkout.stripe.com/test')
        self.client.force_authenticate(user=self.talent)

        resp = self.client.post('/api/v1/payments/create-checkout-session/', {
            'plan': 'Premium Pro',
        }, format='json')

        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        self.assertIn('https://checkout.stripe.com', resp.data['url'])
        mock_create.assert_called_once()

        # Verify subscription mode was used
        call_kwargs = mock_create.call_args[1]
        self.assertEqual(call_kwargs['mode'], 'subscription')
        self.assertEqual(call_kwargs['customer_email'], self.talent.email)
        self.assertEqual(call_kwargs['metadata']['tier'], 'premium')

    @patch('payments.views.stripe.checkout.Session.create')
    def test_company_plan_checkout(self, mock_create):
        """Should create checkout session for company Starter plan."""
        mock_create.return_value = MagicMock(url='https://checkout.stripe.com/company')
        self.client.force_authenticate(user=self.company)

        resp = self.client.post('/api/v1/payments/create-checkout-session/', {
            'plan': 'Starter',
        }, format='json')

        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        call_kwargs = mock_create.call_args[1]
        self.assertEqual(call_kwargs['metadata']['tier'], 'starter')

    def test_free_plan_no_stripe_call(self):
        """Free plan should redirect to success without hitting Stripe."""
        self.client.force_authenticate(user=self.talent)

        resp = self.client.post('/api/v1/payments/create-checkout-session/', {
            'plan': 'Free Agent',
        }, format='json')

        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        self.assertIn('success', resp.data['url'])
        self.assertIn('free', resp.data['url'])

    def test_enterprise_redirects_to_support(self):
        """Enterprise plan should redirect to support/contact page."""
        self.client.force_authenticate(user=self.company)

        resp = self.client.post('/api/v1/payments/create-checkout-session/', {
            'plan': 'Enterprise',
        }, format='json')

        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        self.assertIn('support', resp.data['url'])

    def test_unknown_plan_rejected(self):
        """Unknown plan name should return 400."""
        self.client.force_authenticate(user=self.talent)

        resp = self.client.post('/api/v1/payments/create-checkout-session/', {
            'plan': 'Nonexistent Plan',
        }, format='json')

        self.assertEqual(resp.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('Unknown plan', resp.data['error'])

    def test_unauthenticated_rejected(self):
        """Unauthenticated users should get 401."""
        resp = self.client.post('/api/v1/payments/create-checkout-session/', {
            'plan': 'Premium Pro',
        }, format='json')

        self.assertEqual(resp.status_code, http_status.HTTP_401_UNAUTHORIZED)

    @patch('payments.views.stripe.checkout.Session.create')
    def test_stripe_error_returns_502(self, mock_create):
        """Stripe API errors should return 502."""
        import stripe
        mock_create.side_effect = stripe.error.StripeError('Connection error')
        self.client.force_authenticate(user=self.talent)

        resp = self.client.post('/api/v1/payments/create-checkout-session/', {
            'plan': 'Premium Pro',
        }, format='json')

        self.assertEqual(resp.status_code, http_status.HTTP_502_BAD_GATEWAY)

    @patch('payments.views.stripe.checkout.Session.create')
    def test_professional_plan_metadata(self, mock_create):
        """Professional plan should include correct metadata."""
        mock_create.return_value = MagicMock(url='https://checkout.stripe.com/pro')
        self.client.force_authenticate(user=self.company)

        resp = self.client.post('/api/v1/payments/create-checkout-session/', {
            'plan': 'Professional',
        }, format='json')

        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        call_kwargs = mock_create.call_args[1]
        self.assertEqual(call_kwargs['metadata']['plan'], 'Professional')
        self.assertEqual(call_kwargs['metadata']['user_id'], str(self.company.id))


# ─── Webhook Tests ────────────────────────────────────────────────────────────

@override_settings(
    STRIPE_SECRET_KEY='sk_test_fake',
    STRIPE_WEBHOOK_SECRET='whsec_test_secret_key',
    FRONTEND_URL='http://localhost:5173',
)
class StripeWebhookTest(TestCase):
    """Tests for POST /api/v1/payments/webhook/"""

    def setUp(self):
        self.client = APIClient()
        self.talent = _create_talent(email='wh_talent@test.com')
        self.company = _create_company(email='wh_company@test.com')
        # Clear cache to prevent idempotency guard from deduplicating events across tests
        from django.core.cache import cache
        cache.clear()

    def _post_webhook(self, event_type, data_object):
        """Helper: POST a webhook event with mocked signature verification."""
        event = _build_stripe_event(event_type, data_object)
        payload = json.dumps(event)

        with patch('payments.views.stripe.Webhook.construct_event', return_value=event):
            return self.client.post(
                '/api/v1/payments/webhook/',
                data=payload,
                content_type='application/json',
                HTTP_STRIPE_SIGNATURE='t=123,v1=fakesig',
            )

    def test_checkout_completed_updates_talent_tier(self):
        """checkout.session.completed should upgrade talent to premium."""
        resp = self._post_webhook('checkout.session.completed', {
            'metadata': {
                'user_id': str(self.talent.id),
                'plan': 'Premium Pro',
            },
            'subscription': 'sub_test123',
        })

        self.assertEqual(resp.status_code, 200)
        self.talent.talent_profile.refresh_from_db()
        self.assertEqual(self.talent.talent_profile.subscription_tier, 'premium')

    def test_checkout_completed_updates_company_tier(self):
        """checkout.session.completed should upgrade company to starter."""
        resp = self._post_webhook('checkout.session.completed', {
            'metadata': {
                'user_id': str(self.company.id),
                'plan': 'Starter',
            },
            'subscription': 'sub_company123',
        })

        self.assertEqual(resp.status_code, 200)
        self.company.company_profile.refresh_from_db()
        self.assertEqual(self.company.company_profile.subscription_tier, 'starter')

    def test_subscription_updated_active(self):
        """customer.subscription.updated with active status should update tier."""
        resp = self._post_webhook('customer.subscription.updated', {
            'metadata': {
                'user_id': str(self.company.id),
                'plan': 'Professional',
            },
            'status': 'active',
            'id': 'sub_update123',
        })

        self.assertEqual(resp.status_code, 200)
        self.company.company_profile.refresh_from_db()
        self.assertEqual(self.company.company_profile.subscription_tier, 'professional')

    def test_subscription_updated_non_active_ignored(self):
        """Subscription update with non-active status should not change tier."""
        self.company.company_profile.subscription_tier = 'starter'
        self.company.company_profile.save()

        resp = self._post_webhook('customer.subscription.updated', {
            'metadata': {
                'user_id': str(self.company.id),
                'plan': 'Professional',
            },
            'status': 'past_due',
            'id': 'sub_pastdue123',
        })

        self.assertEqual(resp.status_code, 200)
        self.company.company_profile.refresh_from_db()
        # Should remain starter — not upgraded
        self.assertEqual(self.company.company_profile.subscription_tier, 'starter')

    def test_subscription_deleted_reverts_to_free(self):
        """customer.subscription.deleted should revert user to free tier."""
        self.talent.talent_profile.subscription_tier = 'premium'
        self.talent.talent_profile.save()

        resp = self._post_webhook('customer.subscription.deleted', {
            'metadata': {
                'user_id': str(self.talent.id),
            },
        })

        self.assertEqual(resp.status_code, 200)
        self.talent.talent_profile.refresh_from_db()
        self.assertEqual(self.talent.talent_profile.subscription_tier, 'free')

    def test_invoice_payment_failed_logged(self):
        """invoice.payment_failed should return 200 (logged, no tier change)."""
        self.talent.talent_profile.subscription_tier = 'premium'
        self.talent.talent_profile.save()

        resp = self._post_webhook('invoice.payment_failed', {
            'subscription': 'sub_failing',
        })

        self.assertEqual(resp.status_code, 200)
        self.talent.talent_profile.refresh_from_db()
        # Tier preserved during grace period
        self.assertEqual(self.talent.talent_profile.subscription_tier, 'premium')

    def test_unknown_event_type_returns_200(self):
        """Unhandled event types should return 200 (ack but no-op)."""
        resp = self._post_webhook('some.future.event', {
            'id': 'obj_unknown',
        })
        self.assertEqual(resp.status_code, 200)

    def test_missing_metadata_does_not_crash(self):
        """Events with missing metadata should not crash."""
        resp = self._post_webhook('checkout.session.completed', {
            'subscription': 'sub_nometadata',
            # No metadata key at all
        })
        self.assertEqual(resp.status_code, 200)

    def test_invalid_user_id_does_not_crash(self):
        """Events with non-existent user_id should not crash."""
        resp = self._post_webhook('checkout.session.completed', {
            'metadata': {
                'user_id': '999999',
                'plan': 'Premium Pro',
            },
            'subscription': 'sub_baduser',
        })
        self.assertEqual(resp.status_code, 200)

    def test_invalid_signature_returns_400(self):
        """Invalid Stripe signature should return 400."""
        import stripe
        with patch('payments.views.stripe.Webhook.construct_event',
                   side_effect=stripe.error.SignatureVerificationError('bad', 'sig')):
            resp = self.client.post(
                '/api/v1/payments/webhook/',
                data='{}',
                content_type='application/json',
                HTTP_STRIPE_SIGNATURE='t=123,v1=invalid',
            )
        self.assertEqual(resp.status_code, 400)

    def test_missing_webhook_secret_returns_500(self):
        """Missing webhook secret should return 500."""
        with self.settings(STRIPE_WEBHOOK_SECRET=''):
            resp = self.client.post(
                '/api/v1/payments/webhook/',
                data='{}',
                content_type='application/json',
                HTTP_STRIPE_SIGNATURE='t=123,v1=test',
            )
        self.assertEqual(resp.status_code, 500)

    def test_idempotent_tier_update(self):
        """Applying the same tier twice should not cause errors."""
        self.talent.talent_profile.subscription_tier = 'premium'
        self.talent.talent_profile.save()

        resp = self._post_webhook('checkout.session.completed', {
            'metadata': {
                'user_id': str(self.talent.id),
                'plan': 'Premium Pro',
            },
            'subscription': 'sub_idempotent',
        })

        self.assertEqual(resp.status_code, 200)
        self.talent.talent_profile.refresh_from_db()
        self.assertEqual(self.talent.talent_profile.subscription_tier, 'premium')


# ─── Invoice PDF Tests ────────────────────────────────────────────────────────

class InvoicePDFTest(TestCase):
    """Tests for GET /api/v1/payments/invoice/<id>/"""

    def setUp(self):
        self.client = APIClient()
        self.talent = _create_talent(email='invoice@test.com', tier='premium')

    def test_valid_invoice_returns_pdf(self):
        """Valid invoice ID should return a PDF file."""
        self.client.force_authenticate(user=self.talent)
        resp = self.client.get('/api/v1/payments/invoice/INV-2024-001/')

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertIn('TalentOrbit-Invoice', resp['Content-Disposition'])

    def test_invalid_invoice_id_rejected(self):
        """Invoice IDs with special characters should be rejected."""
        self.client.force_authenticate(user=self.talent)
        # Path traversal chars won't match <str:>, so test with SQL-injection-style ID
        resp = self.client.get('/api/v1/payments/invoice/bad@invoice!id/')
        self.assertEqual(resp.status_code, 400)

    def test_unauthenticated_invoice_rejected(self):
        """Unauthenticated users should get 401."""
        resp = self.client.get('/api/v1/payments/invoice/INV-001/')
        self.assertEqual(resp.status_code, 401)


# ─── Customer Portal Tests ───────────────────────────────────────────────────

@override_settings(
    STRIPE_SECRET_KEY='sk_test_fake',
    FRONTEND_URL='http://localhost:5173',
)
class CustomerPortalTest(TestCase):
    """Tests for POST /api/v1/payments/customer-portal/"""

    def setUp(self):
        self.client = APIClient()
        self.talent = _create_talent(email='portal@test.com', tier='premium')

    @patch('payments.views.stripe.billing_portal.Session.create')
    @patch('payments.views.stripe.Customer.list')
    def test_creates_portal_session(self, mock_list, mock_create):
        """Should create a Stripe customer portal session."""
        mock_list.return_value = MagicMock(data=[MagicMock(id='cus_test123')])
        mock_create.return_value = MagicMock(url='https://billing.stripe.com/portal')
        self.client.force_authenticate(user=self.talent)

        resp = self.client.post('/api/v1/payments/customer-portal/')

        self.assertEqual(resp.status_code, 200)
        self.assertIn('billing.stripe.com', resp.data['url'])
        mock_list.assert_called_once_with(email=self.talent.email, limit=1)

    def test_unauthenticated_rejected(self):
        """Unauthenticated users should get 401."""
        resp = self.client.post('/api/v1/payments/customer-portal/')
        self.assertEqual(resp.status_code, 401)
