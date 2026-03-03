"""
compliance/tests/factories.py
Reusable test factories for the compliance test suite.

Provides helper functions to create users, teams, policies, and other
fixtures needed across multiple test modules.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import CompanyProfile, TalentProfile
from compliance.models import (
    AuditLog,
    PolicyVersion,
    ConsentRecord,
    DataExportRequest,
    DataDeletionRequest,
    Team,
    TeamMember,
    TeamInvitation,
)

User = get_user_model()


def create_user(
    email='talent@example.com',
    password='TestPass123!',
    role='TALENT',
    full_name='Test User',
    is_verified=True,
    **kwargs,
):
    """Create a test user."""
    user = User.objects.create_user(
        email=email,
        password=password,
        role=role,
        full_name=full_name,
        is_verified=is_verified,
        **kwargs,
    )
    return user


def create_admin_user(email='admin@example.com', **kwargs):
    """Create an admin user."""
    return create_user(
        email=email,
        role='ADMIN',
        full_name='Admin User',
        is_staff=True,
        is_superuser=True,
        **kwargs,
    )


def create_company_user(
    email='company@example.com',
    company_name='Acme Corp',
    subscription_tier='professional',
    **kwargs,
):
    """Create a company user with a CompanyProfile."""
    user = create_user(email=email, role='COMPANY', full_name='Company Owner', **kwargs)
    CompanyProfile.objects.create(
        user=user,
        legal_name=company_name,
        industry='Technology',
        subscription_tier=subscription_tier,
    )
    return user


def create_talent_user(email='talent@example.com', **kwargs):
    """Create a talent user with a TalentProfile."""
    user = create_user(email=email, role='TALENT', full_name='Talent User', **kwargs)
    TalentProfile.objects.create(
        user=user,
        bio='Test bio',
        location='Test City',
        skills=['Python', 'Django'],
    )
    return user


def create_policy(
    policy_type='tos',
    version='1.0.0',
    is_active=True,
    requires_re_consent=False,
    **kwargs,
):
    """Create a PolicyVersion."""
    return PolicyVersion.objects.create(
        policy_type=policy_type,
        version=version,
        title=f'Test {policy_type} Policy v{version}',
        summary='Test summary',
        content='# Test Policy\n\nThis is a test policy.',
        effective_date=timezone.now().date(),
        is_active=is_active,
        requires_re_consent=requires_re_consent,
        **kwargs,
    )


def create_team(company_user, name='Test Team'):
    """Create a team with the company user as OWNER."""
    team = Team.objects.create(
        company=company_user.company_profile,
        name=name,
    )
    TeamMember.objects.create(
        team=team,
        user=company_user,
        role=TeamMember.Role.OWNER,
        invited_by=company_user,
    )
    return team


def create_team_invitation(team, email='invitee@example.com', invited_by=None, role='recruiter'):
    """Create a team invitation."""
    return TeamInvitation.objects.create(
        team=team,
        email=email,
        role=role,
        invited_by=invited_by or team.members.filter(role='owner').first().user,
    )


def grant_consent_for_user(user, policy):
    """Create a consent record for a user on a policy."""
    return ConsentRecord.objects.create(
        user=user,
        policy_version=policy,
        ip_address='127.0.0.1',
        user_agent='TestAgent/1.0',
    )
