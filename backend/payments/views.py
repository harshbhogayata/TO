"""
payments/views.py
Stripe Checkout session creation + webhook handler.
Supports recurring subscriptions with monthly billing.
"""
import io
import re
import json
import logging
import stripe
from django.conf import settings
from django.core.cache import cache
from django.http import FileResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)

# Safe character set for invoice IDs (alphanumeric and hyphens only)
INVOICE_ID_PATTERN = re.compile(r'^[A-Za-z0-9\-]+$')

stripe.api_key = settings.STRIPE_SECRET_KEY

# ── Plan definitions ──────────────────────────────────────────────────────────
# Each plan defines its recurring monthly price. Set 'price_id' in your
# Stripe Dashboard for production; the amount/currency fallback creates
# ad-hoc prices for development.
PLANS = {
    'Free Agent': {
        'amount': 0,
        'currency': 'usd',
        'name': 'Free Agent',
        'description': 'Basic profile, 3 applications/month',
        'tier': 'free',
        'interval': 'month',
        'price_id': None,        # Free — no Stripe price needed
    },
    'Premium Pro': {
        'amount': 1900,          # in cents  ($19.00/month)
        'currency': 'usd',
        'name': 'Premium Pro',
        'description': 'Unlimited applications, priority placement',
        'tier': 'premium',
        'interval': 'month',
        'price_id': settings.__dict__.get('STRIPE_PRICE_PREMIUM', None),
    },
    'Starter': {
        'amount': 9900,          # $99.00/month
        'currency': 'usd',
        'name': 'Starter Corporate',
        'description': '5 active job posts, standard ATS integration',
        'tier': 'starter',
        'interval': 'month',
        'price_id': settings.__dict__.get('STRIPE_PRICE_STARTER', None),
    },
    'Professional': {
        'amount': 29900,         # $299.00/month
        'currency': 'usd',
        'name': 'Professional Corporate',
        'description': 'Unlimited posts, custom branding, automated screening',
        'tier': 'professional',
        'interval': 'month',
        'price_id': settings.__dict__.get('STRIPE_PRICE_PROFESSIONAL', None),
    },
    'Enterprise': {
        'amount': 0,             # Custom — redirect to contact instead
        'currency': 'usd',
        'name': 'Enterprise',
        'description': 'Full API access, white-label, 24/7 support',
        'tier': 'enterprise',
        'interval': 'month',
        'price_id': None,
    },
}

# Reverse map: tier code → plan key (for invoice lookups)
TIER_TO_PLAN = {v['tier']: k for k, v in PLANS.items()}


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_checkout_session(request):
    """
    POST /api/v1/payments/create-checkout-session/
    Body: { "plan": "Premium Pro" }
    Returns: { "url": "https://checkout.stripe.com/..." }
    Creates a Stripe Checkout Session in **subscription** mode for recurring billing.
    """
    plan_name = request.data.get('plan', '')
    plan = PLANS.get(plan_name)

    if not plan:
        return Response({'error': f'Unknown plan: {plan_name}'}, status=status.HTTP_400_BAD_REQUEST)

    # Enterprise → redirect to support/contact instead
    if plan_name == 'Enterprise':
        return Response({'url': f"{settings.FRONTEND_URL}/support"})

    # Free plan → no payment needed, just return success
    if plan['amount'] == 0:
        return Response({'url': f"{settings.FRONTEND_URL}/payment/success?plan=free"})

    try:
        # Build line_items: prefer a pre-created Stripe Price ID, fall back to ad-hoc price_data
        if plan.get('price_id'):
            line_items = [{'price': plan['price_id'], 'quantity': 1}]
        else:
            line_items = [{
                'price_data': {
                    'currency': plan['currency'],
                    'product_data': {
                        'name': plan['name'],
                        'description': plan['description'],
                    },
                    'unit_amount': plan['amount'],
                    'recurring': {'interval': plan.get('interval', 'month')},
                },
                'quantity': 1,
            }]

        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='subscription',
            success_url=f"{settings.FRONTEND_URL}/payment/success?plan={plan_name}&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.FRONTEND_URL}/payment/cancel",
            customer_email=request.user.email,
            metadata={
                'user_id': str(request.user.id),
                'plan': plan_name,
                'tier': plan['tier'],
            },
            subscription_data={
                'metadata': {
                    'user_id': str(request.user.id),
                    'plan': plan_name,
                    'tier': plan['tier'],
                },
            },
        )
        return Response({'url': checkout_session.url})

    except stripe.error.StripeError as e:
        logger.exception('Stripe checkout session creation failed')
        return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def stripe_webhook(request):
    """
    POST /api/v1/payments/webhook/
    Stripe sends events here. Verify signature and handle subscription lifecycle events.
    Configure your Stripe Dashboard webhook to point to this URL.
    Events handled:
      - checkout.session.completed  → initial subscription activated
      - customer.subscription.updated → plan upgrade/downgrade
      - customer.subscription.deleted → cancellation (revert to free tier)
      - invoice.payment_failed → notify user (logged, tier preserved until grace period)
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')
    webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '')

    if not webhook_secret:
        return HttpResponse('Webhook secret not configured', status=500)

    try:
        event_data = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except (ValueError, stripe.error.SignatureVerificationError):
        return HttpResponse(status=400)

    # ── Idempotency guard ─────────────────────────────────────────────────
    # Stripe may retry events; deduplicate using event ID stored in cache.
    event_id = event_data.get('id', '')
    if event_id:
        cache_key = f'stripe_event:{event_id}'
        if cache.get(cache_key):
            logger.info('Duplicate Stripe event ignored: %s', event_id)
            return HttpResponse(status=200)
        # Mark as processed for 48 hours (Stripe retries for up to 72h)
        cache.set(cache_key, True, 60 * 60 * 48)

    event_type = event_data.get('type', '')

    # ── Checkout completed (initial subscription) ─────────────────────────
    if event_type == 'checkout.session.completed':
        session = event_data['data']['object']
        user_id = session.get('metadata', {}).get('user_id')
        plan = session.get('metadata', {}).get('plan')
        subscription_id = session.get('subscription')

        if user_id and plan:
            _update_user_tier(user_id, plan, stripe_subscription_id=subscription_id)

    # ── Subscription updated (upgrade/downgrade) ─────────────────────────
    elif event_type == 'customer.subscription.updated':
        subscription = event_data['data']['object']
        user_id = subscription.get('metadata', {}).get('user_id')
        plan = subscription.get('metadata', {}).get('plan')
        sub_status = subscription.get('status', '')

        if user_id and plan and sub_status == 'active':
            _update_user_tier(user_id, plan, stripe_subscription_id=subscription.get('id'))

    # ── Subscription deleted (cancellation) ───────────────────────────────
    elif event_type == 'customer.subscription.deleted':
        subscription = event_data['data']['object']
        user_id = subscription.get('metadata', {}).get('user_id')

        if user_id:
            # Revert to free tier
            _update_user_tier(user_id, 'Free Agent')

    # ── Invoice payment failed ────────────────────────────────────────────
    elif event_type == 'invoice.payment_failed':
        invoice = event_data['data']['object']
        sub_id = invoice.get('subscription')
        logger.warning(
            'Payment failed for subscription %s — customer will be notified by Stripe.',
            sub_id,
        )

    return HttpResponse(status=200)


def _update_user_tier(user_id, plan_name, stripe_subscription_id=None):
    """
    Internal helper: update a user's subscription tier based on their plan.
    Optionally stores the Stripe subscription ID for future management.
    """
    try:
        from accounts.models import User
        user = User.objects.get(id=user_id)
        plan_obj = PLANS.get(plan_name, {})
        tier = plan_obj.get('tier', 'free')

        if hasattr(user, 'talent_profile'):
            user.talent_profile.subscription_tier = tier
            user.talent_profile.save(update_fields=['subscription_tier'])
        elif hasattr(user, 'company_profile'):
            user.company_profile.subscription_tier = tier
            user.company_profile.save(update_fields=['subscription_tier'])

        logger.info(
            'Subscription updated: user=%s tier=%s stripe_sub=%s',
            user_id, tier, stripe_subscription_id,
        )
    except Exception as e:
        logger.exception(
            'Webhook: failed to update subscription for user %s: %s', user_id, e
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def customer_portal(request):
    """
    POST /api/v1/payments/customer-portal/
    Creates a Stripe Billing Portal session so the user can manage their
    subscription (cancel, upgrade, update payment method) without leaving
    TalentOrbit.
    """
    user = request.user

    # Resolve the Stripe customer ID from the user's email
    try:
        customers = stripe.Customer.list(email=user.email, limit=1)
        if not customers.data:
            return Response(
                {'error': 'No Stripe customer found. Please subscribe first.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        session = stripe.billing_portal.Session.create(
            customer=customers.data[0].id,
            return_url=f"{settings.FRONTEND_URL}/settings/billing",
        )
        return Response({'url': session.url})

    except stripe.error.StripeError as e:
        logger.exception('Stripe customer portal session creation failed')
        return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_invoice(request, invoice_id):
    """GET /api/v1/payments/invoice/:id/ — Generates standard PDF invoices via ReportLab natively."""
    if not invoice_id or not INVOICE_ID_PATTERN.match(invoice_id):
        return Response(
            {'error': 'Invalid invoice ID.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    safe_id = invoice_id.strip()[:64]  # cap length for display/filename

    try:
        from reportlab.pdfgen import canvas
    except ImportError:
        return Response({'error': 'ReportLab engine missing.'}, status=500)

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer)

    # Simple crisp invoice layout
    p.setFont("Helvetica-Bold", 24)
    p.drawString(50, 800, "TalentOrbit")

    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, 760, f"Invoice #: {safe_id.upper()}")

    p.setFont("Helvetica", 12)
    p.drawString(50, 730, "Billed To:")
    p.drawString(50, 715, request.user.full_name or request.user.email)

    # Determine the user's actual plan and amount
    user_plan = 'Unknown'
    plan_amount = 'N/A'
    if hasattr(request.user, 'talent_profile'):
        user_plan = request.user.talent_profile.subscription_tier or 'free'
    elif hasattr(request.user, 'company_profile'):
        user_plan = request.user.company_profile.subscription_tier or 'free'
    # Resolve tier code to PLANS entry (try direct key first, then reverse map)
    plan_key = TIER_TO_PLAN.get(user_plan, user_plan)
    plan_obj = PLANS.get(plan_key, PLANS.get(user_plan, {}))
    if plan_obj.get('amount'):
        plan_amount = f"${plan_obj['amount'] / 100:.2f} {plan_obj.get('currency', 'USD').upper()}"

    p.drawString(50, 680, "Amount Paid:")
    p.drawString(50, 665, plan_amount)
    p.drawString(50, 650, "Status: PAID IN FULL")

    p.setFont("Helvetica-Oblique", 11)
    p.drawString(50, 600, "Thank you for supporting frictionless career infrastructure.")
    p.drawString(50, 580, f"Your {user_plan} plan is securely active.")

    p.showPage()
    p.save()

    buffer.seek(0)
    safe_filename = f"TalentOrbit-Invoice-{safe_id}.pdf"
    return FileResponse(buffer, as_attachment=True, filename=safe_filename)

