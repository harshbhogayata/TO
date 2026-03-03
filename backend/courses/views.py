"""
courses/views.py
Phase 7 — LMS Views

Enterprise-grade endpoints for the full course content engine.

Endpoint Groups
───────────────
  Categories      — Browse hierarchical course taxonomy
  Instructors     — View instructor profiles
  Courses         — Catalog listing, filtering, search, detail
  Enrollment      — Enroll, drop, list my courses
  Modules/Lessons — Access course content (enrolled users only)
  Progress        — Track lesson completion
  Reviews         — Read / write course reviews
  Certificates    — View / verify completion certificates

Patterns applied (matching intelligence/views.py, jobs/views.py):
  - Throttle classes on every endpoint
  - IsEmailVerified on write endpoints
  - Structured logger per module
  - select_related / prefetch_related on all querysets
  - Graceful exception handling
"""
import logging

from django.db import models as db_models
from django.db.models import Avg, Count, Prefetch, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from accounts.permissions import IsEmailVerified

from .models import (
    Certificate,
    Course,
    CourseCategory,
    CourseEnrollment,
    CourseInstructor,
    CourseModule,
    CourseReview,
    Lesson,
    LessonAttachment,
    LessonProgress,
)
from .serializers import (
    CertificateSerializer,
    CourseCategorySerializer,
    CourseCategoryWriteSerializer,
    CourseDetailSerializer,
    CourseEnrollmentCreateSerializer,
    CourseEnrollmentSerializer,
    CourseInstructorSerializer,
    CourseListSerializer,
    CourseModuleSerializer,
    CourseReviewSerializer,
    CourseReviewWriteSerializer,
    CourseWriteSerializer,
    LessonDetailSerializer,
    LessonProgressSerializer,
    LessonProgressUpdateSerializer,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER MIXINS
# ═══════════════════════════════════════════════════════════════════════════════

class CourseQueryMixin:
    """Shared queryset optimisations for course views."""

    @staticmethod
    def get_published_courses():
        """
        Base queryset for published courses with all standard prefetches.
        N+1 safe — every FK/M2M used in serializers is eagerly loaded.
        """
        return (
            Course.objects
            .filter(status=Course.Status.PUBLISHED)
            .select_related('category')
            .prefetch_related(
                'instructors',
                'prerequisites',
                Prefetch(
                    'modules',
                    queryset=CourseModule.objects.order_by('position').prefetch_related(
                        Prefetch(
                            'lessons',
                            queryset=Lesson.objects.order_by('position'),
                        )
                    ),
                ),
            )
            .annotate(
                module_count=Count('modules', distinct=True),
                lesson_count=Count('modules__lessons', distinct=True),
            )
        )


# ═══════════════════════════════════════════════════════════════════════════════
# CATEGORIES
# ═══════════════════════════════════════════════════════════════════════════════

class CourseCategoryListView(generics.ListAPIView):
    """
    GET /api/v1/courses/categories/
    Browse the hierarchical course taxonomy. Returns top-level categories
    with nested children and course counts.
    """
    serializer_class = CourseCategorySerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [UserRateThrottle]
    pagination_class = None  # Categories are few; return all

    def get_queryset(self):
        return (
            CourseCategory.objects
            .filter(is_active=True, parent__isnull=True)
            .annotate(
                course_count=Count(
                    'courses',
                    filter=Q(courses__status=Course.Status.PUBLISHED),
                ),
            )
            .prefetch_related(
                Prefetch(
                    'children',
                    queryset=CourseCategory.objects.filter(is_active=True)
                    .annotate(
                        course_count=Count(
                            'courses',
                            filter=Q(courses__status=Course.Status.PUBLISHED),
                        ),
                    )
                    .order_by('position'),
                ),
            )
            .order_by('position', 'name')
        )


class CourseCategoryDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/courses/categories/<slug>/
    Retrieve a single category with its children and published course count.
    """
    serializer_class = CourseCategorySerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [UserRateThrottle]
    lookup_field = 'slug'

    def get_queryset(self):
        return (
            CourseCategory.objects
            .filter(is_active=True)
            .annotate(
                course_count=Count(
                    'courses',
                    filter=Q(courses__status=Course.Status.PUBLISHED),
                ),
            )
            .prefetch_related('children')
        )


# ═══════════════════════════════════════════════════════════════════════════════
# INSTRUCTORS
# ═══════════════════════════════════════════════════════════════════════════════

class CourseInstructorListView(generics.ListAPIView):
    """
    GET /api/v1/courses/instructors/
    Browse verified course instructors.
    """
    serializer_class = CourseInstructorSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [UserRateThrottle]

    def get_queryset(self):
        return (
            CourseInstructor.objects
            .filter(is_verified=True)
            .select_related('user')
            .annotate(
                total_students=Count(
                    'courses__enrollments',
                    filter=Q(courses__status=Course.Status.PUBLISHED),
                    distinct=True,
                ),
            )
            .order_by('-total_students')
        )


class CourseInstructorDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/courses/instructors/<slug>/
    Retrieve an instructor profile.
    """
    serializer_class = CourseInstructorSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [UserRateThrottle]
    lookup_field = 'slug'

    def get_queryset(self):
        return (
            CourseInstructor.objects
            .filter(is_verified=True)
            .select_related('user')
        )


# ═══════════════════════════════════════════════════════════════════════════════
# COURSE CATALOG
# ═══════════════════════════════════════════════════════════════════════════════

class CourseListView(generics.ListAPIView, CourseQueryMixin):
    """
    GET /api/v1/courses/
    Paginated, filterable, searchable course catalog.

    Query parameters:
        ?search=<term>        Full-text search on title, subtitle, description
        ?category=<slug>      Filter by category slug (includes subcategories)
        ?level=<choice>       Filter by difficulty level
        ?access=<choice>      Filter by access level (free/premium/private)
        ?instructor=<slug>    Filter by instructor
        ?skills=<csv>         Filter by skills (comma-separated)
        ?ordering=<field>     Order by: popular, newest, rating, title
    """
    serializer_class = CourseListSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [UserRateThrottle]

    def get_queryset(self):
        qs = self.get_published_courses()
        params = self.request.query_params

        # Search
        search = params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(title__icontains=search)
                | Q(subtitle__icontains=search)
                | Q(description__icontains=search)
                | Q(skills__icontains=search)
                | Q(tags__icontains=search)
            )

        # Category filter (includes subcategories)
        category_slug = params.get('category', '').strip()
        if category_slug:
            qs = qs.filter(
                Q(category__slug=category_slug)
                | Q(category__parent__slug=category_slug)
            )

        # Level filter
        level = params.get('level', '').strip()
        if level and level in dict(Course.Level.choices):
            qs = qs.filter(level=level)

        # Access level filter
        access = params.get('access', '').strip()
        if access and access in dict(Course.AccessLevel.choices):
            qs = qs.filter(access_level=access)

        # Instructor filter
        instructor_slug = params.get('instructor', '').strip()
        if instructor_slug:
            qs = qs.filter(instructors__slug=instructor_slug)

        # Skills filter
        skills = params.get('skills', '').strip()
        if skills:
            for skill in skills.split(','):
                skill = skill.strip()
                if skill:
                    qs = qs.filter(skills__icontains=skill)

        # Ordering
        ordering = params.get('ordering', 'popular').strip()
        ordering_map = {
            'popular': '-enrollment_count',
            'newest': '-published_at',
            'rating': '-average_rating',
            'title': 'title',
            '-title': '-title',
        }
        qs = qs.order_by(ordering_map.get(ordering, '-enrollment_count'))

        return qs.distinct()


class CourseDetailView(generics.RetrieveAPIView, CourseQueryMixin):
    """
    GET /api/v1/courses/<slug>/
    Full course detail with modules, lessons, enrollment state.
    """
    serializer_class = CourseDetailSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [UserRateThrottle]
    lookup_field = 'slug'

    def get_queryset(self):
        return self.get_published_courses()


# ═══════════════════════════════════════════════════════════════════════════════
# ENROLLMENT
# ═══════════════════════════════════════════════════════════════════════════════

class EnrollmentListView(generics.ListAPIView):
    """
    GET /api/v1/courses/enrollments/
    List all of the authenticated user's course enrollments.
    Supports filtering by status: ?status=active|completed|dropped
    """
    serializer_class = CourseEnrollmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def get_queryset(self):
        qs = (
            CourseEnrollment.objects
            .filter(user=self.request.user)
            .select_related('course', 'last_lesson')
            .order_by('-last_accessed_at')
        )
        status_filter = self.request.query_params.get('status', '').strip()
        if status_filter and status_filter in dict(CourseEnrollment.Status.choices):
            qs = qs.filter(status=status_filter)
        return qs


class EnrollmentCreateView(generics.CreateAPIView):
    """
    POST /api/v1/courses/enrollments/
    Enroll in a course. Validates prerequisites and access level.
    Body: { "course_id": <int> }
    """
    serializer_class = CourseEnrollmentCreateSerializer
    permission_classes = [permissions.IsAuthenticated, IsEmailVerified]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'enrollment'

    def perform_create(self, serializer):
        enrollment = serializer.save()
        logger.info(
            'User %s enrolled in course %s',
            self.request.user.id,
            enrollment.course_id,
        )


class EnrollmentDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/courses/enrollments/<id>/
    Retrieve a specific enrollment with progress details.
    """
    serializer_class = CourseEnrollmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def get_queryset(self):
        return (
            CourseEnrollment.objects
            .filter(user=self.request.user)
            .select_related('course', 'last_lesson')
        )


class EnrollmentDropView(APIView):
    """
    POST /api/v1/courses/enrollments/<id>/drop/
    Drop a course enrollment. Sets status to 'dropped'.
    """
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'enrollment'

    def post(self, request, pk):
        enrollment = get_object_or_404(
            CourseEnrollment,
            pk=pk,
            user=request.user,
            status=CourseEnrollment.Status.ACTIVE,
        )
        enrollment.status = CourseEnrollment.Status.DROPPED
        enrollment.save(update_fields=['status'])
        logger.info(
            'User %s dropped enrollment %s (course: %s)',
            request.user.id, enrollment.id, enrollment.course_id,
        )
        return Response(
            CourseEnrollmentSerializer(enrollment).data,
            status=status.HTTP_200_OK,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# LESSON CONTENT ACCESS
# ═══════════════════════════════════════════════════════════════════════════════

class LessonDetailView(APIView):
    """
    GET /api/v1/courses/<course_slug>/lessons/<lesson_slug>/

    Access a specific lesson. Business rules:
        1. Preview lessons — accessible to anyone
        2. Non-preview lessons — require active enrollment
        3. Module unlock — if the module has an unlock_after_module,
           all lessons in the prerequisite module must be completed
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [UserRateThrottle]

    def get(self, request, course_slug, lesson_slug):
        lesson = get_object_or_404(
            Lesson.objects.select_related('module__course', 'module__unlock_after_module'),
            slug=lesson_slug,
            module__course__slug=course_slug,
            module__course__status=Course.Status.PUBLISHED,
        )
        course = lesson.module.course

        # Preview lessons are publicly accessible
        if lesson.is_preview:
            serializer = LessonDetailSerializer(
                lesson, context={'request': request},
            )
            return Response(serializer.data)

        # Non-preview: require authentication + enrollment
        if not request.user.is_authenticated:
            return Response(
                {'detail': 'Authentication required to access this lesson.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        enrollment = CourseEnrollment.objects.filter(
            user=request.user,
            course=course,
            status__in=[
                CourseEnrollment.Status.ACTIVE,
                CourseEnrollment.Status.COMPLETED,
            ],
        ).first()

        if not enrollment:
            return Response(
                {'detail': 'You must enroll in this course to access this lesson.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Module unlock gate
        prerequisite_module = lesson.module.unlock_after_module
        if prerequisite_module:
            prereq_lesson_ids = list(
                prerequisite_module.lessons.values_list('id', flat=True),
            )
            completed_count = LessonProgress.objects.filter(
                enrollment=enrollment,
                lesson_id__in=prereq_lesson_ids,
                is_completed=True,
            ).count()

            if completed_count < len(prereq_lesson_ids):
                return Response(
                    {
                        'detail': (
                            f'Complete all lessons in "{prerequisite_module.title}" '
                            f'to unlock this module.'
                        ),
                        'prerequisite_module': prerequisite_module.title,
                        'completed': completed_count,
                        'required': len(prereq_lesson_ids),
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        # Update last accessed
        CourseEnrollment.objects.filter(pk=enrollment.pk).update(
            last_lesson=lesson,
            last_accessed_at=timezone.now(),
        )

        serializer = LessonDetailSerializer(
            lesson,
            context={'request': request, 'enrollment': enrollment},
        )
        return Response(serializer.data)


# ═══════════════════════════════════════════════════════════════════════════════
# PROGRESS TRACKING
# ═══════════════════════════════════════════════════════════════════════════════

class LessonProgressView(APIView):
    """
    POST /api/v1/courses/<course_slug>/lessons/<lesson_slug>/progress/

    Track lesson progress. Supports incremental updates:
        - time_spent_seconds: accumulated session time (heartbeat)
        - video_position_seconds: resume position for video lessons
        - mark_completed: true to mark the lesson as done
        - score: quiz/code score (0.00 - 100.00)
        - notes: personal notes

    On completion, recalculates enrollment progress_percentage.
    """
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def post(self, request, course_slug, lesson_slug):
        lesson = get_object_or_404(
            Lesson.objects.select_related('module__course'),
            slug=lesson_slug,
            module__course__slug=course_slug,
            module__course__status=Course.Status.PUBLISHED,
        )

        enrollment = get_object_or_404(
            CourseEnrollment,
            user=request.user,
            course=lesson.module.course,
            status=CourseEnrollment.Status.ACTIVE,
        )

        serializer = LessonProgressUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Get or create progress record
        progress, created = LessonProgress.objects.get_or_create(
            enrollment=enrollment,
            lesson=lesson,
        )

        # Accumulate time spent
        if 'time_spent_seconds' in data:
            progress.time_spent_seconds = (
                db_models.F('time_spent_seconds') + data['time_spent_seconds']
            )

        # Update video position
        if 'video_position_seconds' in data:
            progress.video_position_seconds = data['video_position_seconds']

        # Update notes
        if 'notes' in data:
            progress.notes = data['notes']

        # Handle quiz/code score
        if 'score' in data:
            progress.attempts = db_models.F('attempts') + 1
            # Keep best score
            if progress.best_score is None or data['score'] > progress.best_score:
                progress.best_score = data['score']

        # Handle completion
        if data.get('mark_completed') and not progress.is_completed:
            progress.is_completed = True
            progress.completed_at = timezone.now()

        progress.save()
        progress.refresh_from_db()

        # Recalculate enrollment progress
        if data.get('mark_completed'):
            enrollment.recalculate_progress()

        # Accumulate time on enrollment
        if 'time_spent_seconds' in data:
            CourseEnrollment.objects.filter(pk=enrollment.pk).update(
                total_time_spent_seconds=db_models.F('total_time_spent_seconds')
                + data['time_spent_seconds'],
            )

        return Response(
            LessonProgressSerializer(progress).data,
            status=status.HTTP_200_OK,
        )


class CourseProgressOverview(APIView):
    """
    GET /api/v1/courses/<course_slug>/progress/
    Get a summary of the user's progress across all lessons in a course.
    """
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def get(self, request, course_slug):
        course = get_object_or_404(
            Course,
            slug=course_slug,
            status=Course.Status.PUBLISHED,
        )

        enrollment = get_object_or_404(
            CourseEnrollment.objects.select_related('course', 'last_lesson'),
            user=request.user,
            course=course,
        )

        # Per-module progress
        modules = (
            CourseModule.objects
            .filter(course=course)
            .prefetch_related('lessons')
            .order_by('position')
        )

        module_progress = []
        for module in modules:
            lesson_ids = list(module.lessons.values_list('id', flat=True))
            completed = LessonProgress.objects.filter(
                enrollment=enrollment,
                lesson_id__in=lesson_ids,
                is_completed=True,
            ).count()
            module_progress.append({
                'module_id': module.id,
                'module_title': module.title,
                'position': module.position,
                'total_lessons': len(lesson_ids),
                'completed_lessons': completed,
                'percentage': round(
                    (completed / len(lesson_ids) * 100) if lesson_ids else 0, 1,
                ),
            })

        return Response({
            'enrollment': CourseEnrollmentSerializer(enrollment).data,
            'modules': module_progress,
        })


# ═══════════════════════════════════════════════════════════════════════════════
# REVIEWS
# ═══════════════════════════════════════════════════════════════════════════════

class CourseReviewListView(generics.ListAPIView):
    """
    GET /api/v1/courses/<course_slug>/reviews/
    List approved reviews for a course.
    Supports ordering: ?ordering=newest|oldest|helpful
    """
    serializer_class = CourseReviewSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [UserRateThrottle]

    def get_queryset(self):
        course_slug = self.kwargs['course_slug']
        qs = (
            CourseReview.objects
            .filter(course__slug=course_slug, is_approved=True)
            .select_related('user')
        )
        ordering = self.request.query_params.get('ordering', 'newest').strip()
        ordering_map = {
            'newest': '-created_at',
            'oldest': 'created_at',
            'helpful': '-helpful_count',
        }
        return qs.order_by(ordering_map.get(ordering, '-created_at'))


class CourseReviewCreateView(generics.CreateAPIView):
    """
    POST /api/v1/courses/<course_slug>/reviews/
    Submit a review for a course. Requires enrollment.
    Body: { "rating": 4, "title": "...", "content": "..." }
    """
    serializer_class = CourseReviewWriteSerializer
    permission_classes = [permissions.IsAuthenticated, IsEmailVerified]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'review'

    def perform_create(self, serializer):
        # Auto-detect verified enrollment
        course = serializer.validated_data['course']
        is_verified = CourseEnrollment.objects.filter(
            user=self.request.user,
            course=course,
            status__in=['active', 'completed'],
        ).exists()
        serializer.save(
            user=self.request.user,
            is_verified_enrollment=is_verified,
        )
        logger.info(
            'User %s reviewed course %s (rating: %s)',
            self.request.user.id,
            course.id,
            serializer.validated_data['rating'],
        )


class CourseReviewVoteView(APIView):
    """
    POST /api/v1/courses/reviews/<id>/vote/
    Vote a review as helpful or not helpful.
    Body: { "helpful": true|false }
    """
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'review'

    def post(self, request, pk):
        review = get_object_or_404(CourseReview, pk=pk, is_approved=True)
        helpful = request.data.get('helpful')

        if helpful is None:
            return Response(
                {'detail': 'The "helpful" field is required (true/false).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if helpful:
            CourseReview.objects.filter(pk=pk).update(
                helpful_count=db_models.F('helpful_count') + 1,
            )
        else:
            CourseReview.objects.filter(pk=pk).update(
                not_helpful_count=db_models.F('not_helpful_count') + 1,
            )

        review.refresh_from_db()
        return Response(CourseReviewSerializer(review, context={'request': request}).data)


# ═══════════════════════════════════════════════════════════════════════════════
# CERTIFICATES
# ═══════════════════════════════════════════════════════════════════════════════

class MyCertificateListView(generics.ListAPIView):
    """
    GET /api/v1/courses/certificates/
    List all certificates earned by the authenticated user.
    """
    serializer_class = CertificateSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def get_queryset(self):
        return (
            Certificate.objects
            .filter(
                enrollment__user=self.request.user,
                is_revoked=False,
            )
            .select_related('enrollment__course')
            .order_by('-issued_at')
        )


class CertificateVerifyView(APIView):
    """
    GET /api/v1/courses/certificates/verify/<uuid>/
    Public certificate verification endpoint.
    Validates UUID + HMAC signature for tamper-proof verification.
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [UserRateThrottle]

    def get(self, request, certificate_id):
        try:
            certificate = Certificate.objects.get(pk=certificate_id)
        except Certificate.DoesNotExist:
            return Response(
                {'valid': False, 'detail': 'Certificate not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if certificate.is_revoked:
            return Response(
                {'valid': False, 'detail': 'This certificate has been revoked.'},
                status=status.HTTP_200_OK,
            )

        is_valid = certificate.verify_signature()
        data = CertificateSerializer(certificate, context={'request': request}).data
        data['valid'] = is_valid
        if not is_valid:
            data['detail'] = 'Certificate signature verification failed.'

        return Response(data, status=status.HTTP_200_OK)
