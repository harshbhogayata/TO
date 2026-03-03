"""
intelligence/models.py
All Phase 5 data models — Recommendation Engine, Resume Parser, Analytics, A/B Testing.
"""

from django.conf import settings
from django.db import models


# ═══════════════════════════════════════════════════════════════════════════════
#  RECOMMENDATION ENGINE MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class SkillTaxonomy(models.Model):
    """
    Canonical skill names with aliases/synonyms for normalisation.
    Used by the TF-IDF vectoriser, resume parser, and autocomplete.
    """
    canonical_name = models.CharField(max_length=100, unique=True, db_index=True)
    category = models.CharField(
        max_length=100, blank=True, db_index=True,
        help_text='e.g. Programming, Design, Management',
    )
    aliases = models.JSONField(
        default=list,
        help_text='Alternative names: ["React.js", "ReactJS"]',
    )
    embedding_vector = models.BinaryField(
        null=True, blank=True,
        help_text='Serialised numpy array for vector search',
    )
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='children',
        help_text='Parent skill for hierarchical taxonomy',
    )
    related_skills = models.ManyToManyField(
        'self', blank=True, symmetrical=True,
        help_text='Frequently co-occurring skills',
    )
    proficiency_levels = models.JSONField(
        default=list, blank=True,
        help_text='Proficiency descriptors: [{level, label, description}]',
    )
    is_verified = models.BooleanField(default=True)
    usage_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Skill Taxonomy'
        verbose_name_plural = 'Skill Taxonomy'
        ordering = ['-usage_count', 'canonical_name']

    def __str__(self):
        return f'{self.canonical_name} ({self.category})'


class UserInteraction(models.Model):
    """Tracks all user-job interactions for collaborative filtering."""

    class InteractionType(models.TextChoices):
        VIEW = 'view', 'Viewed'
        CLICK = 'click', 'Search Click'
        SAVE = 'save', 'Saved'
        APPLY = 'apply', 'Applied'
        UNSAVE = 'unsave', 'Unsaved'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='intelligence_interactions',
    )
    job = models.ForeignKey(
        'jobs.JobPost', on_delete=models.CASCADE,
        related_name='intelligence_interactions',
    )
    interaction_type = models.CharField(
        max_length=20, choices=InteractionType.choices, db_index=True,
    )
    weight = models.FloatField(default=1.0)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(
                fields=['user', 'job', 'interaction_type'],
                name='idx_intel_user_job_type',
            ),
            models.Index(
                fields=['user', '-created_at'],
                name='idx_intel_user_date',
            ),
            models.Index(
                fields=['job', 'interaction_type'],
                name='idx_intel_job_type',
            ),
        ]
        verbose_name = 'User Interaction'

    def __str__(self):
        return f'{self.user_id} → {self.job_id} ({self.interaction_type})'


class RecommendationLog(models.Model):
    """Audit log for recommendation requests — enables offline evaluation."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='recommendation_logs',
    )
    recommended_jobs = models.JSONField(default=list)
    algorithm_version = models.CharField(max_length=50)
    weights_used = models.JSONField(default=dict)
    latency_ms = models.PositiveIntegerField()
    cache_hit = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Recommendation Log'
        ordering = ['-created_at']

    def __str__(self):
        return f'Recs for {self.user_id} @ {self.created_at:%Y-%m-%d %H:%M}'


class ModelArtifact(models.Model):
    """Stores trained ML model artifacts (TF-IDF vectoriser, interaction matrix, etc.)."""
    name = models.CharField(max_length=100)
    version = models.PositiveIntegerField(default=1)
    artifact_data = models.BinaryField()
    metadata = models.JSONField(default=dict)
    trained_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('name', 'version')
        verbose_name = 'Model Artifact'
        ordering = ['-version']

    def __str__(self):
        return f'{self.name} v{self.version} ({"active" if self.is_active else "inactive"})'


# ═══════════════════════════════════════════════════════════════════════════════
#  RESUME PARSER MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class ParsedResume(models.Model):
    """Stores the result of NLP-based resume parsing. One per user, updated on re-upload."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='parsed_resume',
    )
    raw_text = models.TextField(blank=True)
    parsed_skills = models.JSONField(
        default=list,
        help_text='[{name, canonical_name, confidence, source}]',
    )
    parsed_experience = models.JSONField(
        default=list,
        help_text='[{title, company, start, end, months, description}]',
    )
    parsed_education = models.JSONField(
        default=list,
        help_text='[{degree, institution, field, year}]',
    )
    total_experience_years = models.FloatField(null=True, blank=True)
    generated_bio = models.TextField(blank=True, max_length=500)
    contact_info = models.JSONField(default=dict, blank=True)
    parser_version = models.CharField(max_length=50, default='spacy_v1')
    confidence_score = models.FloatField(default=0.0)
    parsed_at = models.DateTimeField(auto_now=True)
    source_file_hash = models.CharField(max_length=64, blank=True)

    class Meta:
        verbose_name = 'Parsed Resume'

    def __str__(self):
        return f'Resume for {self.user_id} (v{self.parser_version})'


# ═══════════════════════════════════════════════════════════════════════════════
#  ANALYTICS / DATA WAREHOUSE MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class HiringFunnelSnapshot(models.Model):
    """
    Pre-aggregated daily snapshot of hiring funnel metrics per company.
    Computed by ETL task.  Enables fast O(1) dashboard queries.
    """

    class Period(models.TextChoices):
        DAILY = 'daily', 'Daily'
        WEEKLY = 'weekly', 'Weekly'
        MONTHLY = 'monthly', 'Monthly'

    company = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='funnel_snapshots',
    )
    job = models.ForeignKey(
        'jobs.JobPost', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='funnel_snapshots',
        help_text='NULL = aggregate for all company jobs',
    )
    date = models.DateField(db_index=True)
    period = models.CharField(
        max_length=10, choices=Period.choices, default='daily',
    )

    views = models.PositiveIntegerField(default=0)
    applications = models.PositiveIntegerField(default=0)
    reviewing = models.PositiveIntegerField(default=0)
    shortlisted = models.PositiveIntegerField(default=0)
    interviewing = models.PositiveIntegerField(default=0)
    offered = models.PositiveIntegerField(default=0)
    rejected = models.PositiveIntegerField(default=0)
    withdrawn = models.PositiveIntegerField(default=0)

    avg_time_to_review_hours = models.FloatField(null=True, blank=True)
    avg_time_to_shortlist_hours = models.FloatField(null=True, blank=True)
    avg_time_to_offer_hours = models.FloatField(null=True, blank=True)
    avg_time_to_hire_hours = models.FloatField(null=True, blank=True)
    avg_match_score = models.FloatField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('company', 'job', 'date', 'period')
        indexes = [
            models.Index(
                fields=['company', '-date', 'period'],
                name='idx_funnel_company_date',
            ),
            models.Index(
                fields=['job', '-date'],
                name='idx_funnel_job_date',
            ),
        ]
        verbose_name = 'Hiring Funnel Snapshot'
        ordering = ['-date']

    def __str__(self):
        job_label = f'Job #{self.job_id}' if self.job_id else 'All jobs'
        return f'{self.company_id} | {job_label} | {self.date} ({self.period})'


class SourceAttribution(models.Model):
    """Tracks how users discovered a job post."""

    class Source(models.TextChoices):
        DIRECT = 'direct', 'Direct (Job Board)'
        SEARCH = 'search', 'Search'
        RECOMMENDATION = 'recommendation', 'Recommendation Engine'
        EXTERNAL = 'external', 'External Referral'
        NOTIFICATION = 'notification', 'Notification'

    job = models.ForeignKey(
        'jobs.JobPost', on_delete=models.CASCADE,
        related_name='source_attributions',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    source = models.CharField(
        max_length=20, choices=Source.choices, db_index=True,
    )
    search_query = models.CharField(max_length=500, blank=True)
    converted_to_application = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(
                fields=['job', 'source', '-created_at'],
                name='idx_source_job_src_date',
            ),
        ]
        verbose_name = 'Source Attribution'

    def __str__(self):
        return f'{self.job_id} ← {self.source}'


class PlatformBenchmark(models.Model):
    """Platform-wide benchmark metrics computed periodically."""
    metric_name = models.CharField(max_length=100, db_index=True)
    industry = models.CharField(max_length=150, blank=True, db_index=True)
    value = models.FloatField()
    sample_size = models.PositiveIntegerField(default=0)
    period_start = models.DateField()
    period_end = models.DateField()
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('metric_name', 'industry', 'period_start')
        verbose_name = 'Platform Benchmark'

    def __str__(self):
        industry_label = self.industry or 'All'
        return f'{self.metric_name} ({industry_label}): {self.value}'


class DailyPlatformMetrics(models.Model):
    """Daily platform-wide metrics for admin dashboard and investor reporting."""
    date = models.DateField(unique=True, db_index=True)

    # User metrics
    total_users = models.PositiveIntegerField(default=0)
    new_users = models.PositiveIntegerField(default=0)
    active_users_1d = models.PositiveIntegerField(default=0)
    active_users_7d = models.PositiveIntegerField(default=0)
    active_users_30d = models.PositiveIntegerField(default=0)
    talent_count = models.PositiveIntegerField(default=0)
    company_count = models.PositiveIntegerField(default=0)

    # Job metrics
    total_open_jobs = models.PositiveIntegerField(default=0)
    new_jobs_posted = models.PositiveIntegerField(default=0)
    jobs_closed = models.PositiveIntegerField(default=0)

    # Application metrics
    total_applications = models.PositiveIntegerField(default=0)
    new_applications = models.PositiveIntegerField(default=0)
    offers_extended = models.PositiveIntegerField(default=0)

    # Engagement metrics
    total_messages_sent = models.PositiveIntegerField(default=0)
    total_searches = models.PositiveIntegerField(default=0)
    avg_search_results = models.FloatField(null=True, blank=True)
    total_recommendation_requests = models.PositiveIntegerField(default=0)
    avg_recommendation_ctr = models.FloatField(null=True, blank=True)

    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        verbose_name = 'Daily Platform Metrics'
        verbose_name_plural = 'Daily Platform Metrics'

    def __str__(self):
        return f'Platform metrics {self.date}'
