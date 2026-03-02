"""
realtime/authentication.py
JWT-based WebSocket authentication for Django Channels.

WebSockets cannot send custom headers after the initial handshake, so we
authenticate via a query-string token: ws://host/ws/.../?token=<JWT>.

Security considerations:
    - Token is validated on connect; connection is rejected if invalid/expired.
    - The access token is short-lived (60 min default) — same as REST API.
    - The token is only sent once (in the URL) and is not logged by Django.
    - TLS in production ensures the URL is encrypted in transit.
"""

import logging
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError

logger = logging.getLogger(__name__)


@database_sync_to_async
def get_user_from_token(token_str: str):
    """
    Validate a JWT access token and return the corresponding User.
    Returns AnonymousUser if the token is invalid or the user doesn't exist.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()

    try:
        validated = AccessToken(token_str)
        user_id = validated.get('user_id')
        if user_id is None:
            return AnonymousUser()
        user = User.objects.get(pk=user_id, is_active=True)
        return user
    except (TokenError, User.DoesNotExist) as exc:
        logger.debug('WebSocket auth failed: %s', exc)
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """
    Channels middleware that authenticates WebSocket connections via JWT.

    Usage in routing:
        JWTAuthMiddleware(URLRouter([...]))

    The token is extracted from the query string: ?token=<access_token>
    """

    async def __call__(self, scope, receive, send):
        query_string = scope.get('query_string', b'').decode('utf-8')
        params = parse_qs(query_string)
        token_list = params.get('token', [])

        if token_list:
            scope['user'] = await get_user_from_token(token_list[0])
        else:
            scope['user'] = AnonymousUser()

        return await super().__call__(scope, receive, send)
