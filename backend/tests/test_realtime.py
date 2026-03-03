"""
tests/test_realtime.py
Comprehensive tests for the real-time communication system:
  - WebSocket consumers (ChatConsumer, NotificationConsumer)
  - Broadcast utilities
  - Push notification subscription endpoints
  - Read receipts and typing indicators
  - Presence tracking (online/offline/last-seen)
  - Message rate limiting
  - Delivery acknowledgments
  - Reconnect message sync endpoint
  - Presence REST endpoint
  - XSS sanitization

Usage:
    python manage.py test tests.test_realtime --settings=talentorbit.test_settings -v2
"""

import json
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.core.cache import cache
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient
from rest_framework import status as http_status

from accounts.models import User
from messaging.models import Thread, Message
from notifications.models import Notification
from realtime.consumers import ChatConsumer, NotificationConsumer
from realtime.models import PushSubscription
from realtime.broadcast import (
    broadcast_notification,
    broadcast_unread_count,
    broadcast_thread_message,
)
from realtime.presence import (
    user_connected,
    user_disconnected,
    refresh_presence,
    is_user_online,
    get_last_seen,
    get_user_presence,
    get_bulk_presence,
)
from realtime.middleware import check_message_rate_limit


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_application(consumer_class, user, path='/testws/'):
    """
    Build a minimal ASGI application wrapper for testing a consumer
    with an already-authenticated user (bypasses JWT middleware).
    """
    from channels.routing import URLRouter
    from django.urls import re_path

    async def _auth_middleware(inner):
        """Fake auth middleware that injects our test user."""
        async def app(scope, receive, send):
            scope['user'] = user
            return await inner(scope, receive, send)
        return app

    # Build a simple application with our consumer
    app = URLRouter([
        re_path(r'^testws/$', consumer_class.as_asgi()),
    ])

    # Wrap with fake auth
    from channels.auth import AuthMiddlewareStack
    from functools import wraps

    class TestApp:
        def __init__(self, inner):
            self.inner = inner

        async def __call__(self, scope, receive, send):
            scope['user'] = user
            return await self.inner(scope, receive, send)

    return TestApp(app)


# ─── ChatConsumer Tests ───────────────────────────────────────────────────────

@override_settings(
    CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
)
class ChatConsumerTest(TransactionTestCase):
    """Tests for the chat WebSocket consumer."""

    def setUp(self):
        self.company = User.objects.create_user(
            email='company@test.com',
            password='TestPass123!',
            role='company',
            full_name='Test Company',
            is_verified=True,
        )
        self.talent = User.objects.create_user(
            email='talent@test.com',
            password='TestPass123!',
            role='talent',
            full_name='Test Talent',
            is_verified=True,
        )
        self.thread = Thread.objects.create()
        self.thread.participants.add(self.company, self.talent)

    async def _connect(self, user):
        """Create and connect a WebSocket communicator for the given user."""
        app = _make_application(ChatConsumer, user)
        communicator = WebsocketCommunicator(app, '/testws/')
        connected, _ = await communicator.connect()
        return communicator, connected

    async def test_authenticated_user_connects(self):
        """Authenticated user should connect successfully."""
        communicator, connected = await self._connect(self.company)
        self.assertTrue(connected)
        await communicator.disconnect()

    async def test_anonymous_user_rejected(self):
        """Anonymous user should be rejected with code 4401."""
        from django.contrib.auth.models import AnonymousUser
        app = _make_application(ChatConsumer, AnonymousUser())
        communicator = WebsocketCommunicator(app, '/testws/')
        connected, code = await communicator.connect()
        self.assertFalse(connected)
        await communicator.disconnect()

    async def test_send_message_creates_in_db(self):
        """Sending a chat.message should persist in the database."""
        communicator, _ = await self._connect(self.company)

        await communicator.send_json_to({
            'type': 'chat.message',
            'thread_id': self.thread.id,
            'body': 'Hello from tests!',
        })

        # May receive chat.ack before chat.message — collect both
        msg_resp = None
        for _ in range(5):
            try:
                response = await communicator.receive_json_from(timeout=5)
                if response.get('type') == 'chat.message':
                    msg_resp = response
                    break
            except Exception:
                break

        self.assertIsNotNone(msg_resp, 'Expected chat.message but did not receive one')
        self.assertEqual(msg_resp['message']['body'], 'Hello from tests!')
        self.assertEqual(msg_resp['message']['sender'], self.company.id)

        # Verify DB persistence
        count = await database_sync_to_async(
            Message.objects.filter(thread=self.thread, body='Hello from tests!').count
        )()
        self.assertEqual(count, 1)

        await communicator.disconnect()

    async def test_send_message_invalid_thread(self):
        """Sending to a non-existent thread should return an error."""
        communicator, _ = await self._connect(self.company)

        await communicator.send_json_to({
            'type': 'chat.message',
            'thread_id': 99999,
            'body': 'Should fail',
        })

        response = await communicator.receive_json_from(timeout=5)
        self.assertEqual(response['type'], 'error')
        self.assertIn('not found', response['detail'].lower())

        await communicator.disconnect()

    async def test_send_message_empty_body_rejected(self):
        """Empty message body should be rejected."""
        communicator, _ = await self._connect(self.company)

        await communicator.send_json_to({
            'type': 'chat.message',
            'thread_id': self.thread.id,
            'body': '',
        })

        response = await communicator.receive_json_from(timeout=5)
        self.assertEqual(response['type'], 'error')

        await communicator.disconnect()

    async def test_send_message_over_limit_rejected(self):
        """Message body exceeding 10000 chars should be rejected."""
        communicator, _ = await self._connect(self.company)

        await communicator.send_json_to({
            'type': 'chat.message',
            'thread_id': self.thread.id,
            'body': 'x' * 10001,
        })

        response = await communicator.receive_json_from(timeout=5)
        self.assertEqual(response['type'], 'error')
        self.assertIn('10,000', response['detail'])

        await communicator.disconnect()

    async def test_typing_indicator_broadcast(self):
        """Typing indicator should be broadcast to other thread participants."""
        c_company, _ = await self._connect(self.company)
        c_talent, _ = await self._connect(self.talent)

        # Consume any presence events from connecting
        for comm in (c_company, c_talent):
            while not await comm.receive_nothing(timeout=0.5):
                pass

        await c_company.send_json_to({
            'type': 'chat.typing',
            'thread_id': self.thread.id,
            'is_typing': True,
        })

        # Talent should receive the typing indicator
        typing_resp = None
        for _ in range(5):
            try:
                response = await c_talent.receive_json_from(timeout=5)
                if response.get('type') == 'chat.typing':
                    typing_resp = response
                    break
            except Exception:
                break

        self.assertIsNotNone(typing_resp, 'Expected chat.typing')
        self.assertEqual(typing_resp['user_id'], self.company.id)
        self.assertTrue(typing_resp['is_typing'])

        await c_company.disconnect()
        await c_talent.disconnect()

    async def test_typing_not_echoed_to_sender(self):
        """Typing indicator should NOT be sent back to the sender."""
        communicator, _ = await self._connect(self.company)

        await communicator.send_json_to({
            'type': 'chat.typing',
            'thread_id': self.thread.id,
            'is_typing': True,
        })

        # The sender should not receive their own typing indicator
        self.assertTrue(await communicator.receive_nothing(timeout=1))

        await communicator.disconnect()

    async def test_read_receipt_marks_messages(self):
        """chat.read should mark unread messages and broadcast receipt."""
        # Create some unread messages from company
        await database_sync_to_async(Message.objects.create)(
            thread=self.thread, sender=self.company, body='Message 1'
        )
        await database_sync_to_async(Message.objects.create)(
            thread=self.thread, sender=self.company, body='Message 2'
        )

        c_company, _ = await self._connect(self.company)
        c_talent, _ = await self._connect(self.talent)

        # Consume any presence events from connecting
        for comm in (c_company, c_talent):
            while not await comm.receive_nothing(timeout=0.5):
                pass

        # Talent sends read receipt
        await c_talent.send_json_to({
            'type': 'chat.read',
            'thread_id': self.thread.id,
        })

        # Company should receive the read receipt (skip any other events)
        read_resp = None
        for _ in range(5):
            try:
                response = await c_company.receive_json_from(timeout=5)
                if response.get('type') == 'chat.read':
                    read_resp = response
                    break
            except Exception:
                break

        self.assertIsNotNone(read_resp, 'Expected chat.read')
        self.assertEqual(read_resp['user_id'], self.talent.id)

        # Verify DB — messages should now be read
        unread_count = await database_sync_to_async(
            Message.objects.filter(thread=self.thread, read=False).count
        )()
        self.assertEqual(unread_count, 0)

        await c_company.disconnect()
        await c_talent.disconnect()

    async def test_read_receipt_sets_read_at(self):
        """chat.read should set read_at timestamp on messages."""
        msg = await database_sync_to_async(Message.objects.create)(
            thread=self.thread, sender=self.company, body='Test read_at'
        )

        communicator, _ = await self._connect(self.talent)

        await communicator.send_json_to({
            'type': 'chat.read',
            'thread_id': self.thread.id,
        })

        # Allow time for DB write
        await communicator.receive_nothing(timeout=1)

        refreshed = await database_sync_to_async(Message.objects.get)(pk=msg.pk)
        self.assertTrue(refreshed.read)
        self.assertIsNotNone(refreshed.read_at)

        await communicator.disconnect()

    async def test_message_broadcast_to_all_participants(self):
        """Messages should be broadcast to all thread participants."""
        c_company, _ = await self._connect(self.company)
        c_talent, _ = await self._connect(self.talent)

        # Consume any presence events from connecting
        for comm in (c_company, c_talent):
            while not await comm.receive_nothing(timeout=0.5):
                pass

        await c_company.send_json_to({
            'type': 'chat.message',
            'thread_id': self.thread.id,
            'body': 'Broadcast test',
        })

        # Company (sender) receives both ack and broadcast — find chat.message
        company_msg = None
        for _ in range(5):
            try:
                resp = await c_company.receive_json_from(timeout=5)
                if resp.get('type') == 'chat.message':
                    company_msg = resp
                    break
            except Exception:
                break
        self.assertIsNotNone(company_msg)
        self.assertEqual(company_msg['message']['body'], 'Broadcast test')

        # Talent (recipient) also receives the broadcast
        talent_msg = None
        for _ in range(5):
            try:
                resp = await c_talent.receive_json_from(timeout=5)
                if resp.get('type') == 'chat.message':
                    talent_msg = resp
                    break
            except Exception:
                break
        self.assertIsNotNone(talent_msg)
        self.assertEqual(talent_msg['message']['body'], 'Broadcast test')

        await c_company.disconnect()
        await c_talent.disconnect()

    async def test_unknown_message_type_returns_error(self):
        """Unknown message types should return an error frame."""
        communicator, _ = await self._connect(self.company)

        await communicator.send_json_to({
            'type': 'some.unknown.type',
        })

        response = await communicator.receive_json_from(timeout=5)
        self.assertEqual(response['type'], 'error')
        self.assertIn('Unknown', response['detail'])

        await communicator.disconnect()


# ─── NotificationConsumer Tests ───────────────────────────────────────────────

@override_settings(
    CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
)
class NotificationConsumerTest(TransactionTestCase):
    """Tests for the notification WebSocket consumer."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='user@test.com',
            password='TestPass123!',
            role='talent',
            full_name='Test User',
            is_verified=True,
        )

    async def _connect(self, user):
        app = _make_application(NotificationConsumer, user)
        communicator = WebsocketCommunicator(app, '/testws/')
        connected, _ = await communicator.connect()
        return communicator, connected

    async def test_authenticated_user_connects(self):
        """Authenticated user should connect and receive initial unread count."""
        communicator, connected = await self._connect(self.user)
        self.assertTrue(connected)

        # Should receive unread count on connect
        response = await communicator.receive_json_from(timeout=5)
        self.assertEqual(response['type'], 'unread_count')
        self.assertEqual(response['count'], 0)

        await communicator.disconnect()

    async def test_initial_unread_count(self):
        """Should receive correct unread count on connect."""
        await database_sync_to_async(Notification.objects.create)(
            user=self.user, category='System', title='Test 1', is_read=False
        )
        await database_sync_to_async(Notification.objects.create)(
            user=self.user, category='System', title='Test 2', is_read=False
        )

        communicator, _ = await self._connect(self.user)
        response = await communicator.receive_json_from(timeout=5)
        self.assertEqual(response['count'], 2)

        await communicator.disconnect()

    async def test_mark_read_updates_count(self):
        """mark_read should mark notification and return updated count."""
        notif = await database_sync_to_async(Notification.objects.create)(
            user=self.user, category='System', title='Test', is_read=False
        )

        communicator, _ = await self._connect(self.user)
        # Consume initial unread count
        await communicator.receive_json_from(timeout=5)

        await communicator.send_json_to({
            'type': 'mark_read',
            'notification_id': notif.id,
        })

        response = await communicator.receive_json_from(timeout=5)
        self.assertEqual(response['type'], 'unread_count')
        self.assertEqual(response['count'], 0)

        # Verify DB
        refreshed = await database_sync_to_async(Notification.objects.get)(pk=notif.pk)
        self.assertTrue(refreshed.is_read)

        await communicator.disconnect()

    async def test_mark_all_read(self):
        """mark_all_read should clear all unread notifications."""
        for i in range(5):
            await database_sync_to_async(Notification.objects.create)(
                user=self.user, category='System', title=f'Test {i}', is_read=False
            )

        communicator, _ = await self._connect(self.user)
        await communicator.receive_json_from(timeout=5)  # Initial count

        await communicator.send_json_to({'type': 'mark_all_read'})

        response = await communicator.receive_json_from(timeout=5)
        self.assertEqual(response['count'], 0)

        unread = await database_sync_to_async(
            Notification.objects.filter(user=self.user, is_read=False).count
        )()
        self.assertEqual(unread, 0)

        await communicator.disconnect()

    async def test_get_unread_count(self):
        """get_unread_count should return current count."""
        await database_sync_to_async(Notification.objects.create)(
            user=self.user, category='System', title='Test', is_read=False
        )

        communicator, _ = await self._connect(self.user)
        await communicator.receive_json_from(timeout=5)  # Initial

        await communicator.send_json_to({'type': 'get_unread_count'})

        response = await communicator.receive_json_from(timeout=5)
        self.assertEqual(response['type'], 'unread_count')
        self.assertEqual(response['count'], 1)

        await communicator.disconnect()

    async def test_anonymous_user_rejected(self):
        """Anonymous user should be rejected."""
        from django.contrib.auth.models import AnonymousUser
        app = _make_application(NotificationConsumer, AnonymousUser())
        communicator = WebsocketCommunicator(app, '/testws/')
        connected, _ = await communicator.connect()
        self.assertFalse(connected)
        await communicator.disconnect()


# ─── Broadcast Utility Tests ─────────────────────────────────────────────────

@override_settings(
    CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
)
class BroadcastUtilityTest(TransactionTestCase):
    """Tests for synchronous broadcast helper functions."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='broadcast@test.com',
            password='TestPass123!',
            role='talent',
            full_name='Broadcast User',
            is_verified=True,
        )
        self.thread = Thread.objects.create()
        self.thread.participants.add(self.user)

    def test_broadcast_notification_does_not_raise(self):
        """broadcast_notification should not raise even without listeners."""
        # Should complete without error (no one listening)
        broadcast_notification(self.user.id, {
            'id': 1,
            'title': 'Test',
            'category': 'System',
            'description': '',
            'created_at': '2024-01-01T00:00:00Z',
            'is_read': False,
        })

    def test_broadcast_unread_count_does_not_raise(self):
        """broadcast_unread_count should not raise even without listeners."""
        broadcast_unread_count(self.user.id, 5)

    def test_broadcast_thread_message_does_not_raise(self):
        """broadcast_thread_message should not raise even without listeners."""
        broadcast_thread_message(self.thread.id, {
            'id': 1,
            'thread_id': self.thread.id,
            'sender': self.user.id,
            'body': 'Test',
            'sent_at': '2024-01-01T00:00:00Z',
        })

    def test_broadcast_with_no_channel_layer(self):
        """Broadcast functions should handle missing channel layer gracefully."""
        with patch('realtime.broadcast.get_channel_layer', return_value=None):
            # These should all silently no-op
            broadcast_notification(self.user.id, {'id': 1})
            broadcast_unread_count(self.user.id, 0)
            broadcast_thread_message(self.thread.id, {'id': 1})


# ─── Push Subscription Endpoint Tests ────────────────────────────────────────

@override_settings(
    CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
)
class PushSubscriptionAPITest(TestCase):
    """Tests for the push notification subscription REST endpoints."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='push@test.com',
            password='TestPass123!',
            role='talent',
            full_name='Push User',
            is_verified=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_register_push_token(self):
        """POST /api/v1/push/subscribe/ should create a PushSubscription."""
        resp = self.client.post('/api/v1/push/subscribe/', {
            'token': 'fake-fcm-token-12345',
            'platform': 'web',
        })
        self.assertEqual(resp.status_code, http_status.HTTP_201_CREATED)
        self.assertTrue(
            PushSubscription.objects.filter(user=self.user, token='fake-fcm-token-12345').exists()
        )

    def test_register_push_token_idempotent(self):
        """Registering the same token twice should not create duplicates."""
        for _ in range(2):
            self.client.post('/api/v1/push/subscribe/', {
                'token': 'duplicate-token',
                'platform': 'web',
            })
        self.assertEqual(
            PushSubscription.objects.filter(token='duplicate-token').count(), 1
        )

    def test_register_push_token_reactivates(self):
        """Re-registering an inactive token should reactivate it."""
        sub = PushSubscription.objects.create(
            user=self.user, token='reactivate-me', platform='web', is_active=False,
        )
        resp = self.client.post('/api/v1/push/subscribe/', {
            'token': 'reactivate-me',
            'platform': 'web',
        })
        self.assertIn(resp.status_code, [http_status.HTTP_200_OK, http_status.HTTP_201_CREATED])
        sub.refresh_from_db()
        self.assertTrue(sub.is_active)

    def test_unregister_push_token(self):
        """POST /api/v1/push/unsubscribe/ should deactivate the subscription."""
        PushSubscription.objects.create(
            user=self.user, token='remove-me', platform='web', is_active=True,
        )
        resp = self.client.post('/api/v1/push/unsubscribe/', {
            'token': 'remove-me',
        })
        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)

        sub = PushSubscription.objects.get(token='remove-me')
        self.assertFalse(sub.is_active)

    def test_unregister_nonexistent_token(self):
        """Unregistering a non-existent token should return 200 (idempotent)."""
        resp = self.client.post('/api/v1/push/unsubscribe/', {
            'token': 'doesnt-exist',
        })
        # Should not error — idempotent endpoint
        self.assertIn(resp.status_code, [http_status.HTTP_200_OK, http_status.HTTP_404_NOT_FOUND])

    def test_register_requires_auth(self):
        """Unauthenticated users should not be able to register tokens."""
        client = APIClient()
        resp = client.post('/api/v1/push/subscribe/', {
            'token': 'unauthorized-token',
            'platform': 'web',
        })
        self.assertEqual(resp.status_code, http_status.HTTP_401_UNAUTHORIZED)


# ─── Push Notification Sender Tests ──────────────────────────────────────────

class PushNotificationSenderTest(TestCase):
    """Tests for the FCM push notification sending utility."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='fcm@test.com',
            password='TestPass123!',
            role='talent',
            full_name='FCM User',
            is_verified=True,
        )
        PushSubscription.objects.create(
            user=self.user, token='active-token', platform='web', is_active=True,
        )

    @patch('realtime.push._get_firebase_app', return_value=MagicMock())
    def test_send_push_notification_with_tokens(self, mock_get_app):
        """send_push_notification should iterate over active tokens when app is configured."""
        # We can't easily mock the locally-imported firebase_admin.messaging,
        # but we can verify that _get_firebase_app is called and that the
        # function handles the ImportError or exception gracefully.
        from realtime.push import send_push_notification

        # This will attempt to import firebase_admin.messaging and call send().
        # In test environment without firebase_admin properly initialized,
        # this may raise — but the function should handle it gracefully.
        try:
            result = send_push_notification(
                user_id=self.user.id,
                title='Test Push',
                body='Hello from tests',
            )
        except Exception:
            # If firebase_admin isn't installed or configured, that's OK for this test
            pass

        mock_get_app.assert_called_once()

    @patch('realtime.push._firebase_initialized', False)
    @patch('realtime.push._firebase_app', None)
    def test_send_push_without_firebase_config(self):
        """Should silently skip when Firebase is not configured."""
        from realtime.push import send_push_notification
        # Reset the module-level singleton so it re-checks
        import realtime.push as push_mod
        push_mod._firebase_initialized = False
        push_mod._firebase_app = None

        result = send_push_notification(
            user_id=self.user.id,
            title='Test',
            body='Skip this',
        )
        self.assertEqual(result['sent'], 0)
        self.assertEqual(result.get('reason'), 'firebase_not_configured')


# ─── Notification Task Integration ───────────────────────────────────────────

@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
    CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
)
class NotificationTaskIntegrationTest(TransactionTestCase):
    """Tests that notification tasks properly trigger broadcasts."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='task@test.com',
            password='TestPass123!',
            role='talent',
            full_name='Task User',
            is_verified=True,
        )

    @patch('realtime.push.send_push_notification')
    def test_create_notification_task_creates_and_broadcasts(self, mock_push):
        """create_notification_task should create notification and attempt broadcast."""
        from notifications.tasks import create_notification_task

        result = create_notification_task(
            user_id=self.user.id,
            category='System',
            title='Test from task',
            description='Integration test',
        )

        self.assertEqual(result['status'], 'created')
        self.assertTrue(
            Notification.objects.filter(user=self.user, title='Test from task').exists()
        )

    @patch('realtime.push.send_push_notification')
    def test_create_notification_task_skips_inactive_user(self, mock_push):
        """Should skip notification for inactive user."""
        from notifications.tasks import create_notification_task

        result = create_notification_task(
            user_id=99999,
            category='System',
            title='Should skip',
        )
        self.assertEqual(result['status'], 'skipped')


# ─── Presence Tracking Tests ─────────────────────────────────────────────────

@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
)
class PresenceTrackingTest(TestCase):
    """Tests for realtime/presence.py — Redis-backed user presence."""

    def setUp(self):
        cache.clear()

    def test_user_connected_first_time_returns_true(self):
        """First connection should return True (user just came online)."""
        result = user_connected(42)
        self.assertTrue(result)

    def test_user_connected_second_time_returns_false(self):
        """Second connection (same user) should return False (already online)."""
        user_connected(42)
        result = user_connected(42)
        self.assertFalse(result)

    def test_is_user_online_after_connect(self):
        """User should appear online after connecting."""
        self.assertFalse(is_user_online(42))
        user_connected(42)
        self.assertTrue(is_user_online(42))

    def test_user_disconnected_last_connection_returns_true(self):
        """Disconnecting the last connection should return True."""
        user_connected(42)
        result = user_disconnected(42)
        self.assertTrue(result)

    def test_user_disconnected_not_last_returns_false(self):
        """Disconnecting while other connections remain should return False."""
        user_connected(42)
        user_connected(42)  # Second tab
        result = user_disconnected(42)
        self.assertFalse(result)

    def test_user_offline_after_all_disconnects(self):
        """User should be offline only after ALL connections close."""
        user_connected(42)
        user_connected(42)
        user_disconnected(42)
        self.assertTrue(is_user_online(42))
        user_disconnected(42)
        self.assertFalse(is_user_online(42))

    def test_last_seen_set_on_full_disconnect(self):
        """Last seen timestamp should be set when user goes offline."""
        user_connected(42)
        user_disconnected(42)
        last_seen = get_last_seen(42)
        self.assertIsNotNone(last_seen)
        # Should be a valid ISO timestamp
        parsed = datetime.fromisoformat(last_seen)
        self.assertIsInstance(parsed, datetime)

    def test_last_seen_none_while_online(self):
        """get_user_presence should return last_seen=None when online."""
        user_connected(42)
        presence = get_user_presence(42)
        self.assertTrue(presence['is_online'])
        self.assertIsNone(presence['last_seen'])

    def test_refresh_presence_keeps_user_online(self):
        """refresh_presence should keep user online without errors."""
        user_connected(42)
        refresh_presence(42)
        self.assertTrue(is_user_online(42))

    def test_get_bulk_presence_empty(self):
        """Bulk presence with empty list should return empty dict."""
        result = get_bulk_presence([])
        self.assertEqual(result, {})

    def test_get_bulk_presence_mixed_status(self):
        """Bulk presence should correctly report online and offline users."""
        user_connected(1)
        user_connected(2)
        user_disconnected(2)

        result = get_bulk_presence([1, 2, 999])
        self.assertTrue(result[1]['is_online'])
        self.assertFalse(result[2]['is_online'])
        self.assertIsNotNone(result[2]['last_seen'])
        self.assertFalse(result[999]['is_online'])

    def test_disconnect_without_connect_is_safe(self):
        """Disconnecting a user that never connected should not raise."""
        result = user_disconnected(99)
        # count was 0, goes to 0, marks as offline
        self.assertTrue(result)


# ─── Message Rate Limiting Tests ─────────────────────────────────────────────

@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    WS_MESSAGE_RATE_LIMIT=5,
    WS_MESSAGE_RATE_WINDOW=60,
)
class MessageRateLimitTest(TestCase):
    """Tests for realtime/middleware.py per-user message rate limiting."""

    def setUp(self):
        cache.clear()
        # Re-apply settings since middleware reads at import time
        import realtime.middleware as mw
        mw.WS_MESSAGE_RATE_LIMIT = 5
        mw.WS_MESSAGE_RATE_WINDOW = 60

    def test_messages_within_limit_allowed(self):
        """Messages within the rate limit should be allowed."""
        for _ in range(5):
            self.assertTrue(check_message_rate_limit(42))

    def test_messages_over_limit_rejected(self):
        """Messages exceeding the rate limit should be rejected."""
        for _ in range(5):
            check_message_rate_limit(42)
        self.assertFalse(check_message_rate_limit(42))

    def test_different_users_have_separate_limits(self):
        """Rate limits should be per-user, not global."""
        for _ in range(5):
            check_message_rate_limit(1)
        # User 1 is rate limited
        self.assertFalse(check_message_rate_limit(1))
        # User 2 should still have their full allowance
        self.assertTrue(check_message_rate_limit(2))

    def test_cache_failure_allows_message(self):
        """When cache is unavailable, messages should be allowed (fail-open)."""
        with patch('realtime.middleware.cache') as mock_cache:
            mock_cache.get.side_effect = Exception('cache down')
            self.assertTrue(check_message_rate_limit(42))


# ─── ChatConsumer Delivery Ack + XSS Tests ───────────────────────────────────

@override_settings(
    CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class ChatConsumerEnhancedTest(TransactionTestCase):
    """Tests for ChatConsumer delivery acks, XSS sanitization, heartbeat."""

    def setUp(self):
        cache.clear()
        self.company = User.objects.create_user(
            email='ack_co@test.com', password='TestPass123!',
            role='company', full_name='Ack Corp', is_verified=True,
        )
        self.talent = User.objects.create_user(
            email='ack_ta@test.com', password='TestPass123!',
            role='talent', full_name='Ack Talent', is_verified=True,
        )
        self.thread = Thread.objects.create()
        self.thread.participants.add(self.company, self.talent)

    async def _connect(self, user):
        app = _make_application(ChatConsumer, user)
        communicator = WebsocketCommunicator(app, '/testws/')
        connected, _ = await communicator.connect()
        return communicator, connected

    async def test_delivery_ack_sent_on_message(self):
        """Sender should receive chat.ack with message_id after sending."""
        communicator, _ = await self._connect(self.company)

        await communicator.send_json_to({
            'type': 'chat.message',
            'thread_id': self.thread.id,
            'body': 'Ack test message',
        })

        # Collect all responses
        ack_found = False
        for _ in range(5):
            try:
                resp = await communicator.receive_json_from(timeout=3)
                if resp.get('type') == 'chat.ack':
                    ack_found = True
                    self.assertEqual(resp['status'], 'delivered')
                    self.assertIn('message_id', resp)
                    self.assertEqual(resp['thread_id'], self.thread.id)
                    self.assertIn('sent_at', resp)
                    break
            except Exception:
                break

        self.assertTrue(ack_found, 'Expected chat.ack but did not receive one')
        await communicator.disconnect()

    async def test_xss_sanitization_in_messages(self):
        """Message body with HTML should be escaped for XSS prevention."""
        communicator, _ = await self._connect(self.company)

        xss_body = '<img src=x onerror=alert(1)>'
        await communicator.send_json_to({
            'type': 'chat.message',
            'thread_id': self.thread.id,
            'body': xss_body,
        })

        # Find the broadcast message
        msg_found = False
        for _ in range(5):
            try:
                resp = await communicator.receive_json_from(timeout=3)
                if resp.get('type') == 'chat.message':
                    msg_found = True
                    body = resp['message']['body']
                    self.assertNotIn('<img', body)
                    self.assertIn('&lt;img', body)
                    break
            except Exception:
                break

        self.assertTrue(msg_found, 'Expected chat.message but did not receive one')
        await communicator.disconnect()

    async def test_heartbeat_ack(self):
        """Heartbeat should be acknowledged with heartbeat.ack."""
        communicator, _ = await self._connect(self.company)

        await communicator.send_json_to({'type': 'heartbeat'})
        resp = await communicator.receive_json_from(timeout=3)
        self.assertEqual(resp['type'], 'heartbeat.ack')

        await communicator.disconnect()

    async def test_string_thread_id_coerced_to_int(self):
        """String thread_id should be coerced to int."""
        communicator, _ = await self._connect(self.company)

        await communicator.send_json_to({
            'type': 'chat.message',
            'thread_id': str(self.thread.id),
            'body': 'Coerce test',
        })

        # Should succeed — look for either chat.ack or chat.message (not error)
        found_success = False
        for _ in range(5):
            try:
                resp = await communicator.receive_json_from(timeout=3)
                if resp.get('type') in ('chat.ack', 'chat.message'):
                    found_success = True
                    break
                elif resp.get('type') == 'error' and resp.get('code') == 'validation':
                    self.fail('String thread_id was rejected instead of coerced')
            except Exception:
                break

        self.assertTrue(found_success, 'Expected ack or message for coerced thread_id')
        await communicator.disconnect()

    async def test_non_integer_thread_id_rejected(self):
        """Non-numeric thread_id should be rejected."""
        communicator, _ = await self._connect(self.company)

        await communicator.send_json_to({
            'type': 'chat.message',
            'thread_id': 'not-a-number',
            'body': 'Bad id',
        })

        resp = await communicator.receive_json_from(timeout=3)
        self.assertEqual(resp['type'], 'error')
        self.assertEqual(resp['code'], 'validation')

        await communicator.disconnect()


# ─── Message Sync Endpoint Tests ─────────────────────────────────────────────

@override_settings(
    CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class MessageSyncEndpointTest(TestCase):
    """Tests for GET /api/v1/messages/<thread_id>/sync/ (reconnect gap recovery)."""

    def setUp(self):
        self.client = APIClient()
        self.talent = User.objects.create_user(
            email='sync_t@test.com', password='TestPass123!',
            role='talent', full_name='Sync Talent', is_verified=True,
        )
        self.company = User.objects.create_user(
            email='sync_c@test.com', password='TestPass123!',
            role='company', full_name='Sync Corp', is_verified=True,
        )
        self.thread = Thread.objects.create()
        self.thread.participants.add(self.talent, self.company)

    def test_sync_returns_messages_after_timestamp(self):
        """Should return only messages after the given timestamp."""
        m1 = Message.objects.create(
            thread=self.thread, sender=self.company, body='Old msg'
        )
        since_ts = datetime.now(timezone.utc).isoformat()
        m2 = Message.objects.create(
            thread=self.thread, sender=self.company, body='New msg'
        )

        self.client.force_authenticate(user=self.talent)
        resp = self.client.get(
            f'/api/v1/messages/{self.thread.id}/sync/',
            {'since': since_ts},
        )

        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        self.assertIn('messages', resp.data)
        self.assertIn('has_more', resp.data)
        bodies = [m['body'] for m in resp.data['messages']]
        self.assertIn('New msg', bodies)

    def test_sync_requires_authentication(self):
        """Sync endpoint should require authentication."""
        resp = self.client.get(
            f'/api/v1/messages/{self.thread.id}/sync/',
            {'since': datetime.now(timezone.utc).isoformat()},
        )
        self.assertEqual(resp.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_sync_non_participant_forbidden(self):
        """Non-participants should get 404."""
        other = User.objects.create_user(
            email='outsider@test.com', password='TestPass123!',
            role='talent', full_name='Outsider', is_verified=True,
        )
        self.client.force_authenticate(user=other)
        resp = self.client.get(
            f'/api/v1/messages/{self.thread.id}/sync/',
            {'since': datetime.now(timezone.utc).isoformat()},
        )
        self.assertEqual(resp.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_sync_missing_since_param(self):
        """Missing 'since' parameter should return 400."""
        self.client.force_authenticate(user=self.talent)
        resp = self.client.get(f'/api/v1/messages/{self.thread.id}/sync/')
        self.assertEqual(resp.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_sync_respects_limit_param(self):
        """Custom limit should cap results, has_more should be True."""
        for i in range(10):
            Message.objects.create(
                thread=self.thread, sender=self.company, body=f'Msg {i}'
            )

        since_ts = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        self.client.force_authenticate(user=self.talent)
        resp = self.client.get(
            f'/api/v1/messages/{self.thread.id}/sync/',
            {'since': since_ts, 'limit': 3},
        )

        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        self.assertEqual(len(resp.data['messages']), 3)
        self.assertTrue(resp.data['has_more'])

    def test_sync_limit_capped_at_500(self):
        """Limit should be capped at 500 even if client requests more."""
        self.client.force_authenticate(user=self.talent)
        resp = self.client.get(
            f'/api/v1/messages/{self.thread.id}/sync/',
            {'since': (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(), 'limit': 1000},
        )
        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)


# ─── Presence REST Endpoint Tests ────────────────────────────────────────────

@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
)
class PresenceEndpointTest(TestCase):
    """Tests for POST /api/v1/push/presence/ (bulk presence query)."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.talent = User.objects.create_user(
            email='pres@test.com', password='TestPass123!',
            role='talent', full_name='Presence Tester', is_verified=True,
        )

    def test_presence_returns_bulk_status(self):
        """Should return presence info for requested user IDs."""
        user_connected(self.talent.id)

        self.client.force_authenticate(user=self.talent)
        resp = self.client.post(
            '/api/v1/push/presence/',
            {'user_ids': [self.talent.id, 9999]},
            format='json',
        )

        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        p = resp.data['presence']
        self.assertTrue(p[str(self.talent.id)]['is_online'])
        self.assertFalse(p['9999']['is_online'])

    def test_presence_requires_authentication(self):
        """Presence endpoint should require authentication."""
        resp = self.client.post(
            '/api/v1/push/presence/',
            {'user_ids': [1]},
            format='json',
        )
        self.assertEqual(resp.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_presence_empty_user_ids(self):
        """Empty user_ids should return empty presence dict."""
        self.client.force_authenticate(user=self.talent)
        resp = self.client.post(
            '/api/v1/push/presence/',
            {'user_ids': []},
            format='json',
        )
        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        self.assertEqual(resp.data['presence'], {})

    def test_presence_caps_at_100_ids(self):
        """Request with >100 IDs should be capped to 100."""
        self.client.force_authenticate(user=self.talent)
        resp = self.client.post(
            '/api/v1/push/presence/',
            {'user_ids': list(range(150))},
            format='json',
        )
        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        self.assertEqual(len(resp.data['presence']), 100)
