"""
assessments/serializers.py
Phase 7 — Enterprise Assessment Serializers

Full read/write separation, permission-aware, with deep validation:
    - Read serializers are nested with computed fields for client consumption
    - Write serializers validate business rules (timing, attempt limits, etc.)
    - Attempt serializers enforce proctoring and anti-cheat state
    - Grading serializers handle multi-type scoring logic
"""
import re
from decimal import Decimal

from django.db import IntegrityError
from django.utils import timezone
from rest_framework import serializers

from .models import (
    Assessment,
    AssessmentAttempt,
    AssessmentInvitation,
    AssessmentResult,
    AssessmentSection,
    AttemptAnswer,
    ProctorEvent,
    Question,
    QuestionBank,
    QuestionOption,
    QuestionReport,
    QuestionTag,
    SectionQuestionLink,
    SkillBadge,
)


# ═══════════════════════════════════════════════════════════════════════════════
# TAGS
# ═══════════════════════════════════════════════════════════════════════════════

class QuestionTagSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    full_path = serializers.CharField(read_only=True)

    class Meta:
        model = QuestionTag
        fields = [
            'id', 'name', 'slug', 'description', 'icon',
            'parent', 'is_active', 'full_path', 'children',
        ]
        read_only_fields = ['id']

    def get_children(self, obj):
        children = obj.children.filter(is_active=True).order_by('name')
        return QuestionTagSerializer(children, many=True).data


# ═══════════════════════════════════════════════════════════════════════════════
# QUESTION BANK
# ═══════════════════════════════════════════════════════════════════════════════

class QuestionBankListSerializer(serializers.ModelSerializer):
    primary_tag_name = serializers.CharField(
        source='primary_tag.name', default=None, read_only=True,
    )
    owner_company_name = serializers.CharField(
        source='owner_company.legal_name', default=None, read_only=True,
    )

    class Meta:
        model = QuestionBank
        fields = [
            'id', 'name', 'slug', 'description', 'visibility',
            'primary_tag', 'primary_tag_name',
            'owner_company', 'owner_company_name',
            'version', 'question_count', 'avg_difficulty',
            'is_active', 'created_at',
        ]
        read_only_fields = ['id', 'version', 'question_count', 'avg_difficulty']


class QuestionBankWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionBank
        fields = [
            'name', 'slug', 'description', 'visibility',
            'primary_tag', 'owner_company', 'is_active',
        ]


# ═══════════════════════════════════════════════════════════════════════════════
# QUESTION OPTION
# ═══════════════════════════════════════════════════════════════════════════════

class QuestionOptionSerializer(serializers.ModelSerializer):
    """Read serializer — used in assessment review mode (shows is_correct)."""

    class Meta:
        model = QuestionOption
        fields = [
            'id', 'text', 'image', 'is_correct', 'position', 'explanation',
        ]
        read_only_fields = ['id']


class QuestionOptionCandidateSerializer(serializers.ModelSerializer):
    """
    Candidate-facing serializer — hides is_correct and explanation
    during an active attempt.
    """

    class Meta:
        model = QuestionOption
        fields = ['id', 'text', 'image', 'position']
        read_only_fields = ['id']


class QuestionOptionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionOption
        fields = ['text', 'image', 'is_correct', 'position', 'explanation']


# ═══════════════════════════════════════════════════════════════════════════════
# QUESTION
# ═══════════════════════════════════════════════════════════════════════════════

class QuestionListSerializer(serializers.ModelSerializer):
    """Compact question serializer for bank browsing / admin lists."""
    bank_name = serializers.CharField(source='bank.name', read_only=True)
    tag_names = serializers.SerializerMethodField()
    success_rate = serializers.FloatField(read_only=True)

    class Meta:
        model = Question
        fields = [
            'id', 'bank', 'bank_name', 'question_type', 'title',
            'difficulty', 'points', 'negative_points',
            'tag_names', 'success_rate',
            'times_used', 'times_correct', 'avg_time_seconds',
            'is_active', 'is_approved', 'created_at',
        ]
        read_only_fields = ['id', 'times_used', 'times_correct', 'avg_time_seconds']

    def get_tag_names(self, obj):
        return list(obj.tags.values_list('name', flat=True))


class QuestionDetailSerializer(serializers.ModelSerializer):
    """Full question detail — for admin/author editing with options."""
    options = QuestionOptionSerializer(many=True, read_only=True)
    tag_names = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = [
            'id', 'bank', 'question_type', 'title', 'explanation', 'hint',
            'hint_penalty_percent',
            'image', 'code_snippet', 'code_language',
            'points', 'negative_points', 'partial_scoring',
            # Type-specific
            'correct_boolean', 'accepted_answers', 'case_sensitive',
            'code_starter_template', 'code_solution', 'code_test_cases',
            'code_execution_language', 'code_time_limit_ms', 'code_memory_limit_kb',
            'correct_order',
            'essay_rubric', 'essay_min_words', 'essay_max_words',
            # Tags
            'tags', 'tag_names', 'difficulty',
            # Calibration
            'discrimination_index', 'avg_time_seconds',
            'times_used', 'times_correct', 'times_incorrect', 'times_skipped',
            # Options
            'options',
            # Lifecycle
            'is_active', 'is_approved', 'created_by',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'discrimination_index', 'avg_time_seconds',
            'times_used', 'times_correct', 'times_incorrect', 'times_skipped',
            'created_at', 'updated_at',
        ]

    def get_tag_names(self, obj):
        return list(obj.tags.values_list('name', flat=True))


class QuestionCandidateSerializer(serializers.ModelSerializer):
    """
    Candidate-facing during an active attempt.
    Hides: explanation, hint, correct answers, solution, calibration data.
    """
    options = QuestionOptionCandidateSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = [
            'id', 'question_type', 'title',
            'image', 'code_snippet', 'code_language',
            'points', 'negative_points', 'partial_scoring',
            'code_starter_template', 'code_execution_language',
            'code_time_limit_ms',
            'essay_min_words', 'essay_max_words',
            'options',
        ]
        read_only_fields = ['id']


class QuestionWriteSerializer(serializers.ModelSerializer):
    """Write serializer with cross-field validation for question type integrity."""

    class Meta:
        model = Question
        fields = [
            'bank', 'question_type', 'title', 'explanation', 'hint',
            'hint_penalty_percent',
            'image', 'code_snippet', 'code_language',
            'points', 'negative_points', 'partial_scoring',
            'correct_boolean', 'accepted_answers', 'case_sensitive',
            'code_starter_template', 'code_solution', 'code_test_cases',
            'code_execution_language', 'code_time_limit_ms', 'code_memory_limit_kb',
            'correct_order',
            'essay_rubric', 'essay_min_words', 'essay_max_words',
            'tags', 'difficulty', 'is_active',
        ]

    def validate(self, data):
        qt = data.get('question_type') or (self.instance.question_type if self.instance else None)

        if qt == Question.QuestionType.TRUE_FALSE and data.get('correct_boolean') is None:
            raise serializers.ValidationError({
                'correct_boolean': 'Required for true/false questions.',
            })

        if qt == Question.QuestionType.SHORT_ANSWER:
            answers = data.get('accepted_answers', [])
            if not answers:
                raise serializers.ValidationError({
                    'accepted_answers': 'At least one accepted answer is required.',
                })

        if qt == Question.QuestionType.CODE:
            if not data.get('code_execution_language'):
                raise serializers.ValidationError({
                    'code_execution_language': 'Required for code questions.',
                })
            test_cases = data.get('code_test_cases', [])
            if not test_cases:
                raise serializers.ValidationError({
                    'code_test_cases': 'At least one test case is required.',
                })

        if qt == Question.QuestionType.ORDERING:
            order = data.get('correct_order', [])
            if len(order) < 2:
                raise serializers.ValidationError({
                    'correct_order': 'At least 2 items are required for ordering questions.',
                })

        if qt == Question.QuestionType.ESSAY:
            rubric = data.get('essay_rubric', [])
            if not rubric:
                raise serializers.ValidationError({
                    'essay_rubric': 'At least one rubric criterion is required for essay questions.',
                })

        return data


# ═══════════════════════════════════════════════════════════════════════════════
# ASSESSMENT SECTION
# ═══════════════════════════════════════════════════════════════════════════════

class AssessmentSectionSerializer(serializers.ModelSerializer):
    """Read serializer for sections with question count."""
    question_bank_name = serializers.CharField(
        source='question_bank.name', default=None, read_only=True,
    )

    class Meta:
        model = AssessmentSection
        fields = [
            'id', 'title', 'description', 'position',
            'question_bank', 'question_bank_name',
            'random_question_count', 'min_difficulty', 'max_difficulty',
            'question_types_filter',
            'time_limit_minutes', 'is_timed_independently',
            'allow_navigation', 'mandatory', 'instructions',
            'total_questions', 'total_points',
        ]
        read_only_fields = ['id', 'total_questions', 'total_points']


class AssessmentSectionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssessmentSection
        fields = [
            'assessment', 'title', 'description', 'position',
            'question_bank', 'random_question_count',
            'min_difficulty', 'max_difficulty', 'question_types_filter',
            'time_limit_minutes', 'is_timed_independently',
            'allow_navigation', 'mandatory', 'instructions',
        ]


# ═══════════════════════════════════════════════════════════════════════════════
# ASSESSMENT
# ═══════════════════════════════════════════════════════════════════════════════

class AssessmentListSerializer(serializers.ModelSerializer):
    """Compact assessment serializer for catalog / search results."""
    primary_skill_name = serializers.CharField(
        source='primary_skill.name', default=None, read_only=True,
    )
    owner_company_name = serializers.CharField(
        source='owner_company.legal_name', default=None, read_only=True,
    )
    pass_rate = serializers.FloatField(read_only=True)
    is_attempted = serializers.SerializerMethodField()
    best_score = serializers.SerializerMethodField()

    class Meta:
        model = Assessment
        fields = [
            'id', 'title', 'slug', 'short_description', 'thumbnail',
            'assessment_type', 'status', 'access_level',
            'primary_skill', 'primary_skill_name', 'difficulty_level',
            'owner_company', 'owner_company_name',
            'total_time_minutes', 'passing_score_percent',
            'max_attempts', 'total_questions', 'total_points',
            'attempt_count', 'pass_count', 'average_score_percent',
            'pass_rate', 'is_attempted', 'best_score',
            'proctoring_enabled',
            'published_at', 'created_at',
        ]
        read_only_fields = [
            'id', 'total_questions', 'total_points',
            'attempt_count', 'pass_count', 'average_score_percent',
            'published_at', 'created_at',
        ]

    def get_is_attempted(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return AssessmentAttempt.objects.filter(
            assessment=obj, user=request.user,
        ).exists()

    def get_best_score(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        best = (
            AssessmentResult.objects
            .filter(assessment=obj, user=request.user, attempt__status='graded')
            .order_by('-percentage_score')
            .values_list('percentage_score', flat=True)
            .first()
        )
        return float(best) if best is not None else None


class AssessmentDetailSerializer(serializers.ModelSerializer):
    """Full assessment detail with sections and attempt history."""
    primary_skill_name = serializers.CharField(
        source='primary_skill.name', default=None, read_only=True,
    )
    skills_tested_data = serializers.SerializerMethodField()
    sections = AssessmentSectionSerializer(many=True, read_only=True)
    owner_company_name = serializers.CharField(
        source='owner_company.legal_name', default=None, read_only=True,
    )
    pass_rate = serializers.FloatField(read_only=True)
    user_attempts = serializers.SerializerMethodField()
    remaining_attempts = serializers.SerializerMethodField()
    can_start = serializers.SerializerMethodField()

    class Meta:
        model = Assessment
        fields = [
            'id', 'title', 'slug', 'description', 'short_description', 'thumbnail',
            'assessment_type', 'status', 'access_level',
            'primary_skill', 'primary_skill_name', 'skills_tested_data',
            'difficulty_level',
            'owner_company', 'owner_company_name',
            'total_time_minutes', 'passing_score_percent',
            'max_attempts', 'cooldown_hours',
            'show_results_immediately', 'show_correct_answers', 'allow_review',
            'shuffle_sections', 'shuffle_questions', 'shuffle_options',
            'proctoring_enabled', 'max_tab_switches',
            'webcam_required', 'fullscreen_required', 'block_copy_paste',
            'total_questions', 'total_points',
            'attempt_count', 'pass_count', 'average_score_percent',
            'average_completion_minutes', 'pass_rate',
            'version',
            'sections', 'user_attempts', 'remaining_attempts', 'can_start',
            'published_at', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'total_questions', 'total_points',
            'attempt_count', 'pass_count', 'average_score_percent',
            'average_completion_minutes',
            'published_at', 'created_at', 'updated_at',
        ]

    def get_skills_tested_data(self, obj):
        return list(obj.skills_tested.values('id', 'name', 'slug'))

    def get_user_attempts(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return []
        attempts = (
            AssessmentAttempt.objects
            .filter(assessment=obj, user=request.user)
            .order_by('-started_at')
        )
        return AssessmentAttemptListSerializer(attempts, many=True).data

    def get_remaining_attempts(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return obj.max_attempts
        if obj.max_attempts == 0:
            return None  # unlimited
        used = AssessmentAttempt.objects.filter(
            assessment=obj, user=request.user,
        ).exclude(status=AssessmentAttempt.AttemptStatus.IN_PROGRESS).count()
        return max(0, obj.max_attempts - used)

    def get_can_start(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        if obj.status != Assessment.Status.PUBLISHED:
            return False

        # Check attempt limit
        completed_attempts = AssessmentAttempt.objects.filter(
            assessment=obj, user=request.user,
        ).exclude(status=AssessmentAttempt.AttemptStatus.IN_PROGRESS).count()
        if obj.max_attempts > 0 and completed_attempts >= obj.max_attempts:
            return False

        # Check cooldown
        from datetime import timedelta
        last_attempt = (
            AssessmentAttempt.objects
            .filter(assessment=obj, user=request.user)
            .exclude(status=AssessmentAttempt.AttemptStatus.IN_PROGRESS)
            .order_by('-submitted_at')
            .first()
        )
        if last_attempt and last_attempt.submitted_at:
            cooldown = timedelta(hours=obj.cooldown_hours)
            if timezone.now() < last_attempt.submitted_at + cooldown:
                return False

        # Check for in-progress attempt (can resume, not start new)
        if AssessmentAttempt.objects.filter(
            assessment=obj,
            user=request.user,
            status=AssessmentAttempt.AttemptStatus.IN_PROGRESS,
        ).exists():
            return False

        return True


class AssessmentWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Assessment
        fields = [
            'title', 'slug', 'description', 'short_description', 'thumbnail',
            'assessment_type', 'status', 'access_level',
            'primary_skill', 'skills_tested', 'difficulty_level',
            'owner_company',
            'total_time_minutes', 'passing_score_percent',
            'max_attempts', 'cooldown_hours',
            'show_results_immediately', 'show_correct_answers', 'allow_review',
            'shuffle_sections', 'shuffle_questions', 'shuffle_options',
            'proctoring_enabled', 'max_tab_switches',
            'webcam_required', 'fullscreen_required', 'block_copy_paste',
        ]


# ═══════════════════════════════════════════════════════════════════════════════
# ATTEMPT
# ═══════════════════════════════════════════════════════════════════════════════

class AssessmentAttemptListSerializer(serializers.ModelSerializer):
    """Compact attempt serializer for user attempt history."""
    duration_seconds = serializers.IntegerField(read_only=True)
    has_result = serializers.SerializerMethodField()
    score_percent = serializers.SerializerMethodField()

    class Meta:
        model = AssessmentAttempt
        fields = [
            'id', 'assessment', 'attempt_number', 'status',
            'started_at', 'submitted_at', 'duration_seconds',
            'tab_switch_count', 'is_flagged',
            'has_result', 'score_percent',
        ]
        read_only_fields = ['id']

    def get_has_result(self, obj):
        return hasattr(obj, 'result')

    def get_score_percent(self, obj):
        if hasattr(obj, 'result'):
            return float(obj.result.percentage_score)
        return None


class AssessmentAttemptDetailSerializer(serializers.ModelSerializer):
    """
    Full attempt detail with answers and proctoring summary.
    Only served to the attempt owner or the company that invited them.
    """
    assessment_title = serializers.CharField(source='assessment.title', read_only=True)
    duration_seconds = serializers.IntegerField(read_only=True)
    proctor_summary = serializers.SerializerMethodField()
    total_time_minutes = serializers.IntegerField(source='assessment.total_time_minutes', read_only=True)
    questions = serializers.SerializerMethodField()
    answers = serializers.SerializerMethodField()
    flagged_question_ids = serializers.SerializerMethodField()

    class Meta:
        model = AssessmentAttempt
        fields = [
            'id', 'assessment', 'assessment_title', 'attempt_number', 'status',
            'started_at', 'submitted_at', 'duration_seconds',
            'time_remaining_seconds', 'total_time_minutes', 'current_section_index',
            'section_timestamps', 'question_order',
            'tab_switch_count', 'copy_paste_count', 'fullscreen_exit_count',
            'suspicious_activity_score', 'is_flagged', 'flag_reason',
            'proctor_summary', 'questions', 'answers', 'flagged_question_ids',
        ]
        read_only_fields = ['id']

    def get_proctor_summary(self, obj):
        from django.db.models import Count

        events = (
            obj.proctor_events
            .values('event_type')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        return list(events)

    def get_questions(self, obj):
        question_order = obj.question_order or {}
        ordered_pairs = []

        for section_key in sorted(question_order.keys(), key=lambda value: int(value)):
            for question_id in question_order.get(section_key) or []:
                ordered_pairs.append((question_id, int(section_key)))

        if not ordered_pairs:
            return []

        question_ids = [question_id for question_id, _ in ordered_pairs]
        questions = (
            Question.objects
            .filter(pk__in=question_ids, is_active=True)
            .prefetch_related('options')
        )
        question_map = {question.id: question for question in questions}

        serialised_questions = []
        for question_id, section_index in ordered_pairs:
            question = question_map.get(question_id)
            if question is None:
                continue

            question_data = QuestionCandidateSerializer(question).data
            question_data['section_index'] = section_index
            serialised_questions.append(question_data)

        return serialised_questions

    def get_answers(self, obj):
        answers = (
            AttemptAnswer.objects
            .filter(attempt=obj)
            .select_related('question')
        )
        answer_map = {}

        for answer in answers:
            answer_map[str(answer.question_id)] = {
                'selected_option_ids': answer.selected_option_ids,
                'text_answer': answer.text_answer,
                'boolean_answer': answer.boolean_answer,
                'code_answer': answer.code_answer,
                'ordering_answer': answer.ordering_answer,
                'is_bookmarked': answer.is_bookmarked,
                'section_index': answer.section_index,
                'time_spent_seconds': answer.time_spent_seconds,
            }

        return answer_map

    def get_flagged_question_ids(self, obj):
        return list(
            AttemptAnswer.objects
            .filter(attempt=obj, is_bookmarked=True)
            .values_list('question_id', flat=True)
        )


class StartAttemptSerializer(serializers.Serializer):
    """
    Start a new assessment attempt. Validates eligibility:
        - Assessment is published
        - Attempt limit not exceeded
        - Cooldown period respected
        - No in-progress attempt exists
    """
    assessment_id = serializers.IntegerField()

    def validate_assessment_id(self, value):
        try:
            assessment = Assessment.objects.get(
                pk=value, status=Assessment.Status.PUBLISHED,
            )
        except Assessment.DoesNotExist:
            raise serializers.ValidationError('Assessment not found or not published.')

        user = self.context['request'].user

        # Check for existing in-progress attempt (resume instead)
        existing = AssessmentAttempt.objects.filter(
            assessment=assessment,
            user=user,
            status=AssessmentAttempt.AttemptStatus.IN_PROGRESS,
        ).first()
        if existing:
            raise serializers.ValidationError(
                f'You have an in-progress attempt. Resume it or submit before starting a new one. '
                f'Attempt ID: {existing.id}',
            )

        # Check attempt limit
        completed = AssessmentAttempt.objects.filter(
            assessment=assessment, user=user,
        ).exclude(status=AssessmentAttempt.AttemptStatus.IN_PROGRESS).count()
        if assessment.max_attempts > 0 and completed >= assessment.max_attempts:
            raise serializers.ValidationError(
                f'Maximum attempts ({assessment.max_attempts}) reached for this assessment.',
            )

        # Check cooldown
        from datetime import timedelta
        last = (
            AssessmentAttempt.objects
            .filter(assessment=assessment, user=user)
            .exclude(status=AssessmentAttempt.AttemptStatus.IN_PROGRESS)
            .order_by('-submitted_at')
            .first()
        )
        if last and last.submitted_at:
            cooldown = timedelta(hours=assessment.cooldown_hours)
            remaining = (last.submitted_at + cooldown) - timezone.now()
            if remaining.total_seconds() > 0:
                hours = int(remaining.total_seconds() // 3600)
                minutes = int((remaining.total_seconds() % 3600) // 60)
                raise serializers.ValidationError(
                    f'Cooldown period active. Try again in {hours}h {minutes}m.',
                )

        return value


# ═══════════════════════════════════════════════════════════════════════════════
# ANSWERS
# ═══════════════════════════════════════════════════════════════════════════════

class SubmitAnswerSerializer(serializers.Serializer):
    """
    Submit an answer for a single question within an active attempt.
    Polymorphic — the relevant field depends on question type.
    """
    question_id = serializers.IntegerField()
    section_index = serializers.IntegerField()
    time_spent_seconds = serializers.IntegerField(min_value=0, default=0)

    # Type-specific answer fields (only one should be populated)
    selected_option_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list,
    )
    text_answer = serializers.CharField(required=False, default='', allow_blank=True)
    boolean_answer = serializers.BooleanField(required=False, allow_null=True, default=None)
    code_answer = serializers.CharField(required=False, default='', allow_blank=True)
    code_language = serializers.CharField(required=False, default='', allow_blank=True)
    ordering_answer = serializers.ListField(
        child=serializers.CharField(), required=False, default=list,
    )
    used_hint = serializers.BooleanField(required=False, default=False)
    is_bookmarked = serializers.BooleanField(required=False, default=False)


class AttemptAnswerSerializer(serializers.ModelSerializer):
    """Read serializer for attempt answers (review mode)."""
    question_title = serializers.CharField(source='question.title', read_only=True)
    question_type = serializers.CharField(source='question.question_type', read_only=True)

    class Meta:
        model = AttemptAnswer
        fields = [
            'id', 'question', 'question_title', 'question_type',
            'section_index',
            'selected_option_ids', 'text_answer', 'boolean_answer',
            'code_answer', 'code_language', 'ordering_answer',
            'code_execution_results',
            'points_earned', 'max_points', 'is_correct', 'is_partial',
            'used_hint', 'time_spent_seconds', 'answered_at',
            'is_bookmarked', 'is_skipped',
            'graded_by', 'grader_notes',
        ]
        read_only_fields = ['id']


# ═══════════════════════════════════════════════════════════════════════════════
# RESULTS
# ═══════════════════════════════════════════════════════════════════════════════

class AssessmentResultSerializer(serializers.ModelSerializer):
    """Full result serializer with review-ready data."""
    assessment_title = serializers.CharField(source='assessment.title', read_only=True)
    attempt_id = serializers.UUIDField(source='attempt.id', read_only=True)
    passing_score = serializers.FloatField(source='assessment.passing_score_percent', read_only=True)
    correct_count = serializers.IntegerField(source='questions_correct', read_only=True)
    total_questions = serializers.SerializerMethodField()
    time_taken_seconds = serializers.IntegerField(source='total_time_seconds', read_only=True)
    percentile = serializers.FloatField(source='percentile_rank', read_only=True)
    skill_breakdown = serializers.SerializerMethodField()
    show_answers = serializers.SerializerMethodField()
    answers = serializers.SerializerMethodField()
    badge = serializers.SerializerMethodField()

    class Meta:
        model = AssessmentResult
        fields = [
            'id', 'attempt_id', 'assessment', 'assessment_title', 'user',
            'total_points_earned', 'total_points_possible',
            'percentage_score', 'passed',
            'section_scores', 'skill_scores', 'skill_breakdown', 'difficulty_breakdown',
            'questions_answered', 'questions_correct',
            'questions_incorrect', 'questions_partial', 'questions_skipped',
            'correct_count', 'total_questions',
            'total_time_seconds', 'time_taken_seconds', 'avg_time_per_question_seconds',
            'percentile_rank', 'percentile', 'passing_score',
            'show_answers', 'answers', 'badge',
            'graded_at', 'updated_at',
        ]
        read_only_fields = ['id']

    def get_total_questions(self, obj):
        return (
            obj.questions_correct
            + obj.questions_incorrect
            + obj.questions_partial
            + obj.questions_skipped
        )

    def get_skill_breakdown(self, obj):
        if not obj.skill_scores:
            return []

        if isinstance(obj.skill_scores, dict):
            return [
                {
                    'name': skill,
                    'score': score,
                }
                for skill, score in obj.skill_scores.items()
            ]

        if isinstance(obj.skill_scores, list):
            breakdown = []
            for entry in obj.skill_scores:
                if not isinstance(entry, dict):
                    continue

                name = (
                    entry.get('name')
                    or entry.get('skill_name')
                    or entry.get('skill')
                    or entry.get('tag_name')
                )
                if not name:
                    continue

                score = entry.get('score')
                if score is None:
                    score = entry.get('percentage')
                if score is None:
                    earned = entry.get('earned')
                    possible = entry.get('possible')
                    if possible:
                        score = round((float(earned or 0) / float(possible)) * 100, 2)

                item = {'name': name}
                if score is not None:
                    item['score'] = score
                if entry.get('percentage') is not None:
                    item['percentage'] = entry['percentage']
                breakdown.append(item)

            return breakdown

        return []

    def get_show_answers(self, obj):
        return bool(obj.assessment.show_results_immediately and obj.assessment.allow_review)

    def get_badge(self, obj):
        try:
            badge = obj.badge
        except SkillBadge.DoesNotExist:
            return None

        return {
            'id': str(badge.id),
            'title': badge.assessment_title,
            'name': badge.skill_name,
            'level': badge.level,
            'skill': badge.skill_name,
            'issued_at': badge.issued_at,
        }

    def _format_user_answer(self, answer):
        question = answer.question

        if question.question_type in (Question.QuestionType.MCQ, Question.QuestionType.MULTI_SELECT):
            option_text = {
                option.id: option.text
                for option in question.options.all()
            }
            labels = [
                option_text.get(option_id, str(option_id))
                for option_id in (answer.selected_option_ids or [])
            ]
            return ', '.join(labels)

        if question.question_type == Question.QuestionType.TRUE_FALSE:
            if answer.boolean_answer is None:
                return ''
            return 'True' if answer.boolean_answer else 'False'

        if question.question_type == Question.QuestionType.ORDERING:
            return ' -> '.join(answer.ordering_answer or [])

        if question.question_type == Question.QuestionType.CODE:
            return answer.code_answer or ''

        return answer.text_answer or ''

    def _format_correct_answer(self, answer):
        question = answer.question

        if question.question_type in (Question.QuestionType.MCQ, Question.QuestionType.MULTI_SELECT):
            correct_options = question.options.filter(is_correct=True).values_list('text', flat=True)
            return ', '.join(correct_options)

        if question.question_type == Question.QuestionType.TRUE_FALSE:
            if question.correct_boolean is None:
                return None
            return 'True' if question.correct_boolean else 'False'

        if question.question_type == Question.QuestionType.SHORT_ANSWER:
            return ', '.join(question.accepted_answers or [])

        if question.question_type == Question.QuestionType.ORDERING:
            return ' -> '.join(question.correct_order or [])

        return None

    def get_answers(self, obj):
        if not self.get_show_answers(obj):
            return []

        answers = (
            AttemptAnswer.objects
            .filter(attempt=obj.attempt)
            .select_related('question')
            .prefetch_related('question__options')
            .order_by('section_index', 'question__id')
        )

        answer_list = []
        for answer in answers:
            answer_list.append({
                'question_id': answer.question_id,
                'question_text': answer.question.title,
                'question_type': answer.question.question_type,
                'is_correct': answer.is_correct,
                'user_answer': self._format_user_answer(answer),
                'correct_answer': self._format_correct_answer(answer) if obj.assessment.show_correct_answers else None,
                'explanation': answer.grader_notes or answer.question.explanation or None,
            })

        return answer_list


class AssessmentResultCompactSerializer(serializers.ModelSerializer):
    """Compact result for lists / company dashboards."""
    assessment_title = serializers.CharField(source='assessment.title', read_only=True)
    attempt_id = serializers.UUIDField(source='attempt.id', read_only=True)

    class Meta:
        model = AssessmentResult
        fields = [
            'id', 'attempt_id', 'assessment', 'assessment_title',
            'percentage_score', 'passed',
            'questions_answered', 'questions_correct',
            'total_time_seconds', 'percentile_rank',
            'graded_at',
        ]


class AssessmentInvitationSerializer(serializers.ModelSerializer):
    assessment_title = serializers.CharField(source='assessment.title', read_only=True)
    company_name = serializers.CharField(
        source='company.legal_name', read_only=True,
    )
    invited_by_name = serializers.CharField(
        source='invited_by.full_name', read_only=True, default=None,
    )
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = AssessmentInvitation
        fields = [
            'id', 'assessment', 'assessment_title',
            'company', 'company_name',
            'invited_by', 'invited_by_name',
            'candidate', 'candidate_email', 'candidate_name',
            'status', 'personal_message', 'job_post',
            'expires_at', 'is_expired',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'token', 'created_at', 'updated_at']


class AssessmentInvitationCreateSerializer(serializers.Serializer):
    """Create an invitation from a company to a candidate."""
    assessment_id = serializers.IntegerField()
    candidate_email = serializers.EmailField()
    candidate_name = serializers.CharField(max_length=255, required=False, default='')
    personal_message = serializers.CharField(required=False, default='')
    job_post_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    expires_in_days = serializers.IntegerField(min_value=1, max_value=90, default=7)

    def validate_assessment_id(self, value):
        try:
            Assessment.objects.get(pk=value)
        except Assessment.DoesNotExist:
            raise serializers.ValidationError('Assessment not found.')
        return value


# ═══════════════════════════════════════════════════════════════════════════════
# SKILL BADGE
# ═══════════════════════════════════════════════════════════════════════════════

class SkillBadgeSerializer(serializers.ModelSerializer):
    """Read serializer for skill badges."""
    is_valid = serializers.BooleanField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    verification_url = serializers.SerializerMethodField()

    class Meta:
        model = SkillBadge
        fields = [
            'id', 'user', 'holder_name', 'holder_email',
            'skill_name', 'assessment_title', 'level',
            'score_percent', 'issued_at', 'expires_at',
            'is_revoked', 'is_public',
            'is_valid', 'is_expired', 'verification_url',
        ]

    def get_verification_url(self, obj):
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(
                f'/api/v1/assessments/badges/verify/{obj.id}/',
            )
        return f'/api/v1/assessments/badges/verify/{obj.id}/'


# ═══════════════════════════════════════════════════════════════════════════════
# PROCTOR EVENT
# ═══════════════════════════════════════════════════════════════════════════════

class ProctorEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProctorEvent
        fields = [
            'id', 'event_type', 'severity', 'timestamp',
            'metadata', 'question_id', 'section_index',
            'client_timestamp',
        ]
        read_only_fields = ['id']


class ProctorEventCreateSerializer(serializers.Serializer):
    """
    Record a proctoring event from the client.
    Validates event type and rate-limits excessive reporting.
    """
    event_type = serializers.ChoiceField(choices=ProctorEvent.EventType.choices)
    metadata = serializers.DictField(required=False, default=dict)
    question_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    section_index = serializers.IntegerField(required=False, allow_null=True, default=None)
    client_timestamp = serializers.DateTimeField(required=False, allow_null=True, default=None)


# ═══════════════════════════════════════════════════════════════════════════════
# QUESTION REPORT
# ═══════════════════════════════════════════════════════════════════════════════

class QuestionReportSerializer(serializers.ModelSerializer):
    question_title = serializers.CharField(source='question.title', read_only=True)
    reported_by_email = serializers.CharField(
        source='reported_by.email', read_only=True, default=None,
    )

    class Meta:
        model = QuestionReport
        fields = [
            'id', 'question', 'question_title',
            'reported_by', 'reported_by_email',
            'attempt', 'report_type', 'description',
            'status', 'resolution_notes', 'resolved_by',
            'created_at', 'resolved_at',
        ]
        read_only_fields = ['id', 'status', 'resolution_notes', 'resolved_by', 'resolved_at']


class QuestionReportCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionReport
        fields = ['question', 'attempt', 'report_type', 'description']



