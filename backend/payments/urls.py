from django.urls import path
from . import views

urlpatterns = [
    # ── Plans & Billing ──────────────────────────────────────────────
    path('plans/', views.SubscriptionPlanListView.as_view(), name='subscription-plans'),
    path('billing/', views.billing_overview, name='billing-overview'),
    path('create-checkout-session/', views.create_checkout_session, name='create-checkout-session'),
    path('webhook/', views.stripe_webhook, name='stripe-webhook'),
    path('customer-portal/', views.customer_portal, name='customer-portal'),
    path('invoice/<str:invoice_id>/', views.download_invoice, name='download-invoice'),

    # ── Coupons ──────────────────────────────────────────────────────
    path('coupons/validate/', views.validate_coupon, name='validate-coupon'),

    # ── Referrals ────────────────────────────────────────────────────
    path('referrals/program/', views.referral_program, name='referral-program'),
    path('referrals/stats/', views.my_referral_stats, name='referral-stats'),
    path('referrals/rewards/', views.my_referral_rewards, name='referral-rewards'),
    path('referrals/', views.my_referrals, name='referral-list'),
    path('referrals/create/', views.create_referral, name='referral-create'),

    # ── Sponsored Campaigns ──────────────────────────────────────────
    path('sponsored/', views.SponsoredCampaignListCreateView.as_view(), name='sponsored-list-create'),
    path('sponsored/<uuid:pk>/', views.SponsoredCampaignDetailView.as_view(), name='sponsored-detail'),
    path('sponsored/<uuid:pk>/toggle/', views.toggle_campaign_status, name='sponsored-toggle'),

    # ── Talent Pool CRM ──────────────────────────────────────────────
    path('pipelines/', views.TalentPoolPipelineListCreateView.as_view(), name='pipeline-list-create'),
    path('pipelines/<uuid:pk>/', views.TalentPoolPipelineDetailView.as_view(), name='pipeline-detail'),
    path('pipelines/<uuid:pipeline_pk>/candidates/', views.TalentPoolCandidateListCreateView.as_view(), name='candidate-list-create'),
    path('candidates/<uuid:pk>/', views.TalentPoolCandidateDetailView.as_view(), name='candidate-detail'),
    path('candidates/<uuid:pk>/move/', views.move_candidate, name='candidate-move'),
    path('candidates/bulk-move/', views.bulk_move_candidates, name='candidate-bulk-move'),

    # ── Revenue Dashboard (Admin) ────────────────────────────────────
    path('revenue/dashboard/', views.revenue_dashboard, name='revenue-dashboard'),
    path('revenue/trend/', views.revenue_trend, name='revenue-trend'),
]
