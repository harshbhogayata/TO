"""intelligence.engine — Recommendation scoring pipeline.

Public API (import from submodules directly)::

    from intelligence.engine.hybrid import compute_recommendations, compute_match_score
    from intelligence.engine.cache import invalidate_user_recommendations
"""

__all__ = [
    'hybrid',
    'cache',
    'content_based',
    'collaborative',
    'features',
    'vectorizer',
]