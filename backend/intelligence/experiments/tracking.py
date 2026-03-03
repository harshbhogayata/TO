"""
intelligence/experiments/tracking.py
Event tracking helpers for A/B test conversion metrics.
"""

import logging

from intelligence.experiments.client import capture_event

logger = logging.getLogger(__name__)


def track_recommendation_click(user_id: int, job_id: int, position: int, variant: str = ''):
    """Track when a user clicks a recommended job."""
    capture_event(user_id, 'recommendation_clicked', {
        'job_id': job_id,
        'position': position,
        'variant': variant,
    })


def track_recommendation_apply(user_id: int, job_id: int, source: str = 'recommendation'):
    """Track when a user applies from a recommendation."""
    capture_event(user_id, 'recommendation_applied', {
        'job_id': job_id,
        'source': source,
    })


def track_resume_upload(user_id: int, file_type: str = '', variant: str = ''):
    """Track resume upload event for A/B testing."""
    capture_event(user_id, 'resume_uploaded', {
        'file_type': file_type,
        'variant': variant,
    })


def track_resume_apply(user_id: int, fields_applied: list[str] | None = None):
    """Track when a user applies parsed resume data to their profile."""
    capture_event(user_id, 'resume_data_applied', {
        'fields_applied': fields_applied or [],
    })


def track_match_score_view(user_id: int, job_id: int, score: int, variant: str = ''):
    """Track when a user views a match score breakdown."""
    capture_event(user_id, 'match_score_viewed', {
        'job_id': job_id,
        'score': score,
        'variant': variant,
    })


def track_analytics_view(user_id: int, dashboard_type: str = 'company'):
    """Track analytics dashboard view."""
    capture_event(user_id, 'analytics_dashboard_viewed', {
        'dashboard_type': dashboard_type,
    })
