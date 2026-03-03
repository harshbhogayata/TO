"""
intelligence/analytics/benchmarks.py
Platform-wide benchmark computations.
"""

import logging
from datetime import date, timedelta

from django.db.models import Avg, Count
from django.utils import timezone

logger = logging.getLogger(__name__)


def compute_platform_benchmarks():
    """
    Compute platform-wide benchmarks for comparison.
    Called by weekly Celery task.
    """
    from intelligence.models import PlatformBenchmark
    from jobs.models import Application, JobPost

    today = date.today()
    period_start = today - timedelta(days=30)

    jobs = JobPost.objects.filter(status='open')
    apps = Application.objects.filter(applied_at__gte=period_start)

    # Average application rate (applications per job)
    total_jobs = jobs.count()
    total_apps = apps.count()
    avg_app_rate = total_apps / total_jobs if total_jobs > 0 else 0

    _upsert_benchmark('avg_application_rate', '', avg_app_rate, total_jobs, period_start, today)

    # Average views per job
    from django.db.models import Sum
    total_views = jobs.aggregate(s=Sum('views_count'))['s'] or 0
    avg_views = total_views / total_jobs if total_jobs > 0 else 0

    _upsert_benchmark('avg_views_per_job', '', avg_views, total_jobs, period_start, today)

    # Offer rate (offered / total applications)
    offered = apps.filter(status='offered').count()
    offer_rate = offered / total_apps if total_apps > 0 else 0

    _upsert_benchmark('avg_offer_rate', '', offer_rate, total_apps, period_start, today)

    # Per-industry benchmarks
    from accounts.models import CompanyProfile
    industries = CompanyProfile.objects.values_list('industry', flat=True).distinct()

    for industry in industries:
        if not industry:
            continue

        industry_companies = CompanyProfile.objects.filter(
            industry=industry,
        ).values_list('user_id', flat=True)

        industry_jobs = jobs.filter(company_id__in=industry_companies)
        industry_apps = apps.filter(job__in=industry_jobs)

        i_total_jobs = industry_jobs.count()
        i_total_apps = industry_apps.count()

        if i_total_jobs > 0:
            _upsert_benchmark(
                'avg_application_rate', industry,
                i_total_apps / i_total_jobs, i_total_jobs,
                period_start, today,
            )

    logger.info('Computed platform benchmarks for %s to %s', period_start, today)
    return True


def _upsert_benchmark(metric_name, industry, value, sample_size, period_start, period_end):
    """Upsert a single benchmark metric."""
    from intelligence.models import PlatformBenchmark

    PlatformBenchmark.objects.update_or_create(
        metric_name=metric_name,
        industry=industry,
        period_start=period_start,
        defaults={
            'value': round(value, 4),
            'sample_size': sample_size,
            'period_end': period_end,
        },
    )


def get_benchmarks_for_company(company_user) -> list[dict]:
    """
    Get benchmark comparison data for a company.
    Returns list of {name, your_value, platform_avg, industry_avg, percentile}.
    """
    from intelligence.analytics.aggregators import compute_overview_metrics
    from intelligence.models import PlatformBenchmark

    overview = compute_overview_metrics(company_user)

    # Get company's industry
    industry = ''
    try:
        industry = company_user.company_profile.industry or ''
    except Exception:
        pass

    results = []
    metrics_of_interest = ['avg_application_rate', 'avg_views_per_job', 'avg_offer_rate']

    for metric_name in metrics_of_interest:
        platform_benchmark = PlatformBenchmark.objects.filter(
            metric_name=metric_name, industry='',
        ).order_by('-period_start').first()

        industry_benchmark = None
        if industry:
            industry_benchmark = PlatformBenchmark.objects.filter(
                metric_name=metric_name, industry=industry,
            ).order_by('-period_start').first()

        # Compute the company's own value for this metric
        your_value = 0.0
        if metric_name == 'avg_application_rate':
            active_jobs = overview.get('active_jobs', 1)
            your_value = overview.get('total_applications', 0) / max(active_jobs, 1)
        elif metric_name == 'avg_views_per_job':
            active_jobs = overview.get('active_jobs', 1)
            your_value = overview.get('total_views', 0) / max(active_jobs, 1)
        elif metric_name == 'avg_offer_rate':
            total_apps = overview.get('total_applications', 0)
            if total_apps > 0:
                # Count offers for this company's jobs in the current period
                from jobs.models import Application, JobPost
                company_jobs = JobPost.objects.filter(company=company_user)
                company_offers = Application.objects.filter(
                    job__in=company_jobs, status='offered',
                ).count()
                your_value = company_offers / total_apps

        results.append({
            'name': metric_name.replace('_', ' ').title(),
            'your_value': round(your_value, 2),
            'platform_avg': round(platform_benchmark.value, 2) if platform_benchmark else 0,
            'industry_avg': round(industry_benchmark.value, 2) if industry_benchmark else 0,
            'sample_size': platform_benchmark.sample_size if platform_benchmark else 0,
        })

    return results
