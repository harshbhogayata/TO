"""
realtime/serializers.py
Serializers for push subscription management.
"""

from rest_framework import serializers
from .models import PushSubscription


class PushSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PushSubscription
        fields = ['id', 'token', 'platform', 'is_active', 'created_at', 'last_used_at']
        read_only_fields = ['id', 'is_active', 'created_at', 'last_used_at']


class RegisterPushTokenSerializer(serializers.Serializer):
    """Register a new FCM push token for the authenticated user."""
    token = serializers.CharField(max_length=4096)
    platform = serializers.ChoiceField(
        choices=PushSubscription.Platform.choices,
        default=PushSubscription.Platform.WEB,
    )
