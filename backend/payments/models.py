"""
payments/models.py
Enterprise-grade payment, subscription, and revenue models for TalentOrbit.

Contains:
    1. SubscriptionPlan    — Canonical plan definitions synced with Stripe
    2. CustomerProfile     — Links Django user to Stripe customer + subscription
    3. PaymentHistory      — Immutable ledger of all payment events
    4. Invoice             — Invoice records with PDF generation tracking
    5. Coupon              — Promotional coupons with usage tracking
    6. CouponRedemption    — Per-user coupon usage log
    7. ReferralProgram     — Referral campaign configuration
    8. Referral            — Individual referral tracking
    9. ReferralReward      — Reward ledger for completed referrals
    10. SponsoredJobCampaign — Paid job promotion campaigns
    11. TalentPoolPipeline  — CRM pipeline/kanban for talent management
    12. TalentPoolCandidate — Candidates within a pipeline stage
"""
import uuid
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


# ═══════════════════════════════════════════════════════════════════════════════
# 1. SUBSCRIPTION PLAN — Canonical plan definitions
# ═══════════════════════════════════════════════════════════════════════════════

class SubscriptionPlan(models.Model):
    """
    Canonical plan definitions synced with Stripe.
    One row per plan — used as the source of truth for pricing pages,
    tier-limit enforcement, and billing logic.
    """

    class Audience(models.TextChoices):
        TALENT = 'TALENT', 'Talent'
        COMPANY = 'COMPANY', 'Company'

    class BillingInterval(models.TextChoices):
        MONTHLY = 'monthly', 'Monthly'
        YEARLY = 'yearly', 'Yearly'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, help_text='Human-readable plan name, e.g. "Professional"')
    slug = models.SlugField(max_length=60, unique=True, help_text='URL-safe identifier, e.g. "professional"')
    audience = models.CharField(max_length=10, choices=Audience.choices, db_index=True)
    billing_interval = models.CharField(
        max_length=10, choices=BillingInterval.choices, default='monthly',
    )
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text='Price in USD')
    currency = models.CharField(max_length=3, default='usd')
    stripe_price_id = models.CharField(
        max_length=100, unique=True, blank=True, default='',
        help_text='Stripe Price ID (price_xxx). Blank for free tier.',
    )
    features = models.JSONField(
        default=list, blank=True,
        help_text='List of feature strings shown on pricing page.',
    )
    limits = models.JSONField(
        default=dict, blank=True,
        help_text='Plan limits: {"max_applications_per_month": 3, "max_active_job_posts": 1, ...}',
    )
    is_active = models.BooleanField(default=True, db_index=True)
    is_popular = models.BooleanField(default=False, help_text='Highlight on pricing page')
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['audience', 'sort_order', 'price']
        verbose_name = 'Subscription Plan'
        verbose_name_plural = 'Subscription Plans'

    def __str__(self):
        return f'{self.name} ({self.audience} — ${self.price}/{self.billing_interval})'


# ═══════════════════════════════════════════════════════════════════════════════
# 2. CUSTOMER PROFILE — Stripe customer + subscription state
# ═══════════════════════════════════════════════════════════════════════════════

class CustomerProfile(models.Model):
    """
    Links a Django user to their Stripe customer and active subscription.
    Exactly one row per user. Created on first checkout or webhook.
    """

    class SubscriptionStatus(models.TextChoices):
        ACTIVE = 'active', 'Active'
        PAST_DUE = 'past_due', 'Past Due'
        CANCELED = 'canceled', 'Canceled'
        INCOMPLETE = 'incomplete', 'Incomplete'
        INCOMPLETE_EXPIRED = 'incomplete_expired', 'Incomplete Expired'
        TRIALING = 'trialing', 'Trialing'
        UNPAID = 'unpaid', 'Unpaid'
        PAUSED = 'paused', 'Paused'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='customer_profile',
    )
    stripe_customer_id = models.CharField(
        max_length=100, unique=True, blank=True, default='',
        help_text='Stripe Customer ID (cus_xxx)',
    )
    stripe_subscription_id = models.CharField(
        max_length=100, blank=True, default='',
        help_text='Active Stripe Subscription ID (sub_xxx)',
    )
    subscription_status = models.CharField(
        max_length=25,
        choices=SubscriptionStatus.choices,
        default='active',
        db_index=True,
    )
    current_plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='subscribers',
    )
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    trial_end = models.DateTimeField(null=True, blank=True)
    # Dunning
    grace_period_end = models.DateTimeField(
        null=True, blank=True,
        help_text='End of grace period after payment failure. NULL = no active grace.',
    )
    failed_payment_count = models.PositiveSmallIntegerField(default=0)
    last_payment_failure_at = models.DateTimeField(null=True, blank=True)
    # Metadata
    default_payment_method = models.CharField(max_length=100, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Customer Profile'
        verbose_name_plural = 'Customer Profiles'

    def __str__(self):
        plan_name = self.current_plan.name if self.current_plan else 'Free'
        return f'{self.user.email} — {plan_name} ({self.subscription_status})'

    @property
    def is_active_subscription(self):
        return self.subscription_status in ('active', 'trialing')

    @property
    def is_in_grace_period(self):
        if not self.grace_period_end:
            return False
        return timezone.now() < self.grace_period_end

    @property
    def effective_plan_slug(self):
        """Return the effective plan slug, accounting for grace periods."""
        if self.is_active_subscription or self.is_in_grace_period:
            return self.current_plan.slug if self.current_plan else 'free'
        return 'free'

    def start_grace_period(self, days=7):
        """Start a grace period after payment failure."""
        self.grace_period_end = timezone.now() + timedelta(days=days)
        self.failed_payment_count += 1
        self.last_payment_failure_at = timezone.now()
        self.save(update_fields=[
            'grace_period_end', 'failed_payment_count', 'last_payment_failure_at', 'updated_at',
        ])

    def end_grace_period(self):
        """Clear grace period (payment succeeded or subscription downgraded)."""
        self.grace_period_end = None
        self.failed_payment_count = 0
        self.last_payment_failure_at = None
        self.save(update_fields=[
            'grace_period_end', 'failed_payment_count', 'last_payment_failure_at', 'updated_at',
        ])


# ═══════════════════════════════════════════════════════════════════════════════
# 3. PAYMENT HISTORY — Immutable payment event ledger
# ═══════════════════════════════════════════════════════════════════════════════

class PaymentHistory(models.Model):
    """
    Immutable record of every payment-related event.
    Populated by Stripe webhooks — never edited after creation.
    """

    class EventType(models.TextChoices):
        CHARGE_SUCCEEDED = 'charge.succeeded', 'Charge Succeeded'
        CHARGE_FAILED = 'charge.failed', 'Charge Failed'
        CHARGE_REFUNDED = 'charge.refunded', 'Charge Refunded'
        SUBSCRIPTION_CREATED = 'subscription.created', 'Subscription Created'
        SUBSCRIPTION_UPDATED = 'subscription.updated', 'Subscription Updated'
        SUBSCRIPTION_DELETED = 'subscription.deleted', 'Subscription Deleted'
        INVOICE_PAID = 'invoice.paid', 'Invoice Paid'
        INVOICE_PAYMENT_FAILED = 'invoice.payment_failed', 'Invoice Payment Failed'
        CHECKOUT_COMPLETED = 'checkout.completed', 'Checkout Completed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name='payment_history',
    )
    event_type = models.CharField(max_length=40, choices=EventType.choices, db_index=True)
    stripe_event_id = models.CharField(
        max_length=100, unique=True,
        help_text='Stripe Event ID for idempotency (evt_xxx)',
    )
    stripe_invoice_id = models.CharField(max_length=100, blank=True, default='')
    stripe_charge_id = models.CharField(max_length=100, blank=True, default='')
    stripe_payment_intent_id = models.CharField(max_length=100, blank=True, default='')
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text='Amount in base currency units (e.g. USD)',
    )
    currency = models.CharField(max_length=3, default='usd')
    status = models.CharField(max_length=30, blank=True, default='')
    failure_reason = models.TextField(blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Payment History'
        verbose_name_plural = 'Payment History'
        indexes = [
            models.Index(fields=['customer', '-created_at']),
        ]

    def __str__(self):
        return f'{self.event_type} — ${self.amount} ({self.created_at:%Y-%m-%d})'


# ═══════════════════════════════════════════════════════════════════════════════
# 4. INVOICE — Invoice tracking
# ═══════════════════════════════════════════════════════════════════════════════

class Invoice(models.Model):
    """
    Invoice records with PDF tracking. Linked to Stripe invoices.
    """

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        OPEN = 'open', 'Open'
        PAID = 'paid', 'Paid'
        VOID = 'void', 'Void'
        UNCOLLECTIBLE = 'uncollectible', 'Uncollectible'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name='invoices',
    )
    stripe_invoice_id = models.CharField(max_length=100, unique=True)
    number = models.CharField(max_length=50, blank=True, default='')
    status = models.CharField(max_length=20, choices=Status.choices, default='draft')
    amount_due = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    currency = models.CharField(max_length=3, default='usd')
    description = models.TextField(blank=True, default='')
    stripe_hosted_invoice_url = models.URLField(max_length=500, blank=True, default='')
    stripe_pdf_url = models.URLField(max_length=500, blank=True, default='')
    period_start = models.DateTimeField(null=True, blank=True)
    period_end = models.DateTimeField(null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Invoice'
        verbose_name_plural = 'Invoices'
        indexes = [
            models.Index(fields=['customer', 'status', '-created_at'], name='idx_invoice_cust_status'),
            models.Index(fields=['status', 'due_date'], name='idx_invoice_status_due'),
        ]

    def __str__(self):
        return f'Invoice {self.number or self.stripe_invoice_id} — ${self.amount_due}'


# ═══════════════════════════════════════════════════════════════════════════════
# 5. COUPON — Promotional coupons
# ═══════════════════════════════════════════════════════════════════════════════

class Coupon(models.Model):
    """Promotional coupon with usage tracking and expiration."""

    class DiscountType(models.TextChoices):
        PERCENTAGE = 'percentage', 'Percentage'
        FIXED_AMOUNT = 'fixed_amount', 'Fixed Amount'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True, db_index=True)
    discount_type = models.CharField(max_length=15, choices=DiscountType.choices)
    discount_value = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text='Percentage (0-100) or fixed amount in USD',
    )
    applicable_plans = models.ManyToManyField(
        SubscriptionPlan, blank=True,
        help_text='Leave blank to apply to all plans.',
    )
    max_redemptions = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='NULL = unlimited',
    )
    current_redemptions = models.PositiveIntegerField(default=0)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    stripe_coupon_id = models.CharField(max_length=100, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Coupon'
        verbose_name_plural = 'Coupons'

    def __str__(self):
        return f'{self.code} ({self.discount_type}: {self.discount_value})'

    @property
    def is_valid(self):
        now = timezone.now()
        if not self.is_active:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        if self.max_redemptions and self.current_redemptions >= self.max_redemptions:
            return False
        return True


class CouponRedemption(models.Model):
    """Per-user coupon usage log — ensures each coupon used at most once per user."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name='redemptions')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='coupon_redemptions',
    )
    redeemed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('coupon', 'user')
        verbose_name = 'Coupon Redemption'


# ═══════════════════════════════════════════════════════════════════════════════
# 6. REFERRAL PROGRAM — Viral growth engine
# ═══════════════════════════════════════════════════════════════════════════════

class ReferralProgram(models.Model):
    """
    Configurable referral campaign. Supports credit, discount, or cash rewards.
    Exactly one should be active at a time per audience.
    """

    class RewardType(models.TextChoices):
        CREDIT = 'credit', 'Account Credit'
        DISCOUNT = 'discount', 'Subscription Discount'
        CASH = 'cash', 'Cash Payout'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default='')
    audience = models.CharField(
        max_length=10, choices=SubscriptionPlan.Audience.choices,
        db_index=True,
    )
    reward_type = models.CharField(max_length=10, choices=RewardType.choices)
    referrer_reward_amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text='Reward for the person who refers (in USD or %)',
    )
    referee_reward_amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text='Reward for the person who signs up (in USD or %)',
    )
    max_referrals_per_user = models.PositiveIntegerField(
        default=50,
        help_text='Maximum successful referrals per user',
    )
    min_subscription_days = models.PositiveIntegerField(
        default=30,
        help_text='Referee must be subscribed for N days before reward is granted',
    )
    is_active = models.BooleanField(default=True, db_index=True)
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Referral Program'
        verbose_name_plural = 'Referral Programs'

    def __str__(self):
        return f'{self.name} ({self.audience})'


class Referral(models.Model):
    """
    Individual referral tracking — from referrer to referee.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'         # Link clicked, not yet signed up
        SIGNED_UP = 'signed_up', 'Signed Up'   # Referee registered
        SUBSCRIBED = 'subscribed', 'Subscribed' # Referee paid for subscription
        QUALIFIED = 'qualified', 'Qualified'    # Min subscription days met
        REWARDED = 'rewarded', 'Rewarded'       # Both parties rewarded
        EXPIRED = 'expired', 'Expired'          # Referral expired without qualifying
        FRAUDULENT = 'fraudulent', 'Fraudulent' # Flagged for fraud

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    program = models.ForeignKey(
        ReferralProgram, on_delete=models.CASCADE, related_name='referrals',
    )
    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='referrals_given',
    )
    referee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='referrals_received',
    )
    referral_code = models.CharField(max_length=30, unique=True, db_index=True)
    status = models.CharField(
        max_length=15, choices=Status.choices, default='pending', db_index=True,
    )
    referee_email = models.EmailField(blank=True, default='')
    click_count = models.PositiveIntegerField(default=0)
    signed_up_at = models.DateTimeField(null=True, blank=True)
    subscribed_at = models.DateTimeField(null=True, blank=True)
    qualified_at = models.DateTimeField(null=True, blank=True)
    rewarded_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Referral'
        verbose_name_plural = 'Referrals'
        indexes = [
            models.Index(fields=['referrer', 'status']),
        ]

    def __str__(self):
        return f'{self.referral_code} ({self.status})'


class ReferralReward(models.Model):
    """Ledger entry for a referral reward — one per party per referral."""

    class RecipientType(models.TextChoices):
        REFERRER = 'referrer', 'Referrer'
        REFEREE = 'referee', 'Referee'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    referral = models.ForeignKey(
        Referral, on_delete=models.CASCADE, related_name='rewards',
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='referral_rewards',
    )
    recipient_type = models.CharField(max_length=10, choices=RecipientType.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='usd')
    description = models.CharField(max_length=200, blank=True, default='')
    is_paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)
    stripe_transfer_id = models.CharField(max_length=100, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Referral Reward'
        verbose_name_plural = 'Referral Rewards'

    def __str__(self):
        return f'{self.recipient_type} reward: ${self.amount} for {self.referral.referral_code}'


# ═══════════════════════════════════════════════════════════════════════════════
# 7. SPONSORED JOB CAMPAIGNS — Paid job promotion
# ═══════════════════════════════════════════════════════════════════════════════

class SponsoredJobCampaign(models.Model):
    """
    Paid promotion campaign for a job post.
    Supports daily budget, total budget, and CPC/CPM bidding.
    """

    class BidType(models.TextChoices):
        CPC = 'cpc', 'Cost Per Click'
        CPM = 'cpm', 'Cost Per 1000 Impressions'
        FLAT = 'flat', 'Flat Rate'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PENDING_PAYMENT = 'pending_payment', 'Pending Payment'
        ACTIVE = 'active', 'Active'
        PAUSED = 'paused', 'Paused'
        EXHAUSTED = 'exhausted', 'Budget Exhausted'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(
        'jobs.JobPost', on_delete=models.CASCADE, related_name='sponsored_campaigns',
    )
    company = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='sponsored_campaigns',
    )
    bid_type = models.CharField(max_length=5, choices=BidType.choices, default='cpc')
    bid_amount = models.DecimalField(
        max_digits=8, decimal_places=2,
        help_text='Bid amount per unit (CPC, CPM, or flat rate)',
    )
    daily_budget = models.DecimalField(max_digits=10, decimal_places=2)
    total_budget = models.DecimalField(max_digits=10, decimal_places=2)
    amount_spent = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(
        max_length=20, choices=Status.choices, default='draft', db_index=True,
    )
    # Targeting
    target_locations = models.JSONField(default=list, blank=True)
    target_skills = models.JSONField(default=list, blank=True)
    target_experience_levels = models.JSONField(default=list, blank=True)
    # Metrics
    impressions = models.PositiveIntegerField(default=0)
    clicks = models.PositiveIntegerField(default=0)
    applications = models.PositiveIntegerField(default=0)
    # Schedule
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    # Payment
    stripe_payment_intent_id = models.CharField(max_length=100, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Sponsored Job Campaign'
        verbose_name_plural = 'Sponsored Job Campaigns'
        indexes = [
            models.Index(fields=['company', 'status'], name='idx_campaign_company_status'),
            models.Index(fields=['status', 'ends_at'], name='idx_campaign_status_ends'),
            models.Index(fields=['status', 'amount_spent', 'total_budget'], name='idx_campaign_budget'),
        ]

    def __str__(self):
        return f'Campaign for "{self.job.title}" — {self.status}'

    @property
    def ctr(self):
        if self.impressions == 0:
            return 0
        return round((self.clicks / self.impressions) * 100, 2)

    @property
    def cost_per_application(self):
        if self.applications == 0:
            return Decimal('0.00')
        return round(self.amount_spent / self.applications, 2)

    @property
    def budget_remaining(self):
        return self.total_budget - self.amount_spent


# ═══════════════════════════════════════════════════════════════════════════════
# 8. TALENT POOL CRM — Pipeline management for companies
# ═══════════════════════════════════════════════════════════════════════════════

class TalentPoolPipeline(models.Model):
    """
    CRM pipeline for talent management — Kanban-style stages.
    Each company can have multiple pipelines (e.g. per department/role).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='talent_pipelines',
    )
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, default='')
    stages = models.JSONField(
        default=list,
        help_text='Ordered list of stage definitions: [{"id": "sourced", "label": "Sourced", "color": "#E6E2D8"}, ...]',
    )
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Talent Pool Pipeline'
        verbose_name_plural = 'Talent Pool Pipelines'

    def __str__(self):
        return f'{self.name} ({self.company.email})'

    @property
    def candidate_count(self):
        return self.candidates.count()

    def get_default_stages(self):
        """Return default Kanban stages for a new pipeline."""
        return [
            {'id': 'sourced', 'label': 'Sourced', 'color': '#94A3B8'},
            {'id': 'screening', 'label': 'Screening', 'color': '#60A5FA'},
            {'id': 'interview', 'label': 'Interview', 'color': '#FBBF24'},
            {'id': 'assessment', 'label': 'Assessment', 'color': '#A78BFA'},
            {'id': 'offer', 'label': 'Offer', 'color': '#34D399'},
            {'id': 'hired', 'label': 'Hired', 'color': '#10B981'},
            {'id': 'rejected', 'label': 'Rejected', 'color': '#EF4444'},
        ]


class TalentPoolCandidate(models.Model):
    """
    A candidate within a pipeline stage.
    Can be linked to a TalentProfile user or be an external contact.
    """

    class Source(models.TextChoices):
        APPLICATION = 'application', 'Job Application'
        SEARCH = 'search', 'Talent Search'
        REFERRAL = 'referral', 'Referral'
        IMPORT = 'import', 'CSV/File Import'
        MANUAL = 'manual', 'Manual Entry'
        API = 'api', 'API/Integration'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pipeline = models.ForeignKey(
        TalentPoolPipeline, on_delete=models.CASCADE, related_name='candidates',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='pipeline_entries',
        help_text='Linked TalentOrbit user (if registered)',
    )
    # External candidate fields (when user is NULL)
    external_name = models.CharField(max_length=200, blank=True, default='')
    external_email = models.EmailField(blank=True, default='')
    external_phone = models.CharField(max_length=30, blank=True, default='')
    external_resume_url = models.URLField(max_length=500, blank=True, default='')
    external_linkedin_url = models.URLField(max_length=500, blank=True, default='')
    # Pipeline state
    stage_id = models.CharField(max_length=50, help_text='ID of the current pipeline stage')
    source = models.CharField(max_length=15, choices=Source.choices, default='manual')
    rating = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text='1-5 star rating',
    )
    notes = models.TextField(blank=True, default='')
    tags = models.JSONField(default=list, blank=True)
    # Linked records
    application = models.ForeignKey(
        'jobs.Application', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='pipeline_entries',
    )
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='candidates_added',
    )
    last_contacted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Talent Pool Candidate'
        verbose_name_plural = 'Talent Pool Candidates'
        indexes = [
            models.Index(fields=['pipeline', 'stage_id']),
        ]

    def __str__(self):
        name = self.user.full_name if self.user else self.external_name
        return f'{name} — {self.stage_id} in {self.pipeline.name}'

    @property
    def display_name(self):
        if self.user:
            return self.user.full_name or self.user.email
        return self.external_name or self.external_email

    @property
    def display_email(self):
        if self.user:
            return self.user.email
        return self.external_email
