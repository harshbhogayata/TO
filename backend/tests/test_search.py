"""
tests/test_search.py
Comprehensive test suite for the Search & Discovery engine.

Covers:
  - SearchVector/SearchRank/Trigram logic (mocked for SQLite test runs)
  - Faceted filtering (job_type, work_mode, salary range, skills)
  - Unified search across all entity types
  - Autocomplete suggestions
  - Trending searches
  - Search analytics logging and click tracking
  - Cache layer (version-based invalidation)
  - Permission enforcement (talent search = company/admin only)
  - Edge cases: empty query, special chars, Unicode, long queries, SQL injection
  - Serializer contract assertions

Usage (SQLite — fast local):
  python manage.py test tests.test_search --settings=talentorbit.test_settings -v2

Usage (PostgreSQL — full-text + trigram, CI/staging):
  python manage.py test tests.test_search -v2
"""
import time
from collections import namedtuple
from unittest.mock import patch, MagicMock

from django.db import connection
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import User, TalentProfile, CompanyProfile
from jobs.models import JobPost
from search.models import SearchAnalytics
from search.cache import (
    get_entity_version,
    bump_entity_version,
    invalidate_entity_cache,
    get_cached_results,
    set_cached_results,
    get_cached_suggestions,
    set_cached_suggestions,
    get_cached_trending,
    set_cached_trending,
)
from search.vectors import (
    build_search_query,
    make_search_cache_key,
)


IS_POSTGRES = connection.vendor == 'postgresql'


# ─── Test data factories ─────────────────────────────────────────────────────

def create_talent_user(email='talent@test.com', name='Jane Developer', **kwargs):
    user = User.objects.create_user(
        email=email, password='testpass123',
        full_name=name, role='TALENT', is_verified=True,
    )
    profile = TalentProfile.objects.create(
        user=user,
        bio=kwargs.get('bio', 'Full-stack developer with 5 years experience'),
        location=kwargs.get('location', 'San Francisco'),
        skills=kwargs.get('skills', ['python', 'django', 'react', 'typescript']),
        is_open_to_work=kwargs.get('is_open_to_work', True),
    )
    return user, profile


def create_company_user(email='company@test.com', name='TechCorp Inc', **kwargs):
    user = User.objects.create_user(
        email=email, password='testpass123',
        full_name='Company Admin', role='COMPANY', is_verified=True,
    )
    profile = CompanyProfile.objects.create(
        user=user,
        legal_name=name,
        industry=kwargs.get('industry', 'Technology'),
        mission_statement=kwargs.get('mission', 'Building the future'),
        headquarters=kwargs.get('headquarters', 'New York'),
        website=kwargs.get('website', 'https://techcorp.com'),
    )
    return user, profile


def create_job(company_user, **kwargs):
    return JobPost.objects.create(
        company=company_user,
        title=kwargs.get('title', 'Senior React Developer'),
        description=kwargs.get('description', 'We are looking for an experienced React developer.'),
        requirements=kwargs.get('requirements', '5+ years of React experience'),
        responsibilities=kwargs.get('responsibilities', 'Build and maintain frontend applications'),
        job_type=kwargs.get('job_type', 'full_time'),
        work_mode=kwargs.get('work_mode', 'remote'),
        status=kwargs.get('status', 'open'),
        experience_level=kwargs.get('experience_level', 'senior'),
        location=kwargs.get('location', 'San Francisco'),
        salary_min=kwargs.get('salary_min', 120000),
        salary_max=kwargs.get('salary_max', 180000),
        skills_required=kwargs.get('skills_required', ['react', 'typescript', 'node.js']),
    )


def _mock_search_jobs(queryset, query_text, filters=None, sort='relevance'):
    """
    SQLite-safe mock: filters queryset by icontains on title/description,
    annotates rank=1.0, headline=title. Used when PG is not available.
    """
    from django.db.models import Value, F, FloatField

    filters = filters or {}
    if filters.get('job_type'):
        types = [t.strip() for t in filters['job_type'].split(',') if t.strip()]
        queryset = queryset.filter(job_type__in=types)
    if filters.get('work_mode'):
        modes = [m.strip() for m in filters['work_mode'].split(',') if m.strip()]
        queryset = queryset.filter(work_mode__in=modes)
    if filters.get('experience_level'):
        levels = [l.strip() for l in filters['experience_level'].split(',') if l.strip()]
        queryset = queryset.filter(experience_level__in=levels)
    if filters.get('salary_min'):
        try:
            queryset = queryset.filter(salary_max__gte=int(filters['salary_min']))
        except (ValueError, TypeError):
            pass
    if filters.get('salary_max'):
        try:
            queryset = queryset.filter(salary_min__lte=int(filters['salary_max']))
        except (ValueError, TypeError):
            pass

    if query_text and query_text.strip():
        from django.db.models import Q
        queryset = queryset.filter(
            Q(title__icontains=query_text) | Q(description__icontains=query_text)
        )
    queryset = queryset.annotate(
        rank=Value(1.0, output_field=FloatField()),
        headline=F('title'),
    )
    if sort == 'date':
        queryset = queryset.order_by('-created_at')
    elif sort == 'salary':
        queryset = queryset.order_by(F('salary_max').desc(nulls_last=True))
    else:
        queryset = queryset.order_by('-rank', '-created_at')
    return queryset, 0.001


def _mock_search_talent(queryset, query_text, filters=None):
    from django.db.models import Value, FloatField
    filters = filters or {}
    if query_text and query_text.strip():
        queryset = queryset.filter(user__full_name__icontains=query_text)
    queryset = queryset.annotate(rank=Value(1.0, output_field=FloatField()))
    return queryset.order_by('-rank'), 0.001


def _mock_search_companies(queryset, query_text, filters=None):
    from django.db.models import Value, FloatField
    filters = filters or {}
    if query_text and query_text.strip():
        queryset = queryset.filter(legal_name__icontains=query_text)
    queryset = queryset.annotate(rank=Value(1.0, output_field=FloatField()))
    return queryset.order_by('-rank'), 0.001


# Helper: conditionally mock search functions when running on SQLite
def _search_patches():
    """Return a list of active mock patches if running on SQLite."""
    if IS_POSTGRES:
        return []
    return [
        patch('search.views.search_jobs', side_effect=_mock_search_jobs),
        patch('search.views.search_talent', side_effect=_mock_search_talent),
        patch('search.views.search_companies', side_effect=_mock_search_companies),
    ]


# ─── Unit Tests: Search Query Building ───────────────────────────────────────

class SearchQueryBuildTests(TestCase):
    """Test the SearchQuery construction from raw user input."""

    def test_empty_query_returns_none(self):
        self.assertIsNone(build_search_query(''))
        self.assertIsNone(build_search_query('   '))

    def test_single_word_query(self):
        query = build_search_query('react')
        self.assertIsNotNone(query)

    def test_multi_word_query(self):
        query = build_search_query('react developer')
        self.assertIsNotNone(query)

    def test_special_characters_handled(self):
        """Special chars should not crash the query builder."""
        query = build_search_query('c++ developer')
        self.assertIsNotNone(query)

    def test_unicode_query(self):
        query = build_search_query('développeur python')
        self.assertIsNotNone(query)


# ─── Unit Tests: Cache Key Generation ────────────────────────────────────────

class CacheKeyTests(TestCase):
    """Test deterministic cache key generation."""

    def test_same_inputs_produce_same_key(self):
        key1 = make_search_cache_key('jobs', 'react', {'job_type': 'full_time'}, 1)
        key2 = make_search_cache_key('jobs', 'react', {'job_type': 'full_time'}, 1)
        self.assertEqual(key1, key2)

    def test_different_queries_produce_different_keys(self):
        key1 = make_search_cache_key('jobs', 'react', {}, 1)
        key2 = make_search_cache_key('jobs', 'python', {}, 1)
        self.assertNotEqual(key1, key2)

    def test_different_pages_produce_different_keys(self):
        key1 = make_search_cache_key('jobs', 'react', {}, 1)
        key2 = make_search_cache_key('jobs', 'react', {}, 2)
        self.assertNotEqual(key1, key2)

    def test_filter_order_does_not_affect_key(self):
        """Filters are sorted, so order shouldn't matter."""
        key1 = make_search_cache_key('jobs', 'react', {'a': '1', 'b': '2'})
        key2 = make_search_cache_key('jobs', 'react', {'b': '2', 'a': '1'})
        self.assertEqual(key1, key2)

    def test_different_sorts_produce_different_keys(self):
        key1 = make_search_cache_key('jobs', 'react', {}, 1, 'relevance')
        key2 = make_search_cache_key('jobs', 'react', {}, 1, 'date')
        self.assertNotEqual(key1, key2)

    def test_key_starts_with_search_prefix(self):
        key = make_search_cache_key('jobs', 'react', {})
        self.assertTrue(key.startswith('search:jobs:'))

    def test_key_is_deterministic_across_invocations(self):
        """Multiple calls with identical input always yield the same key."""
        keys = [make_search_cache_key('talent', 'dev', {'location': 'NYC'}, 3) for _ in range(50)]
        self.assertEqual(len(set(keys)), 1)


# ─── Unit Tests: Cache Layer ─────────────────────────────────────────────────

class CacheLayerTests(TestCase):
    """Test Redis cache operations (using LocMemCache in tests)."""

    def test_version_starts_at_1(self):
        version = get_entity_version('test_entity_init')
        self.assertEqual(version, 1)

    def test_bump_version_increments(self):
        get_entity_version('test_bump')
        new = bump_entity_version('test_bump')
        self.assertEqual(new, 2)

    def test_double_bump(self):
        get_entity_version('test_double')
        bump_entity_version('test_double')
        third = bump_entity_version('test_double')
        self.assertEqual(third, 3)

    def test_cache_set_and_get(self):
        set_cached_results('test_key_sg', 'jobs', {'data': 'test'})
        result = get_cached_results('test_key_sg', 'jobs')
        self.assertEqual(result, {'data': 'test'})

    def test_cache_miss_returns_none(self):
        result = get_cached_results('nonexistent_key_xyz', 'jobs')
        self.assertIsNone(result)

    def test_invalidation_busts_cache(self):
        set_cached_results('test_inv_key', 'jobs', {'data': 'old'})
        invalidate_entity_cache('jobs')
        result = get_cached_results('test_inv_key', 'jobs')
        self.assertIsNone(result)

    def test_invalidation_only_affects_own_entity(self):
        """Invalidating 'jobs' should not bust 'talent' cache."""
        set_cached_results('shared_key', 'talent', {'data': 'talent_data'})
        invalidate_entity_cache('jobs')
        result = get_cached_results('shared_key', 'talent')
        self.assertEqual(result, {'data': 'talent_data'})

    def test_suggestions_cache_roundtrip(self):
        suggestions = [{'text': 'react', 'entity_type': 'job'}]
        set_cached_suggestions('rea', 'jobs', suggestions)
        result = get_cached_suggestions('rea', 'jobs')
        self.assertEqual(result, suggestions)

    def test_trending_cache_roundtrip(self):
        trending = [{'query': 'react', 'count': 10, 'entity_type': 'all'}]
        set_cached_trending('all', trending)
        result = get_cached_trending('all')
        self.assertEqual(result, trending)


# ─── Integration Tests: Job Search API ───────────────────────────────────────

class JobSearchAPITests(TestCase):
    """
    Integration tests for /api/v1/search/jobs/.

    On SQLite: search_jobs/search_talent/search_companies are mocked with
    icontains fallback. On PostgreSQL: full-text + trigram runs natively.
    """

    def setUp(self):
        self.client = APIClient()
        self.company_user, self.company_profile = create_company_user()
        self.talent_user, self.talent_profile = create_talent_user()

        self.job1 = create_job(
            self.company_user, title='Senior React Developer',
            job_type='full_time', work_mode='remote',
            experience_level='senior', salary_min=120000, salary_max=180000,
            location='San Francisco', skills_required=['react', 'typescript'],
        )
        self.job2 = create_job(
            self.company_user, title='Junior Python Engineer',
            job_type='contract', work_mode='on_site',
            experience_level='junior', salary_min=60000, salary_max=80000,
            location='New York', skills_required=['python', 'django'],
        )
        self.job3 = create_job(
            self.company_user, title='Mid-Level Data Scientist',
            job_type='full_time', work_mode='hybrid',
            experience_level='mid', salary_min=100000, salary_max=140000,
            location='London', skills_required=['python', 'tensorflow', 'sql'],
        )
        self._patches = _search_patches()
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()

    def test_no_query_returns_all_open(self):
        """Search with no query should return all open jobs."""
        response = self.client.get('/api/v1/search/jobs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('results', data)
        self.assertEqual(len(data['results']), 3)

    def test_query_param_filters_results(self):
        """Search with q= should narrow results."""
        response = self.client.get('/api/v1/search/jobs/', {'q': 'react'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('results', data)
        self.assertIn('search_meta', data)
        self.assertEqual(data['search_meta']['query'], 'react')

    def test_filter_job_type(self):
        response = self.client.get('/api/v1/search/jobs/', {'job_type': 'contract'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json()['results']
        for r in results:
            self.assertEqual(r['job_type'], 'contract')

    def test_filter_work_mode(self):
        response = self.client.get('/api/v1/search/jobs/', {'work_mode': 'remote'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json()['results']
        for r in results:
            self.assertEqual(r['work_mode'], 'remote')

    def test_filter_experience_level(self):
        response = self.client.get('/api/v1/search/jobs/', {'experience_level': 'senior'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json()['results']
        for r in results:
            self.assertEqual(r['experience_level'], 'senior')

    def test_filter_salary_range(self):
        """Salary overlap filter: jobs whose range intersects [100k, 150k]."""
        response = self.client.get('/api/v1/search/jobs/', {
            'salary_min': '100000', 'salary_max': '150000',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [r['id'] for r in response.json()['results']]
        self.assertIn(self.job1.id, ids)   # 120k–180k overlaps
        self.assertIn(self.job3.id, ids)   # 100k–140k overlaps
        self.assertNotIn(self.job2.id, ids)  # 60k–80k outside

    def test_filter_multiple_and_logic(self):
        """Multiple filters = AND."""
        response = self.client.get('/api/v1/search/jobs/', {
            'job_type': 'full_time', 'work_mode': 'remote',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json()['results']
        for r in results:
            self.assertEqual(r['job_type'], 'full_time')
            self.assertEqual(r['work_mode'], 'remote')

    def test_sort_by_date(self):
        response = self.client.get('/api/v1/search/jobs/', {'sort': 'date'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json()['results']
        dates = [r['created_at'] for r in results]
        self.assertEqual(dates, sorted(dates, reverse=True))

    def test_closed_jobs_excluded(self):
        self.job1.status = 'closed'
        self.job1.save()
        response = self.client.get('/api/v1/search/jobs/')
        ids = [r['id'] for r in response.json()['results']]
        self.assertNotIn(self.job1.id, ids)

    def test_search_meta_present(self):
        response = self.client.get('/api/v1/search/jobs/', {'q': 'developer'})
        data = response.json()
        self.assertIn('search_meta', data)
        self.assertIn('response_time_ms', data['search_meta'])
        self.assertIn('query', data['search_meta'])
        self.assertIn('sort', data['search_meta'])

    def test_serializer_fields_complete(self):
        """Every result should include the key serializer fields."""
        response = self.client.get('/api/v1/search/jobs/')
        results = response.json()['results']
        self.assertGreater(len(results), 0)
        required_fields = {
            'id', 'title', 'job_type', 'work_mode',
            'experience_level', 'location', 'salary_min', 'salary_max',
            'company_name', 'rank', 'created_at',
        }
        for r in results:
            self.assertTrue(required_fields.issubset(r.keys()), f'Missing fields: {required_fields - r.keys()}')

    def test_match_score_for_authenticated_talent(self):
        """Authenticated talent should see match_score."""
        self.client.force_authenticate(user=self.talent_user)
        response = self.client.get('/api/v1/search/jobs/')
        results = response.json()['results']
        for r in results:
            self.assertIn('match_score', r)

    def test_match_score_zero_for_unauthenticated(self):
        """Anonymous users should see match_score = 0."""
        response = self.client.get('/api/v1/search/jobs/')
        results = response.json()['results']
        for r in results:
            self.assertEqual(r['match_score'], 0)

    def test_analytics_logged_on_search(self):
        """Each search request should create a SearchAnalytics entry."""
        self.client.get('/api/v1/search/jobs/', {'q': 'react developer'})
        self.assertTrue(
            SearchAnalytics.objects.filter(normalized_query='react developer').exists()
        )

    def test_cached_response_served(self):
        """Second identical request should be served from cache."""
        resp1 = self.client.get('/api/v1/search/jobs/', {'q': 'react'})
        resp2 = self.client.get('/api/v1/search/jobs/', {'q': 'react'})
        self.assertEqual(resp1.json(), resp2.json())


# ─── Integration Tests: Talent Search Permissions ────────────────────────────

class TalentSearchPermissionTests(TestCase):
    """Tests for /api/v1/search/talent/ role-based access control."""

    def setUp(self):
        self.client = APIClient()
        self.company_user, _ = create_company_user()
        self.talent_user, _ = create_talent_user()
        self.admin_user = User.objects.create_user(
            email='admin@test.com', password='testpass123',
            full_name='Admin User', role='ADMIN', is_verified=True,
            is_staff=True, is_superuser=True,
        )
        self._patches = _search_patches()
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()

    def test_requires_auth(self):
        response = self.client.get('/api/v1/search/talent/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_denied_for_talent_role(self):
        self.client.force_authenticate(user=self.talent_user)
        response = self.client.get('/api/v1/search/talent/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_allowed_for_company(self):
        self.client.force_authenticate(user=self.company_user)
        response = self.client.get('/api/v1/search/talent/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_allowed_for_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get('/api/v1/search/talent/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_talent_results_have_correct_fields(self):
        self.client.force_authenticate(user=self.company_user)
        response = self.client.get('/api/v1/search/talent/')
        results = response.json()['results']
        self.assertGreater(len(results), 0)
        required = {'id', 'full_name', 'bio', 'skills', 'is_open_to_work', 'rank'}
        for r in results:
            self.assertTrue(required.issubset(r.keys()), f'Missing: {required - r.keys()}')


# ─── Integration Tests: Company Search (public) ──────────────────────────────

class CompanySearchAPITests(TestCase):
    """Tests for /api/v1/search/companies/ (public endpoint)."""

    def setUp(self):
        self.client = APIClient()
        self.company_user, self.company_profile = create_company_user()
        self._patches = _search_patches()
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()

    def test_public_no_auth_required(self):
        response = self.client.get('/api/v1/search/companies/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_returns_company_results(self):
        response = self.client.get('/api/v1/search/companies/')
        data = response.json()
        self.assertIn('results', data)
        self.assertGreaterEqual(len(data['results']), 1)

    def test_company_result_fields(self):
        response = self.client.get('/api/v1/search/companies/')
        results = response.json()['results']
        required = {'id', 'legal_name', 'industry', 'rank'}
        for r in results:
            self.assertTrue(required.issubset(r.keys()))


# ─── Integration Tests: Unified Search ───────────────────────────────────────

class UnifiedSearchAPITests(TestCase):
    """Tests for /api/v1/search/ (cross-entity search)."""

    def setUp(self):
        self.client = APIClient()
        self.company_user, _ = create_company_user()
        self.talent_user, _ = create_talent_user()
        create_job(self.company_user, title='React Developer')
        self._patches = _search_patches()
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()

    def test_no_query_returns_empty(self):
        response = self.client.get('/api/v1/search/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()['results']), 0)

    def test_returns_typed_results(self):
        response = self.client.get('/api/v1/search/', {'q': 'tech'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('results', data)
        self.assertIn('search_meta', data)
        for r in data['results']:
            self.assertIn('entity_type', r)
            self.assertIn('title', r)
            self.assertIn('rank', r)

    def test_entity_type_filter(self):
        """entity_type=jobs should only return job results."""
        response = self.client.get('/api/v1/search/', {'q': 'react', 'entity_type': 'jobs'})
        data = response.json()
        for r in data['results']:
            self.assertEqual(r['entity_type'], 'job')

    def test_search_meta_includes_total(self):
        response = self.client.get('/api/v1/search/', {'q': 'tech'})
        meta = response.json()['search_meta']
        self.assertIn('total', meta)
        self.assertIn('entity_type', meta)
        self.assertIn('response_time_ms', meta)


# ─── Integration Tests: Autocomplete ─────────────────────────────────────────

class AutocompleteAPITests(TestCase):
    """Tests for /api/v1/search/autocomplete/."""

    def setUp(self):
        self.client = APIClient()
        self.company_user, _ = create_company_user()
        create_job(self.company_user, title='Senior React Developer')
        create_job(self.company_user, title='Senior Python Engineer')

    def test_min_length_enforced(self):
        """Single char should return empty suggestions."""
        response = self.client.get('/api/v1/search/autocomplete/', {'q': 'r'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()['suggestions']), 0)

    def test_empty_query_returns_empty(self):
        response = self.client.get('/api/v1/search/autocomplete/', {'q': ''})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()['suggestions']), 0)

    def test_prefix_returns_suggestions(self):
        response = self.client.get('/api/v1/search/autocomplete/', {'q': 'senior'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        suggestions = response.json()['suggestions']
        self.assertGreater(len(suggestions), 0)
        for s in suggestions:
            self.assertIn('text', s)
            self.assertIn('entity_type', s)

    def test_suggestions_contain_matching_text(self):
        response = self.client.get('/api/v1/search/autocomplete/', {'q': 'senior'})
        suggestions = response.json()['suggestions']
        for s in suggestions:
            self.assertIn('senior', s['text'].lower())

    def test_max_8_suggestions(self):
        """Create many jobs; autocomplete should return at most 8."""
        for i in range(20):
            create_job(self.company_user, title=f'Senior Engineer #{i}')
        response = self.client.get('/api/v1/search/autocomplete/', {'q': 'senior'})
        self.assertLessEqual(len(response.json()['suggestions']), 8)

    def test_cached_on_second_call(self):
        """Second identical call should be served from cache."""
        self.client.get('/api/v1/search/autocomplete/', {'q': 'senior'})
        resp2 = self.client.get('/api/v1/search/autocomplete/', {'q': 'senior'})
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)


# ─── Integration Tests: Trending ─────────────────────────────────────────────

class TrendingSearchesAPITests(TestCase):
    """Tests for /api/v1/search/trending/."""

    def setUp(self):
        self.client = APIClient()

    def test_empty_initially(self):
        response = self.client.get('/api/v1/search/trending/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('trending', response.json())
        self.assertEqual(len(response.json()['trending']), 0)

    def test_popular_queries_appear(self):
        for _ in range(5):
            SearchAnalytics.objects.create(
                query='react developer', entity_type='jobs', results_count=10,
            )
        for _ in range(3):
            SearchAnalytics.objects.create(
                query='python engineer', entity_type='jobs', results_count=8,
            )
        response = self.client.get('/api/v1/search/trending/')
        trending = response.json()['trending']
        queries = [t['query'] for t in trending]
        self.assertIn('react developer', queries)
        self.assertIn('python engineer', queries)

    def test_trending_ordered_by_count(self):
        for _ in range(10):
            SearchAnalytics.objects.create(query='top query', entity_type='jobs', results_count=5)
        for _ in range(2):
            SearchAnalytics.objects.create(query='low query', entity_type='jobs', results_count=5)
        response = self.client.get('/api/v1/search/trending/')
        trending = response.json()['trending']
        if len(trending) >= 2:
            self.assertGreaterEqual(trending[0]['count'], trending[1]['count'])

    def test_zero_result_queries_excluded(self):
        """Queries that returned 0 results should NOT trend."""
        for _ in range(20):
            SearchAnalytics.objects.create(
                query='nothing found', entity_type='jobs', results_count=0,
            )
        response = self.client.get('/api/v1/search/trending/')
        queries = [t['query'] for t in response.json()['trending']]
        self.assertNotIn('nothing found', queries)


# ─── Integration Tests: Click Analytics ──────────────────────────────────────

class SearchClickAPITests(TestCase):
    """Tests for POST /api/v1/search/click/."""

    def setUp(self):
        self.client = APIClient()

    def test_record_click_creates_entry(self):
        response = self.client.post('/api/v1/search/click/', {
            'query': 'react', 'entity_type': 'jobs',
            'result_id': 1, 'position': 3,
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(SearchAnalytics.objects.filter(query='react').exists())

    def test_click_updates_existing_analytics(self):
        """If a matching recent search exists, update it instead of creating new."""
        SearchAnalytics.objects.create(
            query='react', entity_type='jobs', results_count=5,
        )
        self.client.post('/api/v1/search/click/', {
            'query': 'react', 'entity_type': 'jobs',
            'result_id': 42, 'position': 1,
        })
        entry = SearchAnalytics.objects.filter(query='react').order_by('-created_at').first()
        self.assertEqual(entry.clicked_result_id, 42)
        self.assertEqual(entry.clicked_position, 1)

    def test_invalid_entity_type_returns_400(self):
        response = self.client.post('/api/v1/search/click/', {
            'query': 'react', 'entity_type': 'invalid',
            'result_id': 1, 'position': 1,
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_required_fields_returns_400(self):
        response = self.client.post('/api/v1/search/click/', {'query': 'react'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_position_must_be_positive(self):
        response = self.client.post('/api/v1/search/click/', {
            'query': 'react', 'entity_type': 'jobs',
            'result_id': 1, 'position': 0,
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ─── Edge Cases & Security ───────────────────────────────────────────────────

class SearchEdgeCaseTests(TestCase):
    """Test edge cases, input sanitization, and security."""

    def setUp(self):
        self.client = APIClient()
        self.company_user, _ = create_company_user()
        create_job(self.company_user, title='Normal Job')
        self._patches = _search_patches()
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()

    def test_empty_query_string(self):
        response = self.client.get('/api/v1/search/jobs/', {'q': ''})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_whitespace_only_query(self):
        response = self.client.get('/api/v1/search/jobs/', {'q': '   '})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_very_long_query_truncated_safely(self):
        long_q = 'a' * 600
        response = self.client.get('/api/v1/search/jobs/', {'q': long_q})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_sql_injection_payloads(self):
        payloads = [
            "'; DROP TABLE jobs;--",
            "1 OR 1=1",
            "' UNION SELECT * FROM accounts_user --",
            "Robert'); DROP TABLE students;--",
        ]
        for payload in payloads:
            response = self.client.get('/api/v1/search/jobs/', {'q': payload})
            self.assertEqual(
                response.status_code, status.HTTP_200_OK,
                f'SQL injection payload caused non-200: {payload}'
            )

    def test_xss_payloads(self):
        payloads = [
            '<script>alert(1)</script>',
            '<img src=x onerror=alert(1)>',
            'javascript:alert(1)',
        ]
        for payload in payloads:
            response = self.client.get('/api/v1/search/jobs/', {'q': payload})
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            # Verify the raw script tag is NOT reflected unescaped in JSON
            body = response.content.decode()
            self.assertNotIn('<script>', body)

    def test_unicode_queries(self):
        for query in ['日本語テスト', 'développeur', '你好世界', '🔥 python dev']:
            response = self.client.get('/api/v1/search/jobs/', {'q': query})
            self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_invalid_salary_filter_ignored(self):
        response = self.client.get('/api/v1/search/jobs/', {'salary_min': 'not_a_number'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_invalid_sort_defaults_gracefully(self):
        response = self.client.get('/api/v1/search/jobs/', {'sort': 'hacker_sort'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_negative_page_does_not_crash(self):
        response = self.client.get('/api/v1/search/jobs/', {'page': '-1'})
        # Should either return 200 with results or 404 (invalid page)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])


# ─── Model Tests: SearchAnalytics ────────────────────────────────────────────

class SearchAnalyticsModelTests(TestCase):
    """Test the SearchAnalytics model behavior."""

    def test_normalized_query_auto_set(self):
        entry = SearchAnalytics.objects.create(
            query='  React Developer  ', entity_type='jobs', results_count=5,
        )
        self.assertEqual(entry.normalized_query, 'react developer')

    def test_normalized_query_lowercase(self):
        entry = SearchAnalytics.objects.create(
            query='PYTHON DJANGO', entity_type='jobs', results_count=3,
        )
        self.assertEqual(entry.normalized_query, 'python django')

    def test_str_representation(self):
        entry = SearchAnalytics(query='python', entity_type='jobs', results_count=10)
        s = str(entry)
        self.assertIn('python', s)
        self.assertIn('10', s)

    def test_ordering_newest_first(self):
        SearchAnalytics.objects.create(query='first', entity_type='jobs', results_count=1)
        SearchAnalytics.objects.create(query='second', entity_type='jobs', results_count=1)
        entries = list(SearchAnalytics.objects.all())
        self.assertEqual(entries[0].query, 'second')

    def test_user_nullable(self):
        """Anonymous searches should save with user=None."""
        entry = SearchAnalytics.objects.create(
            query='anon search', entity_type='jobs', results_count=2,
        )
        self.assertIsNone(entry.user)

    def test_user_linked(self):
        user, _ = create_talent_user()
        entry = SearchAnalytics.objects.create(
            query='talent search', entity_type='jobs', results_count=3, user=user,
        )
        self.assertEqual(entry.user, user)

    def test_filters_applied_stored_as_json(self):
        filters = {'job_type': 'full_time', 'location': 'NYC'}
        entry = SearchAnalytics.objects.create(
            query='test', entity_type='jobs', results_count=1,
            filters_applied=filters,
        )
        entry.refresh_from_db()
        self.assertEqual(entry.filters_applied, filters)

    def test_entity_type_choices(self):
        """All defined entity types should be valid."""
        for choice_val, _ in SearchAnalytics.EntityType.choices:
            entry = SearchAnalytics.objects.create(
                query=f'test_{choice_val}', entity_type=choice_val, results_count=0,
            )
            self.assertEqual(entry.entity_type, choice_val)
