"""admin_api/urls.py"""
from django.urls import path
from .views import (
    platform_stats,
    public_stats,
    AdminUserListView,
    verify_user,
    deactivate_user,
    AdminJobListView,
    toggle_job_status,
    AdminApplicationListView,
)

urlpatterns = [
    path('stats/', platform_stats, name='admin_stats'),
    path('public-stats/', public_stats, name='public_stats'),
    path('users/', AdminUserListView.as_view(), name='admin_users'),
    path('users/<int:pk>/verify/', verify_user, name='admin_verify_user'),
    path('users/<int:pk>/', deactivate_user, name='admin_deactivate_user'),
    path('jobs/', AdminJobListView.as_view(), name='admin_jobs'),
    path('jobs/<int:pk>/toggle/', toggle_job_status, name='admin_toggle_job'),
    path('applications/', AdminApplicationListView.as_view(), name='admin_applications'),
]
