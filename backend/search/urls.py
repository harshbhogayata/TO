"""
search/urls.py
URL patterns for the Search & Discovery engine.
All endpoints are registered under /api/v1/search/ via talentorbit/urls.py.
"""
from django.urls import path
from .views import (
    UnifiedSearchView,
    JobSearchView,
    TalentSearchView,
    CompanySearchView,
    AutocompleteView,
    TrendingSearchesView,
    record_search_click,
)

app_name = 'search'

urlpatterns = [
    # Unified search across all entities
    path('', UnifiedSearchView.as_view(), name='unified_search'),

    # Entity-specific search
    path('jobs/', JobSearchView.as_view(), name='job_search'),
    path('talent/', TalentSearchView.as_view(), name='talent_search'),
    path('companies/', CompanySearchView.as_view(), name='company_search'),

    # Autocomplete (fast prefix suggestions)
    path('autocomplete/', AutocompleteView.as_view(), name='autocomplete'),

    # Trending searches
    path('trending/', TrendingSearchesView.as_view(), name='trending'),

    # Analytics — record clicks
    path('click/', record_search_click, name='record_click'),
]
