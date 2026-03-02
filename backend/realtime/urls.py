"""realtime/urls.py"""
from django.urls import path
from .views import register_push_token, unregister_push_token

urlpatterns = [
    path('subscribe/', register_push_token, name='push-subscribe'),
    path('unsubscribe/', unregister_push_token, name='push-unsubscribe'),
]
