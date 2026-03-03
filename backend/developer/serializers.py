"""
developer/serializers.py
DRF serializers for the Developer Platform.

Covers:
    - API Keys   (list / create / detail)
    - Webhooks   (list / create / detail + delivery log)
    - OAuth Apps (list / create / detail)
    - Changelog  (list)
"""
from rest_framework import serializers

from .models import (
    APIKey,
    WebhookEndpoint,
    WebhookDelivery,
    OAuthApplication,
    APIChangelog,
)


# ═══════════════════════════════════════════════════════════════════════════════
# API KEYS
# ═══════════════════════════════════════════════════════════════════════════════

class APIKeyListSerializer(serializers.ModelSerializer):
    """Read-only list representation of an API key."""
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True, default='')

    class Meta:
        model = APIKey
        fields = [
            'id', 'name', 'prefix', 'scopes', 'ip_allowlist',
            'is_active', 'last_used_at', 'last_used_ip', 'usage_count',
            'daily_usage', 'expires_at', 'created_at', 'created_by_name',
        ]
        read_only_fields = fields


class APIKeyCreateSerializer(serializers.Serializer):
    """
    Write-only serializer for API key creation.
    Returns the raw key exactly once in the response.
    """
    name = serializers.CharField(max_length=100)
    scopes = serializers.ListField(
        child=serializers.CharField(max_length=60),
        allow_empty=False,
        help_text='At least one scope is required.',
    )
    ip_allowlist = serializers.ListField(
        child=serializers.CharField(max_length=45),
        required=False, default=list,
    )
    expires_at = serializers.DateTimeField(required=False, allow_null=True, default=None)

    # ── Available scopes whitelist ───────────────────────────────────────
    VALID_SCOPES = {
        'read:jobs', 'write:jobs',
        'read:assessments', 'write:assessments',
        'read:users', 'write:users',
        'read:analytics',
        'admin',
    }

    def validate_scopes(self, value):
        invalid = set(value) - self.VALID_SCOPES
        if invalid:
            raise serializers.ValidationError(
                f'Invalid scopes: {", ".join(sorted(invalid))}. '
                f'Valid scopes: {", ".join(sorted(self.VALID_SCOPES))}'
            )
        return value

    def validate_name(self, value):
        company = self.context['company']
        if APIKey.objects.filter(company=company, name=value, is_active=True).exists():
            raise serializers.ValidationError('An active key with this name already exists.')
        return value

    def create(self, validated_data):
        company = self.context['company']
        user = self.context['request'].user

        instance, raw_key = APIKey.create_key(
            company=company,
            name=validated_data['name'],
            scopes=validated_data['scopes'],
            ip_allowlist=validated_data.get('ip_allowlist', []),
            expires_at=validated_data.get('expires_at'),
            created_by=user,
        )
        # Attach raw_key so the view can include it in the response
        instance._raw_key = raw_key
        return instance


class APIKeyCreatedSerializer(serializers.ModelSerializer):
    """Response after creating a key — includes the raw key (shown once)."""
    raw_key = serializers.SerializerMethodField()

    class Meta:
        model = APIKey
        fields = [
            'id', 'name', 'prefix', 'scopes', 'ip_allowlist',
            'is_active', 'expires_at', 'created_at', 'raw_key',
        ]
        read_only_fields = fields

    def get_raw_key(self, obj):
        return getattr(obj, '_raw_key', None)


# ═══════════════════════════════════════════════════════════════════════════════
# WEBHOOKS
# ═══════════════════════════════════════════════════════════════════════════════

class WebhookEndpointListSerializer(serializers.ModelSerializer):
    """Read-only webhook endpoint listing."""
    status = serializers.CharField(source='status_label', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True, default='')
    delivery_count = serializers.SerializerMethodField()

    class Meta:
        model = WebhookEndpoint
        fields = [
            'id', 'url', 'events', 'signing_secret_prefix', 'is_active',
            'status', 'failure_count', 'last_delivery_at', 'last_status_code',
            'description', 'created_at', 'created_by_name', 'delivery_count',
        ]
        read_only_fields = fields

    def get_delivery_count(self, obj):
        return obj.deliveries.count()


class WebhookEndpointCreateSerializer(serializers.Serializer):
    """Write-only serializer for creating a webhook endpoint."""
    url = serializers.URLField(max_length=500)
    events = serializers.ListField(
        child=serializers.CharField(max_length=60),
        allow_empty=False,
    )
    description = serializers.CharField(max_length=255, required=False, default='')

    VALID_EVENTS = {e[0] for e in WebhookEndpoint.AVAILABLE_EVENTS}

    def validate_url(self, value):
        if not value.startswith('https://'):
            raise serializers.ValidationError('Webhook URLs must use HTTPS.')
        company = self.context['company']
        if WebhookEndpoint.objects.filter(company=company, url=value, is_active=True).exists():
            raise serializers.ValidationError('An active webhook for this URL already exists.')
        return value

    def validate_events(self, value):
        invalid = set(value) - self.VALID_EVENTS
        if invalid:
            raise serializers.ValidationError(
                f'Invalid events: {", ".join(sorted(invalid))}. '
                f'Valid events: {", ".join(sorted(self.VALID_EVENTS))}'
            )
        return value

    def create(self, validated_data):
        company = self.context['company']
        user = self.context['request'].user

        instance, raw_secret = WebhookEndpoint.create_endpoint(
            company=company,
            url=validated_data['url'],
            events=validated_data['events'],
            description=validated_data.get('description', ''),
            created_by=user,
        )
        instance._raw_secret = raw_secret
        return instance


class WebhookEndpointCreatedSerializer(serializers.ModelSerializer):
    """Response after creating a webhook — includes signing secret (shown once)."""
    signing_secret = serializers.SerializerMethodField()
    status = serializers.CharField(source='status_label', read_only=True)

    class Meta:
        model = WebhookEndpoint
        fields = [
            'id', 'url', 'events', 'signing_secret_prefix', 'signing_secret',
            'is_active', 'status', 'description', 'created_at',
        ]
        read_only_fields = fields

    def get_signing_secret(self, obj):
        return getattr(obj, '_raw_secret', None)


class WebhookDeliverySerializer(serializers.ModelSerializer):
    """Read-only delivery log entry."""

    class Meta:
        model = WebhookDelivery
        fields = [
            'id', 'event_type', 'status_code', 'response_time_ms',
            'attempt_number', 'error_message', 'is_success', 'delivered_at',
        ]
        read_only_fields = fields


# ═══════════════════════════════════════════════════════════════════════════════
# OAUTH APPLICATIONS
# ═══════════════════════════════════════════════════════════════════════════════

class OAuthApplicationListSerializer(serializers.ModelSerializer):
    """Read-only list of registered OAuth applications."""
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True, default='')
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = OAuthApplication
        fields = [
            'id', 'name', 'client_id', 'client_secret_prefix', 'redirect_uris',
            'scopes', 'logo_initials', 'status', 'status_display',
            'authorized_users_count', 'created_at', 'created_by_name',
            'revoked_at',
        ]
        read_only_fields = fields


class OAuthApplicationCreateSerializer(serializers.Serializer):
    """Write-only serializer for registering a new OAuth app."""
    name = serializers.CharField(max_length=150)
    redirect_uris = serializers.ListField(
        child=serializers.URLField(max_length=500),
        allow_empty=False,
    )
    scopes = serializers.ListField(
        child=serializers.CharField(max_length=60),
        allow_empty=False,
    )

    VALID_SCOPES = {
        'user.read', 'user.write',
        'job.read', 'job.post',
        'assessment.read', 'assessment.write',
        'analytics.all',
        'webhook.manage',
    }

    def validate_scopes(self, value):
        invalid = set(value) - self.VALID_SCOPES
        if invalid:
            raise serializers.ValidationError(
                f'Invalid scopes: {", ".join(sorted(invalid))}. '
                f'Valid: {", ".join(sorted(self.VALID_SCOPES))}'
            )
        return value

    def validate_name(self, value):
        company = self.context['company']
        if OAuthApplication.objects.filter(company=company, name=value).exclude(
            status=OAuthApplication.Status.REVOKED,
        ).exists():
            raise serializers.ValidationError('An application with this name already exists.')
        return value

    def create(self, validated_data):
        company = self.context['company']
        user = self.context['request'].user

        instance, raw_secret = OAuthApplication.create_application(
            company=company,
            name=validated_data['name'],
            redirect_uris=validated_data['redirect_uris'],
            scopes=validated_data['scopes'],
            created_by=user,
        )
        instance._raw_secret = raw_secret
        return instance


class OAuthApplicationCreatedSerializer(serializers.ModelSerializer):
    """Response after registering — includes raw client_secret (shown once)."""
    client_secret = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = OAuthApplication
        fields = [
            'id', 'name', 'client_id', 'client_secret', 'client_secret_prefix',
            'redirect_uris', 'scopes', 'logo_initials', 'status', 'status_display',
            'created_at',
        ]
        read_only_fields = fields

    def get_client_secret(self, obj):
        return getattr(obj, '_raw_secret', None)


# ═══════════════════════════════════════════════════════════════════════════════
# CHANGELOG
# ═══════════════════════════════════════════════════════════════════════════════

class APIChangelogSerializer(serializers.ModelSerializer):
    """Read-only changelog entries for the developer portal."""
    author_name = serializers.CharField(source='author.full_name', read_only=True, default='TalentOrbit')
    change_type_display = serializers.CharField(source='get_change_type_display', read_only=True)

    class Meta:
        model = APIChangelog
        fields = [
            'id', 'version', 'title', 'description', 'change_type',
            'change_type_display', 'published_at', 'author_name',
        ]
        read_only_fields = fields


# ═══════════════════════════════════════════════════════════════════════════════
# PORTAL OVERVIEW — Aggregated stats (no model, computed)
# ═══════════════════════════════════════════════════════════════════════════════

class DeveloperPortalStatsSerializer(serializers.Serializer):
    """Aggregated developer portal statistics for a company."""
    api_keys_count = serializers.IntegerField()
    active_api_keys = serializers.IntegerField()
    webhooks_count = serializers.IntegerField()
    active_webhooks = serializers.IntegerField()
    oauth_apps_count = serializers.IntegerField()
    active_oauth_apps = serializers.IntegerField()
    total_api_calls_24h = serializers.IntegerField()
    webhook_delivery_rate = serializers.FloatField()
