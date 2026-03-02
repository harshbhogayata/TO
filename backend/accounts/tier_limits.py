"""
Subscription tier limits and enforcement for TalentOrbit.
Centralizes all plan-based quotas so views can enforce them consistently.
"""
from datetime import timedelta
from django.utils import timezone

# ─── Tier Limit Definitions ──────────────────────────────────────────────────

TALENT_TIER_LIMITS = {
    'free': {
        'max_applications_per_month': 3,
        'max_saved_jobs': 10,
        'label': 'Free Agent',
    },
    'premium': {
        'max_applications_per_month': None,   # Unlimited
        'max_saved_jobs': None,               # Unlimited
        'label': 'Premium Pro',
    },
}

COMPANY_TIER_LIMITS = {
    'free': {
        'max_active_job_posts': 1,
        'max_applications_visible': 10,       # Can only see first 10 applicants
        'label': 'Free',
    },
    'starter': {
        'max_active_job_posts': 5,
        'max_applications_visible': None,     # Unlimited
        'label': 'Starter',
    },
    'professional': {
        'max_active_job_posts': None,         # Unlimited
        'max_applications_visible': None,
        'label': 'Professional',
    },
    'enterprise': {
        'max_active_job_posts': None,
        'max_applications_visible': None,
        'label': 'Enterprise',
    },
}


def get_talent_limits(user):
    """Return the tier limit dict for a talent user."""
    tier = 'free'
    if hasattr(user, 'talent_profile'):
        tier = user.talent_profile.subscription_tier or 'free'
    return TALENT_TIER_LIMITS.get(tier, TALENT_TIER_LIMITS['free'])


def get_company_limits(user):
    """Return the tier limit dict for a company user."""
    tier = 'free'
    if hasattr(user, 'company_profile'):
        tier = user.company_profile.subscription_tier or 'free'
    return COMPANY_TIER_LIMITS.get(tier, COMPANY_TIER_LIMITS['free'])


def check_talent_application_limit(user):
    """
    Check if a talent user has exceeded their monthly application quota.
    Returns (allowed: bool, message: str, current_count: int, limit: int|None).
    """
    from jobs.models import Application
    limits = get_talent_limits(user)
    max_apps = limits['max_applications_per_month']

    if max_apps is None:
        return True, '', 0, None

    month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    current_count = Application.objects.filter(
        applicant=user,
        applied_at__gte=month_start,
    ).exclude(status='withdrawn').count()

    if current_count >= max_apps:
        tier = user.talent_profile.subscription_tier if hasattr(user, 'talent_profile') else 'free'
        return (
            False,
            f'You have reached your monthly application limit ({max_apps}) '
            f'on the {limits["label"]} plan. Upgrade to Premium for unlimited applications.',
            current_count,
            max_apps,
        )
    return True, '', current_count, max_apps


def check_talent_saved_job_limit(user):
    """
    Check if a talent user has exceeded their saved job quota.
    Returns (allowed: bool, message: str).
    """
    from jobs.models import SavedJob
    limits = get_talent_limits(user)
    max_saved = limits['max_saved_jobs']

    if max_saved is None:
        return True, ''

    current_count = SavedJob.objects.filter(user=user).count()
    if current_count >= max_saved:
        return (
            False,
            f'You have reached your saved jobs limit ({max_saved}) '
            f'on the {limits["label"]} plan. Upgrade to Premium for unlimited saves.',
        )
    return True, ''


def check_company_job_post_limit(user):
    """
    Check if a company user has exceeded their active job post quota.
    Returns (allowed: bool, message: str, current_count: int, limit: int|None).
    """
    from jobs.models import JobPost
    limits = get_company_limits(user)
    max_posts = limits['max_active_job_posts']

    if max_posts is None:
        return True, '', 0, None

    current_count = JobPost.objects.filter(
        company=user,
        status__in=['open', 'draft'],
    ).count()

    if current_count >= max_posts:
        tier = user.company_profile.subscription_tier if hasattr(user, 'company_profile') else 'free'
        return (
            False,
            f'You have reached your active job post limit ({max_posts}) '
            f'on the {limits["label"]} plan. Upgrade to post more jobs.',
            current_count,
            max_posts,
        )
    return True, '', current_count, max_posts
