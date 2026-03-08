"""
intelligence/serializers.py
DRF serializers for the Intelligence API layer.

Every serializer's field list exactly matches the data its corresponding view
provides.  Where views return plain dicts (analytics aggregators), we use
``serializers.Serializer`` with explicit fields.  Where views return model
instances, we use ``serializers.ModelSerializer``.

Bug-fix log (Phase 5 audit):
  - ParsedResumeSerializer: replaced non-existent ``created_at``/``updated_at``
    with model's ``parsed_at`` field.
  - MatchScoreResponseSerializer: aligned with ``compute_match_score()`` return.
  - HiringFunnelSerializer: aligned with ``compute_funnel_for_company()`` return.
  - TimeToHireSerializer: ``stage_transition`` → ``stage``, removed ``avg_days``.
  - SourceAttributionSerializer: aligned with ``compute_source_attribution()`` return.
  - TalentPoolSerializer: ``location_distribution`` → ``locations``.
  - OverviewMetricsSerializer: aligned with ``compute_overview_metrics()`` return.
  - JobPerformanceSerializer: aligned with ``get_job_performance_table()`` return.
  - PlatformGrowthSerializer: ``new_jobs`` → ``new_jobs_posted``.
  - PlatformEngagementSerializer: aligned with actual DailyPlatformMetrics fields.
"""

from rest_framework import serializers

from jobs.models import JobPost

from .models import (
    DailyPlatformMetrics,
    ParsedResume,
    PlatformBenchmark,
    SkillTaxonomy,
    UserInteraction,
)


# ──────────────────────────────────────────────────────────────────────────────
# Recommendation engine
# ──────────────────────────────────────────────────────────────────────────────

class RecommendationJobSerializer(serializers.ModelSerializer):
    """Compact job representation embedded inside a recommendation response."""
    company_name = serializers.SerializerMethodField()
    company_logo = serializers.SerializerMethodField()
    salary_display = serializers.ReadOnlyField()

    class Meta:
        model = JobPost
        fields = (
            'id', 'title', 'location', 'job_type', 'work_mode',
            'experience_level', 'skills_required',
            'salary_min', 'salary_max', 'salary_currency', 'salary_display',
            'views_count', 'company_name', 'company_logo', 'created_at',
        )

    def get_company_name(self, obj):
        try:
            return obj.company.company_profile.legal_name
        except Exception:
            return obj.company.full_name

    def get_company_logo(self, obj):
        try:
            logo = obj.company.company_profile.logo
            if logo:
                request = self.context.get('request')
                return request.build_absolute_uri(logo.url) if request else logo.url
        except Exception:
            pass
        return None


class RecommendationItemSerializer(serializers.Serializer):
    """One recommendation inside the response list."""
    job = RecommendationJobSerializer(read_only=True)
    final_score = serializers.FloatField()
    content_score = serializers.FloatField()
    collaborative_score = serializers.FloatField()
    popularity_score = serializers.FloatField()
    freshness_score = serializers.FloatField()
    explanation = serializers.CharField()
    breakdown = serializers.DictField(child=serializers.FloatField(), required=False)


class RecommendationResponseSerializer(serializers.Serializer):
    """Top-level response for GET /recommendations/jobs/."""
    recommendations = RecommendationItemSerializer(many=True)
    algorithm_version = serializers.CharField()
    latency_ms = serializers.FloatField()
    cache_hit = serializers.BooleanField()
    weights = serializers.DictField(child=serializers.FloatField())


class MatchScoreResponseSerializer(serializers.Serializer):
    """
    Response for ``GET /match-score/?job=<id>``.

    Aligned with ``engine.hybrid.compute_match_score()`` return schema::

        {'job_id', 'final_score', 'content_score', 'collaborative_score',
         'explanation', 'breakdown'}
    """
    job_id = serializers.IntegerField()
    final_score = serializers.IntegerField(help_text='0-100 percentage match')
    content_score = serializers.FloatField()
    collaborative_score = serializers.FloatField()
    explanation = serializers.CharField()
    breakdown = serializers.DictField(child=serializers.FloatField(), required=False)


# ──────────────────────────────────────────────────────────────────────────────
# User Interaction
# ──────────────────────────────────────────────────────────────────────────────

class UserInteractionSerializer(serializers.ModelSerializer):
    """Record a user–job interaction (view, click, save, apply, unsave)."""

    class Meta:
        model = UserInteraction
        fields = ('id', 'job', 'interaction_type', 'metadata', 'created_at')
        read_only_fields = ('id', 'created_at')

    def validate_interaction_type(self, value):
        allowed = {'view', 'click', 'save', 'apply', 'unsave'}
        if value not in allowed:
            raise serializers.ValidationError(
                f'Invalid interaction_type. Must be one of: {", ".join(sorted(allowed))}'
            )
        return value

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        # Set weight from constants
        from .constants import INTERACTION_WEIGHTS
        validated_data['weight'] = INTERACTION_WEIGHTS.get(
            validated_data['interaction_type'], 1.0
        )
        return super().create(validated_data)


# ──────────────────────────────────────────────────────────────────────────────
# Resume parser
# ──────────────────────────────────────────────────────────────────────────────

class ParsedResumeSerializer(serializers.ModelSerializer):
    """
    Full parsed resume data (read-only).

    Note: the model uses a single ``parsed_at`` (auto_now) timestamp.
    There is no separate ``created_at``/``updated_at``.
    """
    ai_enhanced = serializers.SerializerMethodField()
    feature_flag_used = serializers.SerializerMethodField()
    cached = serializers.BooleanField(default=False, read_only=True)

    class Meta:
        model = ParsedResume
        fields = (
            'id', 'parsed_skills', 'parsed_experience', 'parsed_education',
            'total_experience_years', 'generated_bio', 'contact_info',
            'confidence_score', 'parser_version', 'source_file_hash',
            'raw_text', 'parsed_at', 'ai_enhanced', 'feature_flag_used', 'cached',
        )
        read_only_fields = fields

    def get_ai_enhanced(self, obj):
        return str(getattr(obj, 'parser_version', '')).startswith('ai_enhanced')

    def get_feature_flag_used(self, obj):
        if self.get_ai_enhanced(obj):
            return 'USE_AI_ENHANCED_RESUME_PARSING'
        return None


class ResumeParseResponseSerializer(serializers.Serializer):
    """Stable resume parsing response used by all parse endpoints."""
    parsed_skills = serializers.ListField(child=serializers.JSONField(), default=list)
    parsed_experience = serializers.ListField(child=serializers.JSONField(), default=list)
    parsed_education = serializers.ListField(child=serializers.JSONField(), default=list)
    total_experience_years = serializers.FloatField(allow_null=True, required=False)
    generated_bio = serializers.CharField(allow_blank=True, default='')
    contact_info = serializers.DictField(default=dict)
    confidence_score = serializers.FloatField(default=0.0)
    parser_version = serializers.CharField(default='spacy_v1')
    source_file_hash = serializers.CharField(required=False, allow_blank=True, default='')
    raw_text = serializers.CharField(required=False, allow_blank=True, default='')
    parsed_at = serializers.DateTimeField(required=False, allow_null=True)
    ai_enhanced = serializers.BooleanField(default=False)
    feature_flag_used = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    cached = serializers.BooleanField(default=False)


def normalise_resume_payload(source, *, cached=None, feature_flag_used=None):
    """Map parser/model output into the canonical resume response contract."""
    if isinstance(source, ParsedResume):
        payload = dict(ParsedResumeSerializer(source).data)
    else:
        payload = {
            'parsed_skills': source.get('parsed_skills', source.get('skills', [])),
            'parsed_experience': source.get('parsed_experience', source.get('experience', [])),
            'parsed_education': source.get('parsed_education', source.get('education', [])),
            'total_experience_years': source.get('total_experience_years'),
            'generated_bio': source.get('generated_bio', source.get('bio', '')),
            'contact_info': source.get('contact_info', source.get('contact', {})),
            'confidence_score': source.get('confidence_score', 0.0),
            'parser_version': source.get('parser_version', 'spacy_v1'),
            'source_file_hash': source.get('source_file_hash', ''),
            'raw_text': source.get('raw_text', ''),
            'parsed_at': source.get('parsed_at'),
            'ai_enhanced': bool(
                source.get('ai_enhanced')
                or str(source.get('parser_version', '')).startswith('ai_enhanced')
            ),
            'feature_flag_used': source.get('feature_flag_used'),
            'cached': source.get('cached', False),
        }

    if cached is not None:
        payload['cached'] = cached

    if feature_flag_used is not None:
        payload['feature_flag_used'] = feature_flag_used
    elif payload.get('ai_enhanced') and not payload.get('feature_flag_used'):
        payload['feature_flag_used'] = 'USE_AI_ENHANCED_RESUME_PARSING'

    return ResumeParseResponseSerializer(payload).data


class ResumeUploadSerializer(serializers.Serializer):
    """Validates the resume upload payload."""
    resume = serializers.FileField(
        help_text='PDF, DOCX, or TXT file (max 10 MB).'
    )

    def validate_resume(self, value):
        max_size = 10 * 1024 * 1024  # 10 MB
        if value.size > max_size:
            raise serializers.ValidationError(
                f'File too large. Maximum size is {max_size // (1024 * 1024)} MB.'
            )

        allowed_types = {
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'text/plain',
        }
        content_type = (getattr(value, 'content_type', '') or '').split(';')[0].strip().lower()
        if content_type and content_type not in allowed_types:
            raise serializers.ValidationError(
                'Unsupported file type. Upload a PDF, DOCX, or TXT file.'
            )

        ext = value.name.rsplit('.', 1)[-1].lower() if value.name else ''
        if ext not in ('pdf', 'docx', 'txt'):
            raise serializers.ValidationError(
                'Unsupported file extension. Use .pdf, .docx, or .txt.'
            )
        return value


class ResumeApplySerializer(serializers.Serializer):
    """Apply parsed resume results to the user's talent profile."""
    skills = serializers.ListField(child=serializers.CharField(), required=False)
    bio = serializers.CharField(required=False, allow_blank=True)


# ──────────────────────────────────────────────────────────────────────────────
# Skill taxonomy
# ──────────────────────────────────────────────────────────────────────────────

class SkillTaxonomySerializer(serializers.ModelSerializer):
    """Read-only skill taxonomy entry."""
    parent_name = serializers.CharField(source='parent.canonical_name', read_only=True, default=None)
    children = serializers.SerializerMethodField()
    related = serializers.SerializerMethodField()

    class Meta:
        model = SkillTaxonomy
        fields = (
            'id', 'canonical_name', 'category', 'aliases',
            'parent', 'parent_name', 'children', 'related',
            'proficiency_levels', 'usage_count', 'is_verified',
        )
        read_only_fields = fields

    def get_children(self, obj):
        children_qs = obj.children.all().order_by('canonical_name')
        return [
            {'id': c.id, 'name': c.canonical_name, 'category': c.category}
            for c in children_qs
        ]

    def get_related(self, obj):
        related_qs = obj.related_skills.all().order_by('canonical_name')[:10]
        return [
            {'id': r.id, 'name': r.canonical_name, 'category': r.category}
            for r in related_qs
        ]


class SkillSuggestionSerializer(serializers.Serializer):
    """Lightweight serializer for skill autocomplete."""
    id = serializers.IntegerField()
    name = serializers.CharField()
    category = serializers.CharField()


# ──────────────────────────────────────────────────────────────────────────────
# Analytics — Company dashboard
# Serializers aligned with ``intelligence.analytics.aggregators`` output.
# ──────────────────────────────────────────────────────────────────────────────

class FunnelStageSerializer(serializers.Serializer):
    """A single stage in the hiring funnel."""
    name = serializers.CharField()
    count = serializers.IntegerField()
    conversion_rate = serializers.FloatField(required=False, default=0.0)


class HiringFunnelSerializer(serializers.Serializer):
    """
    Hiring funnel response from ``compute_funnel_for_company()``.

    Returns a dict, NOT a list — so the view must **not** use ``many=True``::

        {'stages': [...], 'total_views', 'total_applications',
         'rejected', 'withdrawn'}
    """
    stages = FunnelStageSerializer(many=True)
    total_views = serializers.IntegerField()
    total_applications = serializers.IntegerField()
    rejected = serializers.IntegerField(default=0)
    withdrawn = serializers.IntegerField(default=0)


class TimeToHireSerializer(serializers.Serializer):
    """
    Time-to-hire metrics from ``compute_time_to_hire()``.

    Each item has ``stage``, ``avg_hours``, and ``count``.
    """
    stage = serializers.CharField()
    avg_hours = serializers.FloatField()
    count = serializers.IntegerField()


class SourceSerializer(serializers.Serializer):
    """One source in the source attribution breakdown."""
    source = serializers.CharField()
    label = serializers.CharField()
    views = serializers.IntegerField()
    applications = serializers.IntegerField()
    conversion_rate = serializers.FloatField()


class TopQuerySerializer(serializers.Serializer):
    """A single top search query entry."""
    query = serializers.CharField()
    count = serializers.IntegerField()


class SourceAttributionSerializer(serializers.Serializer):
    """
    Source attribution response from ``compute_source_attribution()``.

    Returns a dict with ``sources`` list and ``top_queries`` list.
    """
    sources = SourceSerializer(many=True)
    top_queries = TopQuerySerializer(many=True)


class TalentPoolSerializer(serializers.Serializer):
    """
    Talent pool insights from ``compute_talent_pool()``.

    Keys: ``skills``, ``locations``, ``total_applicants``.
    """
    skills = serializers.ListField(child=serializers.DictField())
    locations = serializers.ListField(child=serializers.DictField())
    total_applicants = serializers.IntegerField()


class OverviewMetricsSerializer(serializers.Serializer):
    """
    High-level company dashboard cards from ``compute_overview_metrics()``.

    Keys: ``total_views``, ``total_applications``, ``application_change``,
    ``active_jobs``, ``total_jobs``.
    """
    total_views = serializers.IntegerField()
    total_applications = serializers.IntegerField()
    application_change = serializers.FloatField(help_text='Percentage change vs previous 30 days')
    active_jobs = serializers.IntegerField()
    total_jobs = serializers.IntegerField()


class JobPerformanceSerializer(serializers.Serializer):
    """
    Per-job performance table row from ``get_job_performance_table()``.

    Each row has: ``id``, ``title``, ``status``, ``views``, ``applications``,
    ``shortlisted``, ``interviewing``, ``offered``, ``days_active``, ``health``.
    """
    id = serializers.IntegerField()
    title = serializers.CharField()
    status = serializers.CharField()
    views = serializers.IntegerField()
    applications = serializers.IntegerField()
    shortlisted = serializers.IntegerField()
    interviewing = serializers.IntegerField()
    offered = serializers.IntegerField()
    days_active = serializers.IntegerField()
    health = serializers.CharField()


class CompanyAnalyticsExportSerializer(serializers.Serializer):
    """Request serializer for CSV/JSON export."""
    format = serializers.ChoiceField(choices=['csv', 'json'], default='json')
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)


# ──────────────────────────────────────────────────────────────────────────────
# Analytics — Admin / Platform
# ──────────────────────────────────────────────────────────────────────────────

class DailyPlatformMetricsSerializer(serializers.ModelSerializer):
    """Daily platform-wide metrics."""

    class Meta:
        model = DailyPlatformMetrics
        fields = '__all__'
        read_only_fields = ('id',)


class PlatformBenchmarkSerializer(serializers.ModelSerializer):
    """Platform benchmark entry."""

    class Meta:
        model = PlatformBenchmark
        fields = '__all__'
        read_only_fields = ('id',)


class PlatformGrowthSerializer(serializers.Serializer):
    """
    Growth metrics for admin dashboard.

    Field names match ``DailyPlatformMetrics`` model column names exactly.
    """
    date = serializers.DateField()
    new_users = serializers.IntegerField()
    new_jobs_posted = serializers.IntegerField()
    new_applications = serializers.IntegerField()


class PlatformEngagementSerializer(serializers.Serializer):
    """
    Engagement metrics for admin dashboard.

    Field names match ``DailyPlatformMetrics`` model column names exactly.
    """
    date = serializers.DateField()
    active_users_1d = serializers.IntegerField()
    active_users_7d = serializers.IntegerField()
    active_users_30d = serializers.IntegerField()
    total_searches = serializers.IntegerField()
    total_messages_sent = serializers.IntegerField()


# ──────────────────────────────────────────────────────────────────────────────
# A/B Testing / Experiments
# ──────────────────────────────────────────────────────────────────────────────

class FeatureFlagsSerializer(serializers.Serializer):
    """All evaluated feature flags for the current user."""
    flags = serializers.DictField(child=serializers.JSONField())


class ExperimentTrackSerializer(serializers.Serializer):
    """Client-side experiment event tracking."""
    event = serializers.CharField(max_length=200)
    properties = serializers.DictField(required=False, default=dict)
    experiment_key = serializers.CharField(max_length=200, required=False)
    variant = serializers.CharField(max_length=100, required=False)

