"""realtime/urls.py"""
from django.urls import path
from .views import register_push_token, unregister_push_token, get_presence

urlpatterns = [
    path('subscribe/', register_push_token, name='push-subscribe'),
    path('unsubscribe/', unregister_push_token, name='push-unsubscribe'),
    path('presence/', get_presence, name='presence'),
]
