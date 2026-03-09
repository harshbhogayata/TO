"""
payments/views.py
Enterprise-grade payment, subscription, referral, CRM, and revenue API.

Stripe Checkout + webhook handler with CustomerProfile persistence,
dunning integration, referral tracking, sponsored campaigns, talent
pool CRM, and revenue dashboard.
"""
import io
import re
import json
import logging
import secrets
import stripe
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache
from django.db import models, transaction
from django.db.models import Sum, Count, Q, F, Avg
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from accounts.permissions import IsCompanyUser, IsEmailVerified
from compliance.constants import AuditAction, AuditCategory
from compliance.decorators import audit_action, create_audit_log
from payments.idempotency import idempotent

from .models import (
    SubscriptionPlan,
    CustomerProfile,
    PaymentHistory,
    Invoice,
    Coupon,
    CouponRedemption,
    ReferralProgram,
    Referral,
    ReferralReward,
    SponsoredJobCampaign,
    TalentPoolPipeline,
    TalentPoolCandidate,
)
from .serializers import (
    SubscriptionPlanSerializer,
    CustomerProfileSerializer,
    PaymentHistorySerializer,
    InvoiceSerializer,
    CouponSerializer,
    CouponValidateSerializer,
    ReferralProgramSerializer,
    ReferralSerializer,
    ReferralCreateSerializer,
    ReferralRewardSerializer,
    ReferralStatsSerializer,
    SponsoredJobCampaignSerializer,
    TalentPoolPipelineSerializer,
    TalentPoolCandidateSerializer,
    TalentPoolCandidateMoveSerializer,
    TalentPoolCandidateBulkMoveSerializer,
    RevenueDashboardSerializer,
)

logger = logging.getLogger(__name__)

INVOICE_ID_PATTERN = re.compile(r'^[A-Za-z0-9\-]+$')

stripe.api_key = settings.STRIPE_SECRET_KEY

# Legacy plan map (kept for backward compatibility with existing Stripe metadata)
PLANS = {
    'Free Agent': {'amount': 0, 'currency': 'usd', 'tier': 'free'},
    'Premium Pro': {'amount': 1900, 'currency': 'usd', 'tier': 'premium'},
    'Starter': {'amount': 9900, 'currency': 'usd', 'tier': 'starter'},
    'Professional': {'amount': 29900, 'currency': 'usd', 'tier': 'professional'},
    'Enterprise': {'amount': 0, 'currency': 'usd', 'tier': 'enterprise'},
}
TIER_TO_PLAN = {v['tier']: k for k, v in PLANS.items()}


class PaymentCheckoutThrottle(ScopedRateThrottle):
    scope = 'payment_checkout'


class PaymentPortalThrottle(ScopedRateThrottle):
    scope = 'payment_portal'


# ═══════════════════════════════════════════════════════════════════════════════
# SUBSCRIPTION PLANS — Public catalog
# ═══════════════════════════════════════════════════════════════════════════════

class SubscriptionPlanListView(generics.ListAPIView):
    """GET /api/v1/payments/plans/ — Public plan catalog."""
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = SubscriptionPlan.objects.filter(is_active=True)
        audience = self.request.query_params.get('audience')
        if audience:
            qs = qs.filter(audience=audience.upper())
        return qs


# ═══════════════════════════════════════════════════════════════════════════════
# BILLING — Customer profile, payment history, invoices
# ═══════════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def billing_overview(request):
    """
    GET /api/v1/payments/billing/
    Returns the user's billing overview: current plan, payment history, invoices.
    """
    customer, _ = CustomerProfile.objects.get_or_create(user=request.user)
    return Response({
        'subscription': CustomerProfileSerializer(customer).data,
        'payment_history': PaymentHistorySerializer(
            customer.payment_history.all()[:20], many=True,
        ).data,
        'invoices': InvoiceSerializer(
            customer.invoices.all()[:20], many=True,
        ).data,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@idempotent(timeout=86400)
@audit_action(
    action=AuditAction.SUBSCRIPTION_CREATE,
    category=AuditCategory.PAYMENT,
    description='Created checkout session',
    resource_type='payments.CustomerProfile',
)
@transaction.atomic
def create_checkout_session(request):
    """
    POST /api/v1/payments/create-checkout-session/
    Body: { "plan_id": "<uuid>" } or { "plan": "Premium Pro" }
    Returns: { "url": "https://checkout.stripe.com/..." }
    """
    plan_id = request.data.get('plan_id')
    plan_name = request.data.get('plan')
    coupon_code = request.data.get('coupon_code')

    # Resolve plan
    plan_obj = None
    if plan_id:
        try:
            plan_obj = SubscriptionPlan.objects.get(pk=plan_id, is_active=True)
        except SubscriptionPlan.DoesNotExist:
            return Response({'error': 'Plan not found.'}, status=status.HTTP_404_NOT_FOUND)
    elif plan_name:
        plan_data = PLANS.get(plan_name)
        if not plan_data:
            return Response({'error': f'Unknown plan: {plan_name}'}, status=status.HTTP_400_BAD_REQUEST)
        if plan_name == 'Enterprise':
            return Response({'url': f"{settings.FRONTEND_URL}/support"})
        if plan_data['amount'] == 0:
            return Response({'url': f"{settings.FRONTEND_URL}/payment/success?plan=free"})
    else:
        return Response({'error': 'Provide plan_id or plan.'}, status=status.HTTP_400_BAD_REQUEST)

    # Ensure CustomerProfile exists
    customer, _ = CustomerProfile.objects.get_or_create(user=request.user)

    try:
        checkout_params = {
            'payment_method_types': ['card'],
            'mode': 'subscription',
            'success_url': f"{settings.FRONTEND_URL}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
            'cancel_url': f"{settings.FRONTEND_URL}/payment/cancel",
            'customer_email': request.user.email,
            'metadata': {
                'user_id': str(request.user.id),
                'customer_profile_id': str(customer.pk),
            },
        }

        if plan_obj and plan_obj.stripe_price_id:
            checkout_params['line_items'] = [{'price': plan_obj.stripe_price_id, 'quantity': 1}]
            checkout_params['metadata']['plan_id'] = str(plan_obj.pk)
            checkout_params['metadata']['plan_name'] = plan_obj.name
            checkout_params['metadata']['tier'] = plan_obj.slug
        elif plan_name:
            plan_data = PLANS[plan_name]
            checkout_params['line_items'] = [{
                'price_data': {
                    'currency': plan_data['currency'],
                    'product_data': {'name': plan_name},
                    'unit_amount': plan_data['amount'],
                    'recurring': {'interval': 'month'},
                },
                'quantity': 1,
            }]
            checkout_params['metadata']['plan'] = plan_name
            checkout_params['metadata']['tier'] = plan_data['tier']

        checkout_params['subscription_data'] = {'metadata': checkout_params['metadata']}

        if coupon_code:
            try:
                coupon = Coupon.objects.get(code__iexact=coupon_code)
                if coupon.is_valid and coupon.stripe_coupon_id:
                    checkout_params['discounts'] = [{'coupon': coupon.stripe_coupon_id}]
            except Coupon.DoesNotExist:
                pass

        if customer.stripe_customer_id:
            checkout_params.pop('customer_email', None)
            checkout_params['customer'] = customer.stripe_customer_id

        session = stripe.checkout.Session.create(**checkout_params)
        return Response({'url': session.url})

    except stripe.error.StripeError as e:
        logger.exception('Stripe checkout session creation failed')
        return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def stripe_webhook(request):
    """
    POST /api/v1/payments/webhook/
    Handles Stripe subscription lifecycle events with full model persistence.
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

    event_id = event_data.get('id', '')
    if event_id:
        cache_key = f'stripe_event:{event_id}'
        if cache.get(cache_key):
            return HttpResponse(status=200)
        cache.set(cache_key, True, 60 * 60 * 48)

    event_type = event_data.get('type', '')

    if event_type == 'checkout.session.completed':
        _handle_checkout_completed(event_data)
    elif event_type == 'customer.subscription.updated':
        _handle_subscription_updated(event_data)
    elif event_type == 'customer.subscription.deleted':
        _handle_subscription_deleted(event_data)
    elif event_type == 'invoice.paid':
        _handle_invoice_paid(event_data)
    elif event_type == 'invoice.payment_failed':
        _handle_invoice_payment_failed(event_data)

    return HttpResponse(status=200)


def _get_or_create_customer(user_id, stripe_customer_id=''):
    """Get or create a CustomerProfile for the given user."""
    from accounts.models import User
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return None

    customer, created = CustomerProfile.objects.get_or_create(user=user)
    if stripe_customer_id and not customer.stripe_customer_id:
        customer.stripe_customer_id = stripe_customer_id
        customer.save(update_fields=['stripe_customer_id', 'updated_at'])
    return customer


@transaction.atomic
def _handle_checkout_completed(event_data):
    """Handle checkout.session.completed — activate subscription."""
    session = event_data['data']['object']
    metadata = session.get('metadata', {})
    user_id = metadata.get('user_id')
    plan_name = metadata.get('plan_name') or metadata.get('plan', '')
    plan_id = metadata.get('plan_id')
    tier = metadata.get('tier', 'free')

    if not user_id:
        return

    customer = _get_or_create_customer(
        user_id, stripe_customer_id=session.get('customer', ''),
    )
    if not customer:
        return

    # Lock CustomerProfile row to prevent concurrent webhook race conditions
    customer = CustomerProfile.objects.select_for_update().get(pk=customer.pk)

    subscription_id = session.get('subscription', '')
    customer.stripe_subscription_id = subscription_id
    customer.subscription_status = 'active'
    customer.grace_period_end = None
    customer.failed_payment_count = 0
    customer.last_payment_failure_at = None

    if plan_id:
        try:
            customer.current_plan = SubscriptionPlan.objects.get(pk=plan_id)
        except SubscriptionPlan.DoesNotExist:
            pass

    customer.save(update_fields=[
        'stripe_subscription_id', 'subscription_status', 'current_plan',
        'grace_period_end', 'failed_payment_count', 'last_payment_failure_at',
        'updated_at',
    ])

    _update_user_tier(user_id, plan_name or tier, stripe_subscription_id=subscription_id)

    PaymentHistory.objects.create(
        customer=customer,
        event_type='checkout.completed',
        stripe_event_id=event_data.get('id', f'evt_{secrets.token_hex(8)}'),
        amount=Decimal(str(session.get('amount_total', 0))) / 100,
        currency=session.get('currency', 'usd'),
        status='completed',
        metadata=metadata,
    )

    _track_referral_subscription(customer.user)

    create_audit_log(
        actor=customer.user,
        action=AuditAction.SUBSCRIPTION_CREATE,
        category=AuditCategory.PAYMENT,
        description=f'Subscription activated: {plan_name or tier}',
        resource_type='payments.CustomerProfile',
        resource_id=str(customer.pk),
    )


@transaction.atomic
def _handle_subscription_updated(event_data):
    """Handle customer.subscription.updated — plan upgrade/downgrade."""
    subscription = event_data['data']['object']
    metadata = subscription.get('metadata', {})
    user_id = metadata.get('user_id')

    if not user_id:
        return

    customer = _get_or_create_customer(user_id)
    if not customer:
        return

    # Lock CustomerProfile row to prevent concurrent webhook race conditions
    customer = CustomerProfile.objects.select_for_update().get(pk=customer.pk)

    sub_status = subscription.get('status', '')
    customer.subscription_status = sub_status
    customer.current_period_start = timezone.datetime.fromtimestamp(
        subscription.get('current_period_start', 0), tz=timezone.utc,
    ) if subscription.get('current_period_start') else None
    customer.current_period_end = timezone.datetime.fromtimestamp(
        subscription.get('current_period_end', 0), tz=timezone.utc,
    ) if subscription.get('current_period_end') else None
    customer.cancel_at_period_end = subscription.get('cancel_at_period_end', False)
    customer.save(update_fields=[
        'subscription_status', 'current_period_start', 'current_period_end',
        'cancel_at_period_end', 'updated_at',
    ])

    if sub_status == 'active':
        plan_name = metadata.get('plan_name') or metadata.get('plan', '')
        _update_user_tier(user_id, plan_name, stripe_subscription_id=subscription.get('id'))

    PaymentHistory.objects.create(
        customer=customer,
        event_type='subscription.updated',
        stripe_event_id=event_data.get('id', f'evt_{secrets.token_hex(8)}'),
        status=sub_status,
        metadata=metadata,
    )


@transaction.atomic
def _handle_subscription_deleted(event_data):
    """Handle customer.subscription.deleted — revert to free tier."""
    subscription = event_data['data']['object']
    metadata = subscription.get('metadata', {})
    user_id = metadata.get('user_id')

    if not user_id:
        return

    customer = _get_or_create_customer(user_id)
    if not customer:
        return

    # Lock CustomerProfile row to prevent concurrent webhook race conditions
    customer = CustomerProfile.objects.select_for_update().get(pk=customer.pk)

    customer.subscription_status = 'canceled'
    customer.stripe_subscription_id = ''
    customer.cancel_at_period_end = False
    customer.save(update_fields=[
        'subscription_status', 'stripe_subscription_id', 'cancel_at_period_end', 'updated_at',
    ])

    _update_user_tier(user_id, 'Free Agent')

    PaymentHistory.objects.create(
        customer=customer,
        event_type='subscription.deleted',
        stripe_event_id=event_data.get('id', f'evt_{secrets.token_hex(8)}'),
        metadata=metadata,
    )

    create_audit_log(
        actor=customer.user,
        action=AuditAction.SUBSCRIPTION_CANCEL,
        category=AuditCategory.PAYMENT,
        description='Subscription canceled',
        resource_type='payments.CustomerProfile',
        resource_id=str(customer.pk),
    )


@transaction.atomic
def _handle_invoice_paid(event_data):
    """Handle invoice.paid — record invoice and payment."""
    invoice_obj = event_data['data']['object']
    customer_id = invoice_obj.get('customer', '')
    customer = CustomerProfile.objects.select_for_update().filter(
        stripe_customer_id=customer_id,
    ).first()
    if not customer:
        return

    if customer.failed_payment_count > 0:
        customer.end_grace_period()
        customer.subscription_status = 'active'
        customer.save(update_fields=['subscription_status', 'updated_at'])

    Invoice.objects.update_or_create(
        stripe_invoice_id=invoice_obj.get('id', ''),
        defaults={
            'customer': customer,
            'number': invoice_obj.get('number', ''),
            'status': 'paid',
            'amount_due': Decimal(str(invoice_obj.get('amount_due', 0))) / 100,
            'amount_paid': Decimal(str(invoice_obj.get('amount_paid', 0))) / 100,
            'currency': invoice_obj.get('currency', 'usd'),
            'stripe_hosted_invoice_url': invoice_obj.get('hosted_invoice_url', ''),
            'stripe_pdf_url': invoice_obj.get('invoice_pdf', ''),
            'paid_at': timezone.now(),
        },
    )

    PaymentHistory.objects.create(
        customer=customer,
        event_type='invoice.paid',
        stripe_event_id=event_data.get('id', f'evt_{secrets.token_hex(8)}'),
        stripe_invoice_id=invoice_obj.get('id', ''),
        amount=Decimal(str(invoice_obj.get('amount_paid', 0))) / 100,
        currency=invoice_obj.get('currency', 'usd'),
        status='paid',
    )


@transaction.atomic
def _handle_invoice_payment_failed(event_data):
    """Handle invoice.payment_failed — start dunning flow."""
    invoice_obj = event_data['data']['object']
    customer_id = invoice_obj.get('customer', '')
    customer = CustomerProfile.objects.select_for_update().filter(
        stripe_customer_id=customer_id,
    ).first()
    if not customer:
        logger.warning('Payment failed for unknown Stripe customer: %s', customer_id)
        return

    PaymentHistory.objects.create(
        customer=customer,
        event_type='invoice.payment_failed',
        stripe_event_id=event_data.get('id', f'evt_{secrets.token_hex(8)}'),
        stripe_invoice_id=invoice_obj.get('id', ''),
        amount=Decimal(str(invoice_obj.get('amount_due', 0))) / 100,
        currency=invoice_obj.get('currency', 'usd'),
        status='failed',
        failure_reason=str(invoice_obj.get('last_finalization_error', '')),
    )

    from payments.tasks import handle_payment_failure
    handle_payment_failure.delay(
        customer_profile_id=str(customer.pk),
        stripe_event_id=event_data.get('id', ''),
    )

    create_audit_log(
        actor=customer.user,
        action=AuditAction.PAYMENT_FAILED,
        category=AuditCategory.PAYMENT,
        description=f'Invoice payment failed (attempt #{customer.failed_payment_count + 1})',
        resource_type='payments.CustomerProfile',
        resource_id=str(customer.pk),
    )


def _update_user_tier(user_id, plan_name, stripe_subscription_id=None):
    """Legacy helper: update a user's subscription tier from plan name."""
    try:
        from accounts.models import User
        user = User.objects.get(id=user_id)
        plan_data = PLANS.get(plan_name, {})
        tier = plan_data.get('tier', plan_name.lower() if plan_name else 'free')

        if hasattr(user, 'talent_profile'):
            user.talent_profile.subscription_tier = tier
            user.talent_profile.save(update_fields=['subscription_tier'])
        elif hasattr(user, 'company_profile'):
            user.company_profile.subscription_tier = tier
            user.company_profile.save(update_fields=['subscription_tier'])

        logger.info('Tier updated: user=%s tier=%s', user_id, tier)
    except Exception as e:
        logger.exception('Failed to update tier for user %s: %s', user_id, e)


def _track_referral_subscription(user):
    """Track that a referred user has subscribed."""
    referral = Referral.objects.filter(referee=user, status='signed_up').first()
    if referral:
        referral.status = 'subscribed'
        referral.subscribed_at = timezone.now()
        referral.save(update_fields=['status', 'subscribed_at', 'updated_at'])


# ═══════════════════════════════════════════════════════════════════════════════
# CUSTOMER PORTAL
# ═══════════════════════════════════════════════════════════════════════════════

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def customer_portal(request):
    """POST /api/v1/payments/customer-portal/ — Stripe Billing Portal."""
    customer = CustomerProfile.objects.filter(user=request.user).first()

    try:
        stripe_customer_id = None
        if customer and customer.stripe_customer_id:
            stripe_customer_id = customer.stripe_customer_id
        else:
            customers = stripe.Customer.list(email=request.user.email, limit=1)
            if customers.data:
                stripe_customer_id = customers.data[0].id
                if customer:
                    customer.stripe_customer_id = stripe_customer_id
                    customer.save(update_fields=['stripe_customer_id', 'updated_at'])

        if not stripe_customer_id:
            return Response(
                {'error': 'No Stripe customer found. Please subscribe first.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        session = stripe.billing_portal.Session.create(
            customer=stripe_customer_id,
            return_url=f"{settings.FRONTEND_URL}/billing",
        )
        return Response({'url': session.url})

    except stripe.error.StripeError as e:
        logger.exception('Stripe customer portal session creation failed')
        return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)


# ═══════════════════════════════════════════════════════════════════════════════
# INVOICE PDF DOWNLOAD
# ═══════════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_invoice(request, invoice_id):
    """GET /api/v1/payments/invoice/:id/ — PDF invoice download."""
    if not invoice_id or not INVOICE_ID_PATTERN.match(invoice_id):
        return Response({'error': 'Invalid invoice ID.'}, status=status.HTTP_400_BAD_REQUEST)

    safe_id = invoice_id.strip()[:64]

    invoice = Invoice.objects.filter(
        Q(stripe_invoice_id=safe_id) | Q(number=safe_id),
        customer__user=request.user,
    ).first()

    if invoice and invoice.stripe_pdf_url:
        return Response({'url': invoice.stripe_pdf_url})

    try:
        from reportlab.pdfgen import canvas
    except ImportError:
        return Response({'error': 'ReportLab engine missing.'}, status=500)

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer)
    p.setFont("Helvetica-Bold", 24)
    p.drawString(50, 800, "TalentOrbit")
    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, 760, f"Invoice #: {safe_id.upper()}")
    p.setFont("Helvetica", 12)
    p.drawString(50, 730, "Billed To:")
    p.drawString(50, 715, request.user.full_name or request.user.email)

    if invoice:
        p.drawString(50, 680, f"Amount Due: ${invoice.amount_due}")
        p.drawString(50, 665, f"Amount Paid: ${invoice.amount_paid}")
        p.drawString(50, 650, f"Status: {invoice.status.upper()}")
    else:
        user_plan = 'Unknown'
        plan_amount = 'N/A'
        if hasattr(request.user, 'talent_profile'):
            user_plan = request.user.talent_profile.subscription_tier or 'free'
        elif hasattr(request.user, 'company_profile'):
            user_plan = request.user.company_profile.subscription_tier or 'free'
        plan_key = TIER_TO_PLAN.get(user_plan, user_plan)
        plan_data = PLANS.get(plan_key, PLANS.get(user_plan, {}))
        if plan_data.get('amount'):
            plan_amount = f"${plan_data['amount'] / 100:.2f} USD"
        p.drawString(50, 680, f"Amount Paid: {plan_amount}")
        p.drawString(50, 665, "Status: PAID IN FULL")

    p.setFont("Helvetica-Oblique", 11)
    p.drawString(50, 620, "Thank you for supporting frictionless career infrastructure.")
    p.showPage()
    p.save()

    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename=f"TalentOrbit-Invoice-{safe_id}.pdf")


# ═══════════════════════════════════════════════════════════════════════════════
# COUPONS
# ═══════════════════════════════════════════════════════════════════════════════

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def validate_coupon(request):
    """POST /api/v1/payments/coupons/validate/ — Check if a coupon code is valid."""
    serializer = CouponValidateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    code = serializer.validated_data['code']
    try:
        coupon = Coupon.objects.get(code__iexact=code)
    except Coupon.DoesNotExist:
        return Response({'valid': False, 'error': 'Coupon not found.'}, status=status.HTTP_404_NOT_FOUND)

    if not coupon.is_valid:
        return Response({'valid': False, 'error': 'Coupon has expired or reached max redemptions.'})

    if CouponRedemption.objects.filter(coupon=coupon, user=request.user).exists():
        return Response({'valid': False, 'error': 'You have already used this coupon.'})

    return Response({'valid': True, 'coupon': CouponSerializer(coupon).data})


# ═══════════════════════════════════════════════════════════════════════════════
# REFERRAL PROGRAM
# ═══════════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def referral_program(request):
    """GET /api/v1/payments/referrals/program/ — Active referral program details."""
    user_role = request.user.role
    audience = 'TALENT' if user_role == 'TALENT' else 'COMPANY'
    program = ReferralProgram.objects.filter(audience=audience, is_active=True).first()
    if not program:
        return Response({'program': None})
    return Response({'program': ReferralProgramSerializer(program).data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_referral_stats(request):
    """GET /api/v1/payments/referrals/stats/ — User's referral statistics."""
    referrals = Referral.objects.filter(referrer=request.user)
    rewards = ReferralReward.objects.filter(recipient=request.user, is_paid=True)

    active_referral = referrals.exclude(status__in=['expired', 'fraudulent']).first()
    referral_code = active_referral.referral_code if active_referral else ''

    if not referral_code:
        user_role = request.user.role
        audience = 'TALENT' if user_role == 'TALENT' else 'COMPANY'
        program = ReferralProgram.objects.filter(audience=audience, is_active=True).first()
        if program:
            referral_code = f'{request.user.email[:4].upper()}{secrets.token_hex(4).upper()}'
            Referral.objects.create(
                program=program,
                referrer=request.user,
                referral_code=referral_code,
                expires_at=timezone.now() + timedelta(days=365),
            )

    data = {
        'total_referrals': referrals.count(),
        'pending': referrals.filter(status__in=['pending', 'signed_up', 'subscribed']).count(),
        'qualified': referrals.filter(status='qualified').count(),
        'rewarded': referrals.filter(status='rewarded').count(),
        'total_earned': str(rewards.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')),
        'referral_code': referral_code,
    }
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_referrals(request):
    """GET /api/v1/payments/referrals/ — List user's referrals."""
    referrals = Referral.objects.filter(referrer=request.user).order_by('-created_at')
    return Response(ReferralSerializer(referrals, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@idempotent(timeout=86400)
@transaction.atomic
def create_referral(request):
    """POST /api/v1/payments/referrals/ — Generate new referral link."""
    serializer = ReferralCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    user_role = request.user.role
    audience = 'TALENT' if user_role == 'TALENT' else 'COMPANY'
    program = ReferralProgram.objects.filter(audience=audience, is_active=True).first()

    if not program:
        return Response({'error': 'No active referral program.'}, status=status.HTTP_404_NOT_FOUND)

    active_count = Referral.objects.filter(
        referrer=request.user, program=program,
    ).exclude(status__in=['expired', 'fraudulent']).count()

    if active_count >= program.max_referrals_per_user:
        return Response(
            {'error': f'Maximum referrals ({program.max_referrals_per_user}) reached.'},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    referral_code = f'{request.user.email[:4].upper()}{secrets.token_hex(4).upper()}'
    referral = Referral.objects.create(
        program=program,
        referrer=request.user,
        referral_code=referral_code,
        referee_email=serializer.validated_data.get('referee_email', ''),
        expires_at=timezone.now() + timedelta(days=90),
    )

    return Response(ReferralSerializer(referral).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_referral_rewards(request):
    """GET /api/v1/payments/referrals/rewards/ — Earned referral rewards."""
    rewards = ReferralReward.objects.filter(recipient=request.user).order_by('-created_at')
    return Response(ReferralRewardSerializer(rewards, many=True).data)


# ═══════════════════════════════════════════════════════════════════════════════
# SPONSORED JOB CAMPAIGNS
# ═══════════════════════════════════════════════════════════════════════════════

class SponsoredCampaignListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/payments/sponsored/"""
    serializer_class = SponsoredJobCampaignSerializer
    permission_classes = [IsAuthenticated, IsCompanyUser, IsEmailVerified]

    def get_queryset(self):
        return SponsoredJobCampaign.objects.filter(company=self.request.user).select_related('job')

    def perform_create(self, serializer):
        serializer.save(company=self.request.user)


class SponsoredCampaignDetailView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/v1/payments/sponsored/<id>/"""
    serializer_class = SponsoredJobCampaignSerializer
    permission_classes = [IsAuthenticated, IsCompanyUser, IsEmailVerified]
    lookup_field = 'pk'

    def get_queryset(self):
        return SponsoredJobCampaign.objects.filter(company=self.request.user)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsCompanyUser, IsEmailVerified])
@transaction.atomic
def toggle_campaign_status(request, pk):
    """POST /api/v1/payments/sponsored/<id>/toggle/"""
    campaign = get_object_or_404(SponsoredJobCampaign, pk=pk, company=request.user)

    if campaign.status == 'active':
        campaign.status = 'paused'
    elif campaign.status == 'paused':
        campaign.status = 'active'
    else:
        return Response({'error': f'Cannot toggle campaign in {campaign.status} status.'}, status=status.HTTP_400_BAD_REQUEST)

    campaign.save(update_fields=['status', 'updated_at'])
    return Response(SponsoredJobCampaignSerializer(campaign).data)


# ═══════════════════════════════════════════════════════════════════════════════
# TALENT POOL CRM
# ═══════════════════════════════════════════════════════════════════════════════

class TalentPoolPipelineListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/payments/pipelines/"""
    serializer_class = TalentPoolPipelineSerializer
    permission_classes = [IsAuthenticated, IsCompanyUser, IsEmailVerified]

    def get_queryset(self):
        return TalentPoolPipeline.objects.filter(company=self.request.user, is_archived=False)

    def perform_create(self, serializer):
        pipeline = serializer.save(company=self.request.user)
        if not pipeline.stages:
            pipeline.stages = pipeline.get_default_stages()
            pipeline.save(update_fields=['stages'])


class TalentPoolPipelineDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET/PATCH/DELETE /api/v1/payments/pipelines/<id>/"""
    serializer_class = TalentPoolPipelineSerializer
    permission_classes = [IsAuthenticated, IsCompanyUser, IsEmailVerified]
    lookup_field = 'pk'

    def get_queryset(self):
        return TalentPoolPipeline.objects.filter(company=self.request.user)

    def perform_destroy(self, instance):
        instance.is_archived = True
        instance.save(update_fields=['is_archived', 'updated_at'])


class TalentPoolCandidateListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/payments/pipelines/<pipeline_pk>/candidates/"""
    serializer_class = TalentPoolCandidateSerializer
    permission_classes = [IsAuthenticated, IsCompanyUser, IsEmailVerified]

    def get_queryset(self):
        pipeline_pk = self.kwargs['pipeline_pk']
        qs = TalentPoolCandidate.objects.filter(
            pipeline_id=pipeline_pk, pipeline__company=self.request.user,
        ).select_related('user', 'application', 'added_by')
        stage_id = self.request.query_params.get('stage_id')
        if stage_id:
            qs = qs.filter(stage_id=stage_id)
        return qs

    def perform_create(self, serializer):
        pipeline = get_object_or_404(
            TalentPoolPipeline, pk=self.kwargs['pipeline_pk'], company=self.request.user,
        )
        serializer.save(pipeline=pipeline, added_by=self.request.user)


class TalentPoolCandidateDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET/PATCH/DELETE /api/v1/payments/candidates/<id>/"""
    serializer_class = TalentPoolCandidateSerializer
    permission_classes = [IsAuthenticated, IsCompanyUser, IsEmailVerified]
    lookup_field = 'pk'

    def get_queryset(self):
        return TalentPoolCandidate.objects.filter(pipeline__company=self.request.user)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsCompanyUser, IsEmailVerified])
@transaction.atomic
def move_candidate(request, pk):
    """POST /api/v1/payments/candidates/<pk>/move/"""
    candidate = get_object_or_404(TalentPoolCandidate, pk=pk, pipeline__company=request.user)
    serializer = TalentPoolCandidateMoveSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    candidate.stage_id = serializer.validated_data['stage_id']
    candidate.save(update_fields=['stage_id', 'updated_at'])
    return Response(TalentPoolCandidateSerializer(candidate).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsCompanyUser, IsEmailVerified])
@transaction.atomic
def bulk_move_candidates(request):
    """POST /api/v1/payments/candidates/bulk-move/"""
    serializer = TalentPoolCandidateBulkMoveSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    updated = TalentPoolCandidate.objects.filter(
        pk__in=serializer.validated_data['candidate_ids'],
        pipeline__company=request.user,
    ).update(stage_id=serializer.validated_data['stage_id'], updated_at=timezone.now())
    return Response({'moved': updated})


# ═══════════════════════════════════════════════════════════════════════════════
# REVENUE DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def revenue_dashboard(request):
    """GET /api/v1/payments/revenue/dashboard/ — Revenue metrics (admin only)."""
    if request.user.role != 'ADMIN':
        return Response({'detail': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)

    cached = cache.get('revenue_dashboard_metrics')
    if cached:
        return Response(cached)

    from payments.tasks import compute_revenue_metrics
    metrics = compute_revenue_metrics()
    return Response(metrics)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def revenue_trend(request):
    """GET /api/v1/payments/revenue/trend/?months=12 — Monthly revenue trend."""
    if request.user.role != 'ADMIN':
        return Response({'detail': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)

    months = min(int(request.query_params.get('months', 12)), 24)
    now = timezone.now()

    trend = []
    for i in range(months - 1, -1, -1):
        month_start = (now - timedelta(days=30 * i)).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0,
        )
        month_end = (now - timedelta(days=30 * (i - 1))).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0,
        ) if i > 0 else now

        revenue = PaymentHistory.objects.filter(
            event_type='invoice.paid',
            created_at__gte=month_start, created_at__lt=month_end,
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        new_subs = PaymentHistory.objects.filter(
            event_type='subscription.created',
            created_at__gte=month_start, created_at__lt=month_end,
        ).count()

        cancellations = PaymentHistory.objects.filter(
            event_type='subscription.deleted',
            created_at__gte=month_start, created_at__lt=month_end,
        ).count()

        trend.append({
            'month': month_start.strftime('%Y-%m'),
            'revenue': str(revenue),
            'new_subscriptions': new_subs,
            'cancellations': cancellations,
        })

    return Response({'trend': trend})


