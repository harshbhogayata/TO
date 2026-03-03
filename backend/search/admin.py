"""
search/admin.py
Admin registration for the Search & Discovery models.
"""
from django.contrib import admin
from .models import SearchAnalytics


@admin.register(SearchAnalytics)
class SearchAnalyticsAdmin(admin.ModelAdmin):
    list_display = ('query', 'entity_type', 'results_count', 'user', 'response_time_ms', 'created_at')
    list_filter = ('entity_type', 'created_at')
    search_fields = ('query', 'normalized_query')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
