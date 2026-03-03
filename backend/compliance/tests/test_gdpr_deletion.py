"""
compliance/tests/test_gdpr_deletion.py
Tests for GDPR data deletion request, confirmation, cancellation, and cooling-off.
"""
from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from compliance.models import DataDeletionRequest
from compliance.constants import MAX_DELETION_REQUESTS_PER_MONTH, DELETION_COOLING_OFF_DAYS
from .factories import create_user


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    CELERY_TASK_ALWAYS_EAGER=True,
)
class DataDeletionAPITests(TestCase):
    """Tests for GDPR data deletion endpoints."""

    def setUp(self):
        self.password = 'TestPass123!'
        self.user = create_user(password=self.password)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_request_deletion(self):
        """User can request account deletion."""
        resp = self.client.post(
            '/api/v1/compliance/gdpr/deletion/',
            {'password': self.password, 'reason': 'Leaving the platform'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['status'], 'pending')
        self.assertTrue(
            DataDeletionRequest.objects.filter(user=self.user).exists()
        )

    def test_deletion_requires_password(self):
        """Deletion request without password returns 400."""
        resp = self.client.post(
            '/api/v1/compliance/gdpr/deletion/',
            {'reason': 'test'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_deletion_wrong_password(self):
        """Wrong password returns 403."""
        resp = self.client.post(
            '/api/v1/compliance/gdpr/deletion/',
            {'password': 'WrongPass!'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_deletion_monthly_rate_limit(self):
        """Exceeding monthly deletion limit returns 429."""
        DataDeletionRequest.objects.create(
            user=self.user,
            user_email=self.user.email,
            status=DataDeletionRequest.Status.COMPLETED,
        )
        resp = self.client.post(
            '/api/v1/compliance/gdpr/deletion/',
            {'password': self.password},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_no_duplicate_active_deletion(self):
        """Can't create deletion while one is already active (rate limit hit first)."""
        DataDeletionRequest.objects.create(
            user=self.user,
            user_email=self.user.email,
            status=DataDeletionRequest.Status.COOLING_OFF,
        )
        resp = self.client.post(
            '/api/v1/compliance/gdpr/deletion/',
            {'password': self.password},
            format='json',
        )
        # Rate limit (MAX=1/month) fires before the active-request check
        self.assertIn(resp.status_code, [
            status.HTTP_429_TOO_MANY_REQUESTS,
            status.HTTP_409_CONFLICT,
        ])

    def test_confirm_deletion(self):
        """Confirming with valid token starts cooling-off period."""
        req = DataDeletionRequest.objects.create(
            user=self.user,
            user_email=self.user.email,
        )
        # Confirm (AllowAny endpoint, so no auth needed)
        client = APIClient()
        resp = client.post(
            '/api/v1/compliance/gdpr/deletion/confirm/',
            {'token': req.confirmation_token},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        req.refresh_from_db()
        self.assertEqual(req.status, DataDeletionRequest.Status.COOLING_OFF)
        self.assertIsNotNone(req.cooling_off_ends_at)

    def test_confirm_invalid_token(self):
        """Invalid confirmation token returns 400."""
        client = APIClient()
        resp = client.post(
            '/api/v1/compliance/gdpr/deletion/confirm/',
            {'token': 'invalid-token'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancel_deletion(self):
        """User can cancel a pending/cooling-off deletion."""
        req = DataDeletionRequest.objects.create(
            user=self.user,
            user_email=self.user.email,
            status=DataDeletionRequest.Status.COOLING_OFF,
            cooling_off_ends_at=timezone.now() + timedelta(days=14),
        )
        client = APIClient()
        resp = client.post(
            '/api/v1/compliance/gdpr/deletion/cancel/',
            {'token': req.cancellation_token},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        req.refresh_from_db()
        self.assertEqual(req.status, DataDeletionRequest.Status.CANCELLED)

    def test_cancel_completed_deletion_fails(self):
        """Can't cancel an already completed deletion."""
        req = DataDeletionRequest.objects.create(
            user=self.user,
            user_email=self.user.email,
            status=DataDeletionRequest.Status.COMPLETED,
        )
        client = APIClient()
        resp = client.post(
            '/api/v1/compliance/gdpr/deletion/cancel/',
            {'token': req.cancellation_token},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    def test_list_my_deletions(self):
        """User can list their deletion requests."""
        DataDeletionRequest.objects.create(
            user=self.user,
            user_email=self.user.email,
        )
        resp = self.client.get('/api/v1/compliance/gdpr/deletion/list/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['results']), 1)

    def test_serializer_includes_cancellation_token(self):
        """Deletion response should include the cancellation_token."""
        resp = self.client.post(
            '/api/v1/compliance/gdpr/deletion/',
            {'password': self.password},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn('cancellation_token', resp.data)
        self.assertTrue(resp.data['cancellation_token'])

    def test_cooling_off_remaining_seconds(self):
        """Serializer should include cooling off remaining seconds."""
        req = DataDeletionRequest.objects.create(
            user=self.user,
            user_email=self.user.email,
            status=DataDeletionRequest.Status.COOLING_OFF,
            cooling_off_ends_at=timezone.now() + timedelta(days=14),
        )
        resp = self.client.get('/api/v1/compliance/gdpr/deletion/list/')
        self.assertIn('cooling_off_remaining_seconds', resp.data['results'][0])
        remaining = resp.data['results'][0]['cooling_off_remaining_seconds']
        self.assertGreater(remaining, 0)
