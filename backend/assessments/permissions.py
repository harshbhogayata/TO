"""
assessments/permissions.py
Permission classes for the assessment system.
"""
from rest_framework import permissions


class IsAssessmentOwnerOrAdmin(permissions.BasePermission):
    """
    Allows access to assessment owners (company that created it) or admins.
    """
    message = 'You do not have permission to manage this assessment.'

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        # Assessment-level object
        assessment = getattr(obj, 'assessment', obj)
        if hasattr(assessment, 'owner_company') and assessment.owner_company:
            return (
                hasattr(request.user, 'company_profile') and
                request.user.company_profile == assessment.owner_company
            )
        # Platform assessments: only admins
        return request.user.is_staff


class IsAttemptOwner(permissions.BasePermission):
    """
    Ensures only the user who started the attempt can interact with it.
    """
    message = 'You can only access your own assessment attempts.'

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        return obj.user == request.user


class CanViewAttemptResults(permissions.BasePermission):
    """
    Results are viewable by:
        1. The user who took the assessment
        2. The company that owns the assessment (hiring context)
        3. Admins
    """
    message = 'You do not have permission to view these results.'

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        # Attempt owner
        if obj.user == request.user:
            return True
        # Company owner
        assessment = obj.assessment
        if hasattr(assessment, 'owner_company') and assessment.owner_company:
            return (
                hasattr(request.user, 'company_profile') and
                request.user.company_profile == assessment.owner_company
            )
        return False


class IsQuestionBankOwner(permissions.BasePermission):
    """
    Bank owners or admins can manage questions in their banks.
    """
    message = 'You do not have permission to manage this question bank.'

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        bank = getattr(obj, 'bank', obj)
        if hasattr(bank, 'owner_company') and bank.owner_company:
            return (
                hasattr(request.user, 'company_profile') and
                request.user.company_profile == bank.owner_company
            )
        return False
