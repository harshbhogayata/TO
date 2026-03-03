"""
search/models.py
Search analytics model for tracking user search behavior.
Provides data foundation for future recommendation engine.
"""
from django.conf import settings
from django.db import models


class SearchAnalytics(models.Model):
    """
    Tracks every search query executed on the platform.
    Captures what users search for, which results they click,
    and the position of clicked results — enabling CTR analysis,
    trending topics, and future ML-based ranking improvements.
    """

    class EntityType(models.TextChoices):
        JOBS = 'jobs', 'Jobs'
        TALENT = 'talent', 'Talent Profiles'
        COMPANIES = 'companies', 'Companies'
        ALL = 'all', 'Unified Search'

    query = models.CharField(
        max_length=500,
        db_index=True,
        help_text='The raw search query entered by the user.',
    )
    normalized_query = models.CharField(
        max_length=500,
        db_index=True,
        blank=True,
        help_text='Lowercased, stripped query for aggregation.',
    )
    entity_type = models.CharField(
        max_length=20,
        choices=EntityType.choices,
        default=EntityType.ALL,
        db_index=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='search_queries',
        help_text='Null for anonymous searches.',
    )
    results_count = models.PositiveIntegerField(
        default=0,
        help_text='Number of results returned for this query.',
    )
    clicked_result_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='PK of the result the user clicked on.',
    )
    clicked_position = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text='1-based position of the clicked result in the list.',
    )
    filters_applied = models.JSONField(
        default=dict,
        blank=True,
        help_text='Snapshot of active filters at search time.',
    )
    response_time_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Server-side response time in milliseconds.',
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Search Query'
        verbose_name_plural = 'Search Queries'
        ordering = ['-created_at']
        indexes = [
            models.Index(
                fields=['normalized_query', '-created_at'],
                name='idx_search_norm_query_date',
            ),
            models.Index(
                fields=['entity_type', '-created_at'],
                name='idx_search_entity_date',
            ),
            models.Index(
                fields=['user', '-created_at'],
                name='idx_search_user_date',
            ),
        ]

    def __str__(self):
        return f'"{self.query}" ({self.entity_type}) → {self.results_count} results'

    def save(self, *args, **kwargs):
        if not self.normalized_query:
            self.normalized_query = self.query.strip().lower()
        super().save(*args, **kwargs)
