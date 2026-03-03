"""
compliance/urls.py
Phase 6 — Trust & Compliance URL configuration.
"""
from django.urls import path

from compliance import views

app_name = 'compliance'

urlpatterns = [
    # ── Audit Logs (Admin only) ──────────────────────────────────────────
    path(
        'audit-logs/',
        views.AuditLogListView.as_view(),
        name='audit-log-list',
    ),
    path(
        'audit-logs/integrity/',
        views.audit_log_integrity,
        name='audit-log-integrity',
    ),
    path(
        'audit-logs/stats/',
        views.audit_log_stats,
        name='audit-log-stats',
    ),
    path(
        'audit-logs/<int:pk>/',
        views.AuditLogDetailView.as_view(),
        name='audit-log-detail',
    ),

    # ── Policies ─────────────────────────────────────────────────────────
    path(
        'policies/',
        views.PolicyVersionListView.as_view(),
        name='policy-list',
    ),
    path(
        'policies/create/',
        views.PolicyVersionCreateView.as_view(),
        name='policy-create',
    ),
    path(
        'policies/<int:pk>/',
        views.PolicyVersionDetailView.as_view(),
        name='policy-detail',
    ),

    # ── Consent ──────────────────────────────────────────────────────────
    path(
        'consent/',
        views.MyConsentRecordsView.as_view(),
        name='consent-list',
    ),
    path(
        'consent/grant/',
        views.grant_consent,
        name='consent-grant',
    ),
    path(
        'consent/withdraw/',
        views.withdraw_consent,
        name='consent-withdraw',
    ),
    path(
        'consent/status/',
        views.consent_status,
        name='consent-status',
    ),

    # ── GDPR Data Export ─────────────────────────────────────────────────
    path(
        'gdpr/export/',
        views.request_data_export,
        name='gdpr-export-request',
    ),
    path(
        'gdpr/export/list/',
        views.MyDataExportRequestsView.as_view(),
        name='gdpr-export-list',
    ),
    path(
        'gdpr/export/<str:token>/download/',
        views.download_data_export,
        name='gdpr-export-download',
    ),

    # ── GDPR Data Deletion ───────────────────────────────────────────────
    path(
        'gdpr/deletion/',
        views.request_data_deletion,
        name='gdpr-deletion-request',
    ),
    path(
        'gdpr/deletion/list/',
        views.MyDataDeletionRequestsView.as_view(),
        name='gdpr-deletion-list',
    ),
    path(
        'gdpr/deletion/confirm/',
        views.confirm_data_deletion,
        name='gdpr-deletion-confirm',
    ),
    path(
        'gdpr/deletion/cancel/',
        views.cancel_data_deletion,
        name='gdpr-deletion-cancel',
    ),

    # ── Teams ────────────────────────────────────────────────────────────
    path(
        'team/',
        views.team_overview,
        name='team-overview',
    ),
    path(
        'team/members/',
        views.TeamMemberListView.as_view(),
        name='team-member-list',
    ),
    path(
        'team/members/<int:pk>/role/',
        views.change_member_role,
        name='team-member-role',
    ),
    path(
        'team/members/<int:pk>/',
        views.remove_team_member,
        name='team-member-remove',
    ),
    path(
        'team/invite/',
        views.invite_team_member,
        name='team-invite',
    ),
    path(
        'team/invite/<str:token>/preview/',
        views.preview_team_invitation,
        name='team-invite-preview',
    ),
    path(
        'team/invite/<str:token>/accept/',
        views.accept_team_invitation,
        name='team-invite-accept',
    ),
    path(
        'team/invite/<str:token>/decline/',
        views.decline_team_invitation,
        name='team-invite-decline',
    ),
    path(
        'team/invite/<int:pk>/',
        views.revoke_team_invitation,
        name='team-invite-revoke',
    ),
    path(
        'team/invitations/',
        views.TeamInvitationListView.as_view(),
        name='team-invitation-list',
    ),

    # ── Security / Bug Bounty ────────────────────────────────────────────
    path(
        'security/',
        views.bug_bounty_info,
        name='security-info',
    ),
]
