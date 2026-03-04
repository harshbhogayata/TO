"""
payments/serializers.py
DRF serializers for all payment, subscription, referral, and CRM models.
"""
from rest_framework import serializers
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


# ═══════════════════════════════════════════════════════════════════════════════
# Subscription Plans
# ═══════════════════════════════════════════════════════════════════════════════

class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = [
            'id', 'name', 'slug', 'audience', 'billing_interval',
            'price', 'currency', 'features', 'limits',
            'is_active', 'is_popular', 'sort_order',
        ]
        read_only_fields = fields


class SubscriptionPlanAdminSerializer(serializers.ModelSerializer):
    subscriber_count = serializers.SerializerMethodField()

    class Meta:
        model = SubscriptionPlan
        fields = '__all__'

    def get_subscriber_count(self, obj):
        return obj.subscribers.filter(subscription_status='active').count()


# ═══════════════════════════════════════════════════════════════════════════════
# Customer Profile & Billing
# ═══════════════════════════════════════════════════════════════════════════════

class CustomerProfileSerializer(serializers.ModelSerializer):
    plan_name = serializers.SerializerMethodField()
    plan_slug = serializers.SerializerMethodField()
    is_active_subscription = serializers.ReadOnlyField()
    is_in_grace_period = serializers.ReadOnlyField()
    effective_plan_slug = serializers.ReadOnlyField()

    class Meta:
        model = CustomerProfile
        fields = [
            'id', 'subscription_status', 'plan_name', 'plan_slug',
            'is_active_subscription', 'is_in_grace_period', 'effective_plan_slug',
            'current_period_start', 'current_period_end',
            'cancel_at_period_end', 'trial_end',
            'grace_period_end', 'failed_payment_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_plan_name(self, obj):
        return obj.current_plan.name if obj.current_plan else 'Free'

    def get_plan_slug(self, obj):
        return obj.current_plan.slug if obj.current_plan else 'free'


class PaymentHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentHistory
        fields = [
            'id', 'event_type', 'amount', 'currency', 'status',
            'failure_reason', 'created_at',
        ]
        read_only_fields = fields


class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = [
            'id', 'number', 'status', 'amount_due', 'amount_paid',
            'currency', 'description', 'stripe_hosted_invoice_url',
            'stripe_pdf_url', 'period_start', 'period_end',
            'due_date', 'paid_at', 'created_at',
        ]
        read_only_fields = fields


# ═══════════════════════════════════════════════════════════════════════════════
# Coupons
# ═══════════════════════════════════════════════════════════════════════════════

class CouponSerializer(serializers.ModelSerializer):
    is_valid = serializers.ReadOnlyField()

    class Meta:
        model = Coupon
        fields = [
            'id', 'code', 'discount_type', 'discount_value',
            'max_redemptions', 'current_redemptions',
            'valid_from', 'valid_until', 'is_active', 'is_valid',
        ]
        read_only_fields = ['id', 'current_redemptions', 'is_valid']


class CouponValidateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=50)
    plan_id = serializers.UUIDField(required=False)


# ═══════════════════════════════════════════════════════════════════════════════
# Referral Program
# ═══════════════════════════════════════════════════════════════════════════════

class ReferralProgramSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralProgram
        fields = [
            'id', 'name', 'description', 'audience', 'reward_type',
            'referrer_reward_amount', 'referee_reward_amount',
            'max_referrals_per_user', 'min_subscription_days',
            'is_active', 'starts_at', 'ends_at',
        ]
        read_only_fields = fields


class ReferralSerializer(serializers.ModelSerializer):
    referrer_name = serializers.SerializerMethodField()
    referee_name = serializers.SerializerMethodField()

    class Meta:
        model = Referral
        fields = [
            'id', 'referral_code', 'status', 'referrer_name', 'referee_name',
            'referee_email', 'click_count', 'signed_up_at', 'subscribed_at',
            'qualified_at', 'rewarded_at', 'expires_at', 'created_at',
        ]
        read_only_fields = fields

    def get_referrer_name(self, obj):
        return obj.referrer.full_name or obj.referrer.email

    def get_referee_name(self, obj):
        if obj.referee:
            return obj.referee.full_name or obj.referee.email
        return obj.referee_email or '—'


class ReferralCreateSerializer(serializers.Serializer):
    referee_email = serializers.EmailField(required=False)


class ReferralRewardSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralReward
        fields = [
            'id', 'recipient_type', 'amount', 'currency',
            'description', 'is_paid', 'paid_at', 'created_at',
        ]
        read_only_fields = fields


class ReferralStatsSerializer(serializers.Serializer):
    total_referrals = serializers.IntegerField()
    pending = serializers.IntegerField()
    qualified = serializers.IntegerField()
    rewarded = serializers.IntegerField()
    total_earned = serializers.DecimalField(max_digits=10, decimal_places=2)
    referral_code = serializers.CharField()


# ═══════════════════════════════════════════════════════════════════════════════
# Sponsored Job Campaigns
# ═══════════════════════════════════════════════════════════════════════════════

class SponsoredJobCampaignSerializer(serializers.ModelSerializer):
    job_title = serializers.ReadOnlyField(source='job.title')
    ctr = serializers.ReadOnlyField()
    cost_per_application = serializers.ReadOnlyField()
    budget_remaining = serializers.ReadOnlyField()

    class Meta:
        model = SponsoredJobCampaign
        fields = [
            'id', 'job', 'job_title', 'bid_type', 'bid_amount',
            'daily_budget', 'total_budget', 'amount_spent', 'status',
            'target_locations', 'target_skills', 'target_experience_levels',
            'impressions', 'clicks', 'applications',
            'ctr', 'cost_per_application', 'budget_remaining',
            'starts_at', 'ends_at', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'amount_spent', 'impressions', 'clicks', 'applications',
            'ctr', 'cost_per_application', 'budget_remaining',
            'created_at', 'updated_at',
        ]

    def validate(self, data):
        if data.get('daily_budget', 0) > data.get('total_budget', 0):
            raise serializers.ValidationError({
                'daily_budget': 'Daily budget cannot exceed total budget.',
            })
        if data.get('starts_at') and data.get('ends_at'):
            if data['starts_at'] >= data['ends_at']:
                raise serializers.ValidationError({
                    'ends_at': 'End date must be after start date.',
                })
        return data


# ═══════════════════════════════════════════════════════════════════════════════
# Talent Pool CRM
# ═══════════════════════════════════════════════════════════════════════════════

class TalentPoolPipelineSerializer(serializers.ModelSerializer):
    candidate_count = serializers.ReadOnlyField()

    class Meta:
        model = TalentPoolPipeline
        fields = [
            'id', 'name', 'description', 'stages', 'is_archived',
            'candidate_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'candidate_count', 'created_at', 'updated_at']


class TalentPoolCandidateSerializer(serializers.ModelSerializer):
    display_name = serializers.ReadOnlyField()
    display_email = serializers.ReadOnlyField()
    user_name = serializers.SerializerMethodField()
    user_avatar = serializers.SerializerMethodField()

    class Meta:
        model = TalentPoolCandidate
        fields = [
            'id', 'pipeline', 'user', 'display_name', 'display_email',
            'user_name', 'user_avatar',
            'external_name', 'external_email', 'external_phone',
            'external_resume_url', 'external_linkedin_url',
            'stage_id', 'source', 'rating', 'notes', 'tags',
            'application', 'added_by', 'last_contacted_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'display_name', 'display_email', 'added_by',
            'created_at', 'updated_at',
        ]

    def get_user_name(self, obj):
        if obj.user:
            return obj.user.full_name or obj.user.email
        return obj.external_name

    def get_user_avatar(self, obj):
        if obj.user and hasattr(obj.user, 'avatar') and obj.user.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.user.avatar.url)
        return None


class TalentPoolCandidateMoveSerializer(serializers.Serializer):
    """Serializer for moving a candidate to a different stage."""
    stage_id = serializers.CharField(max_length=50)


class TalentPoolCandidateBulkMoveSerializer(serializers.Serializer):
    """Serializer for moving multiple candidates at once."""
    candidate_ids = serializers.ListField(
        child=serializers.UUIDField(), min_length=1, max_length=100,
    )
    stage_id = serializers.CharField(max_length=50)


# ═══════════════════════════════════════════════════════════════════════════════
# Revenue Dashboard
# ═══════════════════════════════════════════════════════════════════════════════

class RevenueDashboardSerializer(serializers.Serializer):
    """Read-only serializer for the revenue analytics dashboard."""
    mrr = serializers.DecimalField(max_digits=12, decimal_places=2)
    arr = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_customers = serializers.IntegerField()
    active_subscriptions = serializers.IntegerField()
    churn_rate = serializers.FloatField()
    ltv = serializers.DecimalField(max_digits=10, decimal_places=2)
    average_revenue_per_user = serializers.DecimalField(max_digits=10, decimal_places=2)
    revenue_by_plan = serializers.ListField(child=serializers.DictField())
    revenue_trend = serializers.ListField(child=serializers.DictField())
    new_subscriptions_this_month = serializers.IntegerField()
    cancellations_this_month = serializers.IntegerField()
    net_revenue_this_month = serializers.DecimalField(max_digits=12, decimal_places=2)
    past_due_count = serializers.IntegerField()
    past_due_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
