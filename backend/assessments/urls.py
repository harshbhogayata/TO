"""assessments/urls.py — Wire all assessment endpoints."""
from django.urls import path

from .views import (
    # Tags
    QuestionTagListView,
    QuestionTagDetailView,
    # Question banks
    QuestionBankListView,
    QuestionBankCreateView,
    QuestionBankDetailView,
    # Questions
    QuestionListView,
    QuestionCreateView,
    QuestionDetailView,
    QuestionApproveView,
    QuestionBulkApproveView,
    # Assessment catalog
    AssessmentListView,
    AssessmentDetailView,
    # Company assessments
    CompanyAssessmentListView,
    CompanyAssessmentDetailView,
    # Sections
    AssessmentSectionListView,
    # Attempts
    StartAttemptView,
    AttemptDetailView,
    SubmitAnswerView,
    FinalSubmitView,
    # Results
    AttemptResultView,
    MyResultsView,
    CompanyResultsView,
    CompanyResultsExportView,
    # Invitations
    MyInvitationsView,
    SendInvitationView,
    AcceptInvitationView,
    DeclineInvitationView,
    # Badges
    MyBadgesView,
    BadgeVerifyView,
    # Proctor
    ProctorEventCreateView,
    # Reports
    QuestionReportCreateView,
    QuestionReportListView,
)

urlpatterns = [
    # ── Tags ──────────────────────────────────────────────────────────────
    path('tags/', QuestionTagListView.as_view(), name='assessment_tags'),
    path('tags/<slug:slug>/', QuestionTagDetailView.as_view(), name='assessment_tag_detail'),

    # ── Question Banks ────────────────────────────────────────────────────
    path('question-banks/', QuestionBankListView.as_view(), name='question_bank_list'),
    path('question-banks/create/', QuestionBankCreateView.as_view(), name='question_bank_create'),
    path('question-banks/<int:pk>/', QuestionBankDetailView.as_view(), name='question_bank_detail'),

    # ── Questions ─────────────────────────────────────────────────────────
    path('question-banks/<int:bank_id>/questions/',
         QuestionListView.as_view(), name='question_list'),
    path('question-banks/<int:bank_id>/questions/create/',
         QuestionCreateView.as_view(), name='question_create'),
    path('questions/<int:pk>/',
         QuestionDetailView.as_view(), name='question_detail'),
    path('questions/<int:pk>/approve/',
         QuestionApproveView.as_view(), name='question_approve'),
    path('questions/bulk-approve/',
         QuestionBulkApproveView.as_view(), name='question_bulk_approve'),
    path('questions/<int:pk>/report/',
         QuestionReportCreateView.as_view(), name='question_report_create'),

    # ── Assessment Catalog ────────────────────────────────────────────────
    path('', AssessmentListView.as_view(), name='assessment_list'),
    path('<int:pk>/', AssessmentDetailView.as_view(), name='assessment_detail'),

    # ── Company Assessments ───────────────────────────────────────────────
    path('company/', CompanyAssessmentListView.as_view(), name='company_assessment_list'),
    path('company/<int:pk>/',
         CompanyAssessmentDetailView.as_view(), name='company_assessment_detail'),
    path('company/<int:assessment_id>/sections/',
         AssessmentSectionListView.as_view(), name='assessment_section_list'),

    # ── Attempts ──────────────────────────────────────────────────────────
    path('<int:assessment_id>/start/', StartAttemptView.as_view(), name='start_attempt'),
    path('attempts/<uuid:pk>/', AttemptDetailView.as_view(), name='attempt_detail'),
    path('attempts/<uuid:attempt_id>/answer/',
         SubmitAnswerView.as_view(), name='submit_answer'),
    path('attempts/<uuid:attempt_id>/submit/',
         FinalSubmitView.as_view(), name='final_submit'),
    path('attempts/<uuid:attempt_id>/result/',
         AttemptResultView.as_view(), name='attempt_result'),
    path('attempts/<uuid:attempt_id>/proctor-event/',
         ProctorEventCreateView.as_view(), name='proctor_event_create'),

    # ── Results ───────────────────────────────────────────────────────────
    path('my-results/', MyResultsView.as_view(), name='my_results'),
    path('company/results/', CompanyResultsView.as_view(), name='company_results'),
    path('company/results/export/',
         CompanyResultsExportView.as_view(), name='company_results_export'),

    # ── Invitations ───────────────────────────────────────────────────────
    path('invitations/', MyInvitationsView.as_view(), name='my_invitations'),
    path('invitations/send/', SendInvitationView.as_view(), name='send_invitation'),
    path('invitations/<uuid:token>/accept/',
         AcceptInvitationView.as_view(), name='accept_invitation'),
    path('invitations/<uuid:token>/decline/',
         DeclineInvitationView.as_view(), name='decline_invitation'),

    # ── Badges ────────────────────────────────────────────────────────────
    path('badges/', MyBadgesView.as_view(), name='my_badges'),
    path('badges/verify/<uuid:badge_id>/',
         BadgeVerifyView.as_view(), name='badge_verify'),

    # ── Reports (admin) ──────────────────────────────────────────────────
    path('reports/', QuestionReportListView.as_view(), name='question_report_list'),
]
