"""
developer/views.py
REST API views for the Developer Platform.

Enterprise patterns applied:
    - @audit_action decorator on all mutation endpoints
    - Per-endpoint throttle classes for security-sensitive operations
    - transaction.atomic() on multi-step writes (key rotation)
    - HMAC-SHA256 signed outbound webhook test pings
    - Django cache on static reference data + portal stats
    - Proper error propagation and structured responses

Endpoints:
    ── Portal Overview ──────────────────────────────────────────────
    GET  /portal/stats/            — Aggregated developer stats

    ── API Keys ─────────────────────────────────────────────────────
    GET  /api-keys/                — List company API keys
    POST /api-keys/                — Create a new API key (returns raw key once)
    GET  /api-keys/<id>/           — Detail view
    DEL  /api-keys/<id>/           — Revoke (soft-deactivate) a key
    POST /api-keys/<id>/rotate/    — Rotate: revoke old, create new with same config

    ── Webhooks ─────────────────────────────────────────────────────
    GET  /webhooks/                — List company webhook endpoints
    POST /webhooks/                — Create a new webhook endpoint
    GET  /webhooks/<id>/           — Detail view
    DEL  /webhooks/<id>/           — Deactivate a webhook
    PATCH /webhooks/<id>/          — Update events / URL
    GET  /webhooks/<id>/deliveries/ — Delivery log for a webhook
    POST /webhooks/<id>/test/      — Send a test ping (HMAC-signed)

    ── OAuth Apps ───────────────────────────────────────────────────
    GET  /oauth-apps/              — List company OAuth applications
    POST /oauth-apps/              — Register new app (returns secret once)
    GET  /oauth-apps/<id>/         — Detail view
    POST /oauth-apps/<id>/revoke/  — Revoke application

    ── Changelog ────────────────────────────────────────────────────
    GET  /changelog/               — Public changelog entries

    ── Reference Data ───────────────────────────────────────────────
    GET  /available-events/        — Webhook event type catalogue (cached)
    GET  /available-scopes/        — API key + OAuth scope catalogue (cached)
    GET  /rate-limits/             — Rate limit tiers (cached)
    GET  /endpoints/               — Swagger-lite endpoint list (cached)
"""
import json
import logging
import time

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response

from accounts.permissions import IsCompanyUser, IsEmailVerified
from compliance.constants import AuditAction, AuditCategory
from compliance.decorators import audit_action

from .models import (
    APIChangelog,
    APIKey,
    OAuthApplication,
    WebhookDelivery,
    WebhookEndpoint,
)
from .serializers import (
    APIChangelogSerializer,
    APIKeyCreatedSerializer,
    APIKeyCreateSerializer,
    APIKeyListSerializer,
    DeveloperPortalStatsSerializer,
    OAuthApplicationCreatedSerializer,
    OAuthApplicationCreateSerializer,
    OAuthApplicationListSerializer,
    WebhookDeliverySerializer,
    WebhookEndpointCreatedSerializer,
    WebhookEndpointCreateSerializer,
    WebhookEndpointListSerializer,
)
from .throttling import (
    APIKeyCreateThrottle,
    APIKeyRotateThrottle,
    OAuthAppCreateThrottle,
    OAuthAppRevokeThrottle,
    WebhookCreateThrottle,
    WebhookTestPingThrottle,
)

logger = logging.getLogger(__name__)

# Cache TTLs (seconds)
_CACHE_REFERENCE_TTL = 3600      # 1 hour for static reference data
_CACHE_PORTAL_STATS_TTL = 120    # 2 minutes for portal stats


def _get_company(request):
    """Resolve the current user's CompanyProfile or raise 403."""
    if not hasattr(request.user, 'company_profile'):
        return None
    return request.user.company_profile


# ═══════════════════════════════════════════════════════════════════════════════
# PORTAL OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsCompanyUser])
def portal_stats(request):
    """Aggregated developer platform statistics for the company."""
    company = _get_company(request)
    if not company:
        return Response({'detail': 'Company profile not found.'}, status=status.HTTP_403_FORBIDDEN)

    # Check cache first
    cache_key = f'developer:portal_stats:{company.pk}'
    cached = cache.get(cache_key)
    if cached:
        return Response(cached)

    keys = APIKey.objects.filter(company=company)
    webhooks = WebhookEndpoint.objects.filter(company=company)
    oauth_apps = OAuthApplication.objects.filter(company=company)

    # 24h usage across all active keys
    total_24h = sum(
        (k.daily_usage[-1] if k.daily_usage else 0)
        for k in keys.filter(is_active=True)
    )

    # Webhook delivery success rate (last 100 deliveries)
    recent_deliveries = WebhookDelivery.objects.filter(
        endpoint__company=company,
    ).order_by('-delivered_at')[:100]
    total_recent = recent_deliveries.count()
    success_recent = sum(1 for d in recent_deliveries if d.is_success)
    delivery_rate = round((success_recent / total_recent * 100), 1) if total_recent > 0 else 100.0

    data = {
        'api_keys_count': keys.count(),
        'active_api_keys': keys.filter(is_active=True).count(),
        'webhooks_count': webhooks.count(),
        'active_webhooks': webhooks.filter(is_active=True).count(),
        'oauth_apps_count': oauth_apps.count(),
        'active_oauth_apps': oauth_apps.filter(status=OAuthApplication.Status.ACTIVE).count(),
        'total_api_calls_24h': total_24h,
        'webhook_delivery_rate': delivery_rate,
    }
    serializer = DeveloperPortalStatsSerializer(data)
    cache.set(cache_key, serializer.data, _CACHE_PORTAL_STATS_TTL)
    return Response(serializer.data)


# ═══════════════════════════════════════════════════════════════════════════════
# API KEYS
# ═══════════════════════════════════════════════════════════════════════════════

class APIKeyListCreateView(generics.ListCreateAPIView):
    """
    GET  — List all API keys for the company.
    POST — Create a new API key (throttled, audited).
    """
    permission_classes = [permissions.IsAuthenticated, IsCompanyUser, IsEmailVerified]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return APIKeyCreateSerializer
        return APIKeyListSerializer

    def get_queryset(self):
        company = _get_company(self.request)
        if not company:
            return APIKey.objects.none()
        return APIKey.objects.filter(company=company).select_related('created_by')

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['company'] = _get_company(self.request)
        return ctx

    def get_throttles(self):
        if self.request.method == 'POST':
            return [APIKeyCreateThrottle()]
        return super().get_throttles()

    @audit_action(
        action=AuditAction.API_KEY_CREATE,
        category=AuditCategory.DEVELOPER,
        resource_type='developer.APIKey',
        get_resource_id=lambda req, res: res.data.get('id', ''),
        get_description=lambda req, res: f'Created API key "{req.data.get("name", "")}"',
        get_changes=lambda req, res: {'scopes': req.data.get('scopes', [])},
    )
    def create(self, request, *args, **kwargs):
        company = _get_company(request)
        if not company:
            return Response({'detail': 'Company profile not found.'}, status=status.HTTP_403_FORBIDDEN)

        # Tier-based key limits
        active_count = APIKey.objects.filter(company=company, is_active=True).count()
        tier_limits = {'free': 2, 'starter': 5, 'professional': 20, 'enterprise': 100}
        limit = tier_limits.get(getattr(company, 'subscription_tier', 'free'), 2)
        if active_count >= limit:
            return Response(
                {'detail': f'API key limit reached ({limit} for {getattr(company, "subscription_tier", "free")} tier).'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        # Invalidate portal stats cache
        cache.delete(f'developer:portal_stats:{company.pk}')

        return Response(
            APIKeyCreatedSerializer(instance).data,
            status=status.HTTP_201_CREATED,
        )


class APIKeyDetailView(generics.RetrieveDestroyAPIView):
    """
    GET    — API key detail.
    DELETE — Revoke (soft-deactivate) a key (audited).
    """
    permission_classes = [permissions.IsAuthenticated, IsCompanyUser]
    serializer_class = APIKeyListSerializer
    lookup_field = 'id'

    def get_queryset(self):
        company = _get_company(self.request)
        if not company:
            return APIKey.objects.none()
        return APIKey.objects.filter(company=company)

    @audit_action(
        action=AuditAction.API_KEY_REVOKE,
        category=AuditCategory.DEVELOPER,
        resource_type='developer.APIKey',
        get_resource_id=lambda req, res: req.parser_context['kwargs'].get('id', ''),
        get_description=lambda req, res: 'Revoked API key',
    )
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save(update_fields=['is_active'])
        company = _get_company(request)
        if company:
            cache.delete(f'developer:portal_stats:{company.pk}')
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, IsCompanyUser])
@throttle_classes([APIKeyRotateThrottle])
@audit_action(
    action=AuditAction.API_KEY_ROTATE,
    category=AuditCategory.DEVELOPER,
    resource_type='developer.APIKey',
    get_resource_id=lambda req, res: res.data.get('id', '') if hasattr(res, 'data') else '',
    get_description=lambda req, res: 'Rotated API key (old key revoked, new key generated)',
)
def rotate_api_key(request, id):
    """Revoke old key, create a new one with the same name/scopes/allowlist.

    Uses transaction.atomic() to ensure the old key is not deactivated
    if creation of the replacement fails.
    """
    company = _get_company(request)
    if not company:
        return Response({'detail': 'Company profile not found.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        old_key = APIKey.objects.get(id=id, company=company, is_active=True)
    except APIKey.DoesNotExist:
        return Response({'detail': 'Key not found.'}, status=status.HTTP_404_NOT_FOUND)

    with transaction.atomic():
        # Deactivate old key
        old_key.is_active = False
        old_key.save(update_fields=['is_active'])

        # Create replacement with identical configuration
        new_key, raw_key = APIKey.create_key(
            company=company,
            name=old_key.name,
            scopes=old_key.scopes,
            ip_allowlist=old_key.ip_allowlist,
            expires_at=old_key.expires_at,
            created_by=request.user,
        )

    new_key._raw_key = raw_key
    cache.delete(f'developer:portal_stats:{company.pk}')

    return Response(
        APIKeyCreatedSerializer(new_key).data,
        status=status.HTTP_201_CREATED,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# WEBHOOKS
# ═══════════════════════════════════════════════════════════════════════════════

class WebhookListCreateView(generics.ListCreateAPIView):
    """
    GET  — List webhook endpoints for the company.
    POST — Register a new webhook endpoint (throttled, audited).
    """
    permission_classes = [permissions.IsAuthenticated, IsCompanyUser, IsEmailVerified]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return WebhookEndpointCreateSerializer
        return WebhookEndpointListSerializer

    def get_queryset(self):
        company = _get_company(self.request)
        if not company:
            return WebhookEndpoint.objects.none()
        return WebhookEndpoint.objects.filter(company=company).select_related('created_by')

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['company'] = _get_company(self.request)
        return ctx

    def get_throttles(self):
        if self.request.method == 'POST':
            return [WebhookCreateThrottle()]
        return super().get_throttles()

    @audit_action(
        action=AuditAction.WEBHOOK_CREATE,
        category=AuditCategory.DEVELOPER,
        resource_type='developer.WebhookEndpoint',
        get_resource_id=lambda req, res: res.data.get('id', ''),
        get_description=lambda req, res: f'Registered webhook endpoint: {req.data.get("url", "")}',
        get_changes=lambda req, res: {'events': req.data.get('events', [])},
    )
    def create(self, request, *args, **kwargs):
        company = _get_company(request)
        if not company:
            return Response({'detail': 'Company profile not found.'}, status=status.HTTP_403_FORBIDDEN)

        # Tier-based endpoint limits
        active_count = WebhookEndpoint.objects.filter(company=company, is_active=True).count()
        tier_limits = {'free': 2, 'starter': 5, 'professional': 15, 'enterprise': 50}
        limit = tier_limits.get(getattr(company, 'subscription_tier', 'free'), 2)
        if active_count >= limit:
            return Response(
                {'detail': f'Webhook limit reached ({limit} for {getattr(company, "subscription_tier", "free")} tier).'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        cache.delete(f'developer:portal_stats:{company.pk}')

        return Response(
            WebhookEndpointCreatedSerializer(instance).data,
            status=status.HTTP_201_CREATED,
        )


class WebhookDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    — Webhook detail.
    PATCH  — Update events/url/description (audited).
    DELETE — Deactivate webhook (audited).
    """
    permission_classes = [permissions.IsAuthenticated, IsCompanyUser]
    serializer_class = WebhookEndpointListSerializer
    lookup_field = 'id'

    def get_queryset(self):
        company = _get_company(self.request)
        if not company:
            return WebhookEndpoint.objects.none()
        return WebhookEndpoint.objects.filter(company=company)

    @audit_action(
        action=AuditAction.WEBHOOK_UPDATE,
        category=AuditCategory.DEVELOPER,
        resource_type='developer.WebhookEndpoint',
        get_resource_id=lambda req, res: req.parser_context['kwargs'].get('id', ''),
        get_description=lambda req, res: 'Updated webhook endpoint configuration',
        get_changes=lambda req, res: {k: v for k, v in req.data.items() if k in ('events', 'url', 'description', 'is_active')},
    )
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        # Only allow updating specific fields
        allowed = {'events', 'url', 'description', 'is_active'}
        data = {k: v for k, v in request.data.items() if k in allowed}
        for key, value in data.items():
            setattr(instance, key, value)
        instance.save(update_fields=list(data.keys()))
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @audit_action(
        action=AuditAction.WEBHOOK_DELETE,
        category=AuditCategory.DEVELOPER,
        resource_type='developer.WebhookEndpoint',
        get_resource_id=lambda req, res: req.parser_context['kwargs'].get('id', ''),
        get_description=lambda req, res: 'Deactivated webhook endpoint',
    )
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save(update_fields=['is_active'])
        company = _get_company(request)
        if company:
            cache.delete(f'developer:portal_stats:{company.pk}')
        return Response(status=status.HTTP_204_NO_CONTENT)


class WebhookDeliveryListView(generics.ListAPIView):
    """GET — Delivery log for a specific webhook endpoint."""
    permission_classes = [permissions.IsAuthenticated, IsCompanyUser]
    serializer_class = WebhookDeliverySerializer

    def get_queryset(self):
        company = _get_company(self.request)
        if not company:
            return WebhookDelivery.objects.none()
        return WebhookDelivery.objects.filter(
            endpoint__company=company,
            endpoint__id=self.kwargs['id'],
        ).order_by('-delivered_at')[:100]


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, IsCompanyUser])
@throttle_classes([WebhookTestPingThrottle])
@audit_action(
    action=AuditAction.WEBHOOK_TEST_PING,
    category=AuditCategory.DEVELOPER,
    resource_type='developer.WebhookEndpoint',
    get_resource_id=lambda req, res: req.parser_context['kwargs'].get('id', ''),
    get_description=lambda req, res: 'Sent test ping to webhook endpoint',
)
def webhook_test_ping(request, id):
    """Send an HMAC-signed test ping event to the webhook endpoint."""
    import requests as http_requests

    from .tasks import compute_webhook_signature

    company = _get_company(request)
    if not company:
        return Response({'detail': 'Company profile not found.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        endpoint = WebhookEndpoint.objects.get(id=id, company=company, is_active=True)
    except WebhookEndpoint.DoesNotExist:
        return Response({'detail': 'Webhook not found.'}, status=status.HTTP_404_NOT_FOUND)

    payload = {
        'event': 'ping',
        'timestamp': timezone.now().isoformat(),
        'webhook_id': str(endpoint.id),
    }

    # Sign the payload with HMAC-SHA256
    raw_secret = endpoint.get_signing_secret()
    timestamp_str = str(int(time.time()))
    payload_bytes = json.dumps(payload, separators=(',', ':'), sort_keys=True).encode('utf-8')
    signature = compute_webhook_signature(raw_secret, timestamp_str, payload_bytes)

    headers = {
        'Content-Type': 'application/json',
        'X-TalentOrbit-Event': 'ping',
        'X-TalentOrbit-Timestamp': timestamp_str,
        'X-TalentOrbit-Signature': signature,
        'User-Agent': 'TalentOrbit-Webhook/1.0',
    }

    start = time.monotonic()
    try:
        resp = http_requests.post(
            endpoint.url,
            data=payload_bytes,
            headers=headers,
            timeout=10,
        )
        elapsed = int((time.monotonic() - start) * 1000)

        delivery = WebhookDelivery.objects.create(
            endpoint=endpoint,
            event_type='ping',
            payload=payload,
            status_code=resp.status_code,
            response_body=resp.text[:2048],
            response_time_ms=elapsed,
            is_success=200 <= resp.status_code < 300,
        )
        if delivery.is_success:
            endpoint.failure_count = 0
        else:
            endpoint.failure_count += 1
        endpoint.last_delivery_at = timezone.now()
        endpoint.last_status_code = resp.status_code
        endpoint.save(update_fields=['failure_count', 'last_delivery_at', 'last_status_code'])

        return Response(WebhookDeliverySerializer(delivery).data)

    except http_requests.RequestException as e:
        elapsed = int((time.monotonic() - start) * 1000)
        delivery = WebhookDelivery.objects.create(
            endpoint=endpoint,
            event_type='ping',
            payload=payload,
            response_time_ms=elapsed,
            error_message=str(e)[:500],
            is_success=False,
        )
        endpoint.failure_count += 1
        endpoint.save(update_fields=['failure_count'])
        return Response(
            WebhookDeliverySerializer(delivery).data,
            status=status.HTTP_502_BAD_GATEWAY,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# OAUTH APPLICATIONS
# ═══════════════════════════════════════════════════════════════════════════════

class OAuthAppListCreateView(generics.ListCreateAPIView):
    """
    GET  — List company OAuth applications.
    POST — Register a new OAuth application (throttled, audited).
    """
    permission_classes = [permissions.IsAuthenticated, IsCompanyUser, IsEmailVerified]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return OAuthApplicationCreateSerializer
        return OAuthApplicationListSerializer

    def get_queryset(self):
        company = _get_company(self.request)
        if not company:
            return OAuthApplication.objects.none()
        qs = OAuthApplication.objects.filter(company=company).select_related('created_by')
        # Optional status filter
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['company'] = _get_company(self.request)
        return ctx

    def get_throttles(self):
        if self.request.method == 'POST':
            return [OAuthAppCreateThrottle()]
        return super().get_throttles()

    @audit_action(
        action=AuditAction.OAUTH_APP_CREATE,
        category=AuditCategory.DEVELOPER,
        resource_type='developer.OAuthApplication',
        get_resource_id=lambda req, res: res.data.get('id', ''),
        get_description=lambda req, res: f'Registered OAuth application "{req.data.get("name", "")}"',
        get_changes=lambda req, res: {'scopes': req.data.get('scopes', [])},
    )
    def create(self, request, *args, **kwargs):
        company = _get_company(request)
        if not company:
            return Response({'detail': 'Company profile not found.'}, status=status.HTTP_403_FORBIDDEN)

        # Tier-based app limits
        non_revoked = OAuthApplication.objects.filter(company=company).exclude(
            status=OAuthApplication.Status.REVOKED,
        ).count()
        tier_limits = {'free': 1, 'starter': 3, 'professional': 10, 'enterprise': 50}
        limit = tier_limits.get(getattr(company, 'subscription_tier', 'free'), 1)
        if non_revoked >= limit:
            return Response(
                {'detail': f'OAuth app limit reached ({limit} for {getattr(company, "subscription_tier", "free")} tier).'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        cache.delete(f'developer:portal_stats:{company.pk}')

        return Response(
            OAuthApplicationCreatedSerializer(instance).data,
            status=status.HTTP_201_CREATED,
        )


class OAuthAppDetailView(generics.RetrieveAPIView):
    """GET — OAuth application detail."""
    permission_classes = [permissions.IsAuthenticated, IsCompanyUser]
    serializer_class = OAuthApplicationListSerializer
    lookup_field = 'id'

    def get_queryset(self):
        company = _get_company(self.request)
        if not company:
            return OAuthApplication.objects.none()
        return OAuthApplication.objects.filter(company=company)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, IsCompanyUser])
@throttle_classes([OAuthAppRevokeThrottle])
@audit_action(
    action=AuditAction.OAUTH_APP_REVOKE,
    category=AuditCategory.DEVELOPER,
    resource_type='developer.OAuthApplication',
    get_resource_id=lambda req, res: req.parser_context['kwargs'].get('id', ''),
    get_description=lambda req, res: 'Revoked OAuth application',
)
def revoke_oauth_app(request, id):
    """Revoke an OAuth application permanently."""
    company = _get_company(request)
    if not company:
        return Response({'detail': 'Company profile not found.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        app = OAuthApplication.objects.get(id=id, company=company)
    except OAuthApplication.DoesNotExist:
        return Response({'detail': 'Application not found.'}, status=status.HTTP_404_NOT_FOUND)

    if app.status == OAuthApplication.Status.REVOKED:
        return Response({'detail': 'Application already revoked.'}, status=status.HTTP_400_BAD_REQUEST)

    app.revoke(user=request.user)
    cache.delete(f'developer:portal_stats:{company.pk}')

    return Response(OAuthApplicationListSerializer(app).data)


# ═══════════════════════════════════════════════════════════════════════════════
# CHANGELOG
# ═══════════════════════════════════════════════════════════════════════════════

class ChangelogListView(generics.ListAPIView):
    """
    GET — Public changelog entries for the developer portal.
    No authentication required — displayed in the public dev portal.
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = APIChangelogSerializer
    queryset = APIChangelog.objects.filter(is_published=True)


# ═══════════════════════════════════════════════════════════════════════════════
# REFERENCE DATA (public, cached)
# ═══════════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def available_events(request):
    """List all webhook event types (cached 1h)."""
    cache_key = 'developer:ref:available_events'
    data = cache.get(cache_key)
    if data is None:
        data = [
            {'event': e[0], 'label': e[1]}
            for e in WebhookEndpoint.AVAILABLE_EVENTS
        ]
        cache.set(cache_key, data, _CACHE_REFERENCE_TTL)
    return Response(data)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def available_scopes(request):
    """List all available scopes for API keys and OAuth apps (cached 1h)."""
    cache_key = 'developer:ref:available_scopes'
    data = cache.get(cache_key)
    if data is None:
        api_key_scopes = sorted(APIKeyCreateSerializer.VALID_SCOPES)
        oauth_scopes = sorted(OAuthApplicationCreateSerializer.VALID_SCOPES)
        data = {
            'api_key_scopes': api_key_scopes,
            'oauth_scopes': oauth_scopes,
        }
        cache.set(cache_key, data, _CACHE_REFERENCE_TTL)
    return Response(data)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def rate_limits(request):
    """Rate limit tiers for the API (cached 1h)."""
    cache_key = 'developer:ref:rate_limits'
    data = cache.get(cache_key)
    if data is None:
        data = [
            {'tier': 'Free', 'limit': '1,000', 'window': 'Per Hour', 'burst': '50/min'},
            {'tier': 'Starter', 'limit': '10,000', 'window': 'Per Hour', 'burst': '200/min'},
            {'tier': 'Professional', 'limit': '50,000', 'window': 'Per Hour', 'burst': '1,000/min'},
            {'tier': 'Enterprise', 'limit': 'Unlimited', 'window': '—', 'burst': 'Custom'},
        ]
        cache.set(cache_key, data, _CACHE_REFERENCE_TTL)
    return Response(data)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def endpoint_catalogue(request):
    """Swagger-lite endpoint listing for the developer portal (cached 1h)."""
    cache_key = 'developer:ref:endpoint_catalogue'
    data = cache.get(cache_key)
    if data is None:
        data = [
            {'method': 'GET', 'path': '/v1/jobs', 'description': 'List all published jobs with pagination + filters.'},
            {'method': 'POST', 'path': '/v1/jobs', 'description': 'Create a new job posting (company auth required).'},
            {'method': 'GET', 'path': '/v1/jobs/{id}', 'description': 'Retrieve a single job by ID.'},
            {'method': 'GET', 'path': '/v1/users/{id}', 'description': 'Retrieve user public profile.'},
            {'method': 'POST', 'path': '/v1/auth/token', 'description': 'Obtain JWT access + refresh tokens.'},
            {'method': 'POST', 'path': '/v1/auth/token/refresh', 'description': 'Refresh an expired access token.'},
            {'method': 'GET', 'path': '/v1/assessments', 'description': 'List assessment catalog.'},
            {'method': 'POST', 'path': '/v1/assessments/attempts/{id}/submit', 'description': 'Submit assessment answer.'},
            {'method': 'GET', 'path': '/v1/courses', 'description': 'Browse course catalog.'},
            {'method': 'GET', 'path': '/v1/search', 'description': 'Full-text search across jobs + courses.'},
            {'method': 'GET', 'path': '/v1/webhooks', 'description': 'List webhook endpoints.'},
            {'method': 'POST', 'path': '/v1/webhooks', 'description': 'Register a new webhook endpoint.'},
            {'method': 'GET', 'path': '/v1/intelligence/recommendations', 'description': 'AI-powered job recommendations.'},
            {'method': 'GET', 'path': '/v1/compliance/audit-log', 'description': 'Query audit log (admin only).'},
        ]
        cache.set(cache_key, data, _CACHE_REFERENCE_TTL)
    return Response(data)
