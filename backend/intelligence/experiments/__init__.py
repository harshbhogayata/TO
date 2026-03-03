"""intelligence.experiments — Feature flags, A/B testing, and event tracking.

Public API (import from submodules directly)::

    from intelligence.experiments.client import get_feature_flag, get_all_flags
    from intelligence.experiments.tracking import track_recommendation_click
"""

__all__ = [
    'client',
    'decorators',
    'middleware',
    'tracking',
]