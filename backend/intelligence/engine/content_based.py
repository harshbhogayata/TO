"""
intelligence/engine/content_based.py
Content-based scoring: skills, experience, location, salary, work mode.
"""

import logging
from typing import Optional

from intelligence.constants import EXPERIENCE_LEVEL_ORDINAL
from intelligence.engine.vectorizer import compute_skill_similarity

logger = logging.getLogger(__name__)


def _experience_match(user_level: str, job_level: str) -> float:
    """
    Score experience level match using ordinal distance.
    Exact match → 1.0, one level off → 0.7, two → 0.4, etc.
    """
    user_level = (user_level or '').lower().strip()
    job_level = (job_level or '').lower().strip()

    user_ord = EXPERIENCE_LEVEL_ORDINAL.get(user_level, -1)
    job_ord = EXPERIENCE_LEVEL_ORDINAL.get(job_level, -1)

    if user_ord < 0 or job_ord < 0:
        return 0.5  # Unknown → neutral

    distance = abs(user_ord - job_ord)
    return max(0.0, 1.0 - distance * 0.3)


def _location_match(user_location: str, job_location: str, job_work_mode: str) -> float:
    """
    Score location match.
    Remote jobs → 1.0 always.
    Same city/region → 1.0.
    Different location → 0.3.
    """
    if not job_work_mode:
        job_work_mode = ''

    if job_work_mode.lower() == 'remote':
        return 1.0

    if not user_location or not job_location:
        return 0.5

    user_loc = user_location.lower().strip()
    job_loc = job_location.lower().strip()

    if user_loc == job_loc:
        return 1.0

    # Check partial match (city within region)
    if user_loc in job_loc or job_loc in user_loc:
        return 0.8

    # Hybrid jobs get a small location bonus
    if job_work_mode.lower() == 'hybrid':
        return 0.5

    return 0.3


def _salary_overlap(
    user_min: Optional[float],
    user_max: Optional[float],
    job_min: Optional[float],
    job_max: Optional[float],
) -> float:
    """
    Score salary range overlap.
    Full overlap → 1.0, partial → proportional, no overlap → 0.0.
    """
    if not job_min and not job_max:
        return 0.5  # No salary info → neutral
    if not user_min and not user_max:
        return 0.5

    u_min = user_min or 0
    u_max = user_max or float('inf')
    j_min = job_min or 0
    j_max = job_max or float('inf')

    # Handle infinite ranges
    if u_max == float('inf') and j_max == float('inf'):
        return 0.7 if u_min <= j_min * 1.3 else 0.3

    overlap_start = max(u_min, j_min)
    overlap_end = min(u_max, j_max)

    if overlap_start > overlap_end:
        return 0.0

    overlap = overlap_end - overlap_start
    job_range = (j_max or j_min) - j_min
    if job_range <= 0:
        return 1.0 if overlap >= 0 else 0.0

    return min(1.0, overlap / job_range)


def _work_mode_match(user_pref: str, job_mode: str) -> float:
    """Score work mode preference match."""
    if not user_pref or not job_mode:
        return 0.5

    user_pref = (user_pref or '').lower().strip()
    job_mode = (job_mode or '').lower().strip()

    if user_pref == job_mode:
        return 1.0
    if job_mode == 'remote':
        return 0.8  # Remote is usually acceptable
    if user_pref == 'hybrid' and job_mode in ('remote', 'hybrid'):
        return 0.9
    return 0.4


def compute_content_score(
    user_skills: list[str],
    job_skills: list[str],
    user_experience_level: str = '',
    job_experience_level: str = '',
    user_location: str = '',
    job_location: str = '',
    job_work_mode: str = '',
    user_salary_min: Optional[float] = None,
    user_salary_max: Optional[float] = None,
    job_salary_min: Optional[float] = None,
    job_salary_max: Optional[float] = None,
    user_work_mode_pref: str = '',
) -> dict:
    """
    Compute a content-based match score between a user and a job.
    Returns dict with overall score and per-factor breakdown.
    """
    # Skill similarity (heaviest signal)
    skill_score = compute_skill_similarity(user_skills, job_skills)

    # Experience level match
    exp_score = _experience_match(user_experience_level, job_experience_level)

    # Location match
    loc_score = _location_match(user_location, job_location, job_work_mode)

    # Salary overlap
    salary_score = _salary_overlap(
        user_salary_min, user_salary_max, job_salary_min, job_salary_max,
    )

    # Work mode match
    mode_score = _work_mode_match(user_work_mode_pref, job_work_mode)

    # Weighted combination within content factors
    # Skills are by far the most important content signal
    weights = {
        'skills': 0.50,
        'experience': 0.20,
        'location': 0.15,
        'salary': 0.10,
        'work_mode': 0.05,
    }

    overall = (
        weights['skills'] * skill_score
        + weights['experience'] * exp_score
        + weights['location'] * loc_score
        + weights['salary'] * salary_score
        + weights['work_mode'] * mode_score
    )

    return {
        'score': round(overall, 4),
        'breakdown': {
            'skills': round(skill_score, 4),
            'experience': round(exp_score, 4),
            'location': round(loc_score, 4),
            'salary': round(salary_score, 4),
            'work_mode': round(mode_score, 4),
        },
        'weights': weights,
    }
