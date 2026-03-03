"""
intelligence/analytics/warehouse.py
ETL pipeline orchestrator for daily/weekly/monthly metric computation.
"""

import logging
from datetime import date, timedelta

from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone

logger = logging.getLogger(__name__)


def etl_daily_funnel_snapshots():
    """
    Compute daily HiringFunnelSnapshot for each company with active jobs.
    Called by the daily Celery task at 01:00 UTC.
    Uses prefetch + conditional aggregation to avoid N+1 queries.
    """
    from accounts.models import User
    from intelligence.models import HiringFunnelSnapshot
    from jobs.models import Application, JobPost

    today = date.today()
    companies = User.objects.filter(role='COMPANY', is_active=True)
    created_count = 0

    # Pre-annotate open jobs with status counts in a single query per company
    for company in companies.iterator():
        open_jobs = (
            JobPost.objects.filter(company=company, status='open')
            .annotate(
                app_count=Count('applications'),
                reviewing_count=Count(
                    'applications', filter=Q(applications__status='reviewing'),
                ),
                shortlisted_count=Count(
                    'applications', filter=Q(applications__status='shortlisted'),
                ),
                interviewing_count=Count(
                    'applications', filter=Q(applications__status='interviewing'),
                ),
                offered_count=Count(
                    'applications', filter=Q(applications__status='offered'),
                ),
                rejected_count=Count(
                    'applications', filter=Q(applications__status='rejected'),
                ),
                withdrawn_count=Count(
                    'applications', filter=Q(applications__status='withdrawn'),
                ),
            )
        )

        if not open_jobs.exists():
            continue

        total_views = 0
        total_apps = 0
        total_reviewing = 0
        total_shortlisted = 0
        total_interviewing = 0
        total_offered = 0
        total_rejected = 0
        total_withdrawn = 0

        # Per-job snapshots — already annotated, no extra queries
        for job in open_jobs:
            HiringFunnelSnapshot.objects.update_or_create(
                company=company,
                job=job,
                date=today,
                period='daily',
                defaults={
                    'views': job.views_count or 0,
                    'applications': job.app_count,
                    'reviewing': job.reviewing_count,
                    'shortlisted': job.shortlisted_count,
                    'interviewing': job.interviewing_count,
                    'offered': job.offered_count,
                    'rejected': job.rejected_count,
                    'withdrawn': job.withdrawn_count,
                },
            )
            total_views += job.views_count or 0
            total_apps += job.app_count
            total_reviewing += job.reviewing_count
            total_shortlisted += job.shortlisted_count
            total_interviewing += job.interviewing_count
            total_offered += job.offered_count
            total_rejected += job.rejected_count
            total_withdrawn += job.withdrawn_count
            created_count += 1

        # Aggregate snapshot (job=None)
        HiringFunnelSnapshot.objects.update_or_create(
            company=company,
            job=None,
            date=today,
            period='daily',
            defaults={
                'views': total_views,
                'applications': total_apps,
                'reviewing': total_reviewing,
                'shortlisted': total_shortlisted,
                'interviewing': total_interviewing,
                'offered': total_offered,
                'rejected': total_rejected,
                'withdrawn': total_withdrawn,
            },
        )
        created_count += 1

    logger.info('Computed %d funnel snapshots for %s', created_count, today)
    return created_count


def etl_daily_platform_metrics():
    """
    Compute daily platform-wide metrics for admin dashboard.
    Called by the daily Celery task at 01:15 UTC.
    """
    from accounts.models import User
    from intelligence.models import DailyPlatformMetrics
    from jobs.models import Application, JobPost
    from messaging.models import Message

    today = date.today()
    now = timezone.now()

    total_users = User.objects.filter(is_active=True).count()
    new_users = User.objects.filter(date_joined__date=today).count()

    # Active users
    dau = User.objects.filter(last_login__date=today).count()
    wau = User.objects.filter(last_login__gte=now - timedelta(days=7)).count()
    mau = User.objects.filter(last_login__gte=now - timedelta(days=30)).count()

    talent_count = User.objects.filter(role='TALENT', is_active=True).count()
    company_count = User.objects.filter(role='COMPANY', is_active=True).count()

    total_open_jobs = JobPost.objects.filter(status='open').count()
    new_jobs = JobPost.objects.filter(created_at__date=today).count()

    total_applications = Application.objects.count()
    new_applications = Application.objects.filter(applied_at__date=today).count()
    offers = Application.objects.filter(status='offered', updated_at__date=today).count()

    total_messages = Message.objects.filter(sent_at__date=today).count()

    # Search count
    try:
        from search.models import SearchAnalytics
        total_searches = SearchAnalytics.objects.filter(created_at__date=today).count()
    except Exception:
        total_searches = 0

    # Recommendation requests
    from intelligence.models import RecommendationLog
    rec_requests = RecommendationLog.objects.filter(created_at__date=today).count()

    DailyPlatformMetrics.objects.update_or_create(
        date=today,
        defaults={
            'total_users': total_users,
            'new_users': new_users,
            'active_users_1d': dau,
            'active_users_7d': wau,
            'active_users_30d': mau,
            'talent_count': talent_count,
            'company_count': company_count,
            'total_open_jobs': total_open_jobs,
            'new_jobs_posted': new_jobs,
            'total_applications': total_applications,
            'new_applications': new_applications,
            'offers_extended': offers,
            'total_messages_sent': total_messages,
            'total_searches': total_searches,
            'total_recommendation_requests': rec_requests,
        },
    )

    logger.info('Computed daily platform metrics for %s', today)
    return True
