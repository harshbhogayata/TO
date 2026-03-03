"""
compliance/tests/test_gdpr_export.py
Tests for GDPR data export request, download, and rate limiting.
"""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework import status

from compliance.models import DataExportRequest
from compliance.constants import MAX_EXPORT_REQUESTS_PER_MONTH
from .factories import create_user


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    CELERY_TASK_ALWAYS_EAGER=True,
)
class DataExportAPITests(TestCase):
    """Tests for GDPR data export endpoints."""

    def setUp(self):
        self.user = create_user()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_request_export(self):
        """User can request a data export."""
        resp = self.client.post('/api/v1/compliance/gdpr/export/')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['status'], 'pending')
        self.assertTrue(DataExportRequest.objects.filter(user=self.user).exists())

    def test_export_monthly_rate_limit(self):
        """Exceeding monthly export limit returns 429."""
        for i in range(MAX_EXPORT_REQUESTS_PER_MONTH):
            DataExportRequest.objects.create(user=self.user)
        resp = self.client.post('/api/v1/compliance/gdpr/export/')
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_no_duplicate_active_export(self):
        """Can't create a new export while one is pending/processing."""
        DataExportRequest.objects.create(
            user=self.user,
            status=DataExportRequest.Status.PENDING,
        )
        resp = self.client.post('/api/v1/compliance/gdpr/export/')
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    def test_list_my_exports(self):
        """User can list their export requests."""
        DataExportRequest.objects.create(user=self.user)
        resp = self.client.get('/api/v1/compliance/gdpr/export/list/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['results']), 1)

    def test_download_nonexistent_token(self):
        """Downloading with invalid token returns 404."""
        resp = self.client.get('/api/v1/compliance/gdpr/export/fake-token/download/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_download_expired_export(self):
        """Downloading an expired export returns 410."""
        from django.utils import timezone
        from datetime import timedelta
        export = DataExportRequest.objects.create(
            user=self.user,
            status=DataExportRequest.Status.COMPLETED,
            file_path='some/file.zip',
            expires_at=timezone.now() - timedelta(hours=1),
        )
        resp = self.client.get(
            f'/api/v1/compliance/gdpr/export/{export.download_token}/download/'
        )
        self.assertEqual(resp.status_code, status.HTTP_410_GONE)
        # Safety net should mark it expired
        export.refresh_from_db()
        self.assertEqual(export.status, DataExportRequest.Status.EXPIRED)

    def test_export_serializer_includes_download_token(self):
        """Export response should include the download_token."""
        resp = self.client.post('/api/v1/compliance/gdpr/export/')
        self.assertIn('download_token', resp.data)
        self.assertTrue(resp.data['download_token'])

    def test_unauthenticated_denied(self):
        """Unauthenticated requests return 401."""
        client = APIClient()
        resp = client.post('/api/v1/compliance/gdpr/export/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_another_users_export_not_accessible(self):
        """User can't download another user's export."""
        other = create_user(email='other@test.com')
        export = DataExportRequest.objects.create(user=other)
        resp = self.client.get(
            f'/api/v1/compliance/gdpr/export/{export.download_token}/download/'
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
