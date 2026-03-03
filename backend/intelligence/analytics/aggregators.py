"""
intelligence/analytics/aggregators.py
Metric computation: funnel, time-to-hire, source attribution, talent pool.
"""

import logging
from datetime import timedelta
from typing import Optional

from django.db.models import Avg, Count, F, Q, Sum
from django.utils import timezone

logger = logging.getLogger(__name__)


def compute_funnel_for_company(
    company_user,
    period_days: int = 30,
    job_id: Optional[int] = None,
) -> dict:
    """
    Compute hiring funnel metrics for a company.
    Returns {stages, total_views, total_applications}.
    """
    from jobs.models import Application, JobPost

    cutoff = timezone.now() - timedelta(days=period_days)
    jobs_qs = JobPost.objects.filter(company=company_user)

    if job_id:
        jobs_qs = jobs_qs.filter(id=job_id)

    total_views = jobs_qs.aggregate(s=Sum('views_count'))['s'] or 0

    apps_qs = Application.objects.filter(job__in=jobs_qs, applied_at__gte=cutoff)

    status_counts = dict(apps_qs.values('status').annotate(cnt=Count('id')).values_list('status', 'cnt'))

    stages = [
        {'name': 'Views', 'count': total_views},
        {'name': 'Applications', 'count': apps_qs.count()},
        {'name': 'Reviewing', 'count': status_counts.get('reviewing', 0)},
        {'name': 'Shortlisted', 'count': status_counts.get('shortlisted', 0)},
        {'name': 'Interviewing', 'count': status_counts.get('interviewing', 0)},
        {'name': 'Offered', 'count': status_counts.get('offered', 0)},
    ]

    # Compute conversion rates between stages
    for i in range(1, len(stages)):
        prev = stages[i - 1]['count']
        curr = stages[i]['count']
        stages[i]['conversion_rate'] = round(curr / prev * 100, 1) if prev > 0 else 0.0

    stages[0]['conversion_rate'] = 100.0

    return {
        'stages': stages,
        'total_views': total_views,
        'total_applications': apps_qs.count(),
        'rejected': status_counts.get('rejected', 0),
        'withdrawn': status_counts.get('withdrawn', 0),
    }


def compute_time_to_hire(
    company_user,
    period_days: int = 30,
    job_id: Optional[int] = None,
) -> list[dict]:
    """
    Compute average time between hiring stages.
    Returns list of {stage, avg_hours, count} dicts.
    """
    from jobs.models import Application, JobPost

    cutoff = timezone.now() - timedelta(days=period_days)
    jobs_qs = JobPost.objects.filter(company=company_user)

    if job_id:
        jobs_qs = jobs_qs.filter(id=job_id)

    apps = Application.objects.filter(
        job__in=jobs_qs,
        applied_at__gte=cutoff,
    ).select_related('job')

    # Calculate avg time from applied_at to updated_at for each status
    # This is a simplification — ideally we'd track status change timestamps
    metrics = []

    for status, label in [
        ('reviewing', 'Applied → Reviewing'),
        ('shortlisted', 'Reviewing → Shortlisted'),
        ('interviewing', 'Shortlisted → Interviewing'),
        ('offered', 'Interviewing → Offered'),
    ]:
        status_apps = apps.filter(status=status)
        if status_apps.exists():
            avg_delta = status_apps.annotate(
                delta=F('updated_at') - F('applied_at'),
            ).aggregate(avg=Avg('delta'))

            avg_hours = 0.0
            if avg_delta['avg']:
                avg_hours = avg_delta['avg'].total_seconds() / 3600.0

            metrics.append({
                'stage': label,
                'avg_hours': round(avg_hours, 1),
                'count': status_apps.count(),
            })

    return metrics


def compute_source_attribution(
    company_user,
    period_days: int = 30,
    job_id: Optional[int] = None,
) -> dict:
    """
    Compute source attribution analytics.
    Returns {sources: [...], top_queries: [...]}.
    """
    from intelligence.models import SourceAttribution
    from jobs.models import JobPost

    cutoff = timezone.now() - timedelta(days=period_days)
    jobs_qs = JobPost.objects.filter(company=company_user)

    if job_id:
        jobs_qs = jobs_qs.filter(id=job_id)

    attrs = SourceAttribution.objects.filter(
        job__in=jobs_qs,
        created_at__gte=cutoff,
    )

    sources = []
    for source_choice in SourceAttribution.Source:
        source_qs = attrs.filter(source=source_choice.value)
        total = source_qs.count()
        converted = source_qs.filter(converted_to_application=True).count()

        sources.append({
            'source': source_choice.value,
            'label': source_choice.label,
            'views': total,
            'applications': converted,
            'conversion_rate': round(converted / total * 100, 1) if total > 0 else 0.0,
        })

    # Top search queries
    top_queries = list(
        attrs.filter(source='search', search_query__gt='')
        .values('search_query')
        .annotate(cnt=Count('id'))
        .order_by('-cnt')
        .values_list('search_query', 'cnt')[:10]
    )

    return {
        'sources': sources,
        'top_queries': [{'query': q, 'count': c} for q, c in top_queries],
    }


def compute_talent_pool(
    company_user,
    period_days: int = 30,
    job_id: Optional[int] = None,
) -> dict:
    """
    Compute talent pool demographics for applicants.
    Returns skills distribution, experience levels, locations.
    """
    from collections import Counter

    from jobs.models import Application, JobPost

    cutoff = timezone.now() - timedelta(days=period_days)
    jobs_qs = JobPost.objects.filter(company=company_user)

    if job_id:
        jobs_qs = jobs_qs.filter(id=job_id)

    applicant_ids = Application.objects.filter(
        job__in=jobs_qs,
        applied_at__gte=cutoff,
    ).values_list('applicant_id', flat=True)

    from accounts.models import TalentProfile
    profiles = TalentProfile.objects.filter(user_id__in=applicant_ids)

    # Skills distribution
    skill_counter = Counter()
    for skills in profiles.values_list('skills', flat=True):
        if skills:
            for s in skills:
                skill_counter[s.lower()] += 1

    top_skills = [
        {'name': name, 'count': count}
        for name, count in skill_counter.most_common(20)
    ]

    # Location distribution
    location_counter = Counter()
    for loc in profiles.values_list('location', flat=True):
        if loc:
            location_counter[loc] += 1

    top_locations = [
        {'location': loc, 'count': count}
        for loc, count in location_counter.most_common(10)
    ]

    return {
        'skills': top_skills,
        'locations': top_locations,
        'total_applicants': applicant_ids.distinct().count(),
    }


def compute_overview_metrics(company_user) -> dict:
    """
    Compute high-level overview metrics for the company dashboard.
    """
    from jobs.models import Application, JobPost

    jobs = JobPost.objects.filter(company=company_user)
    active_jobs = jobs.filter(status='open')
    total_views = active_jobs.aggregate(s=Sum('views_count'))['s'] or 0

    now = timezone.now()
    last_30d = now - timedelta(days=30)
    prev_30d = last_30d - timedelta(days=30)

    current_apps = Application.objects.filter(job__in=jobs, applied_at__gte=last_30d).count()
    prev_apps = Application.objects.filter(
        job__in=jobs,
        applied_at__gte=prev_30d,
        applied_at__lt=last_30d,
    ).count()

    app_change = 0.0
    if prev_apps > 0:
        app_change = round((current_apps - prev_apps) / prev_apps * 100, 1)

    return {
        'total_views': total_views,
        'total_applications': current_apps,
        'application_change': app_change,
        'active_jobs': active_jobs.count(),
        'total_jobs': jobs.count(),
    }
