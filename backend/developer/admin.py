"""
developer/admin.py
Django admin configuration for the Developer Platform models.
"""
from django.contrib import admin
from django.utils.html import format_html

from .models import (
    APIChangelog,
    APIKey,
    OAuthApplication,
    WebhookDelivery,
    WebhookEndpoint,
)


# ═══════════════════════════════════════════════════════════════════════════════
# API KEY
# ═══════════════════════════════════════════════════════════════════════════════

@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'company', 'prefix', 'is_active', 'usage_count',
        'last_used_at', 'created_at',
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'prefix', 'company__legal_name']
    readonly_fields = [
        'id', 'key_hash', 'prefix', 'usage_count', 'daily_usage',
        'last_used_at', 'last_used_ip', 'created_at', 'created_by',
    ]
    raw_id_fields = ['company', 'created_by']
    actions = ['revoke_keys']

    @admin.action(description='Revoke selected API keys')
    def revoke_keys(self, request, queryset):
        count = queryset.filter(is_active=True).update(is_active=False)
        self.message_user(request, f'{count} key(s) revoked.')


# ═══════════════════════════════════════════════════════════════════════════════
# WEBHOOK ENDPOINT + DELIVERY INLINE
# ═══════════════════════════════════════════════════════════════════════════════

class WebhookDeliveryInline(admin.TabularInline):
    model = WebhookDelivery
    extra = 0
    max_num = 20
    readonly_fields = [
        'event_type', 'status_code', 'response_time_ms', 'attempt_number',
        'is_success', 'delivered_at', 'error_message',
    ]
    fields = readonly_fields
    ordering = ['-delivered_at']
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(WebhookEndpoint)
class WebhookEndpointAdmin(admin.ModelAdmin):
    list_display = [
        'url_truncated', 'company', 'is_active', 'failure_count',
        'last_status_code', 'last_delivery_at', 'created_at',
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = ['url', 'company__legal_name']
    readonly_fields = [
        'id', 'signing_secret_signed', 'signing_secret_prefix',
        'failure_count', 'last_delivery_at', 'last_status_code',
        'created_at', 'created_by',
    ]
    raw_id_fields = ['company', 'created_by']
    inlines = [WebhookDeliveryInline]
    actions = ['disable_webhooks', 'reset_failure_count']

    @admin.display(description='URL')
    def url_truncated(self, obj):
        return obj.url[:60] + ('…' if len(obj.url) > 60 else '')

    @admin.action(description='Disable selected webhooks')
    def disable_webhooks(self, request, queryset):
        count = queryset.filter(is_active=True).update(is_active=False)
        self.message_user(request, f'{count} webhook(s) disabled.')

    @admin.action(description='Reset failure count to 0')
    def reset_failure_count(self, request, queryset):
        queryset.update(failure_count=0)
        self.message_user(request, 'Failure counts reset.')


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(admin.ModelAdmin):
    list_display = [
        'event_type', 'endpoint', 'status_code', 'response_time_ms',
        'is_success', 'attempt_number', 'delivered_at',
    ]
    list_filter = ['is_success', 'event_type', 'delivered_at']
    search_fields = ['event_type', 'endpoint__url']
    readonly_fields = [
        'id', 'endpoint', 'event_type', 'payload', 'status_code',
        'response_body', 'response_time_ms', 'attempt_number',
        'error_message', 'is_success', 'delivered_at',
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# OAUTH APPLICATION
# ═══════════════════════════════════════════════════════════════════════════════

@admin.register(OAuthApplication)
class OAuthApplicationAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'company', 'client_id', 'status', 'authorized_users_count',
        'created_at',
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['name', 'client_id', 'company__legal_name']
    readonly_fields = [
        'id', 'client_id', 'client_secret_hash', 'client_secret_prefix',
        'logo_initials', 'authorized_users_count', 'created_at', 'created_by',
        'revoked_at', 'revoked_by',
    ]
    raw_id_fields = ['company', 'created_by', 'revoked_by']
    actions = ['revoke_apps', 'activate_apps']

    @admin.action(description='Revoke selected applications')
    def revoke_apps(self, request, queryset):
        from django.utils import timezone as tz
        count = queryset.exclude(status='revoked').update(
            status='revoked', revoked_at=tz.now(),
        )
        self.message_user(request, f'{count} app(s) revoked.')

    @admin.action(description='Activate selected applications')
    def activate_apps(self, request, queryset):
        count = queryset.filter(status='pending').update(status='active')
        self.message_user(request, f'{count} app(s) activated.')


# ═══════════════════════════════════════════════════════════════════════════════
# API CHANGELOG
# ═══════════════════════════════════════════════════════════════════════════════

@admin.register(APIChangelog)
class APIChangelogAdmin(admin.ModelAdmin):
    list_display = ['version', 'title', 'change_type', 'is_published', 'published_at']
    list_filter = ['change_type', 'is_published']
    search_fields = ['version', 'title', 'description']
    raw_id_fields = ['author']
    actions = ['publish_entries']

    @admin.action(description='Publish selected changelog entries')
    def publish_entries(self, request, queryset):
        from django.utils import timezone as tz
        count = queryset.filter(is_published=False).update(
            is_published=True, published_at=tz.now(),
        )
        self.message_user(request, f'{count} entry/entries published.')
