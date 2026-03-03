"""reviews/urls.py"""
from django.urls import path

from .views import (
    CompanyReviewCreateView,
    CompanyReviewListView,
    CompanyReviewStatsView,
    respond_to_review,
    toggle_helpful,
)

urlpatterns = [
    # Public
    path('<int:company_id>/', CompanyReviewListView.as_view(), name='company_reviews'),
    path('<int:company_id>/stats/', CompanyReviewStatsView.as_view(), name='company_review_stats'),

    # Authenticated
    path('', CompanyReviewCreateView.as_view(), name='create_review'),
    path('<uuid:review_id>/helpful/', toggle_helpful, name='toggle_helpful'),
    path('<uuid:review_id>/respond/', respond_to_review, name='respond_to_review'),
]
