"""
intelligence/permissions.py
Custom DRF permissions for Intelligence API endpoints.

Follows the same pattern as ``accounts.permissions.IsEmailVerified``:
  - descriptive ``message`` shown on 403
  - SAFE_METHODS exemption where appropriate (browse-first UX)
"""

from rest_framework import permissions


class IsTalent(permissions.BasePermission):
    """
    Only users with the TALENT role may access the endpoint.
    Read operations (GET, HEAD, OPTIONS) are still allowed so the UI
    can prefetch data before the user fully lands on a page.
    """

    message = 'This feature is only available to talent (job-seeker) accounts.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return getattr(request.user, 'role', None) == 'TALENT'


class IsCompany(permissions.BasePermission):
    """Only users with the COMPANY role may access the endpoint."""

    message = 'This feature is only available to company accounts.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return getattr(request.user, 'role', None) == 'COMPANY'


class IsCompanyOrAdmin(permissions.BasePermission):
    """
    Company or admin users may access the endpoint.
    Used for analytics dashboards where admins can view any company's data.
    """

    message = 'This feature requires a company or admin account.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return getattr(request.user, 'role', None) in ('COMPANY', 'ADMIN')


class IsAdminUser(permissions.BasePermission):
    """Only admin users may access the endpoint (platform analytics, etc.)."""

    message = 'This feature requires admin privileges.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return getattr(request.user, 'role', None) == 'ADMIN'


class IsTalentWriteOnly(permissions.BasePermission):
    """
    Talent role is required for write operations (POST, PUT, PATCH, DELETE).
    Safe methods (GET, HEAD, OPTIONS) are allowed for any authenticated user
    so the UI can render placeholders / loading states.
    """

    message = 'Only talent accounts can perform this action.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return getattr(request.user, 'role', None) == 'TALENT'
