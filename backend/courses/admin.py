"""
courses/admin.py
Phase 7 — LMS Admin Configuration

Enterprise admin interface for the full course content engine.
Features:
    - Inline editing for modules and lessons within courses
    - Bulk actions for course publishing workflows
    - Filtered views by status, level, category
    - Search across course titles and instructor names
    - Certificate verification from admin panel
"""
from django.contrib import admin
from django.utils.html import format_html

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


# ═══════════════════════════════════════════════════════════════════════════════
# INLINES
# ═══════════════════════════════════════════════════════════════════════════════

class CourseModuleInline(admin.TabularInline):
    model = CourseModule
    extra = 0
    fields = ('title', 'position', 'is_preview', 'unlock_after_module')
    ordering = ('position',)
    show_change_link = True


class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 0
    fields = ('title', 'content_type', 'position', 'estimated_duration_minutes', 'is_preview', 'is_mandatory')
    ordering = ('position',)
    show_change_link = True


class LessonAttachmentInline(admin.TabularInline):
    model = LessonAttachment
    extra = 0
    fields = ('title', 'file', 'file_size_bytes', 'download_count')
    readonly_fields = ('file_size_bytes', 'download_count')


# ═══════════════════════════════════════════════════════════════════════════════
# CATEGORY
# ═══════════════════════════════════════════════════════════════════════════════

@admin.register(CourseCategory)
class CourseCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'parent', 'position', 'is_active', 'created_at')
    list_filter = ('is_active', 'parent')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('parent', 'position', 'name')


# ═══════════════════════════════════════════════════════════════════════════════
# INSTRUCTOR
# ═══════════════════════════════════════════════════════════════════════════════

@admin.register(CourseInstructor)
class CourseInstructorAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'slug', 'user', 'is_verified', 'created_at')
    list_filter = ('is_verified',)
    search_fields = ('display_name', 'user__email', 'user__full_name')
    prepopulated_fields = {'slug': ('display_name',)}
    readonly_fields = ('created_at', 'updated_at')


# ═══════════════════════════════════════════════════════════════════════════════
# COURSE
# ═══════════════════════════════════════════════════════════════════════════════

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'status', 'level', 'access_level', 'category',
        'enrollment_count', 'average_rating', 'published_at',
    )
    list_filter = ('status', 'level', 'access_level', 'category', 'language')
    search_fields = ('title', 'subtitle', 'description', 'skills')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = (
        'enrollment_count', 'completion_count', 'average_rating',
        'review_count', 'published_at', 'created_at', 'updated_at',
    )
    inlines = [CourseModuleInline]
    filter_horizontal = ('instructors', 'prerequisites')
    fieldsets = (
        (None, {
            'fields': ('title', 'slug', 'subtitle', 'short_description', 'description'),
        }),
        ('Media', {
            'fields': ('thumbnail', 'preview_video_url'),
        }),
        ('Classification', {
            'fields': ('category', 'skills', 'tags', 'level', 'language', 'version'),
        }),
        ('Access & Status', {
            'fields': (
                'status', 'access_level', 'required_subscription_tier',
                'max_enrollments', 'is_external', 'external_url',
            ),
        }),
        ('Instructors & Prerequisites', {
            'fields': ('instructors', 'prerequisites'),
        }),
        ('Denormalised Metrics (read-only)', {
            'classes': ('collapse',),
            'fields': (
                'enrollment_count', 'completion_count',
                'average_rating', 'review_count',
            ),
        }),
        ('Timestamps', {
            'classes': ('collapse',),
            'fields': ('published_at', 'created_at', 'updated_at'),
        }),
    )
    actions = ['publish_courses', 'archive_courses']

    @admin.action(description='Publish selected courses')
    def publish_courses(self, request, queryset):
        from django.utils import timezone
        updated = queryset.filter(status=Course.Status.DRAFT).update(
            status=Course.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        self.message_user(request, f'{updated} course(s) published.')

    @admin.action(description='Archive selected courses')
    def archive_courses(self, request, queryset):
        updated = queryset.exclude(status=Course.Status.ARCHIVED).update(
            status=Course.Status.ARCHIVED,
        )
        self.message_user(request, f'{updated} course(s) archived.')


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE
# ═══════════════════════════════════════════════════════════════════════════════

@admin.register(CourseModule)
class CourseModuleAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'position', 'is_preview')
    list_filter = ('course', 'is_preview')
    search_fields = ('title', 'course__title')
    inlines = [LessonInline]
    ordering = ('course', 'position')


# ═══════════════════════════════════════════════════════════════════════════════
# LESSON
# ═══════════════════════════════════════════════════════════════════════════════

@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('title', 'module', 'content_type', 'position', 'is_preview', 'is_mandatory')
    list_filter = ('content_type', 'is_preview', 'is_mandatory', 'module__course')
    search_fields = ('title', 'module__title', 'module__course__title')
    inlines = [LessonAttachmentInline]
    ordering = ('module__course', 'module__position', 'position')


# ═══════════════════════════════════════════════════════════════════════════════
# ENROLLMENT
# ═══════════════════════════════════════════════════════════════════════════════

@admin.register(CourseEnrollment)
class CourseEnrollmentAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'course', 'status', 'progress_percentage',
        'lessons_completed', 'enrolled_at', 'completed_at',
    )
    list_filter = ('status', 'course')
    search_fields = ('user__email', 'user__full_name', 'course__title')
    readonly_fields = (
        'progress_percentage', 'lessons_completed',
        'total_time_spent_seconds', 'enrolled_at', 'completed_at',
    )
    raw_id_fields = ('user', 'course', 'last_lesson')


# ═══════════════════════════════════════════════════════════════════════════════
# PROGRESS
# ═══════════════════════════════════════════════════════════════════════════════

@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = (
        'enrollment', 'lesson', 'is_completed', 'time_spent_seconds',
        'best_score', 'attempts', 'completed_at',
    )
    list_filter = ('is_completed', 'lesson__content_type')
    search_fields = (
        'enrollment__user__email',
        'lesson__title',
        'enrollment__course__title',
    )
    readonly_fields = ('started_at', 'completed_at')
    raw_id_fields = ('enrollment', 'lesson')


# ═══════════════════════════════════════════════════════════════════════════════
# REVIEW
# ═══════════════════════════════════════════════════════════════════════════════

@admin.register(CourseReview)
class CourseReviewAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'course', 'rating', 'is_verified_enrollment',
        'is_approved', 'helpful_count', 'created_at',
    )
    list_filter = ('rating', 'is_verified_enrollment', 'is_approved')
    search_fields = ('user__email', 'course__title', 'title', 'content')
    readonly_fields = ('helpful_count', 'not_helpful_count', 'created_at', 'updated_at')
    actions = ['approve_reviews', 'reject_reviews']

    @admin.action(description='Approve selected reviews')
    def approve_reviews(self, request, queryset):
        updated = queryset.update(is_approved=True)
        self.message_user(request, f'{updated} review(s) approved.')

    @admin.action(description='Reject selected reviews')
    def reject_reviews(self, request, queryset):
        updated = queryset.update(is_approved=False)
        self.message_user(request, f'{updated} review(s) rejected.')


# ═══════════════════════════════════════════════════════════════════════════════
# CERTIFICATE
# ═══════════════════════════════════════════════════════════════════════════════

@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'holder_name', 'course_title', 'completion_date',
        'is_revoked', 'signature_valid', 'issued_at',
    )
    list_filter = ('is_revoked', 'completion_date')
    search_fields = ('holder_name', 'holder_email', 'course_title')
    readonly_fields = (
        'id', 'holder_name', 'holder_email', 'course_title',
        'course_version', 'instructor_names', 'completion_date',
        'total_hours', 'skills_earned', 'signature',
        'issued_at', 'signature_valid',
    )

    @admin.display(boolean=True, description='Signature Valid')
    def signature_valid(self, obj):
        return obj.verify_signature()

    actions = ['revoke_certificates']

    @admin.action(description='Revoke selected certificates')
    def revoke_certificates(self, request, queryset):
        updated = queryset.filter(is_revoked=False).update(is_revoked=True)
        self.message_user(request, f'{updated} certificate(s) revoked.')
