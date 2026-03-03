"""
search/vectors.py
Core search engine — builds weighted SearchVectors, ranks results,
provides trigram fallback for typo-tolerant fuzzy matching.

Architecture:
  - Each searchable model gets a pre-computed SearchVectorField (stored + GIN-indexed).
  - On save, signals call `update_search_vector()` to recompute the vector.
  - At query time, we rank against the stored vector (O(log n) via GIN index).
  - If full-text returns < threshold results, we fall back to trigram similarity.
  - Results are annotated with `rank` and `headline` (highlighted snippet).

Supports: JobPost, TalentProfile, CompanyProfile.
"""
import hashlib
import logging
import time

from django.contrib.postgres.search import (
    SearchQuery,
    SearchRank,
    SearchVector,
)
from django.db.models import F, Q, Value, CharField, FloatField
from django.db.models.functions import Greatest
from django.contrib.postgres.search import TrigramSimilarity

logger = logging.getLogger(__name__)

# ─── Weight configurations per model ────────────────────────────────────────
# PostgreSQL search weights: A > B > C > D
# These define how each field contributes to relevance ranking.

JOB_SEARCH_CONFIG = {
    'vectors': [
        ('title', 'A'),
        ('skills_required_text', 'A'),
        ('location', 'B'),
        ('description', 'B'),
        ('requirements', 'C'),
        ('responsibilities', 'C'),
        ('company_name_cache', 'C'),
    ],
    'trigram_fields': ['title', 'location', 'description'],
    'search_config': 'english',
}

TALENT_SEARCH_CONFIG = {
    'vectors': [
        ('skills_text', 'A'),
        ('user_full_name', 'A'),
        ('bio', 'B'),
        ('location', 'B'),
    ],
    'trigram_fields': ['user_full_name', 'bio', 'location'],
    'search_config': 'english',
}

COMPANY_SEARCH_CONFIG = {
    'vectors': [
        ('legal_name', 'A'),
        ('industry', 'A'),
        ('mission_statement', 'B'),
        ('headquarters', 'B'),
    ],
    'trigram_fields': ['legal_name', 'industry', 'headquarters'],
    'search_config': 'english',
}


def build_search_query(raw_query, search_config='english'):
    """
    Build a SearchQuery from raw user input.
    Handles multi-word queries with AND logic for precision.
    Falls back to plain query for single words.
    """
    cleaned = raw_query.strip()
    if not cleaned:
        return None

    # For multi-word queries, use websearch type which supports
    # natural language operators (AND, OR, quotes, -)
    return SearchQuery(
        cleaned,
        config=search_config,
        search_type='websearch',
    )


def compute_job_search_vector(job):
    """
    Compute the SearchVector for a JobPost instance.
    Flattens JSON skills into a text field for full-text indexing.
    """
    # Flatten skills_required (JSONField list) into space-separated text
    skills_text = ' '.join(job.skills_required) if job.skills_required else ''

    # Cache company name for search (avoids join at query time)
    try:
        company_name = job.company.company_profile.legal_name
    except Exception:
        company_name = job.company.full_name or ''

    vector = (
        SearchVector('title', weight='A', config='english')
        + SearchVector(Value(skills_text), weight='A', config='english')
        + SearchVector('location', weight='B', config='english')
        + SearchVector('description', weight='B', config='english')
        + SearchVector('requirements', weight='C', config='english')
        + SearchVector('responsibilities', weight='C', config='english')
        + SearchVector(Value(company_name), weight='C', config='english')
    )
    return vector


def compute_talent_search_vector(profile):
    """
    Compute the SearchVector for a TalentProfile instance.
    Flattens JSON skills into a text field.
    """
    skills_text = ' '.join(profile.skills) if profile.skills else ''
    full_name = profile.user.full_name or ''

    vector = (
        SearchVector(Value(skills_text), weight='A', config='english')
        + SearchVector(Value(full_name), weight='A', config='english')
        + SearchVector('bio', weight='B', config='english')
        + SearchVector('location', weight='B', config='english')
    )
    return vector


def compute_company_search_vector(profile):
    """
    Compute the SearchVector for a CompanyProfile instance.
    """
    vector = (
        SearchVector('legal_name', weight='A', config='english')
        + SearchVector('industry', weight='A', config='english')
        + SearchVector('mission_statement', weight='B', config='english')
        + SearchVector('headquarters', weight='B', config='english')
    )
    return vector


# ─── Query execution ────────────────────────────────────────────────────────


def search_jobs(queryset, query_text, filters=None, sort='relevance'):
    """
    Execute a full-text search against JobPost.search_vector with weighted ranking.
    Falls back to trigram similarity if full-text returns fewer than 3 results.

    Args:
        queryset: Base JobPost queryset (pre-filtered for status='open', etc.)
        query_text: Raw search string from the user
        filters: Dict of facet filters (job_type, work_mode, etc.)
        sort: 'relevance', 'salary', 'date'

    Returns:
        Annotated queryset with `rank` and `headline` fields.
    """
    start = time.monotonic()
    filters = filters or {}

    # Apply facet filters first (before search — narrows the candidate set)
    queryset = _apply_job_filters(queryset, filters)

    if not query_text or not query_text.strip():
        # No search query — return filtered results sorted by default
        queryset = queryset.annotate(
            rank=Value(1.0, output_field=FloatField()),
            headline=F('title'),
        )
        return _apply_job_sort(queryset, sort), time.monotonic() - start

    search_query = build_search_query(query_text)
    if search_query is None:
        queryset = queryset.annotate(
            rank=Value(1.0, output_field=FloatField()),
            headline=F('title'),
        )
        return _apply_job_sort(queryset, sort), time.monotonic() - start

    # Primary: full-text search against stored search_vector
    ft_results = queryset.filter(
        search_vector=search_query
    ).annotate(
        rank=SearchRank(F('search_vector'), search_query, normalization=32),
        headline=F('title'),
    )

    # If full-text returns fewer than 3 results, augment with trigram similarity
    ft_count = ft_results.count()
    if ft_count < 3:
        logger.info(
            'Full-text returned %d results for "%s" — augmenting with trigram fallback',
            ft_count, query_text,
        )
        trigram_results = _trigram_fallback_jobs(queryset, query_text)

        # Combine: full-text results first, then trigram (excluding duplicates)
        ft_ids = set(ft_results.values_list('id', flat=True))
        trigram_extra = trigram_results.exclude(id__in=ft_ids)

        # Union isn't great for annotated querysets, so we use a combined approach
        from itertools import chain
        combined_ids = list(ft_ids) + list(trigram_extra.values_list('id', flat=True)[:50])

        if combined_ids:
            # Re-annotate the combined set
            queryset = queryset.filter(id__in=combined_ids).annotate(
                rank=Greatest(
                    SearchRank(F('search_vector'), search_query, normalization=32),
                    TrigramSimilarity('title', query_text),
                    output_field=FloatField(),
                ),
                headline=F('title'),
            )
        else:
            queryset = ft_results
    else:
        queryset = ft_results

    elapsed = time.monotonic() - start
    return _apply_job_sort(queryset, sort), elapsed


def search_talent(queryset, query_text, filters=None):
    """
    Full-text search against TalentProfile.search_vector.
    """
    start = time.monotonic()
    filters = filters or {}

    queryset = _apply_talent_filters(queryset, filters)

    if not query_text or not query_text.strip():
        queryset = queryset.annotate(
            rank=Value(1.0, output_field=FloatField()),
        )
        return queryset.order_by('-rank'), time.monotonic() - start

    search_query = build_search_query(query_text)
    if search_query is None:
        queryset = queryset.annotate(
            rank=Value(1.0, output_field=FloatField()),
        )
        return queryset.order_by('-rank'), time.monotonic() - start

    # Full-text
    ft_results = queryset.filter(
        search_vector=search_query
    ).annotate(
        rank=SearchRank(F('search_vector'), search_query, normalization=32),
    )

    ft_count = ft_results.count()
    if ft_count < 3:
        trigram_qs = queryset.annotate(
            similarity=Greatest(
                TrigramSimilarity('user__full_name', query_text),
                TrigramSimilarity('bio', query_text),
                TrigramSimilarity('location', query_text),
                output_field=FloatField(),
            )
        ).filter(similarity__gte=0.15).order_by('-similarity')

        ft_ids = set(ft_results.values_list('id', flat=True))
        trigram_extra_ids = list(
            trigram_qs.exclude(id__in=ft_ids).values_list('id', flat=True)[:50]
        )
        combined_ids = list(ft_ids) + trigram_extra_ids

        if combined_ids:
            queryset = queryset.filter(id__in=combined_ids).annotate(
                rank=Greatest(
                    SearchRank(F('search_vector'), search_query, normalization=32),
                    TrigramSimilarity('user__full_name', query_text),
                    output_field=FloatField(),
                ),
            )
        else:
            queryset = ft_results
    else:
        queryset = ft_results

    elapsed = time.monotonic() - start
    return queryset.order_by('-rank'), elapsed


def search_companies(queryset, query_text, filters=None):
    """
    Full-text search against CompanyProfile.search_vector.
    """
    start = time.monotonic()
    filters = filters or {}

    queryset = _apply_company_filters(queryset, filters)

    if not query_text or not query_text.strip():
        queryset = queryset.annotate(
            rank=Value(1.0, output_field=FloatField()),
        )
        return queryset.order_by('-rank'), time.monotonic() - start

    search_query = build_search_query(query_text)
    if search_query is None:
        queryset = queryset.annotate(
            rank=Value(1.0, output_field=FloatField()),
        )
        return queryset.order_by('-rank'), time.monotonic() - start

    ft_results = queryset.filter(
        search_vector=search_query
    ).annotate(
        rank=SearchRank(F('search_vector'), search_query, normalization=32),
    )

    ft_count = ft_results.count()
    if ft_count < 3:
        trigram_qs = queryset.annotate(
            similarity=Greatest(
                TrigramSimilarity('legal_name', query_text),
                TrigramSimilarity('industry', query_text),
                TrigramSimilarity('headquarters', query_text),
                output_field=FloatField(),
            )
        ).filter(similarity__gte=0.15).order_by('-similarity')

        ft_ids = set(ft_results.values_list('id', flat=True))
        trigram_extra_ids = list(
            trigram_qs.exclude(id__in=ft_ids).values_list('id', flat=True)[:50]
        )
        combined_ids = list(ft_ids) + trigram_extra_ids

        if combined_ids:
            queryset = queryset.filter(id__in=combined_ids).annotate(
                rank=Greatest(
                    SearchRank(F('search_vector'), search_query, normalization=32),
                    TrigramSimilarity('legal_name', query_text),
                    output_field=FloatField(),
                ),
            )
        else:
            queryset = ft_results
    else:
        queryset = ft_results

    elapsed = time.monotonic() - start
    return queryset.order_by('-rank'), elapsed


# ─── Facet filter helpers ────────────────────────────────────────────────────


def _apply_job_filters(qs, filters):
    """Apply faceted filters to a JobPost queryset."""
    # Multi-value filters (comma-separated)
    if filters.get('job_type'):
        types = [t.strip() for t in filters['job_type'].split(',') if t.strip()]
        if types:
            qs = qs.filter(job_type__in=types)

    if filters.get('work_mode'):
        modes = [m.strip() for m in filters['work_mode'].split(',') if m.strip()]
        if modes:
            qs = qs.filter(work_mode__in=modes)

    if filters.get('experience_level'):
        levels = [l.strip() for l in filters['experience_level'].split(',') if l.strip()]
        if levels:
            qs = qs.filter(experience_level__in=levels)

    # Range filters
    if filters.get('salary_min'):
        try:
            qs = qs.filter(salary_max__gte=int(filters['salary_min']))
        except (ValueError, TypeError):
            pass

    if filters.get('salary_max'):
        try:
            qs = qs.filter(salary_min__lte=int(filters['salary_max']))
        except (ValueError, TypeError):
            pass

    # Skills filter — match any skill in the JSON array
    if filters.get('skills'):
        skills = [s.strip().lower() for s in filters['skills'].split(',') if s.strip()]
        if skills:
            skills_q = Q()
            for skill in skills:
                skills_q |= Q(skills_required__icontains=skill)
            qs = qs.filter(skills_q)

    # Location — trigram fuzzy match
    if filters.get('location'):
        qs = qs.annotate(
            _loc_similarity=TrigramSimilarity('location', filters['location'])
        ).filter(_loc_similarity__gte=0.2)

    # Date range
    if filters.get('posted_after'):
        qs = qs.filter(created_at__date__gte=filters['posted_after'])

    if filters.get('posted_before'):
        qs = qs.filter(created_at__date__lte=filters['posted_before'])

    return qs


def _apply_talent_filters(qs, filters):
    """Apply faceted filters to a TalentProfile queryset."""
    if filters.get('is_open_to_work'):
        val = filters['is_open_to_work'].lower()
        if val in ('true', '1', 'yes'):
            qs = qs.filter(is_open_to_work=True)

    if filters.get('skills'):
        skills = [s.strip().lower() for s in filters['skills'].split(',') if s.strip()]
        if skills:
            skills_q = Q()
            for skill in skills:
                skills_q |= Q(skills__icontains=skill)
            qs = qs.filter(skills_q)

    if filters.get('location'):
        qs = qs.annotate(
            _loc_similarity=TrigramSimilarity('location', filters['location'])
        ).filter(_loc_similarity__gte=0.2)

    return qs


def _apply_company_filters(qs, filters):
    """Apply faceted filters to a CompanyProfile queryset."""
    if filters.get('industry'):
        industries = [i.strip() for i in filters['industry'].split(',') if i.strip()]
        if industries:
            qs = qs.filter(industry__in=industries)

    if filters.get('is_verified'):
        val = filters['is_verified'].lower()
        if val in ('true', '1', 'yes'):
            qs = qs.filter(is_verified=True)

    if filters.get('location'):
        qs = qs.annotate(
            _loc_similarity=TrigramSimilarity('headquarters', filters['location'])
        ).filter(_loc_similarity__gte=0.2)

    return qs


def _apply_job_sort(qs, sort):
    """Apply sort ordering to job search results."""
    if sort == 'salary':
        return qs.order_by(F('salary_max').desc(nulls_last=True), '-rank')
    elif sort == 'date':
        return qs.order_by('-created_at', '-rank')
    else:
        # Default: relevance
        return qs.order_by('-rank', '-created_at')


def _trigram_fallback_jobs(queryset, query_text):
    """
    Trigram similarity fallback for typo-tolerant search.
    Used when full-text search returns too few results.
    """
    return queryset.annotate(
        similarity=Greatest(
            TrigramSimilarity('title', query_text),
            TrigramSimilarity('location', query_text),
            TrigramSimilarity('description', query_text),
            output_field=FloatField(),
        )
    ).filter(similarity__gte=0.15).order_by('-similarity')


# ─── Cache key helpers ───────────────────────────────────────────────────────


def make_search_cache_key(entity_type, query_text, filters, page=1, sort='relevance'):
    """
    Generate a deterministic cache key for a search query + filters combination.
    Uses MD5 for speed (not security-sensitive).
    """
    # Sort filter keys for deterministic hashing
    filter_str = '&'.join(f'{k}={v}' for k, v in sorted(filters.items()) if v)
    raw = f'{entity_type}:{query_text}:{filter_str}:p{page}:s{sort}'
    digest = hashlib.md5(raw.encode()).hexdigest()[:16]
    return f'search:{entity_type}:{digest}'
