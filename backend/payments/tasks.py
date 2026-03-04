"""
payments/tasks.py
Celery tasks for payment processing, dunning, referral qualification,
and campaign management.
"""
import logging
from datetime import timedelta
from decimal import Decimal

from celery import shared_task
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# DUNNING — Grace period management
# ═══════════════════════════════════════════════════════════════════════════════

@shared_task(
    name='payments.tasks.handle_payment_failure',
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def handle_payment_failure(self, customer_profile_id: str, stripe_event_id: str):
    """
    Handle a failed payment: start/extend grace period, notify user.
    Called by the Stripe webhook handler on invoice.payment_failed.
    """
    from payments.models import CustomerProfile
    from notifications.tasks import create_notification

    try:
        customer = CustomerProfile.objects.select_related('user', 'current_plan').get(
            pk=customer_profile_id,
        )
    except CustomerProfile.DoesNotExist:
        logger.error('handle_payment_failure: CustomerProfile %s not found', customer_profile_id)
        return

    with transaction.atomic():
        # Lock the row to prevent concurrent webhook race conditions
        customer = CustomerProfile.objects.select_for_update().get(pk=customer.pk)

        fail_count = customer.failed_payment_count + 1

        # Escalating grace periods: 7 days first failure, 3 days subsequent
        grace_days = 7 if fail_count == 1 else 3
        customer.start_grace_period(days=grace_days)
        customer.subscription_status = 'past_due'
        customer.save(update_fields=['subscription_status', 'updated_at'])

    # Notify the user
    create_notification.delay(
        user_id=customer.user_id,
        notification_type='payment_failed',
        title='Payment Failed',
        message=(
            f'Your payment for the {customer.current_plan.name if customer.current_plan else "subscription"} '
            f'plan has failed. You have {grace_days} days to update your payment method '
            f'before your account is downgraded.'
        ),
        data={
            'payment_failure_count': fail_count,
            'grace_period_end': customer.grace_period_end.isoformat() if customer.grace_period_end else None,
        },
    )

    # Send email on first failure
    if fail_count == 1:
        _send_payment_failure_email.delay(customer.user_id, grace_days)

    logger.info(
        'Payment failure #%d for user %s — grace period: %d days (ends %s)',
        fail_count, customer.user.email, grace_days,
        customer.grace_period_end,
    )


@shared_task(name='payments.tasks.process_expired_grace_periods')
def process_expired_grace_periods():
    """
    Periodic task: downgrade users whose grace period has expired.
    Should be scheduled via Celery Beat (e.g. every hour).
    """
    from payments.models import CustomerProfile

    expired = CustomerProfile.objects.filter(
        grace_period_end__lt=timezone.now(),
        subscription_status='past_due',
    ).select_related('user', 'current_plan')

    downgraded_count = 0
    for customer in expired:
        with transaction.atomic():
            # Lock each row individually to prevent concurrent modifications
            locked = CustomerProfile.objects.select_for_update().get(pk=customer.pk)
            _downgrade_to_free(locked)
            downgraded_count += 1

    if downgraded_count:
        logger.info('Downgraded %d users with expired grace periods', downgraded_count)

    return downgraded_count


def _downgrade_to_free(customer):
    """Downgrade a customer to the free plan after grace period expiration."""
    from payments.models import SubscriptionPlan
    from notifications.tasks import create_notification
    from compliance.decorators import create_audit_log
    from compliance.constants import AuditAction, AuditCategory

    free_plan = SubscriptionPlan.objects.filter(
        audience=customer.current_plan.audience if customer.current_plan else 'TALENT',
        price=0,
    ).first()

    old_plan_name = customer.current_plan.name if customer.current_plan else 'Unknown'

    customer.current_plan = free_plan
    customer.subscription_status = 'canceled'
    customer.grace_period_end = None
    customer.stripe_subscription_id = ''
    customer.save(update_fields=[
        'current_plan', 'subscription_status', 'grace_period_end',
        'stripe_subscription_id', 'updated_at',
    ])

    # Update the user's profile tier
    user = customer.user
    if hasattr(user, 'talent_profile'):
        user.talent_profile.subscription_tier = 'free'
        user.talent_profile.save(update_fields=['subscription_tier'])
    elif hasattr(user, 'company_profile'):
        user.company_profile.subscription_tier = 'free'
        user.company_profile.save(update_fields=['subscription_tier'])

    create_notification.delay(
        user_id=user.pk,
        notification_type='subscription_downgraded',
        title='Subscription Downgraded',
        message=(
            f'Your {old_plan_name} subscription has been downgraded to the Free plan '
            f'due to an unpaid balance. Update your payment method to resubscribe.'
        ),
    )

    create_audit_log(
        actor=user,
        action=AuditAction.SUBSCRIPTION_CANCEL,
        category=AuditCategory.PAYMENT,
        description=f'Subscription auto-downgraded from {old_plan_name} to Free (grace period expired)',
        resource_type='payments.CustomerProfile',
        resource_id=str(customer.pk),
    )

    logger.info('User %s downgraded from %s to Free (grace expired)', user.email, old_plan_name)


@shared_task(name='payments.tasks._send_payment_failure_email')
def _send_payment_failure_email(user_id: int, grace_days: int):
    """Send a payment failure notification email."""
    from django.contrib.auth import get_user_model
    from django.core.mail import send_mail

    User = get_user_model()
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return

    send_mail(
        subject='Action Required: Payment Failed — TalentOrbit',
        message=(
            f'Hi {user.full_name or "there"},\n\n'
            f'We were unable to process your subscription payment. '
            f'You have {grace_days} days to update your payment method.\n\n'
            f'Please visit your billing settings to update your card:\n'
            f'{settings.FRONTEND_URL}/billing\n\n'
            f'If you need assistance, contact us at support@talentorbit.com.\n\n'
            f'— The TalentOrbit Team'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# REFERRAL QUALIFICATION
# ═══════════════════════════════════════════════════════════════════════════════

@shared_task(name='payments.tasks.check_referral_qualification')
def check_referral_qualification():
    """
    Periodic task: check if any referrals have met the minimum subscription
    requirement and qualify them for rewards.
    """
    from payments.models import Referral, ReferralReward

    now = timezone.now()
    subscribed_referrals = Referral.objects.filter(
        status='subscribed',
        subscribed_at__isnull=False,
    ).select_related('program', 'referrer', 'referee')

    qualified_count = 0
    for referral in subscribed_referrals:
        days_subscribed = (now - referral.subscribed_at).days
        if days_subscribed >= referral.program.min_subscription_days:
            with transaction.atomic():
                referral.status = 'qualified'
                referral.qualified_at = now
                referral.save(update_fields=['status', 'qualified_at', 'updated_at'])

                # Create rewards for both parties
                ReferralReward.objects.create(
                    referral=referral,
                    recipient=referral.referrer,
                    recipient_type='referrer',
                    amount=referral.program.referrer_reward_amount,
                    description=f'Referral reward for {referral.referral_code}',
                )
                if referral.referee:
                    ReferralReward.objects.create(
                        referral=referral,
                        recipient=referral.referee,
                        recipient_type='referee',
                        amount=referral.program.referee_reward_amount,
                        description=f'Welcome reward via referral {referral.referral_code}',
                    )

                referral.status = 'rewarded'
                referral.rewarded_at = now
                referral.save(update_fields=['status', 'rewarded_at', 'updated_at'])
                qualified_count += 1

    if qualified_count:
        logger.info('Qualified and rewarded %d referrals', qualified_count)

    return qualified_count


@shared_task(name='payments.tasks.expire_stale_referrals')
def expire_stale_referrals():
    """Expire referrals that haven't progressed within 90 days."""
    from payments.models import Referral

    cutoff = timezone.now() - timedelta(days=90)
    expired = Referral.objects.filter(
        status__in=['pending', 'signed_up'],
        created_at__lt=cutoff,
    ).update(status='expired')

    if expired:
        logger.info('Expired %d stale referrals', expired)
    return expired


# ═══════════════════════════════════════════════════════════════════════════════
# SPONSORED CAMPAIGNS
# ═══════════════════════════════════════════════════════════════════════════════

@shared_task(name='payments.tasks.process_campaign_budgets')
def process_campaign_budgets():
    """
    Periodic task: pause campaigns that have exhausted their budget
    or passed their end date.
    """
    from payments.models import SponsoredJobCampaign

    now = timezone.now()

    # Exhaust campaigns over budget
    exhausted = SponsoredJobCampaign.objects.filter(
        status='active',
        amount_spent__gte=models.F('total_budget'),
    ).update(status='exhausted')

    # Complete campaigns past end date
    completed = SponsoredJobCampaign.objects.filter(
        status='active',
        ends_at__lt=now,
    ).update(status='completed')

    if exhausted or completed:
        logger.info('Campaign budget check: %d exhausted, %d completed', exhausted, completed)

    return {'exhausted': exhausted, 'completed': completed}


# ═══════════════════════════════════════════════════════════════════════════════
# REVENUE METRICS COMPUTATION
# ═══════════════════════════════════════════════════════════════════════════════

@shared_task(name='payments.tasks.compute_revenue_metrics')
def compute_revenue_metrics():
    """
    Compute and cache key revenue metrics for the admin dashboard.
    Called periodically (e.g. every hour).
    """
    from payments.models import CustomerProfile, PaymentHistory, SubscriptionPlan
    from django.core.cache import cache
    from django.db.models import Sum, Count, Q

    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_start = (month_start - timedelta(days=1)).replace(day=1)

    # Active subscriptions
    active_customers = CustomerProfile.objects.filter(
        subscription_status__in=['active', 'trialing'],
    )
    active_count = active_customers.count()

    # MRR calculation
    mrr = Decimal('0.00')
    for cp in active_customers.select_related('current_plan'):
        if cp.current_plan:
            if cp.current_plan.billing_interval == 'yearly':
                mrr += cp.current_plan.price / 12
            else:
                mrr += cp.current_plan.price

    # Revenue this month
    month_revenue = PaymentHistory.objects.filter(
        event_type='invoice.paid',
        created_at__gte=month_start,
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # Cancellations this month
    cancellations = PaymentHistory.objects.filter(
        event_type='subscription.deleted',
        created_at__gte=month_start,
    ).count()

    # New subscriptions this month
    new_subs = PaymentHistory.objects.filter(
        event_type='subscription.created',
        created_at__gte=month_start,
    ).count()

    # Churn rate
    last_month_active = CustomerProfile.objects.filter(
        subscription_status__in=['active', 'trialing'],
        created_at__lt=month_start,
    ).count()
    churn_rate = (cancellations / last_month_active * 100) if last_month_active > 0 else 0

    # Past due
    past_due = CustomerProfile.objects.filter(subscription_status='past_due')
    past_due_count = past_due.count()
    past_due_amount = Decimal('0.00')
    for cp in past_due.select_related('current_plan'):
        if cp.current_plan:
            past_due_amount += cp.current_plan.price

    # Revenue by plan
    revenue_by_plan = []
    for plan in SubscriptionPlan.objects.filter(is_active=True):
        count = plan.subscribers.filter(subscription_status='active').count()
        if count > 0:
            revenue_by_plan.append({
                'plan': plan.name,
                'subscribers': count,
                'mrr': str(plan.price * count if plan.billing_interval == 'monthly' else (plan.price / 12) * count),
            })

    # LTV (simplified: ARPU / churn rate)
    arpu = mrr / active_count if active_count > 0 else Decimal('0.00')
    ltv = arpu / (Decimal(str(churn_rate / 100)) if churn_rate > 0 else Decimal('0.01'))

    metrics = {
        'mrr': str(mrr),
        'arr': str(mrr * 12),
        'total_customers': CustomerProfile.objects.count(),
        'active_subscriptions': active_count,
        'churn_rate': round(churn_rate, 2),
        'ltv': str(round(ltv, 2)),
        'average_revenue_per_user': str(round(arpu, 2)),
        'revenue_by_plan': revenue_by_plan,
        'new_subscriptions_this_month': new_subs,
        'cancellations_this_month': cancellations,
        'net_revenue_this_month': str(month_revenue),
        'past_due_count': past_due_count,
        'past_due_amount': str(past_due_amount),
        'computed_at': now.isoformat(),
    }

    cache.set('revenue_dashboard_metrics', metrics, timeout=3600)
    logger.info('Revenue metrics computed: MRR=%s, active=%d, churn=%.2f%%', mrr, active_count, churn_rate)
    return metrics
