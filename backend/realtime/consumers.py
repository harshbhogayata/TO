"""
realtime/consumers.py
Production-grade WebSocket consumers for messaging and notifications.

Architecture:
    - Each authenticated user joins a personal notification group: ``user_{id}``
    - Each thread participant joins a thread group: ``thread_{id}``
    - Messages, typing indicators, read receipts, and notifications are
      broadcast via the channel layer (Redis-backed in production).
    - Presence tracking marks users online/offline with last-seen timestamps.
    - Server-side heartbeat validates connection liveness.
    - Per-user message rate limiting prevents abuse.

Protocol (JSON over WebSocket):
    Client → Server:
        { "type": "chat.message",   "thread_id": 123, "body": "Hello" }
        { "type": "chat.typing",    "thread_id": 123, "is_typing": true }
        { "type": "chat.read",      "thread_id": 123 }
        { "type": "heartbeat" }

    Server → Client:
        { "type": "chat.message",   "thread_id": 123, "message": {...} }
        { "type": "chat.typing",    "thread_id": 123, "user_id": 1, ... }
        { "type": "chat.read",      "thread_id": 123, "user_id": 1, ... }
        { "type": "chat.ack",       "message_id": 123, "status": "delivered" }
        { "type": "presence",       "user_id": 1, "is_online": true }
        { "type": "notification",   "notification": {...} }
        { "type": "unread_count",   "count": 5 }
        { "type": "heartbeat.ack" }
"""

import logging
import time
from datetime import datetime, timezone

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from django.utils.html import escape

from .middleware import check_message_rate_limit
from .presence import (
    user_connected,
    user_disconnected,
    refresh_presence,
    get_bulk_presence,
)

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

# Max body length for chat messages
MAX_BODY_LENGTH = 10_000

# Allowed inbound message types (reject unknown types fast)
_CHAT_MSG_TYPES = frozenset({'chat.message', 'chat.typing', 'chat.read', 'heartbeat'})
_NOTIF_MSG_TYPES = frozenset({'mark_read', 'mark_all_read', 'get_unread_count', 'heartbeat'})


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _user_group(user_id: int) -> str:
    """Personal channel group for push notifications and presence."""
    return f'user_{user_id}'


def _thread_group(thread_id: int) -> str:
    """Channel group for a messaging thread."""
    return f'thread_{thread_id}'


def _sanitize_text(text: str) -> str:
    """
    Sanitize user input for storage and transmission.
    Escapes HTML entities to prevent stored XSS via WebSocket messages.
    """
    return escape(text.strip())


# ─── Base Consumer ────────────────────────────────────────────────────────────

class _AuthenticatedConsumer(AsyncJsonWebsocketConsumer):
    """
    Base class for authenticated WebSocket consumers.
    Handles auth validation, presence tracking, heartbeat, and rate limiting.
    """

    consumer_name: str = 'BaseConsumer'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = None
        self._last_message_time: float = 0
        self._connect_time: float = 0

    async def connect(self):
        self.user = self.scope.get('user')

        if not self.user or isinstance(self.user, AnonymousUser):
            logger.info('%s connect rejected: unauthenticated', self.consumer_name)
            await self.close(code=4401)
            return

        self._connect_time = time.monotonic()
        self._last_message_time = time.monotonic()

        # Track presence (returns True if user just came online)
        just_online = user_connected(self.user.id)

        await self.accept()

        # If user just came online, broadcast presence to their contacts
        if just_online:
            await self._broadcast_presence(is_online=True)

        logger.info(
            '%s connected: user=%s',
            self.consumer_name, self.user.id,
        )

    async def disconnect(self, code):
        if self.user and not isinstance(self.user, AnonymousUser):
            # Track presence (returns True if user's last connection closed)
            just_offline = user_disconnected(self.user.id)

            if just_offline:
                await self._broadcast_presence(is_online=False)

            duration = time.monotonic() - self._connect_time
            logger.info(
                '%s disconnected: user=%s code=%s duration=%.1fs',
                self.consumer_name, self.user.id, code, duration,
            )

    async def _check_rate_limit(self) -> bool:
        """Check per-user message rate limit. Returns False if exceeded."""
        allowed = await database_sync_to_async(check_message_rate_limit)(self.user.id)
        if not allowed:
            await self.send_json({
                'type': 'error',
                'code': 'rate_limited',
                'detail': 'Message rate limit exceeded. Please slow down.',
            })
            logger.warning(
                '%s rate-limited: user=%s', self.consumer_name, self.user.id,
            )
            return False
        self._last_message_time = time.monotonic()
        return True

    async def _broadcast_presence(self, is_online: bool):
        """Broadcast presence change to all thread participants."""
        participant_ids = await self._get_contact_user_ids()

        for uid in participant_ids:
            try:
                await self.channel_layer.group_send(
                    _user_group(uid),
                    {
                        'type': 'presence_update',
                        'user_id': self.user.id,
                        'user_name': self.user.full_name or self.user.email,
                        'is_online': is_online,
                        'last_seen': None if is_online else datetime.now(timezone.utc).isoformat(),
                    },
                )
            except Exception:
                pass  # Non-critical — don't fail the connection lifecycle

    @database_sync_to_async
    def _get_contact_user_ids(self) -> list[int]:
        """Get all user IDs that this user has a thread with."""
        from messaging.models import Thread
        from accounts.models import User

        thread_ids = Thread.objects.filter(
            participants=self.user
        ).values_list('id', flat=True)

        return list(
            User.objects.filter(
                threads__id__in=thread_ids
            ).exclude(
                pk=self.user.id
            ).distinct().values_list('pk', flat=True)
        )


# ─── Chat Consumer ────────────────────────────────────────────────────────────

class ChatConsumer(_AuthenticatedConsumer):
    """
    WebSocket consumer for real-time messaging.

    On connect, the user joins channel groups for every thread they
    participate in. New messages, typing indicators, and read receipts
    are broadcast to the thread group.

    Wire protocol uses JSON. Binary frames are rejected.
    """

    consumer_name = 'ChatConsumer'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.thread_groups: set[str] = set()

    # ── Lifecycle ─────────────────────────────────────────────────────────

    async def connect(self):
        await super().connect()

        if not self.user or isinstance(self.user, AnonymousUser):
            return

        # Join personal group (for thread_joined events and presence)
        await self.channel_layer.group_add(
            _user_group(self.user.id), self.channel_name
        )

        # Join groups for all threads the user is part of (capped for safety)
        thread_ids = await self._get_user_thread_ids()
        for tid in thread_ids:
            group = _thread_group(tid)
            await self.channel_layer.group_add(group, self.channel_name)
            self.thread_groups.add(group)

        logger.info(
            'ChatConsumer ready: user=%s threads=%d',
            self.user.id, len(thread_ids),
        )

    async def disconnect(self, code):
        # Leave all thread groups
        for group in self.thread_groups:
            await self.channel_layer.group_discard(group, self.channel_name)
        self.thread_groups.clear()

        # Leave personal group
        if self.user and not isinstance(self.user, AnonymousUser):
            await self.channel_layer.group_discard(
                _user_group(self.user.id), self.channel_name
            )

        await super().disconnect(code)

    # ── Incoming messages from client ─────────────────────────────────────

    async def receive_json(self, content, **kwargs):
        """Route incoming JSON frames to the appropriate handler."""
        msg_type = content.get('type')

        # Heartbeat — lightweight, no rate limit check
        if msg_type == 'heartbeat':
            self._last_message_time = time.monotonic()
            refresh_presence(self.user.id)
            await self.send_json({'type': 'heartbeat.ack'})
            return

        # Validate message type
        if msg_type not in _CHAT_MSG_TYPES:
            await self.send_json({
                'type': 'error',
                'code': 'unknown_type',
                'detail': f'Unknown message type: {msg_type}',
            })
            return

        # Rate limit check for non-heartbeat messages
        if not await self._check_rate_limit():
            return

        if msg_type == 'chat.message':
            await self._handle_send_message(content)
        elif msg_type == 'chat.typing':
            await self._handle_typing(content)
        elif msg_type == 'chat.read':
            await self._handle_read_receipt(content)

    # ── Handlers ──────────────────────────────────────────────────────────

    async def _handle_send_message(self, content):
        """Persist a message and broadcast it to all thread participants."""
        thread_id = content.get('thread_id')
        body = (content.get('body') or '').strip()

        if not thread_id or not body:
            await self.send_json({
                'type': 'error',
                'code': 'validation',
                'detail': 'thread_id and body are required.',
            })
            return

        # Validate thread_id type
        if not isinstance(thread_id, int):
            try:
                thread_id = int(thread_id)
            except (ValueError, TypeError):
                await self.send_json({
                    'type': 'error',
                    'code': 'validation',
                    'detail': 'thread_id must be an integer.',
                })
                return

        if len(body) > MAX_BODY_LENGTH:
            await self.send_json({
                'type': 'error',
                'code': 'validation',
                'detail': f'Message body exceeds {MAX_BODY_LENGTH:,} characters.',
            })
            return

        # Sanitize body for XSS prevention
        sanitized_body = _sanitize_text(body)

        # Verify user is a participant and create the message
        result = await self._create_message_in_db(thread_id, sanitized_body)
        if result is None:
            await self.send_json({
                'type': 'error',
                'code': 'forbidden',
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

        # Send delivery acknowledgment to the sender
        await self.send_json({
            'type': 'chat.ack',
            'message_id': result['id'],
            'thread_id': thread_id,
            'status': 'delivered',
            'sent_at': result['sent_at'],
        })

        # Trigger async notification for offline participants
        await self._dispatch_message_notification(result['id'])

    async def _handle_typing(self, content):
        """Broadcast typing indicator to thread group."""
        thread_id = content.get('thread_id')
        is_typing = bool(content.get('is_typing', True))

        if not thread_id:
            return

        # Validate thread_id
        if not isinstance(thread_id, int):
            try:
                thread_id = int(thread_id)
            except (ValueError, TypeError):
                return

        group = _thread_group(thread_id)
        if group not in self.thread_groups:
            return  # Not a participant — silently ignore

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

        if not isinstance(thread_id, int):
            try:
                thread_id = int(thread_id)
            except (ValueError, TypeError):
                return

        count = await self._mark_messages_read(thread_id)

        if count > 0:
            group = _thread_group(thread_id)
            await self.channel_layer.group_send(group, {
                'type': 'chat_read',
                'thread_id': thread_id,
                'user_id': self.user.id,
                'user_name': self.user.full_name or self.user.email,
                'read_count': count,
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
            'read_count': event.get('read_count', 0),
        })

    async def thread_joined(self, event):
        """Handle being added to a new thread group dynamically."""
        thread_id = event.get('thread_id')
        if thread_id:
            group = _thread_group(thread_id)
            if group not in self.thread_groups:
                await self.channel_layer.group_add(group, self.channel_name)
                self.thread_groups.add(group)

    async def presence_update(self, event):
        """Forward presence changes to the client."""
        if event['user_id'] == self.user.id:
            return
        await self.send_json({
            'type': 'presence',
            'user_id': event['user_id'],
            'user_name': event['user_name'],
            'is_online': event['is_online'],
            'last_seen': event.get('last_seen'),
        })

    # ── Database operations ───────────────────────────────────────────────

    @database_sync_to_async
    def _get_user_thread_ids(self) -> list[int]:
        """Return all thread IDs the user participates in."""
        from messaging.models import Thread
        return list(
            Thread.objects.filter(
                participants=self.user
            ).values_list('id', flat=True)[:200]  # Cap for safety
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
            'read_at': None,
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

class NotificationConsumer(_AuthenticatedConsumer):
    """
    WebSocket consumer for real-time notifications.

    Each authenticated user joins their personal group ``user_{id}``.
    The backend (Celery tasks, signals) pushes notifications to this
    group so the frontend receives them instantly.

    Wire protocol (Server → Client):
        { "type": "notification", "notification": {...} }
        { "type": "unread_count", "count": 5 }
        { "type": "presence",     "user_id": 1, "is_online": true }

    Wire protocol (Client → Server):
        { "type": "mark_read",       "notification_id": 123 }
        { "type": "mark_all_read" }
        { "type": "get_unread_count" }
        { "type": "heartbeat" }
    """

    consumer_name = 'NotificationConsumer'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_group = None

    async def connect(self):
        await super().connect()

        if not self.user or isinstance(self.user, AnonymousUser):
            return

        self.user_group = _user_group(self.user.id)
        await self.channel_layer.group_add(self.user_group, self.channel_name)

        # Send current unread count on connect
        count = await self._get_unread_count()
        await self.send_json({
            'type': 'unread_count',
            'count': count,
        })

        logger.info('NotificationConsumer ready: user=%s', self.user.id)

    async def disconnect(self, code):
        if self.user_group:
            await self.channel_layer.group_discard(self.user_group, self.channel_name)

        await super().disconnect(code)

    async def receive_json(self, content, **kwargs):
        """Client can manage notifications and request updates."""
        msg_type = content.get('type')

        # Heartbeat — lightweight
        if msg_type == 'heartbeat':
            self._last_message_time = time.monotonic()
            refresh_presence(self.user.id)
            await self.send_json({'type': 'heartbeat.ack'})
            return

        # Validate message type
        if msg_type not in _NOTIF_MSG_TYPES:
            await self.send_json({
                'type': 'error',
                'code': 'unknown_type',
                'detail': f'Unknown message type: {msg_type}',
            })
            return

        # Rate limit
        if not await self._check_rate_limit():
            return

        if msg_type == 'mark_read':
            notif_id = content.get('notification_id')
            if notif_id:
                if not isinstance(notif_id, int):
                    try:
                        notif_id = int(notif_id)
                    except (ValueError, TypeError):
                        return
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

    async def presence_update(self, event):
        """Forward presence changes to the client."""
        if event['user_id'] == self.user.id:
            return
        await self.send_json({
            'type': 'presence',
            'user_id': event['user_id'],
            'user_name': event['user_name'],
            'is_online': event['is_online'],
            'last_seen': event.get('last_seen'),
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
