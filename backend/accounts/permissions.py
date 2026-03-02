"""
accounts/permissions.py
Shared permission classes for email verification enforcement.
"""
from rest_framework import permissions


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
