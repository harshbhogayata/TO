"""
intelligence/analytics/materialized.py
Materialized view management and query helpers for analytics.
"""

import logging
from datetime import date, timedelta

from django.db.models import Case, Count, Q, Sum, Value, When

logger = logging.getLogger(__name__)


def get_funnel_trend(
    company_user,
    period_days: int = 30,
    job_id=None,
) -> list[dict]:
    """
    Get daily funnel trend data from HiringFunnelSnapshot.
    Returns list of {date, views, applications, shortlisted, ...} dicts.
    """
    from intelligence.models import HiringFunnelSnapshot

    cutoff = date.today() - timedelta(days=period_days)

    qs = HiringFunnelSnapshot.objects.filter(
        company=company_user,
        date__gte=cutoff,
        period='daily',
    )

    if job_id:
        qs = qs.filter(job_id=job_id)
    else:
        qs = qs.filter(job__isnull=True)

    return list(qs.order_by('date').values(
        'date', 'views', 'applications', 'reviewing',
        'shortlisted', 'interviewing', 'offered',
        'rejected', 'withdrawn',
    ))


def get_platform_metrics_trend(days: int = 30) -> list[dict]:
    """Get daily platform metrics trend for admin dashboard."""
    from intelligence.models import DailyPlatformMetrics

    cutoff = date.today() - timedelta(days=days)
    return list(
        DailyPlatformMetrics.objects.filter(date__gte=cutoff)
        .order_by('date')
        .values(
            'date', 'total_users', 'new_users',
            'active_users_1d', 'active_users_7d', 'active_users_30d',
            'total_open_jobs', 'new_jobs_posted',
            'new_applications', 'offers_extended',
            'total_messages_sent', 'total_searches',
        )
    )


def get_job_performance_table(company_user) -> list[dict]:
    """
    Get per-job performance data for the company analytics table.
    Uses conditional aggregation to avoid N+1 queries.
    Returns list of job performance dicts.
    """
    from django.utils import timezone

    from jobs.models import JobPost

    now = timezone.now()

    jobs = (
        JobPost.objects.filter(company=company_user)
        .order_by('-created_at')[:50]
    )
    # Materialise IDs to avoid sliced-queryset annotation issues
    job_ids = list(jobs.values_list('id', flat=True))

    annotated = (
        JobPost.objects.filter(id__in=job_ids)
        .annotate(
            app_count=Count('applications'),
            shortlisted_count=Count(
                'applications',
                filter=Q(applications__status='shortlisted'),
            ),
            interviewing_count=Count(
                'applications',
                filter=Q(applications__status='interviewing'),
            ),
            offered_count=Count(
                'applications',
                filter=Q(applications__status='offered'),
            ),
        )
        .order_by('-created_at')
    )

    results = []
    for job in annotated:
        days_active = (now - job.created_at).days if job.created_at else 0

        # Health indicator
        if job.status != 'open':
            health = 'closed'
        elif job.app_count == 0 and days_active > 14:
            health = 'underperforming'
        elif days_active > 60:
            health = 'stale'
        else:
            health = 'healthy'

        results.append({
            'id': job.id,
            'title': job.title,
            'status': job.status,
            'views': job.views_count or 0,
            'applications': job.app_count,
            'shortlisted': job.shortlisted_count,
            'interviewing': job.interviewing_count,
            'offered': job.offered_count,
            'days_active': days_active,
            'health': health,
        })

    return results
