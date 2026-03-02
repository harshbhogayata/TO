"""
accounts/utils.py
Shared utility functions for the accounts app.
"""
import logging

logger = logging.getLogger(__name__)


def blacklist_all_tokens(user):
    """Blacklist all outstanding refresh tokens for a user.

    Silently logs errors if the token_blacklist app is not fully configured.
    """
    try:
        from rest_framework_simplejwt.token_blacklist.models import (
            OutstandingToken,
            BlacklistedToken,
        )
        tokens = OutstandingToken.objects.filter(user=user)
        for token in tokens:
            BlacklistedToken.objects.get_or_create(token=token)
    except Exception:
        logger.warning('Failed to blacklist tokens for user %s', user.pk, exc_info=True)
