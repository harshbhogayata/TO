"""
courses/serializers.py
Phase 7 — LMS Serializers

Provides nested, permission-aware serializers for the full course content engine.
Follows existing TalentOrbit patterns:
    - Read serializers (nested, rich) vs Write serializers (flat, validated)
    - Computed fields via SerializerMethodField
    - Consistent error messages
"""
from django.db import IntegrityError
from django.utils import timezone
from rest_framework import serializers

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
# CATEGORY
# ═══════════════════════════════════════════════════════════════════════════════

class CourseCategorySerializer(serializers.ModelSerializer):
    """Read serializer for categories. Includes child count and full path."""
    course_count = serializers.IntegerField(read_only=True, default=0)
    children = serializers.SerializerMethodField()
    full_path = serializers.CharField(read_only=True)

    class Meta:
        model = CourseCategory
        fields = [
            'id', 'name', 'slug', 'description', 'icon',
            'parent', 'position', 'is_active', 'full_path',
            'course_count', 'children',
        ]
        read_only_fields = ['id']

    def get_children(self, obj):
        children = obj.children.filter(is_active=True).order_by('position')
        return CourseCategorySerializer(children, many=True).data


class CourseCategoryWriteSerializer(serializers.ModelSerializer):
    """Write serializer for admin category management."""

    class Meta:
        model = CourseCategory
        fields = ['name', 'slug', 'description', 'icon', 'parent', 'position', 'is_active']


# ═══════════════════════════════════════════════════════════════════════════════
# INSTRUCTOR
# ═══════════════════════════════════════════════════════════════════════════════

class CourseInstructorSerializer(serializers.ModelSerializer):
    """Read serializer for instructor profiles."""
    total_students = serializers.IntegerField(read_only=True, default=0)
    total_courses = serializers.SerializerMethodField()

    class Meta:
        model = CourseInstructor
        fields = [
            'id', 'user', 'display_name', 'slug', 'bio', 'avatar',
            'credentials', 'website_url', 'linkedin_url',
            'is_verified', 'total_students', 'total_courses',
        ]
        read_only_fields = ['id', 'is_verified']

    def get_total_courses(self, obj):
        return obj.courses.filter(status='published').count()


# ═══════════════════════════════════════════════════════════════════════════════
# LESSON & ATTACHMENTS
# ═══════════════════════════════════════════════════════════════════════════════

class LessonAttachmentSerializer(serializers.ModelSerializer):
    """Read serializer for lesson attachments."""
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = LessonAttachment
        fields = ['id', 'title', 'file_url', 'file_size_bytes', 'download_count', 'created_at']
        read_only_fields = ['id', 'file_size_bytes', 'download_count', 'created_at']

    def get_file_url(self, obj):
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None


class LessonListSerializer(serializers.ModelSerializer):
    """
    Compact lesson serializer for course outlines.
    Does NOT include full content (text_content, code_solution, etc.) —
    that's only revealed in the detail serializer for enrolled users.
    """

    class Meta:
        model = Lesson
        fields = [
            'id', 'title', 'slug', 'content_type', 'position',
            'estimated_duration_minutes', 'is_preview', 'is_mandatory',
            'video_duration_seconds',
        ]
        read_only_fields = ['id']


class LessonDetailSerializer(serializers.ModelSerializer):
    """
    Full lesson serializer with content — only served to enrolled users.
    Code solutions are withheld until the lesson is completed.
    """
    attachments = LessonAttachmentSerializer(many=True, read_only=True)
    is_completed = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = [
            'id', 'title', 'slug', 'content_type', 'position',
            'estimated_duration_minutes', 'is_preview', 'is_mandatory',
            # Content fields
            'text_content', 'video_url', 'video_duration_seconds',
            'video_thumbnail_url', 'video_transcript',
            'code_language', 'code_starter', 'code_solution',
            'code_test_cases', 'quiz_config', 'external_url',
            # Relations
            'attachments',
            # Computed
            'is_completed', 'progress',
        ]
        read_only_fields = ['id']

    def get_is_completed(self, obj):
        enrollment = self.context.get('enrollment')
        if not enrollment:
            return False
        return LessonProgress.objects.filter(
            enrollment=enrollment,
            lesson=obj,
            is_completed=True,
        ).exists()

    def get_progress(self, obj):
        enrollment = self.context.get('enrollment')
        if not enrollment:
            return None
        try:
            progress = LessonProgress.objects.get(enrollment=enrollment, lesson=obj)
            return LessonProgressSerializer(progress).data
        except LessonProgress.DoesNotExist:
            return None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Withhold code solution until lesson is completed
        enrollment = self.context.get('enrollment')
        if enrollment:
            is_done = LessonProgress.objects.filter(
                enrollment=enrollment,
                lesson=instance,
                is_completed=True,
            ).exists()
            if not is_done:
                data['code_solution'] = None
        else:
            data['code_solution'] = None
        return data


class LessonWriteSerializer(serializers.ModelSerializer):
    """Write serializer for lesson creation/update by course authors."""

    class Meta:
        model = Lesson
        fields = [
            'module', 'title', 'slug', 'content_type', 'position',
            'text_content', 'video_url', 'video_duration_seconds',
            'video_thumbnail_url', 'video_transcript',
            'code_language', 'code_starter', 'code_solution',
            'code_test_cases', 'quiz_config', 'external_url',
            'estimated_duration_minutes', 'is_preview', 'is_mandatory',
        ]


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE
# ═══════════════════════════════════════════════════════════════════════════════

class CourseModuleSerializer(serializers.ModelSerializer):
    """Read serializer for modules with nested lesson outlines."""
    lessons = LessonListSerializer(many=True, read_only=True)
    lesson_count = serializers.IntegerField(read_only=True, default=0)
    total_duration_minutes = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = CourseModule
        fields = [
            'id', 'title', 'description', 'position', 'is_preview',
            'unlock_after_module', 'lesson_count', 'total_duration_minutes',
            'lessons',
        ]
        read_only_fields = ['id']


class CourseModuleWriteSerializer(serializers.ModelSerializer):
    """Write serializer for module creation/update."""

    class Meta:
        model = CourseModule
        fields = ['course', 'title', 'description', 'position', 'is_preview', 'unlock_after_module']


# ═══════════════════════════════════════════════════════════════════════════════
# COURSE
# ═══════════════════════════════════════════════════════════════════════════════

class CourseListSerializer(serializers.ModelSerializer):
    """
    Compact course serializer for listing/search results.
    Includes denormalised counts and instructor info.
    """
    category_name = serializers.CharField(source='category.name', default=None)
    instructors = CourseInstructorSerializer(many=True, read_only=True)
    module_count = serializers.IntegerField(read_only=True, default=0)
    lesson_count = serializers.IntegerField(read_only=True, default=0)
    is_enrolled = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'slug', 'subtitle', 'short_description',
            'thumbnail_url', 'preview_video_url',
            'category', 'category_name', 'skills', 'tags', 'level',
            'access_level', 'status',
            'estimated_duration_minutes', 'language', 'version',
            'enrollment_count', 'completion_count',
            'average_rating', 'review_count',
            'module_count', 'lesson_count',
            'instructors', 'is_enrolled', 'is_external', 'external_url',
            'published_at', 'created_at',
        ]
        read_only_fields = ['id', 'published_at', 'created_at']

    def get_is_enrolled(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return CourseEnrollment.objects.filter(
            user=request.user,
            course=obj,
            status__in=['active', 'completed'],
        ).exists()

    def get_thumbnail_url(self, obj):
        if obj.thumbnail:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.thumbnail.url)
            return obj.thumbnail.url
        return None


class CourseDetailSerializer(serializers.ModelSerializer):
    """
    Full course serializer with modules, lessons, and enrollment state.
    Served on the course detail page.
    """
    category_data = CourseCategorySerializer(source='category', read_only=True)
    instructors = CourseInstructorSerializer(many=True, read_only=True)
    modules = CourseModuleSerializer(many=True, read_only=True)
    prerequisites = CourseListSerializer(many=True, read_only=True)
    enrollment = serializers.SerializerMethodField()
    is_enrolled = serializers.SerializerMethodField()
    is_enrollable = serializers.BooleanField(read_only=True)
    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'slug', 'subtitle', 'description', 'short_description',
            'thumbnail_url', 'preview_video_url',
            'category', 'category_data', 'skills', 'tags', 'level',
            'access_level', 'required_subscription_tier', 'status',
            'estimated_duration_minutes', 'language', 'version',
            'max_enrollments', 'enrollment_count', 'completion_count',
            'average_rating', 'review_count',
            'instructors', 'modules', 'prerequisites',
            'enrollment', 'is_enrolled', 'is_enrollable',
            'is_external', 'external_url',
            'published_at', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'published_at', 'created_at', 'updated_at']

    def get_enrollment(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        try:
            enrollment = CourseEnrollment.objects.get(user=request.user, course=obj)
            return CourseEnrollmentSerializer(enrollment).data
        except CourseEnrollment.DoesNotExist:
            return None

    def get_is_enrolled(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return CourseEnrollment.objects.filter(
            user=request.user,
            course=obj,
            status__in=['active', 'completed'],
        ).exists()

    def get_thumbnail_url(self, obj):
        if obj.thumbnail:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.thumbnail.url)
            return obj.thumbnail.url
        return None


class CourseWriteSerializer(serializers.ModelSerializer):
    """Write serializer for course creation/update by admins and instructors."""

    class Meta:
        model = Course
        fields = [
            'title', 'slug', 'subtitle', 'description', 'short_description',
            'thumbnail', 'preview_video_url',
            'category', 'skills', 'tags', 'level',
            'access_level', 'required_subscription_tier',
            'status', 'language', 'version', 'max_enrollments',
            'external_url', 'is_external',
        ]

    def validate(self, data):
        # External courses must have a URL
        if data.get('is_external') and not data.get('external_url'):
            raise serializers.ValidationError({
                'external_url': 'External URL is required for externally-hosted courses.',
            })
        return data


# ═══════════════════════════════════════════════════════════════════════════════
# ENROLLMENT
# ═══════════════════════════════════════════════════════════════════════════════

class CourseEnrollmentSerializer(serializers.ModelSerializer):
    """Read serializer for enrollment status and progress."""
    course_title = serializers.CharField(source='course.title', read_only=True)
    course_slug = serializers.CharField(source='course.slug', read_only=True)
    last_lesson_title = serializers.CharField(
        source='last_lesson.title', read_only=True, default=None,
    )
    has_certificate = serializers.SerializerMethodField()

    class Meta:
        model = CourseEnrollment
        fields = [
            'id', 'user', 'course', 'course_title', 'course_slug',
            'status', 'progress_percentage', 'lessons_completed',
            'total_time_spent_seconds', 'last_lesson', 'last_lesson_title',
            'last_accessed_at', 'enrolled_at', 'completed_at',
            'has_certificate',
        ]
        read_only_fields = [
            'id', 'user', 'status', 'progress_percentage',
            'lessons_completed', 'total_time_spent_seconds',
            'enrolled_at', 'completed_at',
        ]

    def get_has_certificate(self, obj):
        return hasattr(obj, 'certificate') and obj.certificate is not None


class CourseEnrollmentCreateSerializer(serializers.Serializer):
    """Enroll in a course. Validates eligibility and prerequisites."""
    course_id = serializers.IntegerField()

    def validate_course_id(self, value):
        try:
            course = Course.objects.get(pk=value, status=Course.Status.PUBLISHED)
        except Course.DoesNotExist:
            raise serializers.ValidationError('Course not found or not published.')

        if not course.is_enrollable:
            raise serializers.ValidationError('This course is not accepting new enrollments.')

        user = self.context['request'].user

        # Check for existing enrollment
        if CourseEnrollment.objects.filter(user=user, course=course).exists():
            raise serializers.ValidationError('You are already enrolled in this course.')

        # Check prerequisites
        prereqs = course.prerequisites.filter(status=Course.Status.PUBLISHED)
        for prereq in prereqs:
            if not CourseEnrollment.objects.filter(
                user=user, course=prereq, status=CourseEnrollment.Status.COMPLETED,
            ).exists():
                raise serializers.ValidationError(
                    f'You must complete "{prereq.title}" before enrolling in this course.'
                )

        # Check access level / subscription tier
        if course.access_level == Course.AccessLevel.PREMIUM:
            profile = None
            if hasattr(user, 'talent_profile'):
                profile = user.talent_profile
                user_tier = profile.subscription_tier
            elif hasattr(user, 'company_profile'):
                profile = user.company_profile
                user_tier = profile.subscription_tier
            else:
                user_tier = 'free'

            if user_tier == 'free':
                raise serializers.ValidationError(
                    'This course requires a premium subscription.'
                )

        return value

    def create(self, validated_data):
        course = Course.objects.get(pk=validated_data['course_id'])
        user = self.context['request'].user

        try:
            enrollment = CourseEnrollment.objects.create(
                user=user,
                course=course,
                status=CourseEnrollment.Status.ACTIVE,
            )
        except IntegrityError:
            raise serializers.ValidationError({
                'course_id': 'You are already enrolled in this course.',
            })

        # Increment denormalised counter
        Course.objects.filter(pk=course.pk).update(
            enrollment_count=models.F('enrollment_count') + 1,
        )

        return enrollment


# ═══════════════════════════════════════════════════════════════════════════════
# PROGRESS
# ═══════════════════════════════════════════════════════════════════════════════

class LessonProgressSerializer(serializers.ModelSerializer):
    """Read serializer for lesson progress."""
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)
    content_type = serializers.CharField(source='lesson.content_type', read_only=True)

    class Meta:
        model = LessonProgress
        fields = [
            'id', 'enrollment', 'lesson', 'lesson_title', 'content_type',
            'is_completed', 'completed_at', 'time_spent_seconds',
            'video_position_seconds', 'attempts', 'best_score',
            'notes', 'started_at', 'updated_at',
        ]
        read_only_fields = ['id', 'enrollment', 'started_at', 'completed_at']


class LessonProgressUpdateSerializer(serializers.Serializer):
    """
    Update lesson progress — supports partial updates for:
    - Video position (resume playback)
    - Time spent (heartbeat tracking)
    - Completion marking
    - Notes
    - Quiz/code submissions
    """
    time_spent_seconds = serializers.IntegerField(min_value=0, required=False)
    video_position_seconds = serializers.IntegerField(min_value=0, required=False)
    mark_completed = serializers.BooleanField(required=False, default=False)
    notes = serializers.CharField(required=False, allow_blank=True)
    submission = serializers.JSONField(required=False)
    score = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)


# ═══════════════════════════════════════════════════════════════════════════════
# REVIEW
# ═══════════════════════════════════════════════════════════════════════════════

class CourseReviewSerializer(serializers.ModelSerializer):
    """Read serializer for course reviews."""
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    user_avatar = serializers.SerializerMethodField()

    class Meta:
        model = CourseReview
        fields = [
            'id', 'user', 'user_name', 'user_avatar', 'course',
            'rating', 'title', 'content',
            'is_verified_enrollment', 'is_approved',
            'helpful_count', 'not_helpful_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'user', 'is_verified_enrollment', 'is_approved',
            'helpful_count', 'not_helpful_count',
        ]

    def get_user_avatar(self, obj):
        if obj.user.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.user.avatar.url)
            return obj.user.avatar.url
        return None


class CourseReviewWriteSerializer(serializers.ModelSerializer):
    """Write serializer for creating/updating reviews."""

    class Meta:
        model = CourseReview
        fields = ['course', 'rating', 'title', 'content']

    def validate(self, data):
        user = self.context['request'].user
        course = data.get('course') or self.instance.course

        # Must be enrolled
        if not CourseEnrollment.objects.filter(
            user=user,
            course=course,
            status__in=['active', 'completed'],
        ).exists():
            raise serializers.ValidationError({
                'course': 'You must be enrolled in this course to leave a review.',
            })

        # One review per course (on create)
        if not self.instance and CourseReview.objects.filter(
            user=user, course=course,
        ).exists():
            raise serializers.ValidationError({
                'course': 'You have already reviewed this course.',
            })

        return data

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


# ═══════════════════════════════════════════════════════════════════════════════
# CERTIFICATE
# ═══════════════════════════════════════════════════════════════════════════════

class CertificateSerializer(serializers.ModelSerializer):
    """Read serializer for certificates."""
    verification_url = serializers.SerializerMethodField()
    is_valid = serializers.SerializerMethodField()

    class Meta:
        model = Certificate
        fields = [
            'id', 'holder_name', 'holder_email',
            'course_title', 'course_version', 'instructor_names',
            'completion_date', 'total_hours', 'skills_earned',
            'issued_at', 'is_revoked',
            'verification_url', 'is_valid',
        ]

    def get_verification_url(self, obj):
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(
                f'/api/v1/courses/certificates/verify/{obj.id}/'
            )
        return f'/api/v1/courses/certificates/verify/{obj.id}/'

    def get_is_valid(self, obj):
        return not obj.is_revoked and obj.verify_signature()
