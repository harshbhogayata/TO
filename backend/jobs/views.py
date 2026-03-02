"""
jobs/views.py
Job board API views for TalentOrbit.
"""
from rest_framework import generics, permissions, status, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.core.cache import cache
from django.db.models import F, Exists, OuterRef, Subquery, Count
from django.utils import timezone

from .models import JobPost, Application, SavedJob
from .serializers import (
    JobPostSerializer, JobPostWriteSerializer,
    ApplicationSerializer, ApplicationStatusSerializer,
    SavedJobSerializer,
)
from .permissions import IsCompanyOwner, IsCompanyUser, IsTalentUser
from accounts.permissions import IsEmailVerified


def _annotate_user_relations(qs, user):
    """Annotate a JobPost queryset with per-user saved/applied state and application count to avoid N+1 queries."""
    qs = qs.annotate(_application_count=Count('applications'))
    if not user or not user.is_authenticated:
        return qs
    return qs.annotate(
        _is_saved=Exists(SavedJob.objects.filter(user=user, job_id=OuterRef('pk'))),
        _saved_record_id=Subquery(
            SavedJob.objects.filter(user=user, job_id=OuterRef('pk')).values('pk')[:1]
        ),
        _has_applied=Exists(Application.objects.filter(applicant=user, job_id=OuterRef('pk'))),
    )


def _should_count_view(job_id, request):
    """Deduplicate view counts: one increment per IP per hour."""
    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
    if ',' in ip:
        ip = ip.split(',')[0].strip()
    cache_key = f'job_view:{job_id}:{ip}'
    if cache.get(cache_key):
        return False
    cache.set(cache_key, 1, 3600)  # 1-hour TTL
    return True


class JobPostListView(generics.ListAPIView):
    """
    GET /api/jobs/ — Public list of all open job posts.
    Supports filtering by work_mode, job_type and text search on title/location.
    """
    queryset = JobPost.objects.filter(status='open').select_related('company__company_profile')
    serializer_class = JobPostSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'location', 'skills_required', 'description']
    ordering_fields = ['created_at', 'salary_max']
    ordering = ['-created_at']

    def get_queryset(self):
        qs = super().get_queryset()
        work_mode = self.request.query_params.get('work_mode')
        job_type = self.request.query_params.get('job_type')
        skill = self.request.query_params.get('skill')
        if work_mode:
            qs = qs.filter(work_mode=work_mode)
        if job_type:
            qs = qs.filter(job_type=job_type)
        if skill:
            qs = qs.filter(skills_required__icontains=skill)
        return _annotate_user_relations(qs, self.request.user)


class JobPostDetailView(generics.RetrieveAPIView):
    """GET /api/jobs/<id>/ — Retrieve a single job post."""
    queryset = JobPost.objects.select_related('company__company_profile')
    serializer_class = JobPostSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return _annotate_user_relations(super().get_queryset(), self.request.user)

    def get(self, request, *args, **kwargs):
        instance = self.get_object()
        if _should_count_view(instance.pk, request):
            JobPost.objects.filter(pk=instance.pk).update(views_count=F('views_count') + 1)
            instance.refresh_from_db()
        serializer = self.get_serializer(instance, context={'request': request})
        return Response(serializer.data)


class CompanyJobsView(generics.ListCreateAPIView):
    """
    GET  /api/jobs/mine/   — Company sees their own posts.
    POST /api/jobs/mine/   — Company creates a new post.
    """
    permission_classes = [permissions.IsAuthenticated, IsCompanyUser, IsEmailVerified]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return JobPostWriteSerializer
        return JobPostSerializer

    def get_queryset(self):
        qs = JobPost.objects.filter(company=self.request.user).select_related('company__company_profile')
        return _annotate_user_relations(qs, self.request.user)


class CompanyJobDetailView(generics.RetrieveUpdateDestroyAPIView):
    """PUT/PATCH/DELETE /api/jobs/mine/<id>/ — Company manages one of their posts."""
    permission_classes = [permissions.IsAuthenticated, IsCompanyOwner, IsEmailVerified]

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return JobPostWriteSerializer
        return JobPostSerializer

    def get_queryset(self):
        return JobPost.objects.filter(company=self.request.user)


class ApplyView(generics.CreateAPIView):
    """POST /api/jobs/<id>/apply/ — Talent applies to a job."""
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated, IsTalentUser, IsEmailVerified]

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError
        job_id = self.kwargs.get('pk')
        job = generics.get_object_or_404(JobPost, pk=job_id, status='open')
        if job.application_deadline and job.application_deadline < timezone.now().date():
            raise ValidationError({'detail': 'The application deadline for this position has passed.'})
        serializer.save(applicant=self.request.user, job=job)


class MyApplicationsView(generics.ListAPIView):
    """GET /api/applications/ — Talent sees all their submitted applications."""
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated, IsTalentUser]

    def get_queryset(self):
        return Application.objects.filter(applicant=self.request.user).select_related('job__company__company_profile')


class CompanyApplicationsView(generics.ListAPIView):
    """GET /api/jobs/<id>/applications/ — Company sees all applicants for a post."""
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated, IsCompanyUser]

    def get_queryset(self):
        job_id = self.kwargs.get('pk')
        return Application.objects.filter(
            job_id=job_id,
            job__company=self.request.user
        ).select_related('applicant__talent_profile')


class UpdateApplicationStatusView(generics.UpdateAPIView):
    """PATCH /api/applications/<id>/status/ — Company updates application status."""
    serializer_class = ApplicationStatusSerializer
    permission_classes = [permissions.IsAuthenticated, IsCompanyUser]
    http_method_names = ['patch']

    def get_queryset(self):
        return Application.objects.filter(job__company=self.request.user)


class WithdrawApplicationView(generics.DestroyAPIView):
    """DELETE /api/applications/<id>/ — Talent withdraws their own application."""
    permission_classes = [permissions.IsAuthenticated, IsTalentUser]

    def get_queryset(self):
        return Application.objects.filter(applicant=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status in [Application.Status.REJECTED, Application.Status.OFFERED, Application.Status.WITHDRAWN]:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'detail': 'Cannot withdraw a finalized or already withdrawn application.'})
        instance.status = Application.Status.WITHDRAWN
        instance.save(update_fields=['status'])
        return Response({'message': 'Application withdrawn.'}, status=status.HTTP_200_OK)


class SavedJobsView(generics.ListCreateAPIView):
    """GET/POST /api/jobs/saved/ — Talent saves or views saved jobs."""
    serializer_class = SavedJobSerializer
    permission_classes = [permissions.IsAuthenticated, IsTalentUser, IsEmailVerified]

    def get_queryset(self):
        return SavedJob.objects.filter(user=self.request.user).select_related('job__company__company_profile')


class UnsaveJobView(generics.DestroyAPIView):
    """DELETE /api/jobs/saved/<id>/ — Talent removes a saved job."""
    permission_classes = [permissions.IsAuthenticated, IsTalentUser]

    def get_queryset(self):
        return SavedJob.objects.filter(user=self.request.user)
