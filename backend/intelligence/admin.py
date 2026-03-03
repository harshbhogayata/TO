"""
intelligence/admin.py
Django admin registrations for the Intelligence layer.
"""
from django.contrib import admin
from .models import (
    SkillTaxonomy,
    UserInteraction,
    RecommendationLog,
    ModelArtifact,
    ParsedResume,
    HiringFunnelSnapshot,
    SourceAttribution,
    PlatformBenchmark,
    DailyPlatformMetrics,
)


@admin.register(SkillTaxonomy)
class SkillTaxonomyAdmin(admin.ModelAdmin):
    list_display = ('canonical_name', 'category', 'parent', 'usage_count', 'is_verified')
    list_filter = ('category', 'is_verified')
    search_fields = ('canonical_name', 'aliases')
    list_editable = ('is_verified', 'category')
    ordering = ('category', 'canonical_name')
    raw_id_fields = ('parent',)
    filter_horizontal = ('related_skills',)


@admin.register(UserInteraction)
class UserInteractionAdmin(admin.ModelAdmin):
    list_display = ('user', 'job', 'interaction_type', 'weight', 'created_at')
    list_filter = ('interaction_type', 'created_at')
    search_fields = ('user__email', 'job__title')
    raw_id_fields = ('user', 'job')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)


@admin.register(RecommendationLog)
class RecommendationLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'algorithm_version', 'latency_ms', 'cache_hit', 'created_at')
    list_filter = ('algorithm_version', 'cache_hit', 'created_at')
    search_fields = ('user__email',)
    raw_id_fields = ('user',)
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)


@admin.register(ModelArtifact)
class ModelArtifactAdmin(admin.ModelAdmin):
    list_display = ('name', 'version', 'is_active', 'trained_at')
    list_filter = ('name', 'is_active')
    search_fields = ('name',)
    list_editable = ('is_active',)
    readonly_fields = ('trained_at',)


@admin.register(ParsedResume)
class ParsedResumeAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'total_experience_years', 'confidence_score',
        'parser_version', 'parsed_at',
    )
    search_fields = ('user__email',)
    raw_id_fields = ('user',)
    readonly_fields = ('parsed_at', 'source_file_hash')


@admin.register(HiringFunnelSnapshot)
class HiringFunnelSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        'company', 'job', 'date', 'period',
        'views', 'applications', 'shortlisted', 'offered',
    )
    list_filter = ('period', 'date')
    search_fields = ('company__email',)
    raw_id_fields = ('company', 'job')
    date_hierarchy = 'date'


@admin.register(SourceAttribution)
class SourceAttributionAdmin(admin.ModelAdmin):
    list_display = ('job', 'user', 'source', 'converted_to_application', 'created_at')
    list_filter = ('source', 'converted_to_application')
    search_fields = ('job__title', 'user__email')
    raw_id_fields = ('job', 'user')
    date_hierarchy = 'created_at'


@admin.register(PlatformBenchmark)
class PlatformBenchmarkAdmin(admin.ModelAdmin):
    list_display = ('metric_name', 'industry', 'value', 'sample_size', 'period_start', 'period_end')
    list_filter = ('metric_name', 'industry')
    search_fields = ('metric_name',)


@admin.register(DailyPlatformMetrics)
class DailyPlatformMetricsAdmin(admin.ModelAdmin):
    list_display = (
        'date', 'active_users_1d', 'new_users', 'new_jobs_posted',
        'new_applications', 'total_open_jobs',
    )
    date_hierarchy = 'date'
    readonly_fields = ('date', 'computed_at')
