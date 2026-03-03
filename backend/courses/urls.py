"""
courses/urls.py
Phase 7 — LMS URL Configuration

Mounted at /api/v1/courses/ by the root urlconf.

URL Structure
─────────────
  /                                          Course catalog (list)
  /<slug>/                                   Course detail
  /<slug>/reviews/                           Reviews for a course
  /<slug>/lessons/<slug>/                    Lesson detail / content
  /<slug>/lessons/<slug>/progress/           Update lesson progress
  /<slug>/progress/                          Course progress overview
  /categories/                               Category tree
  /categories/<slug>/                        Category detail
  /instructors/                              Instructor list
  /instructors/<slug>/                       Instructor detail
  /enrollments/                              My enrollments (list + create)
  /enrollments/<id>/                         Enrollment detail
  /enrollments/<id>/drop/                    Drop a course
  /reviews/<id>/vote/                        Vote on a review
  /certificates/                             My certificates
  /certificates/verify/<uuid>/               Public certificate verification
"""
from django.urls import path

from . import views

urlpatterns = [
    # ── Categories ───────────────────────────────────────────────────────
    path('categories/', views.CourseCategoryListView.as_view(), name='course-category-list'),
    path('categories/<slug:slug>/', views.CourseCategoryDetailView.as_view(), name='course-category-detail'),

    # ── Instructors ──────────────────────────────────────────────────────
    path('instructors/', views.CourseInstructorListView.as_view(), name='course-instructor-list'),
    path('instructors/<slug:slug>/', views.CourseInstructorDetailView.as_view(), name='course-instructor-detail'),

    # ── Enrollments ──────────────────────────────────────────────────────
    path('enrollments/', views.EnrollmentListView.as_view(), name='enrollment-list'),
    path('enrollments/create/', views.EnrollmentCreateView.as_view(), name='enrollment-create'),
    path('enrollments/<int:pk>/', views.EnrollmentDetailView.as_view(), name='enrollment-detail'),
    path('enrollments/<int:pk>/drop/', views.EnrollmentDropView.as_view(), name='enrollment-drop'),

    # ── Certificates ─────────────────────────────────────────────────────
    path('certificates/', views.MyCertificateListView.as_view(), name='certificate-list'),
    path('certificates/verify/<uuid:certificate_id>/', views.CertificateVerifyView.as_view(), name='certificate-verify'),

    # ── Reviews (cross-course) ───────────────────────────────────────────
    path('reviews/<int:pk>/vote/', views.CourseReviewVoteView.as_view(), name='review-vote'),

    # ── Course detail + nested resources ─────────────────────────────────
    path('<slug:slug>/', views.CourseDetailView.as_view(), name='course-detail'),
    path('<slug:course_slug>/reviews/', views.CourseReviewListView.as_view(), name='course-review-list'),
    path('<slug:course_slug>/reviews/create/', views.CourseReviewCreateView.as_view(), name='course-review-create'),
    path('<slug:course_slug>/lessons/<slug:lesson_slug>/', views.LessonDetailView.as_view(), name='lesson-detail'),
    path('<slug:course_slug>/lessons/<slug:lesson_slug>/progress/', views.LessonProgressView.as_view(), name='lesson-progress'),
    path('<slug:course_slug>/progress/', views.CourseProgressOverview.as_view(), name='course-progress'),

    # ── Course list (root) — MUST be last to avoid slug conflicts ────────
    path('', views.CourseListView.as_view(), name='course-list'),
]
