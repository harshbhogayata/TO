"""jobs/urls.py"""
from django.urls import path
from .views import (
    JobPostListView, JobPostDetailView,
    CompanyJobsView, CompanyJobDetailView,
    ApplyView, MyApplicationsView,
    CompanyApplicationsView, UpdateApplicationStatusView,
    WithdrawApplicationView,
    SavedJobsView, UnsaveJobView,
)

urlpatterns = [
    # Public job board
    path('', JobPostListView.as_view(), name='job_list'),
    path('<int:pk>/', JobPostDetailView.as_view(), name='job_detail'),

    # Talent actions
    path('<int:pk>/apply/', ApplyView.as_view(), name='job_apply'),
    path('saved/', SavedJobsView.as_view(), name='saved_jobs'),
    path('saved/<int:pk>/', UnsaveJobView.as_view(), name='unsave_job'),

    # My applications (Talent)
    path('applications/', MyApplicationsView.as_view(), name='my_applications'),
    path('applications/<int:pk>/', WithdrawApplicationView.as_view(), name='withdraw_application'),
    path('applications/<int:pk>/status/', UpdateApplicationStatusView.as_view(), name='update_application_status'),

    # Company management
    path('mine/', CompanyJobsView.as_view(), name='company_jobs'),
    path('mine/<int:pk>/', CompanyJobDetailView.as_view(), name='company_job_detail'),
    path('<int:pk>/applications/', CompanyApplicationsView.as_view(), name='job_applications'),
]
