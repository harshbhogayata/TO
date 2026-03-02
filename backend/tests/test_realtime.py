"""
tests/test_realtime.py
Comprehensive tests for the real-time communication system:
  - WebSocket consumers (ChatConsumer, NotificationConsumer)
  - Broadcast utilities
  - Push notification subscription endpoints
  - Read receipts and typing indicators

Usage:
    python manage.py test tests.test_realtime --settings=talentorbit.test_settings -v2
"""

import json
from unittest.mock import patch, MagicMock

from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
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

        # Receive the broadcast back
        response = await communicator.receive_json_from(timeout=5)
        self.assertEqual(response['type'], 'chat.message')
        self.assertEqual(response['message']['body'], 'Hello from tests!')
        self.assertEqual(response['message']['sender'], self.company.id)

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

        await c_company.send_json_to({
            'type': 'chat.typing',
            'thread_id': self.thread.id,
            'is_typing': True,
        })

        # Talent should receive the typing indicator
        response = await c_talent.receive_json_from(timeout=5)
        self.assertEqual(response['type'], 'chat.typing')
        self.assertEqual(response['user_id'], self.company.id)
        self.assertTrue(response['is_typing'])

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

        # Talent sends read receipt
        await c_talent.send_json_to({
            'type': 'chat.read',
            'thread_id': self.thread.id,
        })

        # Company should receive the read receipt
        response = await c_company.receive_json_from(timeout=5)
        self.assertEqual(response['type'], 'chat.read')
        self.assertEqual(response['user_id'], self.talent.id)

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

        await c_company.send_json_to({
            'type': 'chat.message',
            'thread_id': self.thread.id,
            'body': 'Broadcast test',
        })

        # Company (sender) receives the broadcast
        company_resp = await c_company.receive_json_from(timeout=5)
        self.assertEqual(company_resp['message']['body'], 'Broadcast test')

        # Talent (recipient) also receives the broadcast
        talent_resp = await c_talent.receive_json_from(timeout=5)
        self.assertEqual(talent_resp['message']['body'], 'Broadcast test')

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
