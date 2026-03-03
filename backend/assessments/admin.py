"""
assessments/admin.py
Django admin configuration for the assessment engine.
"""
from django.contrib import admin
from .models import (
    QuestionTag, QuestionBank, Question, QuestionOption,
    Assessment, AssessmentSection, SectionQuestionLink,
    AssessmentInvitation, AssessmentAttempt, AttemptAnswer,
    AssessmentResult, SkillBadge, ProctorEvent, QuestionReport,
)


# ─── Inlines ──────────────────────────────────────────────────────────────────

class QuestionOptionInline(admin.TabularInline):
    model = QuestionOption
    extra = 0
    fields = ('text', 'is_correct', 'position', 'explanation')
    ordering = ('position',)


class SectionQuestionLinkInline(admin.TabularInline):
    model = SectionQuestionLink
    extra = 0
    fields = ('question', 'position', 'points_override', 'is_required')
    ordering = ('position',)
    autocomplete_fields = ('question',)


class AssessmentSectionInline(admin.StackedInline):
    model = AssessmentSection
    extra = 0
    fields = (
        'title', 'position', 'description',
        'question_bank', 'random_question_count',
        'min_difficulty', 'max_difficulty', 'question_types_filter',
        'time_limit_minutes', 'is_timed_independently',
        'allow_navigation', 'mandatory', 'instructions',
    )
    ordering = ('position',)


class AttemptAnswerInline(admin.TabularInline):
    model = AttemptAnswer
    extra = 0
    readonly_fields = (
        'question', 'section_index', 'points_earned', 'max_points',
        'is_correct', 'time_spent_seconds', 'graded_by',
    )
    fields = readonly_fields
    can_delete = False


class ProctorEventInline(admin.TabularInline):
    model = ProctorEvent
    extra = 0
    readonly_fields = ('event_type', 'severity', 'timestamp', 'metadata')
    fields = readonly_fields
    can_delete = False


# ─── Model admins ─────────────────────────────────────────────────────────────

@admin.register(QuestionTag)
class QuestionTagAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'parent', 'is_active')
    list_filter = ('is_active', 'parent')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(QuestionBank)
class QuestionBankAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'visibility', 'owner_company', 'primary_tag',
        'question_count', 'avg_difficulty', 'is_active',
    )
    list_filter = ('visibility', 'is_active')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('question_count', 'avg_difficulty', 'version')


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = (
        'title_short', 'bank', 'question_type', 'difficulty',
        'points', 'success_rate', 'is_active', 'is_approved',
    )
    list_filter = ('question_type', 'difficulty', 'is_active', 'is_approved', 'bank')
    search_fields = ('title', 'bank__name')
    inlines = [QuestionOptionInline]
    readonly_fields = (
        'discrimination_index', 'avg_time_seconds',
        'times_used', 'times_correct', 'times_incorrect', 'times_skipped',
    )
    actions = ['approve_questions', 'deactivate_questions']

    @admin.display(description='Title')
    def title_short(self, obj):
        return obj.title[:80]

    @admin.action(description='Approve selected questions')
    def approve_questions(self, request, queryset):
        count = queryset.update(is_approved=True)
        self.message_user(request, f'{count} questions approved.')

    @admin.action(description='Deactivate selected questions')
    def deactivate_questions(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} questions deactivated.')


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'assessment_type', 'status', 'difficulty_level',
        'owner_company', 'attempt_count', 'pass_rate', 'created_at',
    )
    list_filter = ('status', 'assessment_type', 'access_level', 'difficulty_level')
    search_fields = ('title', 'slug')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [AssessmentSectionInline]
    readonly_fields = (
        'total_questions', 'total_points', 'attempt_count',
        'pass_count', 'average_score_percent', 'average_completion_minutes',
        'published_at',
    )


@admin.register(AssessmentSection)
class AssessmentSectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'assessment', 'position', 'total_questions', 'total_points')
    list_filter = ('assessment',)
    inlines = [SectionQuestionLinkInline]


@admin.register(AssessmentAttempt)
class AssessmentAttemptAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'assessment', 'attempt_number', 'status',
        'started_at', 'submitted_at', 'is_flagged',
    )
    list_filter = ('status', 'is_flagged')
    search_fields = ('user__email', 'assessment__title')
    readonly_fields = (
        'id', 'randomisation_seed', 'question_order', 'section_timestamps',
        'tab_switch_count', 'copy_paste_count', 'fullscreen_exit_count',
        'suspicious_activity_score', 'ip_address', 'user_agent',
        'browser_fingerprint',
    )
    inlines = [AttemptAnswerInline, ProctorEventInline]
    actions = ['invalidate_attempts', 'clear_flags']

    @admin.action(description='Invalidate selected attempts')
    def invalidate_attempts(self, request, queryset):
        count = queryset.filter(status__in=['submitted', 'graded']).update(
            status='invalidated',
        )
        self.message_user(request, f'{count} attempts invalidated.')

    @admin.action(description='Clear flags on selected attempts')
    def clear_flags(self, request, queryset):
        count = queryset.update(is_flagged=False, flag_reason='')
        self.message_user(request, f'Flags cleared on {count} attempts.')


@admin.register(AssessmentResult)
class AssessmentResultAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'assessment', 'percentage_score', 'passed',
        'percentile_rank', 'graded_at',
    )
    list_filter = ('passed',)
    search_fields = ('user__email', 'assessment__title')
    readonly_fields = (
        'total_points_earned', 'total_points_possible', 'percentage_score',
        'passed', 'section_scores', 'skill_scores', 'difficulty_breakdown',
        'questions_answered', 'questions_correct', 'questions_incorrect',
        'questions_partial', 'questions_skipped',
        'total_time_seconds', 'avg_time_per_question_seconds',
        'percentile_rank',
    )


@admin.register(SkillBadge)
class SkillBadgeAdmin(admin.ModelAdmin):
    list_display = (
        'holder_name', 'skill_name', 'level', 'score_percent',
        'is_revoked', 'issued_at', 'expires_at',
    )
    list_filter = ('level', 'is_revoked', 'is_public')
    search_fields = ('holder_name', 'holder_email', 'skill_name')
    readonly_fields = ('id', 'signature')
    actions = ['revoke_badges']

    @admin.action(description='Revoke selected badges')
    def revoke_badges(self, request, queryset):
        count = queryset.update(is_revoked=True, revoked_reason='Revoked by admin')
        self.message_user(request, f'{count} badges revoked.')


@admin.register(AssessmentInvitation)
class AssessmentInvitationAdmin(admin.ModelAdmin):
    list_display = (
        'candidate_email', 'assessment', 'company', 'status',
        'expires_at', 'created_at',
    )
    list_filter = ('status',)
    search_fields = ('candidate_email', 'candidate_name', 'assessment__title')
    readonly_fields = ('id', 'token')


@admin.register(QuestionReport)
class QuestionReportAdmin(admin.ModelAdmin):
    list_display = (
        'question', 'report_type', 'status', 'reported_by', 'created_at',
    )
    list_filter = ('status', 'report_type')
    search_fields = ('question__title', 'description')
    actions = ['resolve_reports', 'dismiss_reports']

    @admin.action(description='Mark selected reports as resolved')
    def resolve_reports(self, request, queryset):
        from django.utils import timezone
        count = queryset.filter(status='pending').update(
            status='resolved', resolved_by=request.user,
            resolved_at=timezone.now(),
        )
        self.message_user(request, f'{count} reports resolved.')

    @admin.action(description='Dismiss selected reports')
    def dismiss_reports(self, request, queryset):
        count = queryset.filter(status='pending').update(status='dismissed')
        self.message_user(request, f'{count} reports dismissed.')
