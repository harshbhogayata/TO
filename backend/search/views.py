"""
search/views.py
API views for the Search & Discovery engine.

Endpoints:
  GET /api/v1/search/                → Unified search (all entities)
  GET /api/v1/search/jobs/           → Job-specific search with facets
  GET /api/v1/search/talent/         → Talent profile search (company + admin only)
  GET /api/v1/search/companies/      → Company search (public)
  GET /api/v1/search/autocomplete/   → Fast prefix suggestions (Redis-backed)
  GET /api/v1/search/trending/       → Trending search terms (public)
  POST /api/v1/search/click/         → Record a result click (analytics)
"""
import html
import logging
import time

from django.db.models import Q, Count
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from jobs.models import JobPost
from accounts.models import TalentProfile, CompanyProfile
from talentorbit.pagination import StandardPagination

from .models import SearchAnalytics
from .serializers import (
    JobSearchResultSerializer,
    TalentSearchResultSerializer,
    CompanySearchResultSerializer,
    UnifiedSearchResultSerializer,
    SearchSuggestionSerializer,
    SearchClickSerializer,
    TrendingSearchSerializer,
)
from .vectors import (
    search_jobs,
    search_talent,
    search_companies,
    make_search_cache_key,
)
from .cache import (
    get_cached_results,
    set_cached_results,
    get_cached_suggestions,
    set_cached_suggestions,
    get_cached_trending,
    set_cached_trending,
)

logger = logging.getLogger(__name__)


# ─── Helper: Extract all filter params from request ──────────────────────────

def _extract_filters(request):
    """Extract all filter query params into a dict (ignoring q, page, sort)."""
    exclude_keys = {'q', 'page', 'page_size', 'sort', 'format', 'entity_type'}
    return {
        k: v for k, v in request.query_params.items()
        if k not in exclude_keys and v
    }


def _safe_meta_value(value):
    """Escape reflected text so raw HTML payloads are not echoed into responses."""
    if isinstance(value, str):
        return html.escape(value, quote=True)
    if isinstance(value, dict):
        return {k: _safe_meta_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_meta_value(v) for v in value]
    return value


def _build_search_meta(**kwargs):
    """Normalize response metadata for safe JSON reflection."""
    return {key: _safe_meta_value(value) for key, value in kwargs.items()}


def _log_search(query, entity_type, user, results_count, response_time_ms, filters):
    """
    Asynchronously log a search query for analytics.
    Non-blocking — failures are swallowed and logged.
    """
    try:
        SearchAnalytics.objects.create(
            query=query,
            entity_type=entity_type,
            user=user if user and user.is_authenticated else None,
            results_count=results_count,
            response_time_ms=int(response_time_ms * 1000),
            filters_applied=filters,
        )
    except Exception:
        logger.exception('Failed to log search analytics for query="%s"', query)


# ─── Job Search View ─────────────────────────────────────────────────────────

class JobSearchView(generics.ListAPIView):
    """
    GET /api/v1/search/jobs/?q=react&job_type=full_time&sort=relevance

    Full-text search across open job posts with faceted filtering,
    weighted ranking, trigram fallback, and Redis-cached results.
    """
    serializer_class = JobSearchResultSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = StandardPagination

    def get_queryset(self):
        return JobPost.objects.filter(
            status='open'
        ).select_related('company__company_profile')

    def list(self, request, *args, **kwargs):
        query = request.query_params.get('q', '').strip()
        sort = request.query_params.get('sort', 'relevance')
        filters = _extract_filters(request)
        page = request.query_params.get('page', '1')

        # Check cache
        cache_key = make_search_cache_key('jobs', query, filters, page, sort)
        cached = get_cached_results(cache_key, 'jobs')
        if cached is not None:
            return Response(cached)

        # Execute search
        base_qs = self.get_queryset()
        result_qs, elapsed = search_jobs(base_qs, query, filters, sort)

        # Paginate
        page_obj = self.paginate_queryset(result_qs)
        if page_obj is not None:
            serializer = self.get_serializer(page_obj, many=True)
            response_data = self.get_paginated_response(serializer.data).data
        else:
            serializer = self.get_serializer(result_qs[:100], many=True)
            response_data = serializer.data

        # Inject search metadata
        if isinstance(response_data, dict):
            response_data['search_meta'] = _build_search_meta(
                query=query,
                filters=filters,
                sort=sort,
                response_time_ms=round(elapsed * 1000, 1),
            )

        # Cache the response
        set_cached_results(cache_key, 'jobs', response_data)

        # Log analytics (non-blocking)
        total = response_data.get('count', len(serializer.data)) if isinstance(response_data, dict) else len(serializer.data)
        _log_search(query, 'jobs', request.user, total, elapsed, filters)

        return Response(response_data)


# ─── Talent Search View ──────────────────────────────────────────────────────

class TalentSearchView(generics.ListAPIView):
    """
    GET /api/v1/search/talent/?q=python&is_open_to_work=true

    Search talent profiles. Restricted to COMPANY and ADMIN roles.
    """
    serializer_class = TalentSearchResultSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination

    def get_queryset(self):
        return TalentProfile.objects.select_related('user').filter(
            user__is_active=True,
        )

    def check_permissions(self, request):
        super().check_permissions(request)
        if request.user.role not in ('COMPANY', 'ADMIN'):
            self.permission_denied(
                request,
                message='Only company accounts and admins can search talent profiles.',
            )

    def list(self, request, *args, **kwargs):
        query = request.query_params.get('q', '').strip()
        filters = _extract_filters(request)
        page = request.query_params.get('page', '1')

        cache_key = make_search_cache_key('talent', query, filters, page)
        cached = get_cached_results(cache_key, 'talent')
        if cached is not None:
            return Response(cached)

        base_qs = self.get_queryset()
        result_qs, elapsed = search_talent(base_qs, query, filters)

        page_obj = self.paginate_queryset(result_qs)
        if page_obj is not None:
            serializer = self.get_serializer(page_obj, many=True)
            response_data = self.get_paginated_response(serializer.data).data
        else:
            serializer = self.get_serializer(result_qs[:100], many=True)
            response_data = serializer.data

        if isinstance(response_data, dict):
            response_data['search_meta'] = _build_search_meta(
                query=query,
                filters=filters,
                response_time_ms=round(elapsed * 1000, 1),
            )

        set_cached_results(cache_key, 'talent', response_data)
        total = response_data.get('count', len(serializer.data)) if isinstance(response_data, dict) else len(serializer.data)
        _log_search(query, 'talent', request.user, total, elapsed, filters)

        return Response(response_data)


# ─── Company Search View ─────────────────────────────────────────────────────

class CompanySearchView(generics.ListAPIView):
    """
    GET /api/v1/search/companies/?q=tech&industry=SaaS

    Search company profiles. Public endpoint.
    """
    serializer_class = CompanySearchResultSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = StandardPagination

    def get_queryset(self):
        return CompanyProfile.objects.select_related('user').filter(
            user__is_active=True,
        )

    def list(self, request, *args, **kwargs):
        query = request.query_params.get('q', '').strip()
        filters = _extract_filters(request)
        page = request.query_params.get('page', '1')

        cache_key = make_search_cache_key('companies', query, filters, page)
        cached = get_cached_results(cache_key, 'companies')
        if cached is not None:
            return Response(cached)

        base_qs = self.get_queryset()
        result_qs, elapsed = search_companies(base_qs, query, filters)

        page_obj = self.paginate_queryset(result_qs)
        if page_obj is not None:
            serializer = self.get_serializer(page_obj, many=True)
            response_data = self.get_paginated_response(serializer.data).data
        else:
            serializer = self.get_serializer(result_qs[:100], many=True)
            response_data = serializer.data

        if isinstance(response_data, dict):
            response_data['search_meta'] = _build_search_meta(
                query=query,
                filters=filters,
                response_time_ms=round(elapsed * 1000, 1),
            )

        set_cached_results(cache_key, 'companies', response_data)
        total = response_data.get('count', len(serializer.data)) if isinstance(response_data, dict) else len(serializer.data)
        _log_search(query, 'companies', request.user, total, elapsed, filters)

        return Response(response_data)


# ─── Unified Search View ─────────────────────────────────────────────────────

class UnifiedSearchView(APIView):
    """
    GET /api/v1/search/?q=react&entity_type=all

    Searches across jobs, talent (if authorized), and companies.
    Returns a mixed result set with type labels and relevance ranking.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        query = request.query_params.get('q', '').strip()
        entity_type = request.query_params.get('entity_type', 'all')
        filters = _extract_filters(request)
        limit = min(int(request.query_params.get('limit', 10)), 50)

        if not query:
            return Response({
                'results': [],
                'search_meta': _build_search_meta(query='', response_time_ms=0),
            })

        start = time.monotonic()
        results = []

        # Jobs (always included)
        if entity_type in ('all', 'jobs'):
            job_qs = JobPost.objects.filter(status='open').select_related('company__company_profile')
            job_results, _ = search_jobs(job_qs, query, filters)
            for job in job_results[:limit]:
                company_name = ''
                logo_url = None
                try:
                    company_name = job.company.company_profile.legal_name
                    if job.company.company_profile.logo:
                        logo_url = request.build_absolute_uri(job.company.company_profile.logo.url)
                except Exception:
                    company_name = job.company.full_name or ''
                results.append({
                    'entity_type': 'job',
                    'id': job.id,
                    'title': job.title,
                    'subtitle': company_name,
                    'description': (job.description or '')[:200],
                    'image_url': logo_url,
                    'rank': getattr(job, 'rank', 0.0),
                    'url': f'/jobs/{job.id}',
                    'meta': {
                        'location': job.location,
                        'job_type': job.job_type,
                        'work_mode': job.work_mode,
                        'salary_display': job.salary_display,
                    },
                })

        # Talent (only for COMPANY/ADMIN)
        if entity_type in ('all', 'talent'):
            if request.user.is_authenticated and request.user.role in ('COMPANY', 'ADMIN'):
                talent_qs = TalentProfile.objects.select_related('user').filter(user__is_active=True)
                talent_results, _ = search_talent(talent_qs, query, filters)
                for tp in talent_results[:limit]:
                    avatar_url = None
                    try:
                        if tp.user.avatar:
                            avatar_url = request.build_absolute_uri(tp.user.avatar.url)
                    except Exception:
                        pass
                    results.append({
                        'entity_type': 'talent',
                        'id': tp.id,
                        'title': tp.user.full_name or 'Anonymous',
                        'subtitle': tp.location or '',
                        'description': (tp.bio or '')[:200],
                        'image_url': avatar_url,
                        'rank': getattr(tp, 'rank', 0.0),
                        'url': f'/talent/{tp.id}',
                        'meta': {
                            'skills': tp.skills[:5] if tp.skills else [],
                            'is_open_to_work': tp.is_open_to_work,
                        },
                    })

        # Companies (always included)
        if entity_type in ('all', 'companies'):
            company_qs = CompanyProfile.objects.select_related('user').filter(user__is_active=True)
            company_results, _ = search_companies(company_qs, query, filters)
            for cp in company_results[:limit]:
                logo_url = None
                try:
                    if cp.logo:
                        logo_url = request.build_absolute_uri(cp.logo.url)
                except Exception:
                    pass
                results.append({
                    'entity_type': 'company',
                    'id': cp.id,
                    'title': cp.legal_name,
                    'subtitle': cp.industry or '',
                    'description': (cp.mission_statement or '')[:200],
                    'image_url': logo_url,
                    'rank': getattr(cp, 'rank', 0.0),
                    'url': f'/companies/{cp.id}',
                    'meta': {
                        'headquarters': cp.headquarters,
                        'is_verified': cp.is_verified,
                        'website': cp.website,
                    },
                })

        # Sort combined results by rank descending
        results.sort(key=lambda r: r.get('rank', 0), reverse=True)

        elapsed = time.monotonic() - start
        _log_search(query, entity_type, request.user, len(results), elapsed, filters)

        return Response({
            'results': results[:limit],
            'search_meta': _build_search_meta(
                query=query,
                entity_type=entity_type,
                total=len(results),
                response_time_ms=round(elapsed * 1000, 1),
            ),
        })


# ─── Autocomplete View ───────────────────────────────────────────────────────

class AutocompleteView(APIView):
    """
    GET /api/v1/search/autocomplete/?q=rea&entity_type=jobs

    Fast prefix-based suggestions backed by Redis cache.
    Returns up to 8 suggestions in <50ms.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        prefix = request.query_params.get('q', '').strip()
        entity_type = request.query_params.get('entity_type', 'jobs')

        if len(prefix) < 2:
            return Response({'suggestions': []})

        # Check cache
        cached = get_cached_suggestions(prefix, entity_type)
        if cached is not None:
            return Response({'suggestions': cached})

        suggestions = []

        if entity_type in ('jobs', 'all'):
            # Job title suggestions
            job_titles = (
                JobPost.objects.filter(
                    status='open',
                    title__icontains=prefix,
                )
                .values_list('title', flat=True)
                .distinct()[:5]
            )
            suggestions.extend([
                {'text': t, 'entity_type': 'job'} for t in job_titles
            ])

            # Skill suggestions from JSON array
            jobs_with_skills = JobPost.objects.filter(
                status='open',
                skills_required__icontains=prefix,
            ).values_list('skills_required', flat=True)[:20]

            seen_skills = set()
            for skill_list in jobs_with_skills:
                if isinstance(skill_list, list):
                    for skill in skill_list:
                        if prefix.lower() in skill.lower() and skill.lower() not in seen_skills:
                            seen_skills.add(skill.lower())
                            suggestions.append({'text': skill, 'entity_type': 'skill'})

        if entity_type in ('companies', 'all'):
            company_names = (
                CompanyProfile.objects.filter(
                    legal_name__icontains=prefix,
                    user__is_active=True,
                )
                .values_list('legal_name', flat=True)
                .distinct()[:5]
            )
            suggestions.extend([
                {'text': n, 'entity_type': 'company'} for n in company_names
            ])

        if entity_type in ('talent', 'all'):
            if request.user.is_authenticated and request.user.role in ('COMPANY', 'ADMIN'):
                talent_names = (
                    TalentProfile.objects.filter(
                        user__full_name__icontains=prefix,
                        user__is_active=True,
                    )
                    .values_list('user__full_name', flat=True)
                    .distinct()[:5]
                )
                suggestions.extend([
                    {'text': n, 'entity_type': 'talent'} for n in talent_names
                ])

        # Deduplicate and limit
        seen = set()
        unique = []
        for s in suggestions:
            key = f"{s['entity_type']}:{s['text'].lower()}"
            if key not in seen:
                seen.add(key)
                unique.append(s)
        suggestions = unique[:8]

        # Cache
        set_cached_suggestions(prefix, entity_type, suggestions)

        return Response({'suggestions': suggestions})


# ─── Trending Searches View ──────────────────────────────────────────────────

class TrendingSearchesView(APIView):
    """
    GET /api/v1/search/trending/

    Returns the top 10 most-searched queries in the last 7 days.
    Cached for 1 hour.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        entity_type = request.query_params.get('entity_type', 'all')

        cutoff = timezone.now() - timezone.timedelta(days=7)
        qs = SearchAnalytics.objects.filter(
            created_at__gte=cutoff,
            results_count__gt=0,  # Only queries that returned results
        )
        if entity_type != 'all':
            qs = qs.filter(entity_type=entity_type)

        # Test database resets and manual data cleanup do not trigger cache invalidation.
        # Treat an empty qualifying queryset as the source of truth before trusting cache.
        if not qs.exists():
            set_cached_trending(entity_type, [])
            return Response({'trending': []})

        cached = get_cached_trending(entity_type)
        if cached is not None:
            return Response({'trending': cached})

        trending = (
            qs
            .values('normalized_query')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )

        results = [
            {'query': t['normalized_query'], 'count': t['count'], 'entity_type': entity_type}
            for t in trending
        ]

        set_cached_trending(entity_type, results)
        return Response({'trending': results})


# ─── Search Click Analytics ──────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def record_search_click(request):
    """
    POST /api/v1/search/click/

    Records when a user clicks a search result, enabling CTR analysis.
    """
    serializer = SearchClickSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    # Find the most recent matching search query for this user
    user = request.user if request.user.is_authenticated else None
    recent_qs = SearchAnalytics.objects.filter(
        normalized_query=data['query'].strip().lower(),
        entity_type=data['entity_type'],
    )
    if user:
        recent_qs = recent_qs.filter(user=user)

    recent = recent_qs.order_by('-created_at').first()

    if recent:
        recent.clicked_result_id = data['result_id']
        recent.clicked_position = data['position']
        recent.save(update_fields=['clicked_result_id', 'clicked_position'])
    else:
        SearchAnalytics.objects.create(
            query=data['query'],
            entity_type=data['entity_type'],
            user=user,
            clicked_result_id=data['result_id'],
            clicked_position=data['position'],
        )

    return Response({'status': 'recorded'}, status=status.HTTP_201_CREATED)
