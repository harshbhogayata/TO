"""
payments/admin.py
Django admin registration for all payment models.
"""
from django.contrib import admin
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


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'audience', 'billing_interval', 'price', 'is_active', 'is_popular']
    list_filter = ['audience', 'billing_interval', 'is_active']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'subscription_status', 'current_plan',
        'cancel_at_period_end', 'failed_payment_count', 'created_at',
    ]
    list_filter = ['subscription_status', 'cancel_at_period_end']
    search_fields = ['user__email', 'stripe_customer_id', 'stripe_subscription_id']
    raw_id_fields = ['user', 'current_plan']
    readonly_fields = ['stripe_customer_id', 'stripe_subscription_id', 'created_at', 'updated_at']


@admin.register(PaymentHistory)
class PaymentHistoryAdmin(admin.ModelAdmin):
    list_display = ['event_type', 'customer', 'amount', 'currency', 'status', 'created_at']
    list_filter = ['event_type', 'currency']
    search_fields = ['stripe_event_id', 'stripe_invoice_id', 'customer__user__email']
    readonly_fields = ['id', 'created_at']
    date_hierarchy = 'created_at'


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['number', 'customer', 'status', 'amount_due', 'amount_paid', 'created_at']
    list_filter = ['status']
    search_fields = ['number', 'stripe_invoice_id', 'customer__user__email']
    readonly_fields = ['id', 'created_at']


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ['code', 'discount_type', 'discount_value', 'current_redemptions', 'max_redemptions', 'is_active']
    list_filter = ['discount_type', 'is_active']
    search_fields = ['code']


@admin.register(CouponRedemption)
class CouponRedemptionAdmin(admin.ModelAdmin):
    list_display = ['coupon', 'user', 'redeemed_at']
    search_fields = ['coupon__code', 'user__email']


@admin.register(ReferralProgram)
class ReferralProgramAdmin(admin.ModelAdmin):
    list_display = ['name', 'audience', 'reward_type', 'referrer_reward_amount', 'is_active']
    list_filter = ['audience', 'reward_type', 'is_active']


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ['referral_code', 'referrer', 'referee', 'status', 'click_count', 'created_at']
    list_filter = ['status']
    search_fields = ['referral_code', 'referrer__email', 'referee__email', 'referee_email']
    raw_id_fields = ['referrer', 'referee', 'program']


@admin.register(ReferralReward)
class ReferralRewardAdmin(admin.ModelAdmin):
    list_display = ['referral', 'recipient', 'recipient_type', 'amount', 'is_paid', 'created_at']
    list_filter = ['recipient_type', 'is_paid']


@admin.register(SponsoredJobCampaign)
class SponsoredJobCampaignAdmin(admin.ModelAdmin):
    list_display = ['job', 'company', 'status', 'bid_type', 'total_budget', 'amount_spent', 'clicks', 'applications']
    list_filter = ['status', 'bid_type']
    search_fields = ['job__title', 'company__email']
    raw_id_fields = ['job', 'company']


@admin.register(TalentPoolPipeline)
class TalentPoolPipelineAdmin(admin.ModelAdmin):
    list_display = ['name', 'company', 'is_archived', 'created_at']
    list_filter = ['is_archived']
    search_fields = ['name', 'company__email']
    raw_id_fields = ['company']


@admin.register(TalentPoolCandidate)
class TalentPoolCandidateAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'pipeline', 'stage_id', 'source', 'rating', 'created_at']
    list_filter = ['source', 'stage_id']
    search_fields = ['external_name', 'external_email', 'user__email']
    raw_id_fields = ['pipeline', 'user', 'application', 'added_by']
