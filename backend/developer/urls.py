"""
developer/urls.py
URL routing for the Developer Platform API.
Mounted at: /api/v1/developer/
"""
from django.urls import path

from . import views

app_name = 'developer'

urlpatterns = [
    # ── Portal overview ───────────────────────────────────────────
    path('portal/stats/', views.portal_stats, name='portal-stats'),

    # ── API Keys ──────────────────────────────────────────────────
    path('api-keys/', views.APIKeyListCreateView.as_view(), name='apikey-list-create'),
    path('api-keys/<uuid:id>/', views.APIKeyDetailView.as_view(), name='apikey-detail'),
    path('api-keys/<uuid:id>/rotate/', views.rotate_api_key, name='apikey-rotate'),

    # ── Webhooks ──────────────────────────────────────────────────
    path('webhooks/', views.WebhookListCreateView.as_view(), name='webhook-list-create'),
    path('webhooks/<uuid:id>/', views.WebhookDetailView.as_view(), name='webhook-detail'),
    path('webhooks/<uuid:id>/deliveries/', views.WebhookDeliveryListView.as_view(), name='webhook-deliveries'),
    path('webhooks/<uuid:id>/test/', views.webhook_test_ping, name='webhook-test'),

    # ── OAuth Apps ────────────────────────────────────────────────
    path('oauth-apps/', views.OAuthAppListCreateView.as_view(), name='oauth-list-create'),
    path('oauth-apps/<uuid:id>/', views.OAuthAppDetailView.as_view(), name='oauth-detail'),
    path('oauth-apps/<uuid:id>/revoke/', views.revoke_oauth_app, name='oauth-revoke'),

    # ── Changelog ─────────────────────────────────────────────────
    path('changelog/', views.ChangelogListView.as_view(), name='changelog-list'),

    # ── Reference data (public) ───────────────────────────────────
    path('available-events/', views.available_events, name='available-events'),
    path('available-scopes/', views.available_scopes, name='available-scopes'),
    path('rate-limits/', views.rate_limits, name='rate-limits'),
    path('endpoints/', views.endpoint_catalogue, name='endpoint-catalogue'),
]
