"""
intelligence/signals.py
Django signals for the Intelligence layer.

Invalidates recommendation caches when relevant models change, and records
source attribution for job applications.
"""
import logging

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='jobs.Application')
def on_application_created(sender, instance, created, **kwargs):
    """
    When a talent submits an application:
    1. Invalidate their recommendation cache (they've now applied).
    2. Record a source attribution entry.
    3. Auto-record an 'apply' interaction for collaborative filtering.
    """
    if not created:
        return

    from .engine.cache import invalidate_user_recommendations
    from .models import UserInteraction, SourceAttribution
    from .constants import INTERACTION_WEIGHTS

    user = instance.applicant

    # Invalidate cache
    try:
        invalidate_user_recommendations(user.id)
    except Exception:
        logger.warning('Failed to invalidate cache for user %s', user.id)

    # Record interaction
    try:
        UserInteraction.objects.get_or_create(
            user=user,
            job=instance.job,
            interaction_type='apply',
            defaults={'weight': INTERACTION_WEIGHTS.get('apply', 5.0)},
        )
    except Exception:
        logger.warning('Failed to record apply interaction for user %s', user.id)

    # Source attribution — default to 'direct'; overridden by frontend
    try:
        SourceAttribution.objects.get_or_create(
            job=instance.job,
            user=user,
            defaults={
                'source': 'direct',
                'converted_to_application': True,
            },
        )
    except Exception:
        logger.warning('Failed to record source attribution for user %s', user.id)


@receiver(post_save, sender='jobs.SavedJob')
def on_job_saved(sender, instance, created, **kwargs):
    """Record a 'save' interaction and invalidate recommendation cache."""
    if not created:
        return

    from .engine.cache import invalidate_user_recommendations
    from .models import UserInteraction
    from .constants import INTERACTION_WEIGHTS

    try:
        UserInteraction.objects.get_or_create(
            user=instance.user,
            job=instance.job,
            interaction_type='save',
            defaults={'weight': INTERACTION_WEIGHTS.get('save', 3.0)},
        )
    except Exception:
        logger.warning('Failed to record save interaction.')

    try:
        invalidate_user_recommendations(instance.user_id)
    except Exception:
        logger.warning('Failed to invalidate cache on save.')


@receiver(post_delete, sender='jobs.SavedJob')
def on_job_unsaved(sender, instance, **kwargs):
    """Record an 'unsave' interaction and invalidate cache."""
    from .engine.cache import invalidate_user_recommendations
    from .models import UserInteraction
    from .constants import INTERACTION_WEIGHTS

    try:
        UserInteraction.objects.create(
            user=instance.user,
            job=instance.job,
            interaction_type='unsave',
            weight=INTERACTION_WEIGHTS.get('unsave', -1.0),
        )
    except Exception:
        logger.warning('Failed to record unsave interaction.')

    try:
        invalidate_user_recommendations(instance.user_id)
    except Exception:
        logger.warning('Failed to invalidate cache on unsave.')


@receiver(post_save, sender='accounts.TalentProfile')
def on_talent_profile_updated(sender, instance, **kwargs):
    """
    When a talent updates their profile (skills, etc.), invalidate their
    recommendation cache so new recommendations reflect the changes.
    """
    from .engine.cache import invalidate_user_recommendations

    try:
        invalidate_user_recommendations(instance.user_id)
    except Exception:
        logger.warning('Failed to invalidate cache for talent profile update.')
