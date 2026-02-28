"""
payments/views.py
Stripe Checkout session creation + webhook handler.
"""
import io
import re
import json
import stripe
from django.conf import settings
from django.http import FileResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status

# Safe character set for invoice IDs (alphanumeric and hyphens only)
INVOICE_ID_PATTERN = re.compile(r'^[A-Za-z0-9\-]+$')

stripe.api_key = settings.STRIPE_SECRET_KEY

# ── Plan definitions ──────────────────────────────────────────────────────────
# If you have Stripe Price IDs set up in your dashboard, replace the
# 'price_id' values below. Otherwise, the amount/currency approach is used.
PLANS = {
    'Free Agent': {
        'amount': 0,
        'currency': 'usd',
        'name': 'Free Agent',
        'description': 'Basic profile, 3 applications/month',
        'tier': 'free',
    },
    'Premium Pro': {
        'amount': 1900,          # in cents  ($19.00)
        'currency': 'usd',
        'name': 'Premium Pro',
        'description': 'Unlimited applications, priority placement',
        'tier': 'premium',
    },
    'Starter': {
        'amount': 9900,          # $99.00
        'currency': 'usd',
        'name': 'Starter Corporate',
        'description': '5 active job posts, standard ATS integration',
        'tier': 'starter',
    },
    'Professional': {
        'amount': 29900,         # $299.00
        'currency': 'usd',
        'name': 'Professional Corporate',
        'description': 'Unlimited posts, custom branding, automated screening',
        'tier': 'professional',
    },
    'Enterprise': {
        'amount': 0,             # Custom — redirect to contact instead
        'currency': 'usd',
        'name': 'Enterprise',
        'description': 'Full API access, white-label, 24/7 support',
        'tier': 'enterprise',
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
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': plan['currency'],
                    'product_data': {
                        'name': plan['name'],
                        'description': plan['description'],
                    },
                    'unit_amount': plan['amount'],
                    # To make it recurring (subscription), add:
                    # 'recurring': {'interval': 'month'},
                },
                'quantity': 1,
            }],
            mode='payment',   # Change to 'subscription' for recurring billing
            success_url=f"{settings.FRONTEND_URL}/payment/success?plan={plan_name}&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.FRONTEND_URL}/payment/cancel",
            customer_email=request.user.email,
            metadata={
                'user_id': str(request.user.id),
                'plan': plan_name,
            },
        )
        return Response({'url': checkout_session.url})

    except stripe.error.StripeError as e:
        return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def stripe_webhook(request):
    """
    POST /api/v1/payments/webhook/
    Stripe sends events here. Verify signature and handle checkout.session.completed.
    Configure your Stripe Dashboard webhook to point to this URL.
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

    event_type = event_data.get('type', '')

    if event_type == 'checkout.session.completed':
        session = event_data['data']['object']
        user_id = session.get('metadata', {}).get('user_id')
        plan = session.get('metadata', {}).get('plan')

        if user_id and plan:
            try:
                from accounts.models import User
                user = User.objects.get(id=user_id)
                # Map the plan name to a normalized tier code for the model
                plan_obj = PLANS.get(plan, {})
                tier = plan_obj.get('tier', plan)
                # Update subscription tier on the user's profile
                if hasattr(user, 'talent_profile'):
                    user.talent_profile.subscription_tier = tier
                    user.talent_profile.save(update_fields=['subscription_tier'])
                elif hasattr(user, 'company_profile'):
                    user.company_profile.subscription_tier = tier
                    user.company_profile.save(update_fields=['subscription_tier'])
            except Exception as e:
                import logging
                logging.getLogger(__name__).exception(
                    'Webhook: failed to update subscription for user %s: %s', user_id, e
                )
                return HttpResponse(status=500)

    return HttpResponse(status=200)


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

