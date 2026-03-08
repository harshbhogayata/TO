"""
intelligence/urls.py
URL routing for the Intelligence API.
Mounted at: /api/v1/intelligence/
"""
from django.urls import path

from .views import (
    # Recommendations
    RecommendedJobsView,
    MatchScoreView,
    # Interactions
    RecordInteractionView,
    # Resume parser
    ParseResumeView,
    ParseResumeUnauthenticatedView,
    ApplyParsedResumeView,
    # Skill taxonomy
    SkillTaxonomyListView,
    SkillSuggestionView,
    # Company analytics
    CompanyOverviewView,
    CompanyFunnelView,
    CompanyTimeToHireView,
    CompanySourcesView,
    CompanyTalentPoolView,
    CompanyBenchmarksView,
    CompanyJobPerformanceView,
    CompanyAnalyticsExportView,
    # Platform analytics (admin)
    PlatformMetricsView,
    PlatformGrowthView,
    PlatformEngagementView,
    PlatformBenchmarksView,
    # Experiments
    FeatureFlagsView,
    ExperimentTrackView,
)

from .views_ai_enhanced import (
    ParseResumeAIEnhancedPublicView,
    ParseResumeAIEnhancedView,
)

from .ai_views import (
    ai_generate_job_description,
    ai_schedule_interviews,
    ai_chat,
    ai_compensation_benchmark,
)

app_name = 'intelligence'

urlpatterns = [
    # â”€â”€ Recommendations â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    path('recommendations/jobs/', RecommendedJobsView.as_view(), name='recommended_jobs'),
    path('match-score/', MatchScoreView.as_view(), name='match_score'),

    # â”€â”€ Interactions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    path('interactions/', RecordInteractionView.as_view(), name='record_interaction'),

    # â”€â”€ Resume Parser â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    path('parse-resume/', ParseResumeView.as_view(), name='parse_resume'),
    path('parse-resume-public/', ParseResumeUnauthenticatedView.as_view(), name='parse_resume_public'),
    path('parse-resume-ai/', ParseResumeAIEnhancedView.as_view(), name='parse_resume_ai'),
    path('parse-resume-ai-public/', ParseResumeAIEnhancedPublicView.as_view(), name='parse_resume_ai_public'),
    path('parse-resume/apply/', ApplyParsedResumeView.as_view(), name='apply_parsed_resume'),

    # â”€â”€ Skill Taxonomy â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    path('skills/taxonomy/', SkillTaxonomyListView.as_view(), name='skill_taxonomy'),
    path('skills/suggestions/', SkillSuggestionView.as_view(), name='skill_suggestions'),

    # â”€â”€ Company Analytics â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    path('analytics/overview/', CompanyOverviewView.as_view(), name='analytics_overview'),
    path('analytics/funnel/', CompanyFunnelView.as_view(), name='analytics_funnel'),
    path('analytics/time-to-hire/', CompanyTimeToHireView.as_view(), name='analytics_time_to_hire'),
    path('analytics/sources/', CompanySourcesView.as_view(), name='analytics_sources'),
    path('analytics/talent-pool/', CompanyTalentPoolView.as_view(), name='analytics_talent_pool'),
    path('analytics/benchmarks/', CompanyBenchmarksView.as_view(), name='analytics_benchmarks'),
    path('analytics/jobs/', CompanyJobPerformanceView.as_view(), name='analytics_jobs'),
    path('analytics/export/', CompanyAnalyticsExportView.as_view(), name='analytics_export'),

    # â”€â”€ Platform Analytics (Admin) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    path('analytics/platform/', PlatformMetricsView.as_view(), name='platform_metrics'),
    path('analytics/platform/growth/', PlatformGrowthView.as_view(), name='platform_growth'),
    path('analytics/platform/engagement/', PlatformEngagementView.as_view(), name='platform_engagement'),
    path('analytics/platform/benchmarks/', PlatformBenchmarksView.as_view(), name='platform_benchmarks'),

    # â”€â”€ Experiments / A/B Testing â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    path('experiments/flags/', FeatureFlagsView.as_view(), name='experiment_flags'),
    path('experiments/track/', ExperimentTrackView.as_view(), name='experiment_track'),

    # â”€â”€ AI Features â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    path('ai/job-description/', ai_generate_job_description, name='ai_job_description'),
    path('ai/schedule-interviews/', ai_schedule_interviews, name='ai_schedule_interviews'),
    path('ai/chat/', ai_chat, name='ai_chat'),
    path('ai/compensation/', ai_compensation_benchmark, name='ai_compensation_benchmark'),
]

