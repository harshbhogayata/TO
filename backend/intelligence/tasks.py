"""
intelligence/tasks.py
Celery tasks for the Intelligence layer.

All tasks use BaseTaskWithDLQ so permanently-failed tasks are routed
to the dead-letter queue instead of being silently dropped.
"""
import logging

from celery import shared_task
from talentorbit.task_base import BaseTaskWithDLQ

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Recommendation engine tasks
# ──────────────────────────────────────────────────────────────────────────────

@shared_task(
    base=BaseTaskWithDLQ,
    bind=True,
    name='intelligence.retrain_tfidf_vectorizer',
    max_retries=2,
    default_retry_delay=60,
)
def retrain_tfidf_vectorizer(self):
    """
    Retrain the TF-IDF skill vectorizer from the current skill taxonomy
    and persist the updated artifact to the database + Redis cache.
    Scheduled: daily at 02:00 UTC.
    """
    from .engine.vectorizer import train_vectorizer
    try:
        train_vectorizer()
        logger.info('TF-IDF vectorizer retrained successfully.')
    except Exception as exc:
        logger.exception('TF-IDF vectorizer retraining failed.')
        raise self.retry(exc=exc)


@shared_task(
    base=BaseTaskWithDLQ,
    bind=True,
    name='intelligence.rebuild_interaction_matrix',
    max_retries=2,
    default_retry_delay=60,
)
def rebuild_interaction_matrix(self):
    """
    Rebuild the user–item interaction matrix for collaborative filtering.
    Scheduled: daily at 02:30 UTC.
    """
    from .engine.collaborative import build_interaction_matrix
    try:
        build_interaction_matrix()
        logger.info('Interaction matrix rebuilt successfully.')
    except Exception as exc:
        logger.exception('Interaction matrix rebuild failed.')
        raise self.retry(exc=exc)


@shared_task(
    base=BaseTaskWithDLQ,
    bind=True,
    name='intelligence.warm_recommendation_cache',
    max_retries=1,
    default_retry_delay=30,
)
def warm_recommendation_cache(self):
    """
    Pre-compute recommendations for the most active users and cache them.
    Scheduled: every 4 hours.
    """
    from django.db.models import Count
    from accounts.models import User
    from .engine.hybrid import compute_recommendations
    from .engine.cache import set_cached_recommendations

    # Top 100 most active talent users by interaction count
    active_users = (
        User.objects.filter(role='TALENT', is_active=True)
        .annotate(interaction_count=Count('intelligence_interactions'))
        .order_by('-interaction_count')[:100]
    )

    warmed = 0
    for user in active_users:
        try:
            results, _ = compute_recommendations(user, limit=20)
            cacheable = [
                {
                    'job_id': r.job_id,
                    'final_score': r.final_score,
                    'content_score': r.content_score,
                    'collaborative_score': r.collaborative_score,
                    'popularity_score': r.popularity_score,
                    'freshness_score': r.freshness_score,
                    'explanation': r.explanation,
                    'breakdown': r.breakdown,
                }
                for r in results
            ]
            set_cached_recommendations(user.id, cacheable)
            warmed += 1
        except Exception:
            logger.warning('Failed to warm cache for user %s', user.id)

    logger.info('Warmed recommendation cache for %d users.', warmed)


# ──────────────────────────────────────────────────────────────────────────────
# NLP / Taxonomy tasks
# ──────────────────────────────────────────────────────────────────────────────

@shared_task(
    base=BaseTaskWithDLQ,
    bind=True,
    name='intelligence.rebuild_skill_entity_ruler',
    max_retries=2,
    default_retry_delay=30,
)
def rebuild_skill_entity_ruler(self):
    """
    Rebuild the spaCy EntityRuler patterns from the skill taxonomy.
    Scheduled: daily at 02:15 UTC.
    """
    from .nlp.taxonomy import build_spacy_patterns
    try:
        build_spacy_patterns()
        logger.info('spaCy skill EntityRuler rebuilt successfully.')
    except Exception as exc:
        logger.exception('EntityRuler rebuild failed.')
        raise self.retry(exc=exc)


@shared_task(
    base=BaseTaskWithDLQ,
    bind=True,
    name='intelligence.update_skill_taxonomy',
    max_retries=2,
    default_retry_delay=30,
)
def update_skill_taxonomy(self):
    """
    Seed new skills from constants and update usage counts.
    Scheduled: weekly on Sundays at 03:00 UTC.
    """
    from .nlp.taxonomy import seed_taxonomy_from_constants, update_usage_counts
    try:
        seed_taxonomy_from_constants()
        update_usage_counts()
        logger.info('Skill taxonomy updated and usage counts refreshed.')
    except Exception as exc:
        logger.exception('Skill taxonomy update failed.')
        raise self.retry(exc=exc)


@shared_task(
    base=BaseTaskWithDLQ,
    bind=True,
    name='intelligence.discover_new_skills',
    max_retries=1,
    default_retry_delay=60,
)
def discover_new_skills(self):
    """
    Scan recent job postings and resumes for skills not yet in the taxonomy.
    Creates unverified taxonomy entries for admin review.
    Scheduled: weekly on Wednesdays at 03:00 UTC.
    """
    from django.utils import timezone
    from datetime import timedelta
    from jobs.models import JobPost
    from .models import SkillTaxonomy, ParsedResume
    from .nlp.taxonomy import get_taxonomy_lookup

    try:
        lookup = get_taxonomy_lookup()
        known = set(k.lower() for k in lookup.keys())

        # Gather skills from recent job posts
        cutoff = timezone.now() - timedelta(days=7)
        recent_jobs = JobPost.objects.filter(created_at__gte=cutoff).values_list(
            'skills_required', flat=True,
        )
        recent_resumes = ParsedResume.objects.filter(parsed_at__gte=cutoff).values_list(
            'parsed_skills', flat=True,
        )

        candidates = {}
        for skills_list in list(recent_jobs) + list(recent_resumes):
            if not isinstance(skills_list, list):
                continue
            for skill in skills_list:
                # JobPost.skills_required stores strings; ParsedResume.parsed_skills stores dicts
                if isinstance(skill, dict):
                    name = (skill.get('canonical_name') or skill.get('name', '')).strip()
                else:
                    name = str(skill).strip()
                if name and name.lower() not in known and len(name) >= 2:
                    candidates[name.lower()] = name

        created = 0
        for key, canonical in candidates.items():
            _, was_created = SkillTaxonomy.objects.get_or_create(
                canonical_name__iexact=canonical,
                defaults={
                    'canonical_name': canonical,
                    'category': 'Uncategorised',
                    'aliases': [],
                    'is_verified': False,
                },
            )
            if was_created:
                created += 1

        logger.info('Discovered %d new unverified skills.', created)
    except Exception as exc:
        logger.exception('Skill discovery failed.')
        raise self.retry(exc=exc)


# ──────────────────────────────────────────────────────────────────────────────
# Analytics / Warehouse tasks
# ──────────────────────────────────────────────────────────────────────────────

@shared_task(
    base=BaseTaskWithDLQ,
    bind=True,
    name='intelligence.compute_daily_funnel_snapshots',
    max_retries=2,
    default_retry_delay=120,
)
def compute_daily_funnel_snapshots(self):
    """
    Materialise daily hiring funnel snapshots for all companies.
    Scheduled: daily at 01:00 UTC.
    """
    from .analytics.warehouse import etl_daily_funnel_snapshots
    try:
        etl_daily_funnel_snapshots()
        logger.info('Daily funnel snapshots computed.')
    except Exception as exc:
        logger.exception('Daily funnel snapshot ETL failed.')
        raise self.retry(exc=exc)


@shared_task(
    base=BaseTaskWithDLQ,
    bind=True,
    name='intelligence.compute_daily_platform_metrics',
    max_retries=2,
    default_retry_delay=120,
)
def compute_daily_platform_metrics(self):
    """
    Materialise daily platform-wide metrics.
    Scheduled: daily at 01:30 UTC.
    """
    from .analytics.warehouse import etl_daily_platform_metrics
    try:
        etl_daily_platform_metrics()
        logger.info('Daily platform metrics computed.')
    except Exception as exc:
        logger.exception('Daily platform metrics ETL failed.')
        raise self.retry(exc=exc)


@shared_task(
    base=BaseTaskWithDLQ,
    bind=True,
    name='intelligence.compute_platform_benchmarks',
    max_retries=2,
    default_retry_delay=120,
)
def compute_platform_benchmarks(self):
    """
    Recompute platform benchmarks (avg application rates, etc.).
    Scheduled: weekly on Mondays at 04:00 UTC.
    """
    from .analytics.benchmarks import compute_platform_benchmarks as _compute
    try:
        _compute()
        logger.info('Platform benchmarks recomputed.')
    except Exception as exc:
        logger.exception('Platform benchmarks computation failed.')
        raise self.retry(exc=exc)


@shared_task(
    base=BaseTaskWithDLQ,
    bind=True,
    name='intelligence.aggregate_period_snapshots',
    max_retries=1,
    default_retry_delay=120,
)
def aggregate_period_snapshots(self):
    """
    Roll up daily snapshots into weekly/monthly aggregates.
    Scheduled: weekly on Mondays at 05:00 UTC.
    """
    from datetime import timedelta
    from django.utils import timezone
    from django.db.models import Sum
    from .models import HiringFunnelSnapshot

    try:
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday() + 7)  # Previous Monday
        week_end = week_start + timedelta(days=6)

        # Aggregate daily snapshots into weekly
        daily_snapshots = HiringFunnelSnapshot.objects.filter(
            date__gte=week_start, date__lte=week_end, period='daily',
        )

        # Group by company
        company_ids = daily_snapshots.values_list('company_id', flat=True).distinct()

        for cid in company_ids:
            company_daily = daily_snapshots.filter(company_id=cid, job__isnull=True)
            agg = company_daily.aggregate(
                total_views=Sum('views'),
                total_apps=Sum('applications'),
                total_reviewing=Sum('reviewing'),
                total_shortlisted=Sum('shortlisted'),
                total_interviewing=Sum('interviewing'),
                total_offered=Sum('offered'),
                total_rejected=Sum('rejected'),
                total_withdrawn=Sum('withdrawn'),
            )

            HiringFunnelSnapshot.objects.update_or_create(
                company_id=cid, job=None, date=week_start, period='weekly',
                defaults={
                    'views': agg['total_views'] or 0,
                    'applications': agg['total_apps'] or 0,
                    'reviewing': agg['total_reviewing'] or 0,
                    'shortlisted': agg['total_shortlisted'] or 0,
                    'interviewing': agg['total_interviewing'] or 0,
                    'offered': agg['total_offered'] or 0,
                    'rejected': agg['total_rejected'] or 0,
                    'withdrawn': agg['total_withdrawn'] or 0,
                },
            )

        logger.info('Weekly snapshot aggregation complete for %d companies.', len(company_ids))
    except Exception as exc:
        logger.exception('Period snapshot aggregation failed.')
        raise self.retry(exc=exc)


# ──────────────────────────────────────────────────────────────────────────────
# Resume parser async task
# ──────────────────────────────────────────────────────────────────────────────

@shared_task(
    base=BaseTaskWithDLQ,
    bind=True,
    name='intelligence.parse_resume_async',
    max_retries=2,
    default_retry_delay=30,
)
def parse_resume_async(self, user_id, file_path):
    """
    Async resume parsing — triggered for batch processing or re-parsing.
    The synchronous path is used for the real-time upload endpoint.
    """
    from django.core.files import File
    from accounts.models import User
    from .nlp.parser import parse_resume

    try:
        user = User.objects.get(pk=user_id)
        with open(file_path, 'rb') as f:
            parse_resume(File(f, name=file_path.split('/')[-1]), user=user)
        logger.info('Async resume parsing complete for user %s', user_id)
    except User.DoesNotExist:
        logger.error('User %s not found for async resume parsing.', user_id)
    except Exception as exc:
        logger.exception('Async resume parsing failed for user %s.', user_id)
        raise self.retry(exc=exc)


# ──────────────────────────────────────────────────────────────────────────────
# Cleanup tasks
# ──────────────────────────────────────────────────────────────────────────────

@shared_task(
    base=BaseTaskWithDLQ,
    name='intelligence.cleanup_old_recommendation_logs',
)
def cleanup_old_recommendation_logs():
    """
    Delete recommendation logs older than 90 days.
    Scheduled: weekly on Saturdays at 04:00 UTC.
    """
    from datetime import timedelta
    from django.utils import timezone
    from .models import RecommendationLog

    cutoff = timezone.now() - timedelta(days=90)
    deleted, _ = RecommendationLog.objects.filter(created_at__lt=cutoff).delete()
    logger.info('Cleaned up %d old recommendation logs.', deleted)


@shared_task(
    base=BaseTaskWithDLQ,
    name='intelligence.cleanup_old_interactions',
)
def cleanup_old_interactions():
    """
    Delete view/click interactions older than 180 days.
    Save and apply interactions are kept indefinitely.
    Scheduled: weekly on Saturdays at 04:30 UTC.
    """
    from datetime import timedelta
    from django.utils import timezone
    from .models import UserInteraction

    cutoff = timezone.now() - timedelta(days=180)
    deleted, _ = UserInteraction.objects.filter(
        interaction_type__in=['view', 'click'],
        created_at__lt=cutoff,
    ).delete()
    logger.info('Cleaned up %d old view/click interactions.', deleted)
