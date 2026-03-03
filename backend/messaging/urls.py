"""messaging/urls.py"""
from django.urls import path
from .views import (
    MyThreadsView,
    create_thread,
    ThreadMessagesView,
    SendMessageView,
    unread_count,
    sync_messages,
)

urlpatterns = [
    path('', MyThreadsView.as_view(), name='my_threads'),
    path('thread/', create_thread, name='create_thread'),
    path('<int:thread_id>/messages/', ThreadMessagesView.as_view(), name='thread_messages'),
    path('<int:thread_id>/sync/', sync_messages, name='sync_messages'),
    path('send/', SendMessageView.as_view(), name='send_message'),
    path('unread/', unread_count, name='unread_count'),
]
