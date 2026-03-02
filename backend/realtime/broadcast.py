"""
realtime/broadcast.py
Utility functions for broadcasting events from synchronous contexts
(Django views, Celery tasks, signal handlers) to WebSocket consumers.

These functions use ``async_to_sync`` to bridge the sync/async gap,
allowing any Django code to push real-time updates.
"""

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


def _get_layer():
    """Get the configured channel layer, or None if unavailable."""
    try:
        layer = get_channel_layer()
        if layer is None:
            logger.debug('Channel layer not configured — skipping broadcast.')
        return layer
    except Exception:
        logger.debug('Channel layer unavailable — skipping broadcast.')
        return None


def broadcast_notification(user_id: int, notification_data: dict):
    """
    Push a notification to a user's WebSocket connection in real time.

    Args:
        user_id: The recipient user's ID.
        notification_data: Dict matching the NotificationSerializer output.
    """
    layer = _get_layer()
    if layer is None:
        return

    group = f'user_{user_id}'
    try:
        async_to_sync(layer.group_send)(group, {
            'type': 'push_notification',
            'notification': notification_data,
        })
    except Exception:
        logger.exception('Failed to broadcast notification to user %s', user_id)


def broadcast_unread_count(user_id: int, count: int):
    """
    Push an updated unread count to a user's notification WebSocket.

    Args:
        user_id: The recipient user's ID.
        count: New unread notification count.
    """
    layer = _get_layer()
    if layer is None:
        return

    group = f'user_{user_id}'
    try:
        async_to_sync(layer.group_send)(group, {
            'type': 'unread_count_update',
            'count': count,
        })
    except Exception:
        logger.exception('Failed to broadcast unread count to user %s', user_id)


def broadcast_thread_message(thread_id: int, message_data: dict):
    """
    Push a new message to a thread's WebSocket group.
    Used when messages are created via REST API (non-WebSocket path).

    Args:
        thread_id: The thread ID.
        message_data: Dict matching the MessageSerializer output.
    """
    layer = _get_layer()
    if layer is None:
        return

    group = f'thread_{thread_id}'
    try:
        async_to_sync(layer.group_send)(group, {
            'type': 'chat_message',
            'message': message_data,
        })
    except Exception:
        logger.exception('Failed to broadcast message to thread %s', thread_id)


def notify_thread_joined(user_id: int, thread_id: int):
    """
    Tell a user's ChatConsumer to join a new thread group.
    Used when a thread is created via REST API.
    """
    layer = _get_layer()
    if layer is None:
        return

    # We broadcast to the user's notification group since
    # the ChatConsumer doesn't have a personal group.
    # Instead, we send to all thread groups the user is in.
    # A simpler approach: broadcast to user's personal group.
    group = f'user_{user_id}'
    try:
        async_to_sync(layer.group_send)(group, {
            'type': 'thread_joined',
            'thread_id': thread_id,
        })
    except Exception:
        logger.debug('Failed to notify thread join for user %s', user_id)
