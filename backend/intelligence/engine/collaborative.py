"""
intelligence/engine/collaborative.py
Collaborative filtering using sparse user-item interaction matrices.

Builds a user-job interaction matrix from views, clicks, saves, and applications.
Uses cosine similarity on interaction vectors to find k-nearest-neighbour users,
then aggregates neighbour preferences to score unseen jobs.
"""

import logging
import pickle
from collections import defaultdict

import numpy as np
from django.core.cache import cache

from intelligence.constants import (
    COLD_START_THRESHOLD,
    INTERACTION_MATRIX_CACHE_TTL,
    INTERACTION_WEIGHTS,
)

logger = logging.getLogger(__name__)

_CACHE_KEY = 'intelligence:interaction_matrix'


def _load_matrix():
    """Load pre-built interaction matrix from cache or DB."""
    cached = cache.get(_CACHE_KEY)
    if cached:
        return pickle.loads(cached)

    try:
        from intelligence.models import ModelArtifact
        artifact = ModelArtifact.objects.filter(
            name='interaction_matrix', is_active=True,
        ).order_by('-version').first()

        if artifact:
            data = pickle.loads(artifact.artifact_data)
            cache.set(_CACHE_KEY, artifact.artifact_data, INTERACTION_MATRIX_CACHE_TTL)
            return data
    except Exception:
        logger.warning('Failed to load interaction matrix', exc_info=True)

    return None


def build_interaction_matrix() -> dict:
    """
    Build and persist the user-item interaction matrix.
    Called by the daily Celery task.
    Returns metadata dict.
    """
    from intelligence.models import UserInteraction

    interactions = UserInteraction.objects.values_list(
        'user_id', 'job_id', 'interaction_type',
    ).iterator(chunk_size=10_000)

    user_ids = set()
    job_ids = set()
    entries = []

    for user_id, job_id, itype in interactions:
        user_ids.add(user_id)
        job_ids.add(job_id)
        weight = INTERACTION_WEIGHTS.get(itype, 1.0)
        entries.append((user_id, job_id, weight))

    if not entries:
        logger.info('No interactions found for matrix building')
        return {'status': 'empty', 'users': 0, 'jobs': 0}

    user_list = sorted(user_ids)
    job_list = sorted(job_ids)
    user_idx = {uid: i for i, uid in enumerate(user_list)}
    job_idx = {jid: i for i, jid in enumerate(job_list)}

    # Build sparse-like dict: user_idx → {job_idx: aggregated_weight}
    matrix = defaultdict(lambda: defaultdict(float))
    for user_id, job_id, weight in entries:
        matrix[user_idx[user_id]][job_idx[job_id]] += weight

    data = {
        'user_list': user_list,
        'job_list': job_list,
        'user_idx': user_idx,
        'job_idx': job_idx,
        # Convert inner defaultdicts to plain dicts for clean serialisation
        'matrix': {k: dict(v) for k, v in matrix.items()},
    }

    # Persist
    from intelligence.models import ModelArtifact
    ModelArtifact.objects.filter(name='interaction_matrix').update(is_active=False)

    latest_version = (
        ModelArtifact.objects.filter(name='interaction_matrix')
        .order_by('-version').values_list('version', flat=True).first() or 0
    )

    payload = pickle.dumps(data)
    ModelArtifact.objects.create(
        name='interaction_matrix',
        version=latest_version + 1,
        artifact_data=payload,
        metadata={
            'num_users': len(user_list),
            'num_jobs': len(job_list),
            'num_interactions': len(entries),
        },
        is_active=True,
    )

    cache.set(_CACHE_KEY, payload, INTERACTION_MATRIX_CACHE_TTL)

    return {
        'status': 'built',
        'num_users': len(user_list),
        'num_jobs': len(job_list),
        'num_interactions': len(entries),
        'version': latest_version + 1,
    }


def _cosine_sim(vec_a: dict, vec_b: dict) -> float:
    """Cosine similarity between two sparse vectors (dict of index→weight)."""
    common = set(vec_a.keys()) & set(vec_b.keys())
    if not common:
        return 0.0

    dot = sum(vec_a[k] * vec_b[k] for k in common)
    norm_a = np.sqrt(sum(v ** 2 for v in vec_a.values()))
    norm_b = np.sqrt(sum(v ** 2 for v in vec_b.values()))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)


def get_collaborative_scores(
    user_id: int,
    candidate_job_ids: list[int],
    k: int = 20,
) -> dict[int, float]:
    """
    Compute collaborative filtering scores for candidate jobs.
    Returns {job_id: score} dict with scores in [0, 1].
    """
    data = _load_matrix()
    if data is None:
        return {}

    user_idx = data['user_idx']
    job_idx = data['job_idx']
    job_list = data['job_list']
    matrix = data['matrix']

    if user_id not in user_idx:
        return {}

    target_uidx = user_idx[user_id]
    target_vec = matrix.get(target_uidx, {})

    if len(target_vec) < COLD_START_THRESHOLD:
        return {}

    # Find k nearest neighbours by cosine similarity
    similarities = []
    for other_uidx, other_vec in matrix.items():
        if other_uidx == target_uidx:
            continue
        sim = _cosine_sim(target_vec, other_vec)
        if sim > 0:
            similarities.append((other_uidx, sim, other_vec))

    similarities.sort(key=lambda x: -x[1])
    neighbours = similarities[:k]

    if not neighbours:
        return {}

    # Aggregate neighbour preferences for candidate jobs
    scores = {}
    candidate_jidxs = {job_idx[jid]: jid for jid in candidate_job_ids if jid in job_idx}

    for jidx, jid in candidate_jidxs.items():
        weighted_sum = 0.0
        sim_sum = 0.0
        for _, sim, nvec in neighbours:
            if jidx in nvec:
                weighted_sum += sim * nvec[jidx]
                sim_sum += abs(sim)
        if sim_sum > 0:
            scores[jid] = weighted_sum / sim_sum

    # Normalise to [0, 1]
    if scores:
        max_score = max(scores.values())
        if max_score > 0:
            scores = {jid: s / max_score for jid, s in scores.items()}

    return scores


def is_cold_start(user_id: int) -> bool:
    """Check if user has too few interactions for collaborative filtering."""
    from intelligence.models import UserInteraction
    count = UserInteraction.objects.filter(user_id=user_id).count()
    return count < COLD_START_THRESHOLD
