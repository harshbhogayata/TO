"""
intelligence/experiments/middleware.py
Django middleware that attaches active feature flags to every request.
"""

import logging

logger = logging.getLogger(__name__)


class ExperimentMiddleware:
    """
    Attaches active feature flags to every request as `request.feature_flags`.
    Only runs for authenticated users.  Flags are cached per-user in Redis.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.feature_flags = {}

        if hasattr(request, 'user') and request.user.is_authenticated:
            try:
                from intelligence.experiments.client import get_all_flags
                request.feature_flags = get_all_flags(request.user.id)
            except Exception:
                logger.debug('Failed to load feature flags for request', exc_info=True)

        response = self.get_response(request)
        return response
