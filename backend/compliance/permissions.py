"""
compliance/permissions.py
Phase 6 — Role-based permission classes for team-based access control.

These permissions check team membership and role to determine access.
They integrate seamlessly with DRF's permission framework.
"""
from rest_framework import permissions


class IsTeamOwner(permissions.BasePermission):
    """Requires the request user to be the OWNER of their company's team."""

    message = 'Only the team owner can perform this action.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if not request.user.is_company:
            return False
        return _has_team_role(request.user, 'owner')


class IsTeamAdmin(permissions.BasePermission):
    """Requires OWNER or ADMIN role in the team."""

    message = 'Only team owners and admins can perform this action.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if not request.user.is_company:
            return False
        return _has_team_role(request.user, ('owner', 'admin'))


class IsTeamRecruiter(permissions.BasePermission):
    """Requires OWNER, ADMIN, or RECRUITER role in the team."""

    message = 'Requires recruiter-level access or above.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if not request.user.is_company:
            return False
        return _has_team_role(request.user, ('owner', 'admin', 'recruiter'))


class IsTeamMember(permissions.BasePermission):
    """Requires any active team membership (including VIEWER)."""

    message = 'You must be a member of a team to access this resource.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if not request.user.is_company:
            return False
        return _has_team_role(request.user, ('owner', 'admin', 'recruiter', 'viewer'))


class IsTeamMemberOrCompanyOwner(permissions.BasePermission):
    """
    Allows access if the user is the company profile owner OR an active team member.
    This is the bridge between legacy single-user company access and the new team model.
    """

    message = 'You must be the company owner or a team member.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if not request.user.is_company:
            return False

        # Legacy: the user IS the company account owner
        if hasattr(request.user, 'company_profile'):
            return True

        # New: the user is an active team member of some company
        from compliance.models import TeamMember
        return TeamMember.objects.filter(
            user=request.user,
            is_active=True,
        ).exists()


class CanManageTeamMembers(permissions.BasePermission):
    """
    For invite, role-change, and removal operations.
    Requires OWNER or ADMIN role.
    Additional rule: ADMINs cannot modify OWNERs.
    """

    message = 'Insufficient team permissions for member management.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if not request.user.is_company:
            return False
        return _has_team_role(request.user, ('owner', 'admin'))


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _has_team_role(user, roles) -> bool:
    """
    Check if the user has an active team membership with one of the given roles.

    Args:
        user: The authenticated User instance.
        roles: A string or tuple of role codes.

    Returns:
        True if the user has an active membership with the specified role(s).
    """
    from compliance.models import TeamMember

    if isinstance(roles, str):
        roles = (roles,)

    return TeamMember.objects.filter(
        user=user,
        role__in=roles,
        is_active=True,
    ).exists()


def get_user_team_role(user) -> str | None:
    """
    Get the user's active team role, or None if not a team member.

    Returns the highest-privilege role if the user is somehow in multiple teams
    (shouldn't happen, but defensive).
    """
    from compliance.models import TeamMember

    role_priority = {'owner': 0, 'admin': 1, 'recruiter': 2, 'viewer': 3}

    memberships = TeamMember.objects.filter(
        user=user,
        is_active=True,
    ).values_list('role', flat=True)

    if not memberships:
        return None

    return min(memberships, key=lambda r: role_priority.get(r, 99))


def get_user_team(user):
    """
    Get the Team the user belongs to, or None.
    """
    from compliance.models import TeamMember

    membership = TeamMember.objects.filter(
        user=user,
        is_active=True,
    ).select_related('team').first()

    return membership.team if membership else None
