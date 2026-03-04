"""
realtime/views.py
REST endpoints for push notification token management and user presence.
"""

import logging

from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from .models import PushSubscription
from .serializers import RegisterPushTokenSerializer

logger = logging.getLogger(__name__)


class PushSubscribeThrottle(ScopedRateThrottle):
    scope = 'push_subscribe'


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([PushSubscribeThrottle])
def register_push_token(request):
    """
    POST /api/v1/push/subscribe/
    Register an FCM device token for the authenticated user.
    Idempotent — re-registering an existing token reactivates it.
    """
    serializer = RegisterPushTokenSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    token = serializer.validated_data['token']
    platform = serializer.validated_data['platform']
    user_agent = request.META.get('HTTP_USER_AGENT', '')

    subscription, created = PushSubscription.objects.update_or_create(
        token=token,
        defaults={
            'user': request.user,
            'platform': platform,
            'user_agent': user_agent,
            'is_active': True,
        },
    )

    logger.info(
        'Push token %s: user=%s platform=%s',
        'registered' if created else 'updated',
        request.user.id,
        platform,
    )

    return Response(
        {
            'status': 'registered' if created else 'updated',
            'subscription_id': subscription.id,
        },
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def unregister_push_token(request):
    """
    POST /api/v1/push/unsubscribe/
    Deactivate a push token (e.g. when user disables notifications).
    """
    token = request.data.get('token')
    if not token:
        return Response(
            {'detail': 'Token is required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    count = PushSubscription.objects.filter(
        user=request.user,
        token=token,
    ).update(is_active=False)

    if count == 0:
        return Response({'detail': 'Token not found.'}, status=status.HTTP_404_NOT_FOUND)

    return Response({'status': 'unsubscribed'})


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def get_presence(request):
    """
    POST /api/v1/push/presence/
    Get presence (online/offline/last-seen) for a list of user IDs.

    Body:
        { "user_ids": [1, 2, 3] }

    Response:
        {
            "presence": {
                "1": { "is_online": true, "last_seen": null },
                "2": { "is_online": false, "last_seen": "2026-03-01T12:00:00+00:00" }
            }
        }

    Clients call this on initial page load to populate presence state,
    then rely on WebSocket presence events for real-time updates.
    """
    from .presence import get_bulk_presence

    user_ids = request.data.get('user_ids', [])
    if not isinstance(user_ids, list):
        return Response(
            {'detail': 'user_ids must be a list of integers.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Cap to prevent abuse
    user_ids = [int(uid) for uid in user_ids[:100] if isinstance(uid, (int, str))]

    presence = get_bulk_presence(user_ids)

    # Convert int keys to string for JSON compatibility
    return Response({
        'presence': {str(k): v for k, v in presence.items()},
    })
