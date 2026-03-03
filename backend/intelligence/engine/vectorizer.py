"""
intelligence/engine/vectorizer.py
TF-IDF skill vectorisation + cosine similarity for content-based recommendations.

The vectoriser is trained on the full skill corpus from all JobPosts + TalentProfiles,
stored as a pickled ModelArtifact, and cached in Redis for fast inference.
"""

import logging
import pickle
from typing import Optional

import numpy as np
from django.core.cache import cache

from intelligence.constants import ALIAS_TO_CANONICAL, TFIDF_MODEL_CACHE_TTL

logger = logging.getLogger(__name__)

_CACHE_KEY = 'intelligence:tfidf_vectorizer'


def normalise_skills(skills: list[str]) -> list[str]:
    """Map raw skill strings to canonical names via the alias lookup."""
    normalised = []
    for skill in skills:
        canonical = ALIAS_TO_CANONICAL.get(skill.lower().strip(), skill.lower().strip())
        if canonical:
            normalised.append(canonical)
    return sorted(set(normalised))


def _get_vectorizer():
    """
    Load the trained TF-IDF vectoriser from Redis cache, or fall back to DB.
    Returns (vectorizer, feature_names) or (None, None) if no model exists.
    """
    cached = cache.get(_CACHE_KEY)
    if cached:
        return pickle.loads(cached)

    try:
        from intelligence.models import ModelArtifact
        artifact = ModelArtifact.objects.filter(
            name='tfidf_vectorizer', is_active=True,
        ).order_by('-version').first()

        if artifact:
            data = pickle.loads(artifact.artifact_data)
            cache.set(_CACHE_KEY, artifact.artifact_data, TFIDF_MODEL_CACHE_TTL)
            return data
    except Exception:
        logger.warning('Failed to load TF-IDF vectoriser from DB', exc_info=True)

    return None, None


def train_vectorizer() -> dict:
    """
    Train a new TF-IDF vectoriser on the full skill corpus and persist it.
    Called by the daily Celery task.
    Returns metadata dict.
    """
    from sklearn.feature_extraction.text import TfidfVectorizer

    from accounts.models import TalentProfile
    from jobs.models import JobPost

    # Collect all skill documents: each user/job skill list → single space-joined string
    documents = []

    for skills in TalentProfile.objects.values_list('skills', flat=True):
        if skills:
            normalised = normalise_skills(skills)
            if normalised:
                documents.append(' '.join(normalised))

    for skills in JobPost.objects.filter(status='open').values_list('skills_required', flat=True):
        if skills:
            normalised = normalise_skills(skills)
            if normalised:
                documents.append(' '.join(normalised))

    if not documents:
        logger.warning('No skill documents found for TF-IDF training')
        return {'status': 'empty', 'num_documents': 0}

    vectorizer = TfidfVectorizer(
        analyzer='word',
        token_pattern=r'[a-z0-9\-\.]+',
        max_features=2000,
        min_df=1,
        max_df=0.95,
        sublinear_tf=True,
    )
    vectorizer.fit(documents)

    # Persist as ModelArtifact
    from intelligence.models import ModelArtifact
    ModelArtifact.objects.filter(name='tfidf_vectorizer').update(is_active=False)

    latest_version = (
        ModelArtifact.objects.filter(name='tfidf_vectorizer')
        .order_by('-version').values_list('version', flat=True).first() or 0
    )

    payload = pickle.dumps((vectorizer, vectorizer.get_feature_names_out().tolist()))
    ModelArtifact.objects.create(
        name='tfidf_vectorizer',
        version=latest_version + 1,
        artifact_data=payload,
        metadata={
            'num_documents': len(documents),
            'num_features': len(vectorizer.get_feature_names_out()),
        },
        is_active=True,
    )

    # Update cache
    cache.set(_CACHE_KEY, payload, TFIDF_MODEL_CACHE_TTL)
    cache.delete('intelligence:interaction_matrix')  # bust stale interaction cache

    return {
        'status': 'trained',
        'num_documents': len(documents),
        'num_features': len(vectorizer.get_feature_names_out()),
        'version': latest_version + 1,
    }


def compute_skill_similarity(
    user_skills: list[str],
    job_skills: list[str],
) -> float:
    """
    Compute cosine similarity between user skills and job skills
    using the trained TF-IDF vectoriser.
    Falls back to simple Jaccard if no vectoriser is available.
    """
    norm_user = normalise_skills(user_skills)
    norm_job = normalise_skills(job_skills)

    if not norm_user or not norm_job:
        return 0.0

    vectorizer_data = _get_vectorizer()
    if vectorizer_data is None or vectorizer_data[0] is None:
        # Fallback: Jaccard similarity
        user_set = set(norm_user)
        job_set = set(norm_job)
        intersection = len(user_set & job_set)
        union = len(user_set | job_set)
        return intersection / union if union else 0.0

    vectorizer, feature_names = vectorizer_data

    try:
        from sklearn.metrics.pairwise import cosine_similarity

        user_doc = ' '.join(norm_user)
        job_doc = ' '.join(norm_job)

        vectors = vectorizer.transform([user_doc, job_doc])
        similarity = cosine_similarity(vectors[0:1], vectors[1:2])[0][0]
        return float(max(0.0, min(1.0, similarity)))
    except Exception:
        logger.warning('TF-IDF transform failed, using Jaccard fallback', exc_info=True)
        user_set = set(norm_user)
        job_set = set(norm_job)
        intersection = len(user_set & job_set)
        union = len(user_set | job_set)
        return intersection / union if union else 0.0


def vectorize_skills(skills: list[str]) -> Optional[np.ndarray]:
    """Transform a skill list into a TF-IDF vector. Returns None if no vectoriser."""
    norm = normalise_skills(skills)
    if not norm:
        return None

    vectorizer_data = _get_vectorizer()
    if vectorizer_data is None or vectorizer_data[0] is None:
        return None

    vectorizer, _ = vectorizer_data
    try:
        return vectorizer.transform([' '.join(norm)]).toarray()[0]
    except Exception:
        return None
