"""
ASGI config for talentorbit project.

Routes HTTP requests to Django and WebSocket connections to Channels.
JWT authentication is applied to WebSocket connections via query-string token.
Rate limiting and connection tracking middleware protect against abuse.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'talentorbit.settings')

# Initialize Django ASGI application early to ensure AppRegistry is populated
# before importing consumers.
django_asgi_app = get_asgi_application()

# Import after Django setup to avoid AppRegistryNotReady
from realtime.authentication import JWTAuthMiddleware  # noqa: E402
from realtime.middleware import (  # noqa: E402
    ConnectionRateLimitMiddleware,
    ConnectionTrackingMiddleware,
)
from realtime.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AllowedHostsOriginValidator(
        ConnectionRateLimitMiddleware(
            ConnectionTrackingMiddleware(
                JWTAuthMiddleware(
                    URLRouter(websocket_urlpatterns)
                )
            )
        )
    ),
})
