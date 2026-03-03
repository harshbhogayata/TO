"""
courses/models.py
Phase 7 — Full Learning Management System (LMS)

Replaces the simple Course catalog with an enterprise-grade content engine:

    1. CourseCategory     — Hierarchical taxonomy for course organisation
    2. Course             — Enhanced course with modules, prerequisites, pricing
    3. CourseModule        — Ordered sections within a course
    4. Lesson             — Individual content units (video, text, quiz, code)
    5. LessonAttachment   — Supplementary files for lessons
    6. CourseEnrollment    — Tracks user enrollment status and progress
    7. LessonProgress     — Per-lesson completion tracking with time spent
    8. CourseReview        — User reviews of courses with moderation
    9. Certificate         — Completion certificates with tamper-proof verification
    10. CourseInstructor   — Instructor profiles with bio and credentials

Design decisions:
    - CourseCategory is self-referential for unlimited nesting depth
    - Lessons support multiple content types (video, text, markdown, code, quiz)
    - Progress is tracked per-lesson with time-spent analytics
    - Certificates use UUID + HMAC for tamper-proof verification URLs
    - Course ordering uses explicit position fields (not created_at)
    - Video content stores both source URL (R2) and duration metadata
    - All models follow existing TalentOrbit patterns:
        * Composite indexes for common query patterns
        * Consistent naming conventions
        * BigAutoField (inherited from settings)
"""
import hashlib
import hmac
import uuid

from django.conf import settings
from django.core.validators import (
    FileExtensionValidator,
    MaxValueValidator,
    MinValueValidator,
)
from django.db import models
from django.utils import timezone


# ═══════════════════════════════════════════════════════════════════════════════
# 1. COURSE CATEGORY — Hierarchical Taxonomy
# ═══════════════════════════════════════════════════════════════════════════════

class CourseCategory(models.Model):
    """
    Hierarchical category tree for organising courses.
    Supports unlimited nesting (e.g. Technology → Programming → Python → Django).
    """
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True, db_index=True)
    description = models.TextField(blank=True)
    icon = models.CharField(
        max_length=100, blank=True,
        help_text='Icon identifier (e.g. Lucide icon name or emoji)',
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
    )
    position = models.PositiveIntegerField(
        default=0,
        help_text='Display order within parent category.',
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Course Category'
        verbose_name_plural = 'Course Categories'
        ordering = ['position', 'name']
        unique_together = ('parent', 'slug')
        indexes = [
            models.Index(fields=['parent', 'position'], name='idx_coursecat_parent_pos'),
        ]

    def __str__(self):
        if self.parent:
            return f'{self.parent.name} → {self.name}'
        return self.name

    @property
    def full_path(self) -> str:
        """Return the full category path (e.g. 'Technology → Programming → Python')."""
        parts = [self.name]
        current = self.parent
        depth = 0
        while current and depth < 10:
            parts.append(current.name)
            current = current.parent
            depth += 1
        return ' → '.join(reversed(parts))

    @property
    def course_count(self) -> int:
        """Number of published courses in this category (cached at query time via annotation)."""
        return getattr(self, '_course_count', self.courses.filter(status='published').count())


# ═══════════════════════════════════════════════════════════════════════════════
# 2. COURSE INSTRUCTOR — Who Teaches
# ═══════════════════════════════════════════════════════════════════════════════

class CourseInstructor(models.Model):
    """
    Instructor profile. Can be linked to a platform User or be an external
    instructor (e.g. for curated third-party content).
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='instructor_profile',
        help_text='Platform user. NULL for external instructors.',
    )
    display_name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    bio = models.TextField(blank=True, max_length=2000)
    avatar = models.ImageField(
        upload_to='instructors/avatars/',
        null=True,
        blank=True,
    )
    credentials = models.JSONField(
        default=list,
        blank=True,
        help_text='List of credentials: [{"title": "...", "issuer": "...", "year": 2024}]',
    )
    website_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    is_verified = models.BooleanField(
        default=False,
        help_text='Verified by TalentOrbit team.',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Course Instructor'
        verbose_name_plural = 'Course Instructors'
        ordering = ['display_name']

    def __str__(self):
        verified = '✓' if self.is_verified else '○'
        return f'{verified} {self.display_name}'

    @property
    def total_students(self) -> int:
        """Total unique students across all instructor's courses."""
        return getattr(
            self, '_total_students',
            CourseEnrollment.objects.filter(
                course__instructors=self,
                status__in=['active', 'completed'],
            ).values('user').distinct().count()
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 3. COURSE — The Core Entity
# ═══════════════════════════════════════════════════════════════════════════════

class Course(models.Model):
    """
    A course is a structured learning experience composed of ordered modules.

    Lifecycle: draft → under_review → published → archived
    Access: free (anyone enrolled) or premium (requires subscription tier)
    """

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        UNDER_REVIEW = 'under_review', 'Under Review'
        PUBLISHED = 'published', 'Published'
        ARCHIVED = 'archived', 'Archived'

    class Level(models.TextChoices):
        BEGINNER = 'beginner', 'Beginner'
        INTERMEDIATE = 'intermediate', 'Intermediate'
        ADVANCED = 'advanced', 'Advanced'
        EXPERT = 'expert', 'Expert'

    class AccessLevel(models.TextChoices):
        FREE = 'free', 'Free'
        PREMIUM = 'premium', 'Premium (requires subscription)'

    # ── Identity ──────────────────────────────────────────────────────────
    title = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(max_length=280, unique=True)
    subtitle = models.CharField(max_length=500, blank=True)
    description = models.TextField(
        help_text='Full course description (Markdown supported).',
    )
    short_description = models.CharField(
        max_length=300, blank=True,
        help_text='One-liner for cards and search results.',
    )

    # ── Media ─────────────────────────────────────────────────────────────
    thumbnail = models.ImageField(
        upload_to='courses/thumbnails/',
        null=True,
        blank=True,
    )
    preview_video_url = models.URLField(
        blank=True,
        help_text='URL to a preview/trailer video (R2 or external).',
    )

    # ── Classification ────────────────────────────────────────────────────
    category = models.ForeignKey(
        CourseCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='courses',
    )
    skills = models.JSONField(
        default=list,
        help_text='Skills taught in this course: ["Python", "Django", "REST APIs"]',
    )
    tags = models.JSONField(
        default=list,
        help_text='Searchable tags: ["web-development", "backend"]',
    )
    level = models.CharField(
        max_length=20,
        choices=Level.choices,
        default=Level.BEGINNER,
        db_index=True,
    )

    # ── Access & Pricing ──────────────────────────────────────────────────
    access_level = models.CharField(
        max_length=20,
        choices=AccessLevel.choices,
        default=AccessLevel.FREE,
        db_index=True,
    )
    required_subscription_tier = models.CharField(
        max_length=30,
        blank=True,
        help_text='Minimum subscription tier required (e.g. "premium", "professional"). '
                  'Empty = no tier restriction beyond access_level.',
    )

    # ── Instructors ───────────────────────────────────────────────────────
    instructors = models.ManyToManyField(
        CourseInstructor,
        related_name='courses',
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_courses',
        help_text='Admin/instructor who created this course.',
    )

    # ── Prerequisites ─────────────────────────────────────────────────────
    prerequisites = models.ManyToManyField(
        'self',
        symmetrical=False,
        blank=True,
        related_name='dependent_courses',
        help_text='Courses that should be completed before this one.',
    )

    # ── Metadata ──────────────────────────────────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    estimated_duration_minutes = models.PositiveIntegerField(
        default=0,
        help_text='Total estimated duration in minutes (auto-computed from lessons).',
    )
    language = models.CharField(max_length=10, default='en')
    version = models.CharField(
        max_length=20, default='1.0',
        help_text='Content version (for tracking updates to published courses).',
    )
    max_enrollments = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Maximum number of enrollments. NULL = unlimited.',
    )

    # ── Analytics (denormalised for fast reads) ───────────────────────────
    enrollment_count = models.PositiveIntegerField(default=0)
    completion_count = models.PositiveIntegerField(default=0)
    average_rating = models.DecimalField(
        max_digits=3, decimal_places=2, default=0.00,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
    )
    review_count = models.PositiveIntegerField(default=0)

    # ── External course support (backward compatibility) ──────────────────
    external_url = models.URLField(
        blank=True,
        help_text='URL for externally-hosted courses (opens in new tab). '
                  'If set, the course acts as a link rather than hosted content.',
    )
    is_external = models.BooleanField(
        default=False,
        help_text='True if this course is hosted externally.',
    )

    # ── Timestamps ────────────────────────────────────────────────────────
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-published_at', '-created_at']
        verbose_name = 'Course'
        verbose_name_plural = 'Courses'
        indexes = [
            models.Index(
                fields=['status', '-published_at'],
                name='idx_course_status_pub',
            ),
            models.Index(
                fields=['category', 'status'],
                name='idx_course_cat_status',
            ),
            models.Index(
                fields=['level', 'status'],
                name='idx_course_level_status',
            ),
            models.Index(
                fields=['access_level', 'status'],
                name='idx_course_access_status',
            ),
            models.Index(
                fields=['-average_rating', 'status'],
                name='idx_course_rating_status',
            ),
            models.Index(
                fields=['-enrollment_count'],
                name='idx_course_enrollment_ct',
            ),
        ]

    def __str__(self):
        status_icon = {'draft': '📝', 'under_review': '🔍', 'published': '✅', 'archived': '📦'}
        return f'{status_icon.get(self.status, "?")} {self.title}'

    def save(self, *args, **kwargs):
        if self.status == self.Status.PUBLISHED and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    @property
    def module_count(self) -> int:
        return getattr(self, '_module_count', self.modules.count())

    @property
    def lesson_count(self) -> int:
        return getattr(self, '_lesson_count', Lesson.objects.filter(module__course=self).count())

    @property
    def is_enrollable(self) -> bool:
        """Check if new enrollments are accepted."""
        if self.status != self.Status.PUBLISHED:
            return False
        if self.max_enrollments and self.enrollment_count >= self.max_enrollments:
            return False
        return True

    def compute_duration(self) -> int:
        """Recompute total duration from all lessons and update the field."""
        total = Lesson.objects.filter(
            module__course=self
        ).aggregate(
            total=models.Sum('estimated_duration_minutes')
        )['total'] or 0
        if total != self.estimated_duration_minutes:
            self.estimated_duration_minutes = total
            Course.objects.filter(pk=self.pk).update(estimated_duration_minutes=total)
        return total


# ═══════════════════════════════════════════════════════════════════════════════
# 4. COURSE MODULE — Sections Within a Course
# ═══════════════════════════════════════════════════════════════════════════════

class CourseModule(models.Model):
    """
    An ordered section within a course. Groups related lessons together.
    E.g. "Module 1: Getting Started", "Module 2: Advanced Patterns".
    """
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='modules',
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    position = models.PositiveIntegerField(
        default=0,
        help_text='Display order within the course (0-indexed).',
    )
    is_preview = models.BooleanField(
        default=False,
        help_text='If True, this module is accessible without enrollment (free preview).',
    )
    unlock_after_module = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='unlocks',
        help_text='Module that must be completed before this one is accessible.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['position']
        verbose_name = 'Course Module'
        verbose_name_plural = 'Course Modules'
        unique_together = ('course', 'position')
        indexes = [
            models.Index(fields=['course', 'position'], name='idx_module_course_pos'),
        ]

    def __str__(self):
        return f'{self.course.title} — Module {self.position}: {self.title}'

    @property
    def lesson_count(self) -> int:
        return getattr(self, '_lesson_count', self.lessons.count())

    @property
    def total_duration_minutes(self) -> int:
        return getattr(
            self, '_total_duration',
            self.lessons.aggregate(t=models.Sum('estimated_duration_minutes'))['t'] or 0
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 5. LESSON — Individual Content Units
# ═══════════════════════════════════════════════════════════════════════════════

class Lesson(models.Model):
    """
    A single content unit within a module.
    Supports multiple content types — the type field determines which
    content field(s) are populated and how the frontend renders it.
    """

    class ContentType(models.TextChoices):
        VIDEO = 'video', 'Video'
        TEXT = 'text', 'Text / Article'
        MARKDOWN = 'markdown', 'Markdown'
        CODE = 'code', 'Interactive Code'
        QUIZ = 'quiz', 'Quiz / Assessment'
        ASSIGNMENT = 'assignment', 'Assignment'
        EXTERNAL = 'external', 'External Link'

    module = models.ForeignKey(
        CourseModule,
        on_delete=models.CASCADE,
        related_name='lessons',
    )
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280)
    content_type = models.CharField(
        max_length=20,
        choices=ContentType.choices,
        default=ContentType.TEXT,
        db_index=True,
    )
    position = models.PositiveIntegerField(
        default=0,
        help_text='Display order within the module.',
    )

    # ── Content Fields (populated based on content_type) ──────────────────
    text_content = models.TextField(
        blank=True,
        help_text='Rich text or Markdown content for text/markdown lessons.',
    )
    video_url = models.URLField(
        blank=True,
        help_text='URL to the video file (R2, Cloudflare Stream, or external).',
    )
    video_duration_seconds = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Video duration in seconds (for progress tracking).',
    )
    video_thumbnail_url = models.URLField(blank=True)
    video_transcript = models.TextField(
        blank=True,
        help_text='Full video transcript (for search indexing and accessibility).',
    )
    code_language = models.CharField(
        max_length=50, blank=True,
        help_text='Programming language for code lessons (e.g. "python", "javascript").',
    )
    code_starter = models.TextField(
        blank=True,
        help_text='Starter code template provided to the student.',
    )
    code_solution = models.TextField(
        blank=True,
        help_text='Reference solution (shown after completion).',
    )
    code_test_cases = models.JSONField(
        default=list,
        blank=True,
        help_text='[{"input": "...", "expected_output": "...", "description": "..."}]',
    )
    quiz_config = models.JSONField(
        default=dict,
        blank=True,
        help_text='{"assessment_id": ..., "passing_score": 70, "max_attempts": 3}',
    )
    external_url = models.URLField(blank=True)

    # ── Metadata ──────────────────────────────────────────────────────────
    estimated_duration_minutes = models.PositiveIntegerField(
        default=5,
        help_text='Estimated time to complete this lesson.',
    )
    is_preview = models.BooleanField(
        default=False,
        help_text='Accessible without enrollment (free preview lesson).',
    )
    is_mandatory = models.BooleanField(
        default=True,
        help_text='Must be completed for course completion certificate.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['position']
        verbose_name = 'Lesson'
        verbose_name_plural = 'Lessons'
        unique_together = ('module', 'position')
        indexes = [
            models.Index(fields=['module', 'position'], name='idx_lesson_module_pos'),
            models.Index(fields=['content_type'], name='idx_lesson_type'),
        ]

    def __str__(self):
        icon = {
            'video': '🎬', 'text': '📄', 'markdown': '📝',
            'code': '💻', 'quiz': '❓', 'assignment': '📋', 'external': '🔗',
        }
        return f'{icon.get(self.content_type, "?")} {self.module.course.title} — {self.title}'


# ═══════════════════════════════════════════════════════════════════════════════
# 6. LESSON ATTACHMENT — Supplementary Files
# ═══════════════════════════════════════════════════════════════════════════════

class LessonAttachment(models.Model):
    """Downloadable files attached to a lesson (PDFs, datasets, starter projects)."""

    ALLOWED_EXTENSIONS = [
        'pdf', 'doc', 'docx', 'txt', 'csv', 'xlsx', 'xls',
        'zip', 'tar', 'gz',
        'png', 'jpg', 'jpeg', 'gif', 'svg', 'webp',
        'py', 'js', 'ts', 'jsx', 'tsx', 'html', 'css', 'json', 'yaml', 'yml',
    ]

    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='attachments',
    )
    title = models.CharField(max_length=255)
    file = models.FileField(
        upload_to='courses/attachments/%Y/%m/',
        validators=[FileExtensionValidator(allowed_extensions=ALLOWED_EXTENSIONS)],
    )
    file_size_bytes = models.PositiveIntegerField(
        default=0,
        help_text='Auto-populated on save.',
    )
    download_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['title']
        verbose_name = 'Lesson Attachment'
        verbose_name_plural = 'Lesson Attachments'

    def __str__(self):
        return f'{self.title} ({self.lesson.title})'

    def save(self, *args, **kwargs):
        if self.file and hasattr(self.file, 'size'):
            self.file_size_bytes = self.file.size
        super().save(*args, **kwargs)


# ═══════════════════════════════════════════════════════════════════════════════
# 7. COURSE ENROLLMENT — User ↔ Course Relationship
# ═══════════════════════════════════════════════════════════════════════════════

class CourseEnrollment(models.Model):
    """
    Tracks a user's enrollment in a course.
    One enrollment per user per course (enforced by unique_together).
    """

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        COMPLETED = 'completed', 'Completed'
        DROPPED = 'dropped', 'Dropped'
        EXPIRED = 'expired', 'Expired'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='course_enrollments',
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='enrollments',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    progress_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='Overall course completion percentage (0.00–100.00).',
    )
    lessons_completed = models.PositiveIntegerField(default=0)
    total_time_spent_seconds = models.PositiveIntegerField(
        default=0,
        help_text='Cumulative time spent on all lessons.',
    )
    last_lesson = models.ForeignKey(
        Lesson,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        help_text='Last lesson the user accessed (for "Continue" button).',
    )
    last_accessed_at = models.DateTimeField(null=True, blank=True)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-enrolled_at']
        verbose_name = 'Course Enrollment'
        verbose_name_plural = 'Course Enrollments'
        unique_together = ('user', 'course')
        indexes = [
            models.Index(
                fields=['user', 'status'],
                name='idx_enrollment_user_status',
            ),
            models.Index(
                fields=['course', 'status'],
                name='idx_enrollment_course_status',
            ),
            models.Index(
                fields=['user', '-last_accessed_at'],
                name='idx_enrollment_user_access',
            ),
        ]

    def __str__(self):
        return f'{self.user.email} → {self.course.title} ({self.status})'

    def recalculate_progress(self) -> None:
        """
        Recompute progress_percentage from actual LessonProgress records.
        Called after each lesson completion.
        """
        total_mandatory = Lesson.objects.filter(
            module__course=self.course,
            is_mandatory=True,
        ).count()

        if total_mandatory == 0:
            self.progress_percentage = 100.00
        else:
            completed = LessonProgress.objects.filter(
                enrollment=self,
                lesson__is_mandatory=True,
                is_completed=True,
            ).count()
            self.progress_percentage = round((completed / total_mandatory) * 100, 2)

        self.lessons_completed = LessonProgress.objects.filter(
            enrollment=self,
            is_completed=True,
        ).count()

        if self.progress_percentage >= 100.00 and self.status == self.Status.ACTIVE:
            self.status = self.Status.COMPLETED
            self.completed_at = timezone.now()

        self.save(update_fields=[
            'progress_percentage', 'lessons_completed',
            'status', 'completed_at', 'updated_at',
        ])


# ═══════════════════════════════════════════════════════════════════════════════
# 8. LESSON PROGRESS — Per-Lesson Tracking
# ═══════════════════════════════════════════════════════════════════════════════

class LessonProgress(models.Model):
    """
    Tracks individual lesson completion within an enrollment.
    Stores time spent for analytics and video playback resume position.
    """
    enrollment = models.ForeignKey(
        CourseEnrollment,
        on_delete=models.CASCADE,
        related_name='lesson_progress',
    )
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='progress_records',
    )
    is_completed = models.BooleanField(default=False, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    time_spent_seconds = models.PositiveIntegerField(default=0)
    video_position_seconds = models.PositiveIntegerField(
        default=0,
        help_text='Last playback position (for resume functionality).',
    )
    attempts = models.PositiveIntegerField(
        default=0,
        help_text='Number of attempts (for quizzes and code challenges).',
    )
    best_score = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        help_text='Best score achieved (0–100 for quizzes).',
    )
    last_submission = models.JSONField(
        default=dict, blank=True,
        help_text='Last submitted answer/code for reference.',
    )
    notes = models.TextField(
        blank=True,
        help_text='User\'s personal notes for this lesson.',
    )
    started_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['lesson__position']
        verbose_name = 'Lesson Progress'
        verbose_name_plural = 'Lesson Progress'
        unique_together = ('enrollment', 'lesson')
        indexes = [
            models.Index(
                fields=['enrollment', 'is_completed'],
                name='idx_progress_enroll_done',
            ),
        ]

    def __str__(self):
        status = '✓' if self.is_completed else '○'
        return f'{status} {self.enrollment.user.email} — {self.lesson.title}'

    def mark_completed(self) -> None:
        """Mark this lesson as completed and trigger enrollment progress recalculation."""
        if not self.is_completed:
            self.is_completed = True
            self.completed_at = timezone.now()
            self.save(update_fields=['is_completed', 'completed_at', 'updated_at'])
            self.enrollment.recalculate_progress()


# ═══════════════════════════════════════════════════════════════════════════════
# 9. COURSE REVIEW — User Feedback
# ═══════════════════════════════════════════════════════════════════════════════

class CourseReview(models.Model):
    """
    User review of a course. Only one review per user per course.
    Must be enrolled to leave a review. Reviews are auto-approved by default.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='course_reviews',
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='reviews',
    )
    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text='1–5 star rating.',
    )
    title = models.CharField(max_length=200, blank=True)
    content = models.TextField(
        max_length=5000,
        help_text='Written review.',
    )
    is_verified_enrollment = models.BooleanField(
        default=False,
        help_text='Auto-set to True if user has an active/completed enrollment.',
    )
    is_approved = models.BooleanField(default=True)
    is_flagged = models.BooleanField(default=False)
    moderation_notes = models.TextField(blank=True)
    helpful_count = models.PositiveIntegerField(default=0)
    not_helpful_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Course Review'
        verbose_name_plural = 'Course Reviews'
        unique_together = ('user', 'course')
        indexes = [
            models.Index(
                fields=['course', '-created_at'],
                name='idx_creview_course_date',
            ),
            models.Index(
                fields=['course', '-helpful_count'],
                name='idx_creview_course_helpful',
            ),
        ]

    def __str__(self):
        return f'{"⭐" * self.rating} {self.user.email} → {self.course.title}'

    def save(self, *args, **kwargs):
        if not self.pk:
            self.is_verified_enrollment = CourseEnrollment.objects.filter(
                user=self.user,
                course=self.course,
                status__in=['active', 'completed'],
            ).exists()
        super().save(*args, **kwargs)


# ═══════════════════════════════════════════════════════════════════════════════
# 10. CERTIFICATE — Completion Credentials
# ═══════════════════════════════════════════════════════════════════════════════

class Certificate(models.Model):
    """
    Tamper-proof course completion certificate.
    Verifiable via a unique UUID + HMAC signature.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    enrollment = models.OneToOneField(
        CourseEnrollment,
        on_delete=models.CASCADE,
        related_name='certificate',
    )
    holder_name = models.CharField(max_length=255)
    holder_email = models.EmailField()
    course_title = models.CharField(max_length=255)
    course_version = models.CharField(max_length=20)
    instructor_names = models.JSONField(
        default=list,
        help_text='Instructor names at time of issuance.',
    )
    completion_date = models.DateField()
    total_hours = models.DecimalField(
        max_digits=6, decimal_places=1,
        help_text='Total hours spent on the course.',
    )
    skills_earned = models.JSONField(
        default=list,
        help_text='Skills validated by completing this course.',
    )
    signature = models.CharField(
        max_length=64,
        editable=False,
        help_text='HMAC-SHA256 signature for verification.',
    )
    issued_at = models.DateTimeField(auto_now_add=True)
    is_revoked = models.BooleanField(default=False)
    revoked_reason = models.TextField(blank=True)

    class Meta:
        ordering = ['-issued_at']
        verbose_name = 'Certificate'
        verbose_name_plural = 'Certificates'

    def __str__(self):
        status = '🚫' if self.is_revoked else '🎓'
        return f'{status} {self.holder_name} — {self.course_title}'

    def save(self, *args, **kwargs):
        if not self.signature:
            self.signature = self._generate_signature()
        super().save(*args, **kwargs)

    def _generate_signature(self) -> str:
        """Generate HMAC-SHA256 signature over the certificate's canonical data."""
        payload = '|'.join([
            str(self.id),
            self.holder_email,
            self.course_title,
            self.course_version,
            str(self.completion_date),
            str(self.total_hours),
        ])
        return hmac.new(
            settings.SECRET_KEY.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()

    def verify_signature(self) -> bool:
        """Verify that the certificate has not been tampered with."""
        return hmac.compare_digest(self.signature, self._generate_signature())
