"""
compliance/tests/test_anomaly.py
Tests for IP anomaly detection module (compliance.anomaly).
"""
from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from compliance.anomaly import (
    record_known_ip,
    is_new_ip,
    detect_anomalies,
    FAILED_LOGIN_THRESHOLD,
    BULK_ACCESS_THRESHOLD,
)
from compliance.constants import AuditAction, AuditCategory
from compliance.decorators import create_audit_log
from compliance.models import AuditLog
from .factories import create_user


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
)
class KnownIPTests(TestCase):
    """Tests for record_known_ip / is_new_ip helpers."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def test_new_ip_detected(self):
        self.assertTrue(is_new_ip(1, '10.0.0.1'))

    def test_recorded_ip_is_known(self):
        record_known_ip(1, '10.0.0.1')
        self.assertFalse(is_new_ip(1, '10.0.0.1'))

    def test_different_user_same_ip_still_new(self):
        record_known_ip(1, '10.0.0.1')
        self.assertTrue(is_new_ip(2, '10.0.0.1'))

    def test_multiple_ips_tracked(self):
        record_known_ip(1, '10.0.0.1')
        record_known_ip(1, '10.0.0.2')
        self.assertFalse(is_new_ip(1, '10.0.0.1'))
        self.assertFalse(is_new_ip(1, '10.0.0.2'))
        self.assertTrue(is_new_ip(1, '10.0.0.3'))

    def test_empty_ip_not_flagged(self):
        """Empty/None IP should never be flagged as new."""
        self.assertFalse(is_new_ip(1, ''))
        self.assertFalse(is_new_ip(1, None))

    def test_empty_ip_not_recorded(self):
        """Recording an empty IP should be a no-op."""
        record_known_ip(1, '')
        record_known_ip(1, None)
        # Still new for a real IP
        self.assertTrue(is_new_ip(1, '10.0.0.1'))


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
)
class DetectAnomaliesTests(TestCase):
    """Tests for the detect_anomalies() scanner."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.user = create_user(email='anomaly@test.com')

    def test_no_anomalies_on_clean_logs(self):
        """Empty audit log → no anomalies."""
        result = detect_anomalies()
        self.assertEqual(result['new_ip_logins'], 0)
        self.assertEqual(result['brute_force_ips'], 0)
        self.assertEqual(result['bulk_access_users'], 0)

    def test_new_ip_login_detected(self):
        """A login from an unseen IP should trigger a new-IP alert."""
        create_audit_log(
            actor=self.user,
            action=AuditAction.LOGIN,
            category=AuditCategory.AUTH,
            description='Login',
            ip_address='192.168.1.1',
        )
        result = detect_anomalies()
        self.assertEqual(result['new_ip_logins'], 1)
        # Verify an anomaly audit entry was created
        self.assertTrue(
            AuditLog.objects.filter(
                description__contains='[ANOMALY]',
                category=AuditCategory.SYSTEM,
            ).exists()
        )

    def test_known_ip_login_not_flagged(self):
        """A login from a known IP should NOT trigger an alert."""
        record_known_ip(self.user.pk, '192.168.1.1')
        create_audit_log(
            actor=self.user,
            action=AuditAction.LOGIN,
            category=AuditCategory.AUTH,
            description='Login',
            ip_address='192.168.1.1',
        )
        result = detect_anomalies()
        self.assertEqual(result['new_ip_logins'], 0)

    def test_brute_force_detected(self):
        """Many failed logins from one IP should trigger a brute-force alert."""
        for i in range(FAILED_LOGIN_THRESHOLD):
            AuditLog.objects.create(
                action=AuditAction.LOGIN_FAILED,
                category=AuditCategory.AUTH,
                description=f'Failed login attempt #{i+1}',
                ip_address='10.0.0.99',
                checksum='placeholder',
            )
        result = detect_anomalies()
        self.assertEqual(result['brute_force_ips'], 1)

    def test_brute_force_below_threshold_not_flagged(self):
        """Fewer than threshold failed logins should not alert."""
        for i in range(FAILED_LOGIN_THRESHOLD - 1):
            AuditLog.objects.create(
                action=AuditAction.LOGIN_FAILED,
                category=AuditCategory.AUTH,
                description=f'Failed login attempt #{i+1}',
                ip_address='10.0.0.99',
                checksum='placeholder',
            )
        result = detect_anomalies()
        self.assertEqual(result['brute_force_ips'], 0)

    def test_bulk_data_access_detected(self):
        """Many export requests from one user in the window should alert."""
        for i in range(BULK_ACCESS_THRESHOLD):
            create_audit_log(
                actor=self.user,
                action=AuditAction.DATA_EXPORT_REQUEST,
                category=AuditCategory.COMPLIANCE,
                description=f'Export #{i+1}',
            )
        result = detect_anomalies()
        self.assertEqual(result['bulk_access_users'], 1)

    def test_bulk_data_access_below_threshold_not_flagged(self):
        for i in range(BULK_ACCESS_THRESHOLD - 1):
            create_audit_log(
                actor=self.user,
                action=AuditAction.DATA_EXPORT_REQUEST,
                category=AuditCategory.COMPLIANCE,
                description=f'Export #{i+1}',
            )
        result = detect_anomalies()
        self.assertEqual(result['bulk_access_users'], 0)

    def test_old_events_outside_window_ignored(self):
        """Events older than the scan window should be ignored."""
        old_time = timezone.now() - timedelta(hours=2)
        # Create a login entry that looks old
        entry = AuditLog.objects.create(
            actor=self.user,
            action=AuditAction.LOGIN,
            category=AuditCategory.AUTH,
            description='Old login',
            ip_address='10.0.0.50',
            checksum='placeholder',
            actor_email=self.user.email,
        )
        AuditLog.objects.filter(pk=entry.pk).update(created_at=old_time)

        result = detect_anomalies()
        self.assertEqual(result['new_ip_logins'], 0)
