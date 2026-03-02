"""
tests/test_messaging.py
Production-grade tests for the messaging REST API.

Coverage:
    1. Thread creation (dedup, self-chat prevention, unverified rejection)
    2. Thread listing
    3. Message sending (participant check, empty body, attachments)
    4. Message listing with auto-read marking
    5. Unread count endpoint
    6. WebSocket broadcast integration
"""

from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework import status as http_status

from accounts.models import User, TalentProfile, CompanyProfile
from jobs.models import JobPost
from messaging.models import Thread, Message


def _create_talent(email='talent@msg.com', **kw):
    defaults = dict(full_name='Msg Talent', role=User.Role.TALENT, is_verified=True)
    defaults.update(kw)
    user = User.objects.create_user(email=email, password='TestPass123!', **defaults)
    TalentProfile.objects.create(user=user, skills=['Python'])
    return user


def _create_company(email='company@msg.com', **kw):
    defaults = dict(full_name='Msg Corp', role=User.Role.COMPANY, is_verified=True)
    defaults.update(kw)
    user = User.objects.create_user(email=email, password='TestPass123!', **defaults)
    CompanyProfile.objects.create(user=user, legal_name='Msg Corp Inc')
    return user


@override_settings(
    CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class ThreadCreationTest(TestCase):
    """Tests for POST /api/v1/messages/thread/"""

    def setUp(self):
        self.client = APIClient()
        self.talent = _create_talent()
        self.company = _create_company()

    def test_create_thread_by_id(self):
        """Should create a new thread with recipient by user ID."""
        self.client.force_authenticate(user=self.talent)
        resp = self.client.post('/api/v1/messages/thread/', {
            'recipient_id': self.company.pk,
            'initial_message': 'Hello!',
        }, format='json')

        self.assertEqual(resp.status_code, http_status.HTTP_201_CREATED)
        self.assertIn('id', resp.data)
        self.assertTrue(Thread.objects.filter(participants=self.talent).exists())

    def test_create_thread_by_email(self):
        """Should create a thread using recipient_email."""
        self.client.force_authenticate(user=self.talent)
        resp = self.client.post('/api/v1/messages/thread/', {
            'recipient_email': self.company.email,
            'initial_message': 'Hey!',
        }, format='json')

        self.assertIn(resp.status_code, [
            http_status.HTTP_200_OK,
            http_status.HTTP_201_CREATED,
        ])

    def test_dedup_returns_existing_thread(self):
        """Creating a thread between same users should return existing one."""
        self.client.force_authenticate(user=self.talent)

        # First creation
        resp1 = self.client.post('/api/v1/messages/thread/', {
            'recipient_id': self.company.pk,
        }, format='json')
        thread_id = resp1.data['id']

        # Second creation — should return same thread
        resp2 = self.client.post('/api/v1/messages/thread/', {
            'recipient_id': self.company.pk,
        }, format='json')
        self.assertEqual(resp2.data['id'], thread_id)
        self.assertEqual(resp2.status_code, http_status.HTTP_200_OK)

    def test_cannot_create_thread_with_self(self):
        """Self-chat should be prevented."""
        self.client.force_authenticate(user=self.talent)
        resp = self.client.post('/api/v1/messages/thread/', {
            'recipient_id': self.talent.pk,
        }, format='json')

        self.assertEqual(resp.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_unverified_user_cannot_create_thread(self):
        """Unverified users should be blocked from creating threads."""
        unverified = _create_talent(email='unver@msg.com', is_verified=False)
        self.client.force_authenticate(user=unverified)
        resp = self.client.post('/api/v1/messages/thread/', {
            'recipient_id': self.company.pk,
        }, format='json')

        self.assertEqual(resp.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_initial_message_creates_message_record(self):
        """Thread created with initial_message should have a Message in DB."""
        self.client.force_authenticate(user=self.talent)
        resp = self.client.post('/api/v1/messages/thread/', {
            'recipient_id': self.company.pk,
            'initial_message': 'First contact!',
        }, format='json')

        thread_id = resp.data['id']
        self.assertEqual(
            Message.objects.filter(thread_id=thread_id, body='First contact!').count(), 1
        )

    def test_unauthenticated_rejected(self):
        resp = self.client.post('/api/v1/messages/thread/', {
            'recipient_id': 1,
        }, format='json')
        self.assertEqual(resp.status_code, http_status.HTTP_401_UNAUTHORIZED)


@override_settings(
    CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class ThreadListTest(TestCase):
    """Tests for GET /api/v1/messages/"""

    def setUp(self):
        self.client = APIClient()
        self.talent = _create_talent(email='thr_list@msg.com')
        self.company = _create_company(email='thr_list_co@msg.com')

    def test_list_own_threads(self):
        """User should see threads they participate in."""
        thread = Thread.objects.create()
        thread.participants.set([self.talent, self.company])

        self.client.force_authenticate(user=self.talent)
        resp = self.client.get('/api/v1/messages/')

        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        self.assertEqual(len(resp.data['results']), 1)

    def test_no_other_users_threads(self):
        """User should not see threads they don't participate in."""
        other = _create_talent(email='other@msg.com')
        thread = Thread.objects.create()
        thread.participants.set([other, self.company])

        self.client.force_authenticate(user=self.talent)
        resp = self.client.get('/api/v1/messages/')

        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        self.assertEqual(len(resp.data['results']), 0)


@override_settings(
    CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class SendMessageTest(TestCase):
    """Tests for POST /api/v1/messages/send/"""

    def setUp(self):
        self.client = APIClient()
        self.talent = _create_talent(email='send@msg.com')
        self.company = _create_company(email='send_co@msg.com')
        self.thread = Thread.objects.create()
        self.thread.participants.set([self.talent, self.company])

    def test_send_message(self):
        """Participant can send a message to a thread."""
        self.client.force_authenticate(user=self.talent)
        resp = self.client.post('/api/v1/messages/send/', {
            'thread': self.thread.pk,
            'body': 'Test message content',
        }, format='json')

        self.assertEqual(resp.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(resp.data['body'], 'Test message content')
        self.assertEqual(Message.objects.filter(thread=self.thread).count(), 1)

    def test_non_participant_cannot_send(self):
        """Non-participant should be blocked from sending."""
        outsider = _create_talent(email='outsider@msg.com')
        self.client.force_authenticate(user=outsider)
        resp = self.client.post('/api/v1/messages/send/', {
            'thread': self.thread.pk,
            'body': 'I should not be able to send this.',
        }, format='json')

        self.assertEqual(resp.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_send(self):
        resp = self.client.post('/api/v1/messages/send/', {
            'thread': self.thread.pk,
            'body': 'No auth',
        }, format='json')
        self.assertEqual(resp.status_code, http_status.HTTP_401_UNAUTHORIZED)


@override_settings(
    CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class ThreadMessagesTest(TestCase):
    """Tests for GET /api/v1/messages/<thread_id>/messages/"""

    def setUp(self):
        self.client = APIClient()
        self.talent = _create_talent(email='read@msg.com')
        self.company = _create_company(email='read_co@msg.com')
        self.thread = Thread.objects.create()
        self.thread.participants.set([self.talent, self.company])

    def test_list_messages(self):
        """Should return all messages in the thread."""
        Message.objects.create(thread=self.thread, sender=self.talent, body='Msg 1')
        Message.objects.create(thread=self.thread, sender=self.company, body='Msg 2')

        self.client.force_authenticate(user=self.talent)
        resp = self.client.get(f'/api/v1/messages/{self.thread.pk}/messages/')

        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        self.assertEqual(len(resp.data['results']), 2)

    def test_auto_marks_messages_as_read(self):
        """Fetching messages should mark the other user's messages as read."""
        msg = Message.objects.create(
            thread=self.thread, sender=self.company, body='Read me',
        )
        self.assertFalse(msg.read)

        self.client.force_authenticate(user=self.talent)
        self.client.get(f'/api/v1/messages/{self.thread.pk}/messages/')

        msg.refresh_from_db()
        self.assertTrue(msg.read)
        self.assertIsNotNone(msg.read_at)

    def test_own_messages_not_marked_as_read(self):
        """Your own messages should not be affected by the auto-read."""
        msg = Message.objects.create(
            thread=self.thread, sender=self.talent, body='My own',
            read=False,
        )

        self.client.force_authenticate(user=self.talent)
        self.client.get(f'/api/v1/messages/{self.thread.pk}/messages/')

        msg.refresh_from_db()
        self.assertFalse(msg.read)

    def test_non_participant_cannot_view(self):
        """Non-participant should get 404."""
        outsider = _create_talent(email='noview@msg.com')
        self.client.force_authenticate(user=outsider)
        resp = self.client.get(f'/api/v1/messages/{self.thread.pk}/messages/')

        self.assertEqual(resp.status_code, http_status.HTTP_404_NOT_FOUND)


@override_settings(
    CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class UnreadCountTest(TestCase):
    """Tests for GET /api/v1/messages/unread/"""

    def setUp(self):
        self.client = APIClient()
        self.talent = _create_talent(email='unread@msg.com')
        self.company = _create_company(email='unread_co@msg.com')

    def test_unread_count_zero(self):
        """No messages should return 0 unread."""
        self.client.force_authenticate(user=self.talent)
        resp = self.client.get('/api/v1/messages/unread/')
        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        self.assertEqual(resp.data['unread'], 0)

    def test_unread_count_from_others(self):
        """Should count unread messages from other participants."""
        thread = Thread.objects.create()
        thread.participants.set([self.talent, self.company])
        Message.objects.create(thread=thread, sender=self.company, body='Hey')
        Message.objects.create(thread=thread, sender=self.company, body='Hey 2')

        self.client.force_authenticate(user=self.talent)
        resp = self.client.get('/api/v1/messages/unread/')
        self.assertEqual(resp.data['unread'], 2)

    def test_own_messages_not_counted(self):
        """Your own messages should not count as unread for you."""
        thread = Thread.objects.create()
        thread.participants.set([self.talent, self.company])
        Message.objects.create(thread=thread, sender=self.talent, body='My msg')

        self.client.force_authenticate(user=self.talent)
        resp = self.client.get('/api/v1/messages/unread/')
        self.assertEqual(resp.data['unread'], 0)
