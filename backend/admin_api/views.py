"""
admin_api/views.py
Admin-only API views for platform oversight.
"""
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.db.models import Count, Sum
from django.contrib.auth import get_user_model
from jobs.models import JobPost, Application
from jobs.serializers import JobPostSerializer, ApplicationSerializer
from accounts.serializers import UserMeSerializer

User = get_user_model()


class IsAdminUser(permissions.BasePermission):
    """Admin API: require authenticated user with role ADMIN and is_staff (aligned with Django admin)."""
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role == 'ADMIN'
            and getattr(request.user, 'is_staff', False)
        )


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def public_stats(request):
    """GET /api/v1/admin-api/public-stats/ — Public platform counts (no auth required)."""
    return Response({
        'total_users': User.objects.filter(is_active=True).count(),
        'total_jobs': JobPost.objects.filter(status='open').count(),
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def platform_stats(request):
    """GET /api/admin/stats/ — High-level platform metrics."""
    total_users = User.objects.filter(is_active=True).count()
    talent_count = User.objects.filter(role='TALENT', is_active=True).count()
    company_count = User.objects.filter(role='COMPANY', is_active=True).count()
    job_count = JobPost.objects.filter(status='open').count()
    application_count = Application.objects.count()
    return Response({
        'talent_count': talent_count,
        'company_count': company_count,
        'open_jobs': job_count,
        'total_applications': application_count,
        # Additional fields consumed by About page and future dashboards
        'total_users': total_users,
        'total_jobs': job_count,
    })


class AdminUserListView(generics.ListAPIView):
    """GET /api/admin/users/ — List all users (paginated)."""
    serializer_class = UserMeSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        qs = User.objects.all().order_by('-date_joined')
        role = self.request.query_params.get('role')
        search = self.request.query_params.get('search')
        if role:
            qs = qs.filter(role=role)
        if search:
            from django.db.models import Q
            qs = qs.filter(Q(email__icontains=search) | Q(full_name__icontains=search))
        return qs


@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def verify_user(request, pk):
    """PATCH /api/admin/users/<pk>/verify/ — Mark user as verified."""
    try:
        user = User.objects.get(pk=pk)
        user.is_verified = True
        user.save(update_fields=['is_verified'])
        return Response({'message': f'{user.email} verified successfully.'})
    except User.DoesNotExist:
        return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['DELETE'])
@permission_classes([IsAdminUser])
def deactivate_user(request, pk):
    """DELETE /api/admin/users/<pk>/ — Deactivate a user account."""
    try:
        user = User.objects.get(pk=pk)
        user.is_active = False
        user.save(update_fields=['is_active'])
        return Response({'message': f'{user.email} deactivated.'})
    except User.DoesNotExist:
        return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)


class AdminJobListView(generics.ListAPIView):
    """GET /api/admin/jobs/ — List all jobs across all companies."""
    serializer_class = JobPostSerializer
    permission_classes = [IsAdminUser]
    queryset = JobPost.objects.all().select_related('company__company_profile').order_by('-created_at')


@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def toggle_job_status(request, pk):
    """PATCH /api/admin/jobs/<pk>/toggle/ — Open or close a job listing."""
    try:
        job = JobPost.objects.get(pk=pk)
        job.status = 'closed' if job.status == 'open' else 'open'
        job.save(update_fields=['status'])
        return Response({'status': job.status})
    except JobPost.DoesNotExist:
        return Response({'error': 'Job not found.'}, status=status.HTTP_404_NOT_FOUND)


class AdminApplicationListView(generics.ListAPIView):
    """GET /api/admin/applications/ — All applications platform-wide."""
    serializer_class = ApplicationSerializer
    permission_classes = [IsAdminUser]
    queryset = Application.objects.all().select_related(
        'applicant', 'job__company__company_profile'
    ).order_by('-applied_at')
