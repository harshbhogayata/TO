"""
intelligence/engine/hybrid.py
Hybrid recommendation scorer — weighted ensemble of content-based, collaborative,
popularity, and freshness signals.

This is the main entry point for computing recommendations.
"""

import logging
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field

from intelligence.constants import (
    DEFAULT_RECOMMENDATIONS,
    DEFAULT_WEIGHTS,
    FRESHNESS_DECAY_LAMBDA,
    MAX_DIVERSITY_PER_COMPANY,
    MAX_RECOMMENDATIONS,
)
from intelligence.engine.collaborative import get_collaborative_scores, is_cold_start
from intelligence.engine.content_based import compute_content_score
from intelligence.engine.features import (
    JobFeatures,
    UserFeatures,
    extract_bulk_job_features,
    extract_user_features,
)

logger = logging.getLogger(__name__)


@dataclass
class RecommendationResult:
    """A single recommended job with full score breakdown."""
    job_id: int
    final_score: float
    content_score: float
    collaborative_score: float
    popularity_score: float
    freshness_score: float
    explanation: str
    breakdown: dict = field(default_factory=dict)


def _popularity_score(job: JobFeatures) -> float:
    """
    Compute popularity score from views, applications, and saves.
    Log-scaled to prevent runaway popular jobs from dominating.
    """
    weighted = (
        job.views_count * 0.2
        + job.application_count * 0.5
        + job.save_count * 0.3
    )
    if weighted <= 0:
        return 0.0
    # Log scale, normalised to roughly [0, 1]
    return min(1.0, math.log1p(weighted) / 10.0)


def _freshness_score(days_since_posted: float) -> float:
    """Exponential decay: newer jobs score higher."""
    return math.exp(-FRESHNESS_DECAY_LAMBDA * days_since_posted)


def _generate_explanation(
    content_breakdown: dict,
    user_skills: list[str],
    job_skills: list[str],
    collab_score: float,
) -> str:
    """Generate human-readable explanation for why a job was recommended."""
    parts = []

    # Skill match
    skill_sim = content_breakdown.get('skills', 0)
    if skill_sim > 0.7:
        common = set(s.lower() for s in user_skills) & set(s.lower() for s in job_skills)
        top_common = sorted(common)[:3]
        if top_common:
            parts.append(f'Strong skill match ({", ".join(top_common)})')
        else:
            parts.append('Strong skill alignment')
    elif skill_sim > 0.4:
        parts.append('Good skill overlap')

    # Experience
    exp_score = content_breakdown.get('experience', 0)
    if exp_score > 0.8:
        parts.append('experience level fits well')

    # Location
    loc_score = content_breakdown.get('location', 0)
    if loc_score > 0.8:
        parts.append('location matches')

    # Collaborative
    if collab_score > 0.5:
        parts.append('similar professionals applied')
    elif collab_score > 0.2:
        parts.append('matches patterns of similar users')

    if not parts:
        parts.append('Potential match based on your profile')

    explanation = parts[0]
    if len(parts) > 1:
        explanation += ' + ' + ', '.join(parts[1:])

    return explanation


def _apply_diversity(
    results: list[RecommendationResult],
    max_per_company: int,
    job_features_map: dict[int, JobFeatures],
) -> list[RecommendationResult]:
    """No more than N jobs from the same company."""
    company_counts = defaultdict(int)
    diverse_results = []

    for result in results:
        jf = job_features_map.get(result.job_id)
        company_id = jf.company_id if jf else 0
        if company_counts[company_id] < max_per_company:
            diverse_results.append(result)
            company_counts[company_id] += 1

    return diverse_results


def compute_recommendations(
    user,
    limit: int = DEFAULT_RECOMMENDATIONS,
    exclude_applied: bool = True,
    diversity: bool = True,
    weights: dict | None = None,
) -> tuple[list[RecommendationResult], int]:
    """
    Compute personalised job recommendations for a user.

    Returns (results_list, latency_ms).
    """
    start_time = time.monotonic()
    w = weights or DEFAULT_WEIGHTS

    # Extract user features
    user_features = extract_user_features(user)

    # Get candidate jobs (open, not expired)
    from jobs.models import JobPost
    candidates_qs = JobPost.objects.filter(status='open').select_related('company')

    if exclude_applied:
        candidates_qs = candidates_qs.exclude(id__in=user_features.applied_job_ids)

    # Limit candidates to a reasonable pool (top 500 by recency + views).
    # IMPORTANT: Sliced querysets cannot be annotated/filtered further, so
    # materialise to IDs first, then build a fresh queryset for bulk extraction.
    candidate_ids = list(
        candidates_qs.order_by('-created_at').values_list('id', flat=True)[:500]
    )
    candidates_qs = JobPost.objects.filter(id__in=candidate_ids).select_related('company')

    job_features_list = extract_bulk_job_features(candidates_qs)
    job_features_map = {jf.job_id: jf for jf in job_features_list}

    if not job_features_list:
        latency = int((time.monotonic() - start_time) * 1000)
        return [], latency

    # Collaborative filtering scores
    candidate_ids = [jf.job_id for jf in job_features_list]
    cold_start = is_cold_start(user.id)
    collab_scores = {}
    if not cold_start:
        collab_scores = get_collaborative_scores(user.id, candidate_ids)

    # Score each candidate — per-job try/except for resilience
    results = []
    for jf in job_features_list:
        try:
            # Content-based
            content = compute_content_score(
                user_skills=user_features.skills,
                job_skills=jf.skills_required,
                user_experience_level='',
                job_experience_level=jf.experience_level,
                user_location=user_features.location,
                job_location=jf.location,
                job_work_mode=jf.work_mode,
                user_salary_min=user_features.salary_min,
                user_salary_max=user_features.salary_max,
                job_salary_min=jf.salary_min,
                job_salary_max=jf.salary_max,
                user_work_mode_pref=user_features.work_mode_pref,
            )

            content_score = content['score']
            collab_score = collab_scores.get(jf.job_id, 0.0)
            pop_score = _popularity_score(jf)
            fresh_score = _freshness_score(jf.days_since_posted)

            # Adjust weights for cold start (boost content, zero collab)
            effective_w = dict(w)
            if cold_start:
                effective_w['content'] = w['content'] + w['collaborative']
                effective_w['collaborative'] = 0.0

            final = (
                effective_w['content'] * content_score
                + effective_w['collaborative'] * collab_score
                + effective_w['popularity'] * pop_score
                + effective_w['freshness'] * fresh_score
            )

            explanation = _generate_explanation(
                content['breakdown'],
                user_features.skills,
                jf.skills_required,
                collab_score,
            )

            results.append(RecommendationResult(
                job_id=jf.job_id,
                final_score=round(final, 4),
                content_score=round(content_score, 4),
                collaborative_score=round(collab_score, 4),
                popularity_score=round(pop_score, 4),
                freshness_score=round(fresh_score, 4),
                explanation=explanation,
                breakdown=content['breakdown'],
            ))
        except Exception:
            logger.warning(
                'Scoring failed for job %s, skipping', jf.job_id, exc_info=True,
            )
            continue

    # Sort by final score descending
    results.sort(key=lambda r: -r.final_score)

    # Apply diversity filter
    if diversity:
        results = _apply_diversity(results, MAX_DIVERSITY_PER_COMPANY, job_features_map)

    # Trim to limit
    results = results[:min(limit, MAX_RECOMMENDATIONS)]

    latency = int((time.monotonic() - start_time) * 1000)
    return results, latency


def compute_match_score(user, job) -> dict:
    """
    Compute a detailed match score between a specific user and job.

    Returns dict matching ``MatchScoreResponseSerializer`` schema::

        {
            'job_id': int,
            'final_score': int,          # 0-100 percentage
            'content_score': float,      # raw 0-1 content score
            'collaborative_score': float,
            'explanation': str,
            'breakdown': dict,           # per-factor 0-1 scores
        }
    """
    from intelligence.engine.features import extract_user_features

    uf = extract_user_features(user)

    content = compute_content_score(
        user_skills=uf.skills,
        job_skills=job.skills_required or [],
        user_experience_level='',
        job_experience_level=job.experience_level or '',
        user_location=uf.location,
        job_location=job.location or '',
        job_work_mode=job.work_mode or '',
        user_salary_min=uf.salary_min,
        user_salary_max=uf.salary_max,
        job_salary_min=float(job.salary_min) if job.salary_min else None,
        job_salary_max=float(job.salary_max) if job.salary_max else None,
        user_work_mode_pref=uf.work_mode_pref,
    )

    score_pct = min(int(content['score'] * 100), 100)

    # Attempt collaborative score (may be 0 for cold-start users)
    collab_score = 0.0
    try:
        if not is_cold_start(user.id):
            collab_scores = get_collaborative_scores(user.id, [job.id])
            collab_score = collab_scores.get(job.id, 0.0)
    except Exception:
        logger.debug('Collaborative score unavailable for match-score', exc_info=True)

    explanation = _generate_explanation(
        content['breakdown'],
        uf.skills,
        job.skills_required or [],
        collab_score,
    )

    return {
        'job_id': job.id,
        'final_score': score_pct,
        'content_score': round(content['score'], 4),
        'collaborative_score': round(collab_score, 4),
        'explanation': explanation,
        'breakdown': content['breakdown'],
    }
