"""
intelligence/engine/features.py
Feature extraction from User, TalentProfile, JobPost, and Application data.
Provides clean data structures for the scoring pipeline.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from django.core.exceptions import ObjectDoesNotExist

logger = logging.getLogger(__name__)


@dataclass
class UserFeatures:
    """Extracted features for a talent user."""
    user_id: int
    skills: list[str] = field(default_factory=list)
    experience_level: str = ''
    location: str = ''
    is_open_to_work: bool = True
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    work_mode_pref: str = ''
    applied_job_ids: set = field(default_factory=set)
    saved_job_ids: set = field(default_factory=set)
    viewed_job_ids: set = field(default_factory=set)


@dataclass
class JobFeatures:
    """Extracted features for a job post."""
    job_id: int
    company_id: int
    title: str = ''
    skills_required: list[str] = field(default_factory=list)
    experience_level: str = ''
    location: str = ''
    work_mode: str = ''
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    views_count: int = 0
    application_count: int = 0
    save_count: int = 0
    days_since_posted: float = 0.0
    status: str = 'open'


def extract_user_features(user) -> UserFeatures:
    """Extract recommendation-relevant features from a User object."""
    features = UserFeatures(user_id=user.id)

    try:
        profile = user.talent_profile
        features.skills = profile.skills or []
        features.location = profile.location or ''
        features.is_open_to_work = getattr(profile, 'is_open_to_work', True)
    except ObjectDoesNotExist:
        logger.debug('No TalentProfile for user %s, using defaults', user.id)
    except Exception:
        logger.exception('Unexpected error loading profile for user %s', user.id)

    # Applied and saved jobs
    from jobs.models import Application, SavedJob
    features.applied_job_ids = set(
        Application.objects.filter(applicant=user)
        .values_list('job_id', flat=True)
    )
    features.saved_job_ids = set(
        SavedJob.objects.filter(user=user)
        .values_list('job_id', flat=True)
    )

    return features


def extract_job_features(job) -> JobFeatures:
    """Extract recommendation-relevant features from a JobPost object."""
    from django.utils import timezone

    days = 0.0
    if job.created_at:
        delta = timezone.now() - job.created_at
        days = delta.total_seconds() / 86400.0

    app_count = 0
    try:
        app_count = job.applications.count()
    except Exception:
        logger.debug('Could not count applications for job %s', job.id)

    save_count = 0
    try:
        from jobs.models import SavedJob
        save_count = SavedJob.objects.filter(job=job).count()
    except Exception:
        logger.debug('Could not count saves for job %s', job.id)

    return JobFeatures(
        job_id=job.id,
        company_id=job.company_id,
        title=job.title,
        skills_required=job.skills_required or [],
        experience_level=job.experience_level or '',
        location=job.location or '',
        work_mode=job.work_mode or '',
        salary_min=float(job.salary_min) if job.salary_min else None,
        salary_max=float(job.salary_max) if job.salary_max else None,
        views_count=job.views_count or 0,
        application_count=app_count,
        save_count=save_count,
        days_since_posted=days,
        status=job.status or 'open',
    )


def extract_bulk_job_features(jobs_queryset) -> list[JobFeatures]:
    """Extract features for multiple jobs efficiently (reduces N+1)."""
    from django.utils import timezone
    from django.db.models import Count
    from jobs.models import SavedJob

    now = timezone.now()
    job_features = []

    # Pre-fetch application counts
    app_counts = dict(
        jobs_queryset.annotate(
            _app_count=Count('applications'),
        ).values_list('id', '_app_count')
    )

    save_counts = dict(
        SavedJob.objects.filter(job__in=jobs_queryset)
        .values('job_id').annotate(cnt=Count('id'))
        .values_list('job_id', 'cnt')
    )

    for job in jobs_queryset:
        days = 0.0
        if job.created_at:
            delta = now - job.created_at
            days = delta.total_seconds() / 86400.0

        jf = JobFeatures(
            job_id=job.id,
            company_id=job.company_id,
            title=job.title,
            skills_required=job.skills_required or [],
            experience_level=job.experience_level or '',
            location=job.location or '',
            work_mode=job.work_mode or '',
            salary_min=float(job.salary_min) if job.salary_min else None,
            salary_max=float(job.salary_max) if job.salary_max else None,
            views_count=job.views_count or 0,
            application_count=app_counts.get(job.id, 0),
            save_count=save_counts.get(job.id, 0),
            days_since_posted=days,
            status=job.status or 'open',
        )
        job_features.append(jf)

    return job_features
