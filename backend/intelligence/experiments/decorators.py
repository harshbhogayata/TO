"""
intelligence/experiments/decorators.py
View decorators for experiment gating and variant injection.
"""

import functools
import logging
from contextlib import contextmanager

from intelligence.experiments.client import get_feature_flag

logger = logging.getLogger(__name__)


def experiment(experiment_name: str, default_variant: str = 'control'):
    """
    View decorator that injects the experiment variant into the request.

    Usage:
        @experiment('recommendation_weights')
        def my_view(request):
            variant = request.experiment_variant  # 'control' or 'treatment'
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if hasattr(request, 'user') and request.user.is_authenticated:
                variant = get_feature_flag(
                    experiment_name,
                    request.user.id,
                    default=default_variant,
                )
            else:
                variant = default_variant

            request.experiment_variant = variant
            request.experiment_name = experiment_name
            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator


@contextmanager
def experiment_context(experiment_name: str, user_id, default_variant: str = 'control'):
    """
    Context manager for experiment gating in non-view code.

    Usage:
        with experiment_context('rec_weights', user.id) as variant:
            if variant == 'treatment':
                ...
    """
    try:
        variant = get_feature_flag(experiment_name, user_id, default=default_variant)
    except Exception:
        variant = default_variant

    yield variant
