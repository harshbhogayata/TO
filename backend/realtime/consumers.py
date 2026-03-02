"""
realtime/consumers.py
Production-grade WebSocket consumers for messaging and notifications.

Architecture:
    - Each authenticated user joins a personal notification group: ``user_{id}``
    - Each thread participant joins a thread group: ``thread_{id}``
    - Messages, typing indicators, read receipts, and notifications are
      broadcast via the channel layer (Redis-backed in production).

Protocol (JSON over WebSocket):
    Client → Server:
        { "type": "chat.message",   "thread_id": 123, "body": "Hello" }
        { "type": "chat.typing",    "thread_id": 123, "is_typing": true }
        { "type": "chat.read",      "thread_id": 123 }

    Server → Client:
        { "type": "chat.message",   "thread_id": 123, "message": {...} }
        { "type": "chat.typing",    "thread_id": 123, "user_id": 1, "user_name": "...", "is_typing": true }
        { "type": "chat.read",      "thread_id": 123, "user_id": 1, "user_name": "..." }
        { "type": "notification",   "notification": {...} }
"""

import json
import logging
from datetime import datetime, timezone

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger(__name__)

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _user_group(user_id: int) -> str:
    """Personal channel group for push notifications."""
    return f'user_{user_id}'


def _thread_group(thread_id: int) -> str:
    """Channel group for a messaging thread."""
    return f'thread_{thread_id}'


# ─── Chat Consumer ────────────────────────────────────────────────────────────

class ChatConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for real-time messaging.

    On connect, the user joins channel groups for every thread they
    participate in. New messages, typing indicators, and read receipts
    are broadcast to the thread group.

    Wire protocol uses JSON. Binary frames are rejected.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = None
        self.thread_groups: set[str] = set()

    # ── Lifecycle ─────────────────────────────────────────────────────────

    async def connect(self):
        self.user = self.scope.get('user')

        if not self.user or isinstance(self.user, AnonymousUser):
            logger.info('WebSocket connect rejected: unauthenticated')
            await self.close(code=4401)
            return

        await self.accept()

        # Join groups for all threads the user is part of
        thread_ids = await self._get_user_thread_ids()
        for tid in thread_ids:
            group = _thread_group(tid)
            await self.channel_layer.group_add(group, self.channel_name)
            self.thread_groups.add(group)

        logger.info(
            'ChatConsumer connected: user=%s threads=%d',
            self.user.id, len(thread_ids),
        )

    async def disconnect(self, code):
        # Leave all thread groups
        for group in self.thread_groups:
            await self.channel_layer.group_discard(group, self.channel_name)
        self.thread_groups.clear()

        if self.user and not isinstance(self.user, AnonymousUser):
            logger.info('ChatConsumer disconnected: user=%s code=%s', self.user.id, code)

    # ── Incoming messages from client ─────────────────────────────────────

    async def receive_json(self, content, **kwargs):
        """Route incoming JSON frames to the appropriate handler."""
        msg_type = content.get('type')

        if msg_type == 'chat.message':
            await self._handle_send_message(content)
        elif msg_type == 'chat.typing':
            await self._handle_typing(content)
        elif msg_type == 'chat.read':
            await self._handle_read_receipt(content)
        else:
            await self.send_json({
                'type': 'error',
                'detail': f'Unknown message type: {msg_type}',
            })

    # ── Handlers ──────────────────────────────────────────────────────────

    async def _handle_send_message(self, content):
        """Persist a message and broadcast it to all thread participants."""
        thread_id = content.get('thread_id')
        body = (content.get('body') or '').strip()

        if not thread_id or not body:
            await self.send_json({
                'type': 'error',
                'detail': 'thread_id and body are required.',
            })
            return

        if len(body) > 10000:
            await self.send_json({
                'type': 'error',
                'detail': 'Message body exceeds 10,000 characters.',
            })
            return

        # Verify user is a participant and create the message
        result = await self._create_message_in_db(thread_id, body)
        if result is None:
            await self.send_json({
                'type': 'error',
                'detail': 'Thread not found or you are not a participant.',
            })
            return

        group = _thread_group(thread_id)

        # Ensure we're in this group (handles newly created threads)
        if group not in self.thread_groups:
            await self.channel_layer.group_add(group, self.channel_name)
            self.thread_groups.add(group)

        # Broadcast to thread group
        await self.channel_layer.group_send(group, {
            'type': 'chat_message',
            'message': result,
        })

        # Trigger async notification for offline participants
        await self._dispatch_message_notification(result['id'])

    async def _handle_typing(self, content):
        """Broadcast typing indicator to thread group."""
        thread_id = content.get('thread_id')
        is_typing = bool(content.get('is_typing', True))

        if not thread_id:
            return

        group = _thread_group(thread_id)
        if group not in self.thread_groups:
            return  # Not a participant

        await self.channel_layer.group_send(group, {
            'type': 'chat_typing',
            'thread_id': thread_id,
            'user_id': self.user.id,
            'user_name': self.user.full_name or self.user.email,
            'is_typing': is_typing,
        })

    async def _handle_read_receipt(self, content):
        """Mark all messages in thread as read and broadcast."""
        thread_id = content.get('thread_id')
        if not thread_id:
            return

        count = await self._mark_messages_read(thread_id)

        if count > 0:
            group = _thread_group(thread_id)
            await self.channel_layer.group_send(group, {
                'type': 'chat_read',
                'thread_id': thread_id,
                'user_id': self.user.id,
                'user_name': self.user.full_name or self.user.email,
            })

    # ── Channel layer event handlers (group_send dispatch) ────────────────

    async def chat_message(self, event):
        """Receive a message broadcast from the channel layer."""
        await self.send_json({
            'type': 'chat.message',
            'thread_id': event['message']['thread_id'],
            'message': event['message'],
        })

    async def chat_typing(self, event):
        """Receive a typing indicator from the channel layer."""
        # Don't echo typing indicator back to the sender
        if event['user_id'] == self.user.id:
            return
        await self.send_json({
            'type': 'chat.typing',
            'thread_id': event['thread_id'],
            'user_id': event['user_id'],
            'user_name': event['user_name'],
            'is_typing': event['is_typing'],
        })

    async def chat_read(self, event):
        """Receive a read receipt from the channel layer."""
        if event['user_id'] == self.user.id:
            return
        await self.send_json({
            'type': 'chat.read',
            'thread_id': event['thread_id'],
            'user_id': event['user_id'],
            'user_name': event['user_name'],
        })

    async def thread_joined(self, event):
        """Handle being added to a new thread group dynamically."""
        thread_id = event.get('thread_id')
        if thread_id:
            group = _thread_group(thread_id)
            if group not in self.thread_groups:
                await self.channel_layer.group_add(group, self.channel_name)
                self.thread_groups.add(group)

    # ── Database operations ───────────────────────────────────────────────

    @database_sync_to_async
    def _get_user_thread_ids(self) -> list[int]:
        """Return all thread IDs the user participates in."""
        from messaging.models import Thread
        return list(
            Thread.objects.filter(
                participants=self.user
            ).values_list('id', flat=True)
        )

    @database_sync_to_async
    def _create_message_in_db(self, thread_id: int, body: str) -> dict | None:
        """
        Create a message in the database.
        Returns serialized message dict or None if unauthorized.
        """
        from messaging.models import Thread, Message

        try:
            thread = Thread.objects.get(
                pk=thread_id,
                participants=self.user,
            )
        except Thread.DoesNotExist:
            return None

        msg = Message.objects.create(
            thread=thread,
            sender=self.user,
            body=body,
        )
        # Touch thread.updated_at for ordering
        thread.save(update_fields=['updated_at'])

        return {
            'id': msg.id,
            'thread_id': thread.id,
            'sender': self.user.id,
            'sender_name': self.user.full_name or self.user.email,
            'sender_role': self.user.role,
            'body': msg.body,
            'read': False,
            'sent_at': msg.sent_at.isoformat(),
        }

    @database_sync_to_async
    def _mark_messages_read(self, thread_id: int) -> int:
        """Mark all messages from others in this thread as read. Returns count."""
        from messaging.models import Message
        from django.utils import timezone

        return Message.objects.filter(
            thread_id=thread_id,
            read=False,
        ).exclude(
            sender=self.user,
        ).update(read=True, read_at=timezone.now())

    @database_sync_to_async
    def _dispatch_message_notification(self, message_id: int):
        """Dispatch a Celery task for push/email notification."""
        from notifications.tasks import send_message_notification_task
        try:
            send_message_notification_task.delay(message_id=message_id)
        except Exception:
            logger.exception('Failed to dispatch message notification for %s', message_id)


# ─── Notification Consumer ────────────────────────────────────────────────────

class NotificationConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for real-time notifications.

    Each authenticated user joins their personal group ``user_{id}``.
    The backend (Celery tasks, signals) pushes notifications to this
    group so the frontend receives them instantly.

    Wire protocol (Server → Client only):
        { "type": "notification", "notification": {...} }
        { "type": "unread_count", "count": 5 }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = None
        self.user_group = None

    async def connect(self):
        self.user = self.scope.get('user')

        if not self.user or isinstance(self.user, AnonymousUser):
            logger.info('NotificationConsumer connect rejected: unauthenticated')
            await self.close(code=4401)
            return

        self.user_group = _user_group(self.user.id)
        await self.channel_layer.group_add(self.user_group, self.channel_name)
        await self.accept()

        # Send current unread count on connect
        count = await self._get_unread_count()
        await self.send_json({
            'type': 'unread_count',
            'count': count,
        })

        logger.info('NotificationConsumer connected: user=%s', self.user.id)

    async def disconnect(self, code):
        if self.user_group:
            await self.channel_layer.group_discard(self.user_group, self.channel_name)

        if self.user and not isinstance(self.user, AnonymousUser):
            logger.info('NotificationConsumer disconnected: user=%s code=%s', self.user.id, code)

    async def receive_json(self, content, **kwargs):
        """Client can request updated unread count."""
        msg_type = content.get('type')

        if msg_type == 'mark_read':
            notif_id = content.get('notification_id')
            if notif_id:
                await self._mark_notification_read(notif_id)
                count = await self._get_unread_count()
                await self.send_json({
                    'type': 'unread_count',
                    'count': count,
                })
        elif msg_type == 'mark_all_read':
            await self._mark_all_read()
            await self.send_json({
                'type': 'unread_count',
                'count': 0,
            })
        elif msg_type == 'get_unread_count':
            count = await self._get_unread_count()
            await self.send_json({
                'type': 'unread_count',
                'count': count,
            })

    # ── Channel layer event handlers ──────────────────────────────────────

    async def push_notification(self, event):
        """Receive a notification push from the channel layer."""
        await self.send_json({
            'type': 'notification',
            'notification': event['notification'],
        })

    async def unread_count_update(self, event):
        """Receive an unread count update."""
        await self.send_json({
            'type': 'unread_count',
            'count': event['count'],
        })

    # ── Database operations ───────────────────────────────────────────────

    @database_sync_to_async
    def _get_unread_count(self) -> int:
        return self.user.notifications.filter(is_read=False).count()

    @database_sync_to_async
    def _mark_notification_read(self, notif_id: int):
        self.user.notifications.filter(pk=notif_id, is_read=False).update(is_read=True)

    @database_sync_to_async
    def _mark_all_read(self):
        self.user.notifications.filter(is_read=False).update(is_read=True)
