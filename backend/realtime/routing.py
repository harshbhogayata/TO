"""
realtime/routing.py
WebSocket URL routing for Django Channels.

All WebSocket endpoints are namespaced under /ws/ to clearly separate
them from HTTP routes and simplify reverse-proxy configuration
(e.g. Nginx `location /ws/` → Daphne).
"""

from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/chat/$', consumers.ChatConsumer.as_asgi()),
    re_path(r'ws/notifications/$', consumers.NotificationConsumer.as_asgi()),
]
