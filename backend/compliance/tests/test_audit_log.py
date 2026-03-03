"""
compliance/tests/test_audit_log.py
Tests for the AuditLog model, chain integrity, and admin API endpoints.
"""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework import status

from compliance.models import AuditLog
from compliance.constants import AuditAction, AuditCategory
from compliance.decorators import create_audit_log
from .factories import create_admin_user, create_user


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
)
class AuditLogModelTests(TestCase):
    """Tests for AuditLog model and tamper-evidence chain."""

    def test_create_audit_log_sets_checksum(self):
        """Each audit log entry should have a non-empty checksum."""
        user = create_user()
        log = AuditLog.objects.create(
            actor=user,
            action=AuditLog.Action.LOGIN,
            category=AuditLog.Category.AUTH,
            description='Test login',
        )
        self.assertTrue(log.checksum)
        self.assertEqual(len(log.checksum), 64)  # SHA-256 hex

    def test_chain_links_previous_checksum(self):
        """Each new entry should link to the previous entry's checksum."""
        user = create_user()
        log1 = AuditLog.objects.create(
            actor=user,
            action=AuditLog.Action.LOGIN,
            category=AuditLog.Category.AUTH,
            description='Login 1',
        )
        log2 = AuditLog.objects.create(
            actor=user,
            action=AuditLog.Action.LOGOUT,
            category=AuditLog.Category.AUTH,
            description='Logout',
        )
        self.assertEqual(log2.previous_checksum, log1.checksum)

    def test_first_entry_uses_zero_previous(self):
        """The very first entry in the chain uses all-zeros as previous checksum."""
        first = AuditLog.objects.order_by('pk').first()
        if first is None:
            # No signal-created logs — create one manually
            first = AuditLog.objects.create(
                action=AuditLog.Action.LOGIN,
                category=AuditLog.Category.AUTH,
                description='First entry',
            )
        self.assertEqual(first.previous_checksum, '0' * 64)

    def test_verify_integrity_passes(self):
        """verify_integrity() should pass for an untampered record."""
        user = create_user()
        log = AuditLog.objects.create(
            actor=user,
            action=AuditLog.Action.CREATE,
            category=AuditLog.Category.USER,
            description='Created something',
        )
        self.assertTrue(log.verify_integrity())

    def test_verify_chain_passes(self):
        """verify_chain() should validate a clean chain."""
        user = create_user()
        for i in range(5):
            AuditLog.objects.create(
                actor=user,
                action=AuditLog.Action.LOGIN,
                category=AuditLog.Category.AUTH,
                description=f'Login {i}',
            )
        total = AuditLog.objects.count()
        result = AuditLog.verify_chain(limit=total + 10)
        self.assertTrue(result['valid'])
        self.assertEqual(result['checked'], total)

    def test_verify_chain_detects_tampering(self):
        """verify_chain() should detect a broken chain."""
        user = create_user()
        for i in range(3):
            AuditLog.objects.create(
                actor=user,
                action=AuditLog.Action.LOGIN,
                category=AuditLog.Category.AUTH,
                description=f'Login {i}',
            )
        # Tamper with the second entry
        second = AuditLog.objects.order_by('pk')[1]
        AuditLog.objects.filter(pk=second.pk).update(checksum='tampered_hash')

        result = AuditLog.verify_chain(limit=10)
        self.assertFalse(result['valid'])

    def test_denormalises_actor_info(self):
        """Actor email and role should be denormalised on save."""
        user = create_user(email='test@example.com', role='TALENT')
        log = AuditLog.objects.create(
            actor=user,
            action=AuditLog.Action.LOGIN,
            category=AuditLog.Category.AUTH,
            description='Test login',
        )
        self.assertEqual(log.actor_email, 'test@example.com')
        self.assertEqual(log.actor_role, 'TALENT')

    def test_create_audit_log_helper(self):
        """The create_audit_log() helper should create an entry."""
        user = create_user()
        baseline = AuditLog.objects.count()
        create_audit_log(
            actor=user,
            action=AuditAction.CREATE,
            category=AuditCategory.JOB,
            description='Test helper',
            resource_type='jobs.JobPost',
            resource_id='42',
        )
        self.assertEqual(AuditLog.objects.count(), baseline + 1)
        log = AuditLog.objects.latest('pk')
        self.assertEqual(log.resource_type, 'jobs.JobPost')
        self.assertEqual(log.resource_id, '42')


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
)
class AuditLogAPITests(TestCase):
    """Tests for the admin audit log API endpoints."""

    def setUp(self):
        self.admin = create_admin_user()
        self.talent = create_user(email='talent@test.com')
        self.client = APIClient()

        # Create some audit logs
        for i in range(5):
            AuditLog.objects.create(
                actor=self.talent,
                action=AuditLog.Action.LOGIN,
                category=AuditLog.Category.AUTH,
                description=f'Login {i}',
                ip_address='127.0.0.1',
            )

    def test_list_requires_admin(self):
        """Non-admin users should get 403 on audit log list."""
        self.client.force_authenticate(user=self.talent)
        resp = self.client.get('/api/v1/compliance/audit-logs/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_returns_logs(self):
        """Admin should get paginated audit logs."""
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get('/api/v1/compliance/audit-logs/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('results', resp.data)
        self.assertGreaterEqual(len(resp.data['results']), 5)

    def test_filter_by_action(self):
        """Admin can filter audit logs by action."""
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get('/api/v1/compliance/audit-logs/?action=LOGIN')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data['results']), 5)

    def test_integrity_check(self):
        """Integrity endpoint should return valid chain result."""
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get('/api/v1/compliance/audit-logs/integrity/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['valid'])

    def test_stats_endpoint(self):
        """Stats endpoint should return aggregate data."""
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get('/api/v1/compliance/audit-logs/stats/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('total_entries', resp.data)
        self.assertGreaterEqual(resp.data['total_entries'], 5)
