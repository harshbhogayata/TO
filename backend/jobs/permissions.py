"""
jobs/permissions.py
Custom DRF permissions for the job board.
"""
from rest_framework import permissions
from .models import JobPost


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


class IsCompanyOwner(permissions.BasePermission):
    """
    Object-level permission: only the company that created
    this job post can modify or delete it.
    """
    message = 'You do not own this job post.'

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'COMPANY'

    def has_object_permission(self, request, view, obj):
        return obj.company == request.user
