"""
accounts/permissions.py
Shared permission classes for role enforcement and email verification.
"""
from rest_framework import permissions


class IsCompanyUser(permissions.BasePermission):
    """Only allow users with COMPANY role."""
    message = 'Access restricted to verified company accounts.'

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role == 'COMPANY'
        )


class IsTalentUser(permissions.BasePermission):
    """Only allow users with TALENT role."""
    message = 'Access restricted to talent accounts.'

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role == 'TALENT'
        )


class IsAdminUser(permissions.BasePermission):
    """Only allow users with ADMIN role."""
    message = 'Access restricted to admin accounts.'

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role == 'ADMIN'
        )


class IsEmailVerified(permissions.BasePermission):
    """
    Denies access to users who haven't verified their email.
    Apply to sensitive write operations (apply to job, send message, etc.).
    Read operations are still allowed so users can browse.
    """
    message = 'Please verify your email address before performing this action.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        # Allow GET/HEAD/OPTIONS without verification (browsing is fine)
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_verified
