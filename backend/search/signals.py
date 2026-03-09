"""
search/signals.py
Auto-update search vectors on model save and invalidate caches.

Connects to post_save signals for JobPost, TalentProfile, and CompanyProfile.
Updates the stored SearchVectorField and bumps the Redis cache version.
"""
import logging

from django.db import connections
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from accounts.models import CompanyProfile, TalentProfile
from jobs.models import JobPost

from search.cache import invalidate_entity_cache, invalidate_trending_cache
from search.models import SearchAnalytics

logger = logging.getLogger(__name__)


def _supports_postgres_search(using: str | None) -> bool:
    alias = using or 'default'
    return connections[alias].vendor == 'postgresql'


@receiver(post_save, sender=JobPost)
def update_job_search_vector(sender, instance, using=None, **kwargs):
    """
    Recompute the search_vector for a JobPost after save.
    Uses .update() to avoid triggering another post_save (infinite loop).
    """
    if not _supports_postgres_search(using):
        invalidate_entity_cache('jobs')
        return

    from django.contrib.postgres.search import SearchVector
    from django.db.models import Value

    try:
        skills_text = ' '.join(instance.skills_required) if instance.skills_required else ''
        try:
            company_name = instance.company.company_profile.legal_name
        except Exception:
            company_name = instance.company.full_name or ''

        JobPost.objects.filter(pk=instance.pk).update(
            search_vector=(
                SearchVector('title', weight='A', config='english')
                + SearchVector(Value(skills_text), weight='A', config='english')
                + SearchVector('location', weight='B', config='english')
                + SearchVector('description', weight='B', config='english')
                + SearchVector('requirements', weight='C', config='english')
                + SearchVector('responsibilities', weight='C', config='english')
                + SearchVector(Value(company_name), weight='C', config='english')
            )
        )
        invalidate_entity_cache('jobs')
    except Exception:
        logger.exception('Failed to update search vector for JobPost pk=%s', instance.pk)


@receiver(post_delete, sender=JobPost)
def invalidate_job_cache_on_delete(sender, instance, **kwargs):
    """Invalidate job search cache when a job is deleted."""
    invalidate_entity_cache('jobs')


@receiver(post_save, sender=TalentProfile)
def update_talent_search_vector(sender, instance, using=None, **kwargs):
    """Recompute the search_vector for a TalentProfile after save."""
    if not _supports_postgres_search(using):
        invalidate_entity_cache('talent')
        return

    from django.contrib.postgres.search import SearchVector
    from django.db.models import Value

    try:
        skills_text = ' '.join(instance.skills) if instance.skills else ''
        full_name = instance.user.full_name or ''

        TalentProfile.objects.filter(pk=instance.pk).update(
            search_vector=(
                SearchVector(Value(skills_text), weight='A', config='english')
                + SearchVector(Value(full_name), weight='A', config='english')
                + SearchVector('bio', weight='B', config='english')
                + SearchVector('location', weight='B', config='english')
            )
        )
        invalidate_entity_cache('talent')
    except Exception:
        logger.exception('Failed to update search vector for TalentProfile pk=%s', instance.pk)


@receiver(post_delete, sender=TalentProfile)
def invalidate_talent_cache_on_delete(sender, instance, **kwargs):
    """Invalidate talent search cache on profile deletion."""
    invalidate_entity_cache('talent')


@receiver(post_save, sender=CompanyProfile)
def update_company_search_vector(sender, instance, using=None, **kwargs):
    """Recompute the search_vector for a CompanyProfile after save."""
    if not _supports_postgres_search(using):
        invalidate_entity_cache('companies')
        return

    from django.contrib.postgres.search import SearchVector

    try:
        CompanyProfile.objects.filter(pk=instance.pk).update(
            search_vector=(
                SearchVector('legal_name', weight='A', config='english')
                + SearchVector('industry', weight='A', config='english')
                + SearchVector('mission_statement', weight='B', config='english')
                + SearchVector('headquarters', weight='B', config='english')
            )
        )
        invalidate_entity_cache('companies')
    except Exception:
        logger.exception('Failed to update search vector for CompanyProfile pk=%s', instance.pk)


@receiver(post_delete, sender=CompanyProfile)
def invalidate_company_cache_on_delete(sender, instance, **kwargs):
    """Invalidate company search cache on profile deletion."""
    invalidate_entity_cache('companies')

@receiver(post_save, sender=SearchAnalytics)
def invalidate_trending_on_search_analytics_save(sender, instance, **kwargs):
    """Keep trending results fresh when analytics rows are written."""
    invalidate_trending_cache(instance.entity_type)


@receiver(post_delete, sender=SearchAnalytics)
def invalidate_trending_on_search_analytics_delete(sender, instance, **kwargs):
    """Keep trending results fresh when analytics rows are removed."""
    invalidate_trending_cache(instance.entity_type)

