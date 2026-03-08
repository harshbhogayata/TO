"""
intelligence/views.py
API views for the Intelligence layer.

Endpoints
â”€â”€â”€â”€â”€â”€â”€â”€â”€
  Recommendations  â€” personalised job/talent recommendations
  Interactions     â€” record user-job interactions
  Resume Parser    â€” NLP resume parsing + apply
  Skill Taxonomy   â€” browse / search / suggest skills
  Company Analytics â€” hiring funnel, time-to-hire, sources, talent pool
  Platform Analytics â€” admin-only platform-wide metrics
  Experiments      â€” feature flags + event tracking

Enterprise quality patterns applied:
  - Throttle classes on every endpoint (matching accounts/views.py)
  - IsEmailVerified on write endpoints (matching jobs/views.py)
  - Structured logger per module
  - Graceful exception handling with 503 fallback
  - Query parameter validation
  - select_related / prefetch_related on all querysets
"""
import csv
import io
import json
import logging

from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from accounts.models import TalentProfile
from accounts.permissions import IsEmailVerified
from jobs.models import JobPost

from .models import (
    DailyPlatformMetrics,
    HiringFunnelSnapshot,
    ParsedResume,
    PlatformBenchmark,
    SkillTaxonomy,
    UserInteraction,
    RecommendationLog,
)
from .permissions import IsAdminUser, IsCompany, IsCompanyOrAdmin, IsTalent
from .serializers import (

    CompanyAnalyticsExportSerializer,
    DailyPlatformMetricsSerializer,
    ExperimentTrackSerializer,
    FeatureFlagsSerializer,
    HiringFunnelSerializer,
    JobPerformanceSerializer,
    MatchScoreResponseSerializer,
    OverviewMetricsSerializer,
    ParsedResumeSerializer,
    normalise_resume_payload,
    PlatformBenchmarkSerializer,
    PlatformEngagementSerializer,
    PlatformGrowthSerializer,
    RecommendationResponseSerializer,
    ResumeApplySerializer,
    ResumeUploadSerializer,
    SkillSuggestionSerializer,
    SkillTaxonomySerializer,
    SourceAttributionSerializer,
    TalentPoolSerializer,
    TimeToHireSerializer,
    UserInteractionSerializer,
)

from .throttling import (
    AuthenticatedAIResumeParseThrottle,
    AuthenticatedResumeParseThrottle,
    PublicAIResumeParseThrottle,
    PublicResumeParseThrottle,
)

logger = logging.getLogger(__name__)


def _parse_int_param(request, name: str, default: int, max_val: int | None = None) -> int:
    """
    Safely parse an integer query parameter, raising 400 on invalid input.
    Returns the clamped value.
    """
    raw = request.query_params.get(name, default)
    try:
        value = int(raw)
    except (ValueError, TypeError):
        from rest_framework.exceptions import ValidationError
        raise ValidationError({name: f'Must be an integer.'})
    if max_val is not None:
        value = min(value, max_val)
    return max(1, value)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Recommendations
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

class RecommendedJobsView(APIView):
    """
    GET /api/v1/intelligence/recommendations/jobs/

    Returns personalised job recommendations for the authenticated talent user.
    Supports ``?limit=N`` (default 20, max 50).
    """
    permission_classes = [permissions.IsAuthenticated, IsTalent]
    throttle_classes = [UserRateThrottle]

    def get(self, request):
        from .constants import DEFAULT_WEIGHTS
        from .engine.cache import get_cached_recommendations, set_cached_recommendations
        from .engine.hybrid import compute_recommendations

        try:
            limit = min(int(request.query_params.get('limit', 20)), 50)
        except (ValueError, TypeError):
            return Response(
                {'detail': 'Parameter "limit" must be an integer.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = request.user

        # â”€â”€ Check cache â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        cached = get_cached_recommendations(user.id)
        if cached is not None:
            results = cached[:limit]
            job_ids = [r['job_id'] for r in results]
            jobs_map = {
                j.id: j
                for j in JobPost.objects.filter(id__in=job_ids)
                    .select_related('company__company_profile')
            }
            items = []
            for r in results:
                job = jobs_map.get(r['job_id'])
                if not job:
                    continue
                items.append({
                    'job': job,
                    'final_score': r['final_score'],
                    'content_score': r.get('content_score', 0),
                    'collaborative_score': r.get('collaborative_score', 0),
                    'popularity_score': r.get('popularity_score', 0),
                    'freshness_score': r.get('freshness_score', 0),
                    'explanation': r.get('explanation', ''),
                    'breakdown': r.get('breakdown', {}),
                })

            serializer = RecommendationResponseSerializer({
                'recommendations': items,
                'algorithm_version': 'hybrid-v1',
                'latency_ms': 0,
                'cache_hit': True,
                'weights': DEFAULT_WEIGHTS,
            }, context={'request': request})
            return Response(serializer.data)

        # â”€â”€ Compute fresh recommendations â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        try:
            results, latency_ms = compute_recommendations(user, limit=limit)
        except Exception:
            logger.exception('Recommendation computation failed for user %s', user.id)
            return Response(
                {'detail': 'Unable to generate recommendations at this time.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Cache serialisable form
        cacheable = [
            {
                'job_id': r.job_id,
                'final_score': r.final_score,
                'content_score': r.content_score,
                'collaborative_score': r.collaborative_score,
                'popularity_score': r.popularity_score,
                'freshness_score': r.freshness_score,
                'explanation': r.explanation,
                'breakdown': r.breakdown,
            }
            for r in results
        ]
        set_cached_recommendations(user.id, cacheable)

        # Audit log
        RecommendationLog.objects.create(
            user=user,
            recommended_jobs=[r.job_id for r in results],
            algorithm_version='hybrid-v1',
            weights_used=DEFAULT_WEIGHTS,
            latency_ms=latency_ms,
            cache_hit=False,
        )

        # Hydrate job objects for serialisation
        job_ids = [r.job_id for r in results]
        jobs_map = {
            j.id: j
            for j in JobPost.objects.filter(id__in=job_ids)
                .select_related('company__company_profile')
        }
        items = []
        for r in results:
            job = jobs_map.get(r.job_id)
            if not job:
                continue
            items.append({
                'job': job,
                'final_score': r.final_score,
                'content_score': r.content_score,
                'collaborative_score': r.collaborative_score,
                'popularity_score': r.popularity_score,
                'freshness_score': r.freshness_score,
                'explanation': r.explanation,
                'breakdown': r.breakdown,
            })

        serializer = RecommendationResponseSerializer({
            'recommendations': items,
            'algorithm_version': 'hybrid-v1',
            'latency_ms': latency_ms,
            'cache_hit': False,
            'weights': DEFAULT_WEIGHTS,
        }, context={'request': request})
        return Response(serializer.data)


class MatchScoreView(APIView):
    """
    GET /api/v1/intelligence/match-score/?job=<id>

    Returns a detailed match score between the authenticated talent and
    a specific job posting.
    """
    permission_classes = [permissions.IsAuthenticated, IsTalent]
    throttle_classes = [UserRateThrottle]

    def get(self, request):
        job_id = request.query_params.get('job')
        if not job_id:
            return Response(
                {'detail': 'Query parameter "job" is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            job = JobPost.objects.select_related('company__company_profile').get(pk=job_id)
        except JobPost.DoesNotExist:
            return Response(
                {'detail': 'Job not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        from .engine.hybrid import compute_match_score

        try:
            result = compute_match_score(request.user, job)
        except Exception:
            logger.exception('Match score computation failed')
            return Response(
                {'detail': 'Unable to compute match score.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        serializer = MatchScoreResponseSerializer(result)
        return Response(serializer.data)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Interactions
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

class RecordInteractionView(generics.CreateAPIView):
    """
    POST /api/v1/intelligence/interactions/

    Record a user-job interaction event (view, click, save, apply, unsave).
    Used to train the collaborative filtering model.
    """
    serializer_class = UserInteractionSerializer
    permission_classes = [permissions.IsAuthenticated, IsTalent, IsEmailVerified]
    throttle_classes = [UserRateThrottle]


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Resume Parser
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

class ParseResumeView(APIView):
    """
    POST /api/v1/intelligence/parse-resume/
    GET  /api/v1/intelligence/parse-resume/

    POST - Upload and parse a resume file. Returns extracted data.
    GET  - Return most recent parsed resume for the current user.
    """
    permission_classes = [permissions.IsAuthenticated, IsTalent, IsEmailVerified]
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [AuthenticatedResumeParseThrottle]

    def get(self, request):
        try:
            parsed = ParsedResume.objects.get(user=request.user)
        except ParsedResume.DoesNotExist:
            return Response(
                {'detail': 'No parsed resume found. Upload one first.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(normalise_resume_payload(parsed))

    def post(self, request):
        upload_serializer = ResumeUploadSerializer(data=request.data)
        upload_serializer.is_valid(raise_exception=True)

        resume_file = upload_serializer.validated_data['resume']

        from .nlp.parser import parse_resume

        try:
            parsed = parse_resume(resume_file, user=request.user)
        except Exception:
            logger.exception('Resume parsing failed for user %s', request.user.id)
            return Response(
                {'detail': 'Resume parsing failed. Please try a different file.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        instance = ParsedResume.objects.filter(user=request.user).first()
        if instance:
            payload = normalise_resume_payload(
                instance,
                cached=parsed.get('cached', False),
            )
        else:
            payload = normalise_resume_payload(parsed)

        return Response(payload, status=status.HTTP_201_CREATED)


class ParseResumeUnauthenticatedView(APIView):
    """
    POST /api/v1/intelligence/parse-resume-public/

    Unauthenticated resume parsing for user registration.
    Returns extracted data without saving to database.
    """
    permission_classes = [permissions.AllowAny]
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [PublicResumeParseThrottle]

    def post(self, request):
        upload_serializer = ResumeUploadSerializer(data=request.data)
        upload_serializer.is_valid(raise_exception=True)

        resume_file = upload_serializer.validated_data['resume']

        from .nlp.parser import parse_resume

        try:
            parsed = parse_resume(resume_file, user=None)
            return Response(normalise_resume_payload(parsed), status=status.HTTP_200_OK)
        except Exception:
            logger.exception('Resume parsing failed for unauthenticated user')
            return Response(
                {'detail': 'Resume parsing failed. Please try a different file.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ApplyParsedResumeView(APIView):
    """
    POST /api/v1/intelligence/parse-resume/apply/

    Apply selected parsed data (skills, bio) to the talent profile.
    """
    permission_classes = [permissions.IsAuthenticated, IsTalent, IsEmailVerified]
    throttle_classes = [UserRateThrottle]

    def post(self, request):
        serializer = ResumeApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            profile = request.user.talent_profile
        except TalentProfile.DoesNotExist:
            return Response(
                {'detail': 'Talent profile not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        skills = serializer.validated_data.get('skills')
        bio = serializer.validated_data.get('bio')

        updated_fields = []
        if skills is not None:
            profile.skills = skills
            updated_fields.append('skills')
        if bio is not None:
            profile.bio = bio
            updated_fields.append('bio')

        if updated_fields:
            profile.save(update_fields=updated_fields)

        # Track the event â€” track_resume_apply(user_id, fields_applied)
        try:
            from .experiments.tracking import track_resume_apply
            track_resume_apply(request.user.id, fields_applied=updated_fields)
        except Exception:
            logger.debug('Failed to track resume apply event', exc_info=True)

        return Response({'detail': 'Profile updated successfully.'})


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Skill Taxonomy
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

class SkillTaxonomyListView(generics.ListAPIView):
    """
    GET /api/v1/intelligence/skills/taxonomy/

    Browse the full skill taxonomy. Supports ``?category=&search=&parent=``.
    """
    serializer_class = SkillTaxonomySerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def get_queryset(self):
        qs = SkillTaxonomy.objects.select_related('parent').prefetch_related(
            'children', 'related_skills',
        ).order_by('category', 'canonical_name')

        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category__iexact=category)

        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(canonical_name__icontains=search) |
                Q(aliases__icontains=search)
            )

        parent = self.request.query_params.get('parent')
        if parent == 'root':
            qs = qs.filter(parent__isnull=True)
        elif parent:
            qs = qs.filter(parent_id=parent)

        return qs


class SkillSuggestionView(APIView):
    """
    GET /api/v1/intelligence/skills/suggestions/?q=<query>

    Fast skill autocomplete for typeahead inputs.  Returns top 10 matches.
    """
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def get(self, request):
        q = request.query_params.get('q', '').strip()
        if len(q) < 2:
            return Response([])

        results = SkillTaxonomy.objects.filter(
            Q(canonical_name__icontains=q) | Q(aliases__icontains=q)
        ).values('id', 'canonical_name', 'category').order_by('-usage_count')[:10]

        data = [
            {'id': r['id'], 'name': r['canonical_name'], 'category': r['category']}
            for r in results
        ]
        return Response(data)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Company Analytics
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

class CompanyOverviewView(APIView):
    """GET /api/v1/intelligence/analytics/overview/"""
    permission_classes = [permissions.IsAuthenticated, IsCompanyOrAdmin]
    throttle_classes = [UserRateThrottle]

    def get(self, request):
        from .analytics.aggregators import compute_overview_metrics

        try:
            data = compute_overview_metrics(request.user)
        except Exception:
            logger.exception('Overview metrics failed for user %s', request.user.id)
            return Response(
                {'detail': 'Unable to compute analytics at this time.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        serializer = OverviewMetricsSerializer(data)
        return Response(serializer.data)


class CompanyFunnelView(APIView):
    """
    GET /api/v1/intelligence/analytics/funnel/?job=<id>

    Hiring funnel.  Optional ``?job=`` to scope to a single posting.
    """
    permission_classes = [permissions.IsAuthenticated, IsCompanyOrAdmin]
    throttle_classes = [UserRateThrottle]

    def get(self, request):
        from .analytics.aggregators import compute_funnel_for_company

        job_id = request.query_params.get('job')
        try:
            data = compute_funnel_for_company(request.user, job_id=job_id)
        except Exception:
            logger.exception('Funnel computation failed for user %s', request.user.id)
            return Response(
                {'detail': 'Unable to compute funnel analytics.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        # compute_funnel_for_company returns a single dict, NOT a list
        serializer = HiringFunnelSerializer(data)
        return Response(serializer.data)


class CompanyTimeToHireView(APIView):
    """GET /api/v1/intelligence/analytics/time-to-hire/"""
    permission_classes = [permissions.IsAuthenticated, IsCompanyOrAdmin]
    throttle_classes = [UserRateThrottle]

    def get(self, request):
        from .analytics.aggregators import compute_time_to_hire

        try:
            data = compute_time_to_hire(request.user)
        except Exception:
            logger.exception('Time-to-hire computation failed for user %s', request.user.id)
            return Response(
                {'detail': 'Unable to compute time-to-hire analytics.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        serializer = TimeToHireSerializer(data, many=True)
        return Response(serializer.data)


class CompanySourcesView(APIView):
    """GET /api/v1/intelligence/analytics/sources/"""
    permission_classes = [permissions.IsAuthenticated, IsCompanyOrAdmin]
    throttle_classes = [UserRateThrottle]

    def get(self, request):
        from .analytics.aggregators import compute_source_attribution

        try:
            data = compute_source_attribution(request.user)
        except Exception:
            logger.exception('Source attribution failed for user %s', request.user.id)
            return Response(
                {'detail': 'Unable to compute source analytics.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        # compute_source_attribution returns {sources: [...], top_queries: [...]}
        serializer = SourceAttributionSerializer(data)
        return Response(serializer.data)


class CompanyTalentPoolView(APIView):
    """GET /api/v1/intelligence/analytics/talent-pool/"""
    permission_classes = [permissions.IsAuthenticated, IsCompanyOrAdmin]
    throttle_classes = [UserRateThrottle]

    def get(self, request):
        from .analytics.aggregators import compute_talent_pool

        try:
            data = compute_talent_pool(request.user)
        except Exception:
            logger.exception('Talent pool computation failed for user %s', request.user.id)
            return Response(
                {'detail': 'Unable to compute talent pool analytics.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        serializer = TalentPoolSerializer(data)
        return Response(serializer.data)


class CompanyBenchmarksView(APIView):
    """GET /api/v1/intelligence/analytics/benchmarks/"""
    permission_classes = [permissions.IsAuthenticated, IsCompanyOrAdmin]
    throttle_classes = [UserRateThrottle]

    def get(self, request):
        from .analytics.benchmarks import get_benchmarks_for_company

        try:
            data = get_benchmarks_for_company(request.user)
        except Exception:
            logger.exception('Benchmarks computation failed for user %s', request.user.id)
            return Response(
                {'detail': 'Unable to compute benchmarks.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(data)


class CompanyJobPerformanceView(APIView):
    """GET /api/v1/intelligence/analytics/jobs/"""
    permission_classes = [permissions.IsAuthenticated, IsCompanyOrAdmin]
    throttle_classes = [UserRateThrottle]

    def get(self, request):
        from .analytics.materialized import get_job_performance_table

        try:
            data = get_job_performance_table(request.user)
        except Exception:
            logger.exception('Job performance computation failed for user %s', request.user.id)
            return Response(
                {'detail': 'Unable to compute job performance data.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        serializer = JobPerformanceSerializer(data, many=True)
        return Response(serializer.data)


class CompanyAnalyticsExportView(APIView):
    """
    GET /api/v1/intelligence/analytics/export/?format=csv|json&date_from=&date_to=

    Export company analytics data as CSV or JSON attachment.
    """
    permission_classes = [permissions.IsAuthenticated, IsCompanyOrAdmin]
    throttle_classes = [UserRateThrottle]

    def get(self, request):
        from datetime import date as date_type

        fmt = request.query_params.get('format', 'json')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')

        # Validate date parameters
        for param_name, param_val in [('date_from', date_from), ('date_to', date_to)]:
            if param_val:
                try:
                    date_type.fromisoformat(param_val)
                except (ValueError, TypeError):
                    return Response(
                        {'detail': f'"{param_name}" must be a valid date (YYYY-MM-DD).'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        qs = HiringFunnelSnapshot.objects.filter(company=request.user)
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)
        qs = qs.order_by('-date')[:365]

        if fmt == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = (
                f'attachment; filename="analytics_{timezone.now().strftime("%Y%m%d")}.csv"'
            )
            writer = csv.writer(response)
            writer.writerow([
                'date', 'job_id', 'period', 'views', 'applications',
                'reviewing', 'shortlisted', 'interviewing', 'offered',
                'rejected', 'withdrawn',
            ])
            for snap in qs:
                writer.writerow([
                    snap.date, snap.job_id or '', snap.period,
                    snap.views, snap.applications, snap.reviewing,
                    snap.shortlisted, snap.interviewing, snap.offered,
                    snap.rejected, snap.withdrawn,
                ])
            return response

        # JSON export
        data = list(qs.values(
            'date', 'job_id', 'period', 'views', 'applications',
            'reviewing', 'shortlisted', 'interviewing', 'offered',
            'rejected', 'withdrawn',
        ))
        response = HttpResponse(
            json.dumps(data, default=str),
            content_type='application/json',
        )
        response['Content-Disposition'] = (
            f'attachment; filename="analytics_{timezone.now().strftime("%Y%m%d")}.json"'
        )
        return response


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Platform Analytics (Admin only)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

class PlatformMetricsView(APIView):
    """GET /api/v1/intelligence/analytics/platform/"""
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]
    throttle_classes = [UserRateThrottle]

    def get(self, request):
        from .analytics.materialized import get_platform_metrics_trend

        days = _parse_int_param(request, 'days', 30, max_val=365)
        data = get_platform_metrics_trend(days=days)
        serializer = DailyPlatformMetricsSerializer(data, many=True)
        return Response(serializer.data)


class PlatformGrowthView(APIView):
    """GET /api/v1/intelligence/analytics/platform/growth/"""
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]
    throttle_classes = [UserRateThrottle]

    def get(self, request):
        from .analytics.materialized import get_platform_metrics_trend

        days = _parse_int_param(request, 'days', 30, max_val=365)
        metrics = get_platform_metrics_trend(days=days)
        # get_platform_metrics_trend returns list of dicts from .values()
        data = [
            {
                'date': m['date'],
                'new_users': m['new_users'],
                'new_jobs_posted': m['new_jobs_posted'],
                'new_applications': m['new_applications'],
            }
            for m in metrics
        ]
        serializer = PlatformGrowthSerializer(data, many=True)
        return Response(serializer.data)


class PlatformEngagementView(APIView):
    """GET /api/v1/intelligence/analytics/platform/engagement/"""
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]
    throttle_classes = [UserRateThrottle]

    def get(self, request):
        from .analytics.materialized import get_platform_metrics_trend

        days = _parse_int_param(request, 'days', 30, max_val=365)
        metrics = get_platform_metrics_trend(days=days)
        # get_platform_metrics_trend returns list of dicts from .values()
        data = [
            {
                'date': m['date'],
                'active_users_1d': m['active_users_1d'],
                'active_users_7d': m['active_users_7d'],
                'active_users_30d': m['active_users_30d'],
                'total_searches': m.get('total_searches', 0),
                'total_messages_sent': m.get('total_messages_sent', 0),
            }
            for m in metrics
        ]
        serializer = PlatformEngagementSerializer(data, many=True)
        return Response(serializer.data)


class PlatformBenchmarksView(APIView):
    """GET /api/v1/intelligence/analytics/platform/benchmarks/"""
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]
    throttle_classes = [UserRateThrottle]

    def get(self, request):
        benchmarks = PlatformBenchmark.objects.all().order_by('-period_end')[:100]
        serializer = PlatformBenchmarkSerializer(benchmarks, many=True)
        return Response(serializer.data)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# A/B Testing / Experiments
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

class FeatureFlagsView(APIView):
    """
    GET /api/v1/intelligence/experiments/flags/

    Returns all evaluated feature flags for the current user.
    """
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def get(self, request):
        from .experiments.client import get_all_flags

        flags = get_all_flags(request.user.id)
        serializer = FeatureFlagsSerializer({'flags': flags})
        return Response(serializer.data)


class ExperimentTrackView(APIView):
    """
    POST /api/v1/intelligence/experiments/track/

    Track a client-side experiment event.
    """
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def post(self, request):
        serializer = ExperimentTrackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from .experiments.client import capture_event

        properties = serializer.validated_data.get('properties', {})
        if serializer.validated_data.get('experiment_key'):
            properties['$experiment_key'] = serializer.validated_data['experiment_key']
        if serializer.validated_data.get('variant'):
            properties['$experiment_variant'] = serializer.validated_data['variant']

        capture_event(
            request.user.id,
            serializer.validated_data['event'],
            properties,
        )
        return Response({'detail': 'Event tracked.'}, status=status.HTTP_202_ACCEPTED)

