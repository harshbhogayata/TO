"""
compliance/tests/test_team.py
Comprehensive tests for Team CRUD, seat limits, member management,
invitation lifecycle, role changes, HMAC token verification, and permissions.
"""
from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from compliance.models import Team, TeamMember, TeamInvitation
from compliance.token_utils import generate_signed_token, verify_signed_token
from .factories import (
    create_user,
    create_admin_user,
    create_company_user,
    create_talent_user,
    create_team,
    create_team_invitation,
)


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    CELERY_TASK_ALWAYS_EAGER=True,
)
class TeamOverviewTests(TestCase):
    """Tests for GET/POST /api/v1/compliance/team/"""

    def setUp(self):
        self.company = create_company_user(email='owner@test.com')
        self.talent = create_talent_user(email='talent@test.com')
        self.client = APIClient()

    def test_talent_user_cannot_create_team(self):
        self.client.force_authenticate(user=self.talent)
        resp = self.client.post('/api/v1/compliance/team/', {'name': 'My Team'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_talent_user_cannot_get_team(self):
        self.client.force_authenticate(user=self.talent)
        resp = self.client.get('/api/v1/compliance/team/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_company_no_team_returns_has_team_false(self):
        self.client.force_authenticate(user=self.company)
        resp = self.client.get('/api/v1/compliance/team/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data['has_team'])
        self.assertIsNone(resp.data['team'])

    def test_company_creates_team(self):
        self.client.force_authenticate(user=self.company)
        resp = self.client.post('/api/v1/compliance/team/', {'name': 'Acme Team'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['team']['name'], 'Acme Team')
        # Owner auto-added
        self.assertTrue(
            TeamMember.objects.filter(
                team__company=self.company.company_profile,
                user=self.company,
                role='owner',
            ).exists()
        )

    def test_duplicate_team_rejected(self):
        create_team(self.company)
        self.client.force_authenticate(user=self.company)
        resp = self.client.post('/api/v1/compliance/team/', {'name': 'Another'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    def test_get_team_after_create(self):
        create_team(self.company, name='My Team')
        self.client.force_authenticate(user=self.company)
        resp = self.client.get('/api/v1/compliance/team/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['has_team'])
        self.assertEqual(resp.data['team']['name'], 'My Team')

    def test_unauthenticated_denied(self):
        resp = APIClient().get('/api/v1/compliance/team/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    CELERY_TASK_ALWAYS_EAGER=True,
)
class TeamMemberListTests(TestCase):
    """Tests for GET /api/v1/compliance/team/members/"""

    def setUp(self):
        self.company = create_company_user(email='owner@test.com')
        self.team = create_team(self.company)
        self.client = APIClient()

    def test_owner_sees_members(self):
        self.client.force_authenticate(user=self.company)
        resp = self.client.get('/api/v1/compliance/team/members/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # No pagination wrapper — raw list
        self.assertIsInstance(resp.data, list)
        self.assertEqual(len(resp.data), 1)  # Just the owner
        self.assertEqual(resp.data[0]['role'], 'owner')

    def test_inactive_members_excluded(self):
        """Deactivated members should not appear in the list."""
        other = create_user(email='removed@test.com', role='COMPANY')
        TeamMember.objects.create(
            team=self.team, user=other, role='recruiter',
            invited_by=self.company, is_active=False,
            deactivated_at=timezone.now(),
        )
        self.client.force_authenticate(user=self.company)
        resp = self.client.get('/api/v1/compliance/team/members/')
        self.assertEqual(len(resp.data), 1)

    def test_non_member_sees_empty(self):
        outsider = create_user(email='outsider@test.com', role='COMPANY')
        self.client.force_authenticate(user=outsider)
        resp = self.client.get('/api/v1/compliance/team/members/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 0)


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    CELERY_TASK_ALWAYS_EAGER=True,
)
class TeamInvitationTests(TestCase):
    """Tests for team invitation lifecycle."""

    def setUp(self):
        self.company = create_company_user(email='owner@test.com', subscription_tier='professional')
        self.team = create_team(self.company)
        self.client = APIClient()
        self.client.force_authenticate(user=self.company)

    def test_invite_member(self):
        resp = self.client.post(
            '/api/v1/compliance/team/invite/',
            {'email': 'new@test.com', 'role': 'recruiter'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['email'], 'new@test.com')
        self.assertEqual(resp.data['role'], 'recruiter')
        self.assertEqual(resp.data['status'], 'pending')

    def test_invite_duplicate_pending_rejected(self):
        create_team_invitation(self.team, email='dup@test.com', invited_by=self.company)
        resp = self.client.post(
            '/api/v1/compliance/team/invite/',
            {'email': 'dup@test.com', 'role': 'viewer'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    def test_invite_existing_member_rejected(self):
        existing = create_user(email='existing@test.com', role='COMPANY')
        TeamMember.objects.create(team=self.team, user=existing, role='recruiter', invited_by=self.company)
        resp = self.client.post(
            '/api/v1/compliance/team/invite/',
            {'email': 'existing@test.com', 'role': 'viewer'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    def test_invite_at_capacity_rejected(self):
        """When team is at seat capacity, inviting should fail."""
        # Free tier has 1 seat (owner only)
        self.company.company_profile.subscription_tier = 'free'
        self.company.company_profile.save()
        resp = self.client.post(
            '/api/v1/compliance/team/invite/',
            {'email': 'nope@test.com', 'role': 'viewer'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('capacity', resp.data['error'].lower())

    def test_viewer_cannot_invite(self):
        viewer = create_user(email='viewer@test.com', role='COMPANY')
        TeamMember.objects.create(team=self.team, user=viewer, role='viewer', invited_by=self.company)
        self.client.force_authenticate(user=viewer)
        resp = self.client.post(
            '/api/v1/compliance/team/invite/',
            {'email': 'nobody@test.com', 'role': 'viewer'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_invitation_token_is_hmac_signed(self):
        """Invitation tokens must be HMAC-signed."""
        invitation = create_team_invitation(self.team, email='tok@test.com')
        self.assertTrue(verify_signed_token(invitation.token))

    def test_invitation_list(self):
        create_team_invitation(self.team, email='a@test.com')
        create_team_invitation(self.team, email='b@test.com')
        resp = self.client.get('/api/v1/compliance/team/invitations/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsInstance(resp.data, list)  # No pagination
        self.assertEqual(len(resp.data), 2)


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    CELERY_TASK_ALWAYS_EAGER=True,
)
class AcceptDeclineInvitationTests(TestCase):
    """Tests for accepting and declining invitations with HMAC verification."""

    def setUp(self):
        self.company = create_company_user(email='owner@test.com', subscription_tier='professional')
        self.team = create_team(self.company)
        self.invitee = create_user(email='invitee@test.com', role='COMPANY')
        self.invitation = create_team_invitation(
            self.team, email='invitee@test.com', invited_by=self.company,
        )
        self.client = APIClient()

    def test_accept_invitation(self):
        self.client.force_authenticate(user=self.invitee)
        resp = self.client.post(f'/api/v1/compliance/team/invite/{self.invitation.token}/accept/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('Welcome', resp.data['message'])
        # Verify membership created
        self.assertTrue(
            TeamMember.objects.filter(team=self.team, user=self.invitee, is_active=True).exists()
        )
        # Invitation status updated
        self.invitation.refresh_from_db()
        self.assertEqual(self.invitation.status, TeamInvitation.Status.ACCEPTED)

    def test_accept_with_forged_token_rejected(self):
        """A completely forged token (no valid HMAC) should be rejected."""
        self.client.force_authenticate(user=self.invitee)
        resp = self.client.post('/api/v1/compliance/team/invite/totally-fake-token/accept/')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_accept_wrong_email_rejected(self):
        """A different user cannot accept someone else's invitation."""
        other = create_user(email='other@test.com', role='COMPANY')
        self.client.force_authenticate(user=other)
        resp = self.client.post(f'/api/v1/compliance/team/invite/{self.invitation.token}/accept/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_accept_expired_invitation(self):
        """Expired invitations should return 410 Gone."""
        self.invitation.expires_at = timezone.now() - timedelta(hours=1)
        self.invitation.save(update_fields=['expires_at'])
        self.client.force_authenticate(user=self.invitee)
        resp = self.client.post(f'/api/v1/compliance/team/invite/{self.invitation.token}/accept/')
        self.assertEqual(resp.status_code, status.HTTP_410_GONE)

    def test_accept_at_capacity_rejected(self):
        """If team is now at capacity, accept should fail."""
        self.company.company_profile.subscription_tier = 'free'
        self.company.company_profile.save()
        self.client.force_authenticate(user=self.invitee)
        resp = self.client.post(f'/api/v1/compliance/team/invite/{self.invitation.token}/accept/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('capacity', resp.data['error'].lower())

    def test_decline_invitation(self):
        self.client.force_authenticate(user=self.invitee)
        resp = self.client.post(f'/api/v1/compliance/team/invite/{self.invitation.token}/decline/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.invitation.refresh_from_db()
        self.assertEqual(self.invitation.status, TeamInvitation.Status.DECLINED)

    def test_decline_forged_token_rejected(self):
        self.client.force_authenticate(user=self.invitee)
        resp = self.client.post('/api/v1/compliance/team/invite/bad-token/decline/')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_accept_already_accepted_fails(self):
        """Can't accept an already-accepted invitation."""
        self.invitation.status = TeamInvitation.Status.ACCEPTED
        self.invitation.save(update_fields=['status'])
        self.client.force_authenticate(user=self.invitee)
        resp = self.client.post(f'/api/v1/compliance/team/invite/{self.invitation.token}/accept/')
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    def test_preview_invitation(self):
        """Public preview endpoint returns invitation details."""
        resp = APIClient().get(f'/api/v1/compliance/team/invite/{self.invitation.token}/preview/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['valid'])
        self.assertEqual(resp.data['team_name'], self.team.name)
        self.assertEqual(resp.data['email'], 'invitee@test.com')

    def test_preview_forged_token_rejected(self):
        resp = APIClient().get('/api/v1/compliance/team/invite/forged/preview/')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reactivate_previously_removed_member(self):
        """Accepting an invitation reactivates a previously deactivated member."""
        # First create, then deactivate
        member = TeamMember.objects.create(
            team=self.team, user=self.invitee, role='viewer',
            invited_by=self.company, is_active=False,
            deactivated_at=timezone.now(),
        )
        self.client.force_authenticate(user=self.invitee)
        resp = self.client.post(f'/api/v1/compliance/team/invite/{self.invitation.token}/accept/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        member.refresh_from_db()
        self.assertTrue(member.is_active)
        self.assertEqual(member.role, self.invitation.role)  # Role updated to invite role


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    CELERY_TASK_ALWAYS_EAGER=True,
)
class RevokeInvitationTests(TestCase):
    """Tests for DELETE /api/v1/compliance/team/invite/<pk>/"""

    def setUp(self):
        self.company = create_company_user(email='owner@test.com', subscription_tier='professional')
        self.team = create_team(self.company)
        self.invitation = create_team_invitation(self.team, email='tgt@test.com')
        self.client = APIClient()
        self.client.force_authenticate(user=self.company)

    def test_revoke_pending_invitation(self):
        resp = self.client.delete(f'/api/v1/compliance/team/invite/{self.invitation.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.invitation.refresh_from_db()
        self.assertEqual(self.invitation.status, TeamInvitation.Status.REVOKED)

    def test_revoke_non_pending_fails(self):
        self.invitation.status = TeamInvitation.Status.ACCEPTED
        self.invitation.save(update_fields=['status'])
        resp = self.client.delete(f'/api/v1/compliance/team/invite/{self.invitation.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    def test_viewer_cannot_revoke(self):
        viewer = create_user(email='v@test.com', role='COMPANY')
        TeamMember.objects.create(team=self.team, user=viewer, role='viewer', invited_by=self.company)
        self.client.force_authenticate(user=viewer)
        resp = self.client.delete(f'/api/v1/compliance/team/invite/{self.invitation.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    CELERY_TASK_ALWAYS_EAGER=True,
)
class ChangeRoleTests(TestCase):
    """Tests for PATCH /api/v1/compliance/team/members/<pk>/role/"""

    def setUp(self):
        self.company = create_company_user(email='owner@test.com', subscription_tier='professional')
        self.team = create_team(self.company)
        self.member_user = create_user(email='member@test.com', role='COMPANY')
        self.member = TeamMember.objects.create(
            team=self.team, user=self.member_user, role='recruiter', invited_by=self.company,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.company)

    def test_owner_changes_role(self):
        resp = self.client.patch(
            f'/api/v1/compliance/team/members/{self.member.pk}/role/',
            {'role': 'admin'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.member.refresh_from_db()
        self.assertEqual(self.member.role, 'admin')

    def test_admin_cannot_change_owner(self):
        admin_user = create_user(email='admin@test.com', role='COMPANY')
        TeamMember.objects.create(
            team=self.team, user=admin_user, role='admin', invited_by=self.company,
        )
        owner_member = TeamMember.objects.get(team=self.team, user=self.company)
        self.client.force_authenticate(user=admin_user)
        resp = self.client.patch(
            f'/api/v1/compliance/team/members/{owner_member.pk}/role/',
            {'role': 'admin'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_viewer_cannot_change_role(self):
        viewer = create_user(email='v@test.com', role='COMPANY')
        TeamMember.objects.create(team=self.team, user=viewer, role='viewer', invited_by=self.company)
        self.client.force_authenticate(user=viewer)
        resp = self.client.patch(
            f'/api/v1/compliance/team/members/{self.member.pk}/role/',
            {'role': 'admin'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_role_change_audited(self):
        """Role changes should create an audit log entry."""
        from compliance.models import AuditLog
        initial_count = AuditLog.objects.count()
        self.client.patch(
            f'/api/v1/compliance/team/members/{self.member.pk}/role/',
            {'role': 'viewer'},
            format='json',
        )
        self.assertGreater(AuditLog.objects.count(), initial_count)


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    CELERY_TASK_ALWAYS_EAGER=True,
)
class RemoveMemberTests(TestCase):
    """Tests for DELETE /api/v1/compliance/team/members/<pk>/"""

    def setUp(self):
        self.company = create_company_user(email='owner@test.com', subscription_tier='professional')
        self.team = create_team(self.company)
        self.member_user = create_user(email='member@test.com', role='COMPANY')
        self.member = TeamMember.objects.create(
            team=self.team, user=self.member_user, role='recruiter', invited_by=self.company,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.company)

    def test_remove_member(self):
        resp = self.client.delete(f'/api/v1/compliance/team/members/{self.member.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_active)
        self.assertIsNotNone(self.member.deactivated_at)

    def test_cannot_remove_owner(self):
        owner_member = TeamMember.objects.get(team=self.team, user=self.company)
        resp = self.client.delete(f'/api/v1/compliance/team/members/{owner_member.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_self_removal_allowed(self):
        """Members can remove themselves even without admin permission."""
        self.client.force_authenticate(user=self.member_user)
        resp = self.client.delete(f'/api/v1/compliance/team/members/{self.member.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_active)

    def test_outsider_cannot_remove(self):
        outsider = create_user(email='out@test.com', role='COMPANY')
        self.client.force_authenticate(user=outsider)
        resp = self.client.delete(f'/api/v1/compliance/team/members/{self.member.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_removed_member_not_in_list(self):
        """Removed members should not appear in the member list."""
        self.member.is_active = False
        self.member.deactivated_at = timezone.now()
        self.member.save()
        self.client.force_authenticate(user=self.company)
        resp = self.client.get('/api/v1/compliance/team/members/')
        emails = [m['email'] for m in resp.data]
        self.assertNotIn('member@test.com', emails)


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    CELERY_TASK_ALWAYS_EAGER=True,
)
class TeamSeatLimitTests(TestCase):
    """Tests that seat limits per subscription tier are enforced correctly."""

    def test_free_tier_one_seat(self):
        company = create_company_user(email='free@test.com', subscription_tier='free')
        team = create_team(company)
        self.assertEqual(team.max_seats, 1)
        self.assertTrue(team.is_at_capacity)  # Owner occupies the only seat

    def test_starter_tier_three_seats(self):
        company = create_company_user(email='starter@test.com', subscription_tier='starter')
        team = create_team(company)
        self.assertEqual(team.max_seats, 3)
        self.assertFalse(team.is_at_capacity)
        self.assertEqual(team.seats_available, 2)

    def test_professional_tier_ten_seats(self):
        company = create_company_user(email='pro@test.com', subscription_tier='professional')
        team = create_team(company)
        self.assertEqual(team.max_seats, 10)
        self.assertEqual(team.seats_available, 9)

    def test_enterprise_tier_fifty_seats(self):
        company = create_company_user(email='ent@test.com', subscription_tier='enterprise')
        team = create_team(company)
        self.assertEqual(team.max_seats, 50)

    def test_current_seat_count_only_active(self):
        """Inactive members don't count toward seat usage."""
        company = create_company_user(email='s@test.com', subscription_tier='starter')
        team = create_team(company)
        other = create_user(email='other@test.com', role='COMPANY')
        TeamMember.objects.create(
            team=team, user=other, role='recruiter',
            invited_by=company, is_active=False,
        )
        self.assertEqual(team.current_seat_count, 1)  # Only owner counts
