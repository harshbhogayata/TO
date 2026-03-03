"""
compliance/tests/test_throttling.py
Tests to verify throttle classes are correctly wired and configured.

These tests check class-level attributes (scope, inheritance) without
instantiating throttle objects, which avoids DRF's rate-lookup at
__init__ time that requires production settings.
"""
from django.test import TestCase

from compliance.throttling import (
    AuditLogThrottle,
    AuditIntegrityThrottle,
    PolicyCreateThrottle,
    ConsentWriteThrottle,
    DataExportThrottle,
    DataExportDownloadThrottle,
    DataDeletionThrottle,
    DeletionConfirmThrottle,
    TeamInviteThrottle,
    TeamInviteActionThrottle,
    _UserOrIPThrottle,
)

_ALL_THROTTLE_CLASSES = [
    AuditLogThrottle,
    AuditIntegrityThrottle,
    PolicyCreateThrottle,
    ConsentWriteThrottle,
    DataExportThrottle,
    DataExportDownloadThrottle,
    DataDeletionThrottle,
    DeletionConfirmThrottle,
    TeamInviteThrottle,
    TeamInviteActionThrottle,
]

_EXPECTED_SCOPES = {
    AuditLogThrottle: 'compliance_audit',
    AuditIntegrityThrottle: 'compliance_audit_integrity',
    PolicyCreateThrottle: 'compliance_policy_create',
    ConsentWriteThrottle: 'compliance_consent_write',
    DataExportThrottle: 'compliance_export',
    DataExportDownloadThrottle: 'compliance_export_download',
    DataDeletionThrottle: 'compliance_deletion',
    DeletionConfirmThrottle: 'compliance_deletion_confirm',
    TeamInviteThrottle: 'compliance_team_invite',
    TeamInviteActionThrottle: 'compliance_team_invite_action',
}


class ThrottleClassTests(TestCase):
    """Verify every compliance throttle class has the correct scope and lineage."""

    def test_correct_scopes(self):
        """Each throttle class should have the expected scope attribute."""
        for klass, expected_scope in _EXPECTED_SCOPES.items():
            self.assertEqual(
                klass.scope, expected_scope,
                f'{klass.__name__}.scope should be {expected_scope!r}',
            )

    def test_all_inherit_from_user_or_ip_throttle(self):
        """All throttle classes should derive from _UserOrIPThrottle."""
        for klass in _ALL_THROTTLE_CLASSES:
            self.assertTrue(
                issubclass(klass, _UserOrIPThrottle),
                f'{klass.__name__} should inherit from _UserOrIPThrottle',
            )

    def test_ten_throttle_classes_exist(self):
        """There should be exactly 10 compliance throttle classes."""
        self.assertEqual(len(_ALL_THROTTLE_CLASSES), 10)

    def test_scopes_are_unique(self):
        """No two throttle classes should share a scope."""
        scopes = [k.scope for k in _ALL_THROTTLE_CLASSES]
        self.assertEqual(len(scopes), len(set(scopes)))
