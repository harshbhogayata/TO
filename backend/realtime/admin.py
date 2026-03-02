"""
realtime/admin.py
Admin registration for push subscription management.
"""

from django.contrib import admin
from .models import PushSubscription


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user', 'platform', 'is_active', 'created_at', 'last_used_at']
    list_filter = ['platform', 'is_active']
    search_fields = ['user__email', 'token']
    readonly_fields = ['created_at', 'last_used_at']
    raw_id_fields = ['user']
