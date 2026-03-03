"""
assessments/models.py
Phase 7 — Enterprise Assessment & Skill Verification Engine

A production-grade assessment system that goes far beyond basic quizzes:

    1.  QuestionBank         — Categorised pools with difficulty calibration
    2.  Question              — 7 question types with rich metadata
    3.  QuestionOption        — Options for MCQ / multi-select questions
    4.  QuestionTag           — Hierarchical skill tags for questions
    5.  Assessment            — Timed assessments with section-based structure
    6.  AssessmentSection     — Sections within an assessment (time-boxed)
    7.  SectionQuestionLink   — Through table: section → question with ordering
    8.  AssessmentInvitation  — Company-initiated candidate invitations
    9.  AssessmentAttempt     — A user's attempt with timing + proctoring
    10. AttemptAnswer         — Individual answers within an attempt
    11. AssessmentResult      — Scored results with per-section breakdowns
    12. SkillBadge            — Verified skill badges from passing assessments
    13. ProctorEvent          — Anti-cheating event log (tab switches, pastes, etc.)
    14. QuestionReport        — User-submitted reports for erroneous questions

Design decisions:
    - Question banks support versioning so published assessments are snapshot-safe
    - Sections can be time-boxed independently (like GRE/GMAT sections)
    - Proctoring is event-sourced — every suspicious action is logged with timestamps
    - Skill badges use HMAC verification identical to course certificates
    - Question randomisation is seed-based for reproducibility on resume
    - Anti-cheating: copy/paste detection, tab-switch counting, IP fingerprinting
    - Assessment invitations support company workflows (hire → assess → verify)
    - All scoring is server-side — no client-side evaluation
    - Partial scoring for multi-select and ordering questions
    - Full audit trail — attempts cannot be deleted, only invalidated
"""
import hashlib
import hmac
import secrets
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
# 1. QUESTION TAG — Skill-Based Taxonomy for Questions
# ═══════════════════════════════════════════════════════════════════════════════

class QuestionTag(models.Model):
    """
    Hierarchical skill tags for categorising questions.
    E.g. Programming → Python → Django → ORM Queries

    Enables:
        - Skill-based assessment generation
        - Per-skill score breakdowns in results
        - Skill badge mapping
    """
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True, db_index=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
    )
    description = models.TextField(blank=True)
    icon = models.CharField(
        max_length=100, blank=True,
        help_text='Icon identifier (Lucide name or emoji)',
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Question Tag'
        verbose_name_plural = 'Question Tags'
        ordering = ['name']
        unique_together = ('parent', 'slug')
        indexes = [
            models.Index(fields=['parent', 'name'], name='idx_qtag_parent_name'),
        ]

    def __str__(self):
        if self.parent:
            return f'{self.parent.name} → {self.name}'
        return self.name

    @property
    def full_path(self) -> str:
        parts = [self.name]
        current = self.parent
        depth = 0
        while current and depth < 10:
            parts.append(current.name)
            current = current.parent
            depth += 1
        return ' → '.join(reversed(parts))


# ═══════════════════════════════════════════════════════════════════════════════
# 2. QUESTION BANK — Organised Pools of Questions
# ═══════════════════════════════════════════════════════════════════════════════

class QuestionBank(models.Model):
    """
    A curated collection of questions grouped by domain/skill.
    Assessment sections draw from one or more banks.

    Banks can be:
        - Platform-managed (TalentOrbit curated)
        - Company-specific (for custom hiring assessments)
    """

    class Visibility(models.TextChoices):
        PUBLIC = 'public', 'Public (platform-wide)'
        COMPANY = 'company', 'Company-specific'
        PRIVATE = 'private', 'Private (draft)'

    name = models.CharField(max_length=200, db_index=True)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField(blank=True)
    visibility = models.CharField(
        max_length=20,
        choices=Visibility.choices,
        default=Visibility.PRIVATE,
        db_index=True,
    )
    owner_company = models.ForeignKey(
        'accounts.CompanyProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='question_banks',
        help_text='Owning company. NULL = platform-managed bank.',
    )
    primary_tag = models.ForeignKey(
        QuestionTag,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='banks',
        help_text='Primary skill domain for this bank.',
    )
    tags = models.ManyToManyField(
        QuestionTag,
        blank=True,
        related_name='associated_banks',
        help_text='All skill tags covered by this bank.',
    )
    version = models.PositiveIntegerField(
        default=1,
        help_text='Incremented when questions are added/modified. '
                  'Published assessments snapshot the version.',
    )
    # Denormalised counters for admin dashboards
    question_count = models.PositiveIntegerField(default=0)
    avg_difficulty = models.DecimalField(
        max_digits=3, decimal_places=2, default=0.00,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_question_banks',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Question Bank'
        verbose_name_plural = 'Question Banks'
        ordering = ['name']
        indexes = [
            models.Index(fields=['visibility', 'is_active'], name='idx_qbank_vis_active'),
            models.Index(fields=['owner_company', 'is_active'], name='idx_qbank_company'),
        ]

    def __str__(self):
        return f'{self.name} (v{self.version}, {self.question_count} Q)'

    def recalculate_stats(self):
        """Recompute question count and average difficulty from child questions."""
        from django.db.models import Avg, Count
        stats = self.questions.filter(is_active=True).aggregate(
            count=Count('id'),
            avg_diff=Avg('difficulty'),
        )
        self.question_count = stats['count'] or 0
        self.avg_difficulty = stats['avg_diff'] or 0.00
        QuestionBank.objects.filter(pk=self.pk).update(
            question_count=self.question_count,
            avg_difficulty=self.avg_difficulty,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 3. QUESTION — The Atomic Assessment Unit
# ═══════════════════════════════════════════════════════════════════════════════

class Question(models.Model):
    """
    A single question with full metadata for scoring, analytics, and reporting.

    Supports 7 question types:
        - MCQ: single correct answer from options
        - MULTI_SELECT: multiple correct answers (partial scoring)
        - TRUE_FALSE: boolean answer
        - SHORT_ANSWER: exact/regex text match
        - CODE: code execution with test cases
        - ESSAY: manual/AI grading with rubric
        - ORDERING: arrange items in correct sequence (partial scoring)

    Each question tracks calibration data:
        - difficulty (1–5 scale, auto-adjusted from attempt statistics)
        - discrimination_index (how well it separates high/low performers)
        - avg_time_seconds (mean time to answer, auto-computed)
    """

    class QuestionType(models.TextChoices):
        MCQ = 'mcq', 'Multiple Choice (single answer)'
        MULTI_SELECT = 'multi_select', 'Multiple Select (multiple answers)'
        TRUE_FALSE = 'true_false', 'True / False'
        SHORT_ANSWER = 'short_answer', 'Short Answer'
        CODE = 'code', 'Code Challenge'
        ESSAY = 'essay', 'Essay / Long-form'
        ORDERING = 'ordering', 'Ordering / Ranking'

    class DifficultyLevel(models.IntegerChoices):
        VERY_EASY = 1, 'Very Easy'
        EASY = 2, 'Easy'
        MEDIUM = 3, 'Medium'
        HARD = 4, 'Hard'
        VERY_HARD = 5, 'Very Hard'

    # ── Identity ──────────────────────────────────────────────────────────
    bank = models.ForeignKey(
        QuestionBank,
        on_delete=models.CASCADE,
        related_name='questions',
    )
    question_type = models.CharField(
        max_length=20,
        choices=QuestionType.choices,
        db_index=True,
    )
    title = models.CharField(
        max_length=500,
        help_text='The question text (Markdown supported).',
    )
    explanation = models.TextField(
        blank=True,
        help_text='Explanation shown after answering (for learning mode).',
    )
    hint = models.TextField(
        blank=True,
        help_text='Optional hint that can be revealed at a score penalty.',
    )
    hint_penalty_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=10.00,
        help_text='Percentage penalty for using the hint.',
    )

    # ── Media ─────────────────────────────────────────────────────────────
    image = models.ImageField(
        upload_to='assessments/questions/',
        null=True, blank=True,
        help_text='Image embedded in the question (diagrams, code screenshots, etc.).',
    )
    code_snippet = models.TextField(
        blank=True,
        help_text='Pre-formatted code block shown with the question.',
    )
    code_language = models.CharField(
        max_length=30, blank=True,
        help_text='Language for syntax highlighting of code_snippet.',
    )

    # ── Scoring ───────────────────────────────────────────────────────────
    points = models.DecimalField(
        max_digits=6, decimal_places=2, default=1.00,
        validators=[MinValueValidator(0.01)],
        help_text='Points awarded for a fully correct answer.',
    )
    negative_points = models.DecimalField(
        max_digits=6, decimal_places=2, default=0.00,
        help_text='Points deducted for a wrong answer (0 = no negative marking).',
    )
    partial_scoring = models.BooleanField(
        default=False,
        help_text='Allow partial credit for partially correct answers '
                  '(multi-select, ordering).',
    )

    # ── Type-specific config ──────────────────────────────────────────────
    # TRUE_FALSE
    correct_boolean = models.BooleanField(
        null=True, blank=True,
        help_text='Correct answer for true/false questions.',
    )

    # SHORT_ANSWER
    accepted_answers = models.JSONField(
        default=list, blank=True,
        help_text='List of accepted answers: ["Django", "django"]. '
                  'Supports regex if prefixed with "regex:".',
    )
    case_sensitive = models.BooleanField(
        default=False,
        help_text='Whether short answer matching is case-sensitive.',
    )

    # CODE
    code_starter_template = models.TextField(
        blank=True,
        help_text='Starter code provided to the candidate.',
    )
    code_solution = models.TextField(
        blank=True,
        help_text='Reference solution (never shown to candidates during assessment).',
    )
    code_test_cases = models.JSONField(
        default=list, blank=True,
        help_text='Test cases: [{"input": "...", "expected_output": "...", '
                  '"is_hidden": false, "points": 10}]',
    )
    code_execution_language = models.CharField(
        max_length=30, blank=True,
        help_text='Execution language for the Piston code runner.',
    )
    code_time_limit_ms = models.PositiveIntegerField(
        default=5000,
        help_text='Code execution timeout in milliseconds.',
    )
    code_memory_limit_kb = models.PositiveIntegerField(
        default=256000,
        help_text='Code execution memory limit in KB.',
    )

    # ORDERING
    correct_order = models.JSONField(
        default=list, blank=True,
        help_text='Correct order of items: ["item_a", "item_b", "item_c"].',
    )

    # ESSAY
    essay_rubric = models.JSONField(
        default=list, blank=True,
        help_text='Rubric criteria: [{"criterion": "...", "max_points": 10, '
                  '"description": "..."}].',
    )
    essay_min_words = models.PositiveIntegerField(
        default=0,
        help_text='Minimum word count for essay answers.',
    )
    essay_max_words = models.PositiveIntegerField(
        default=5000,
        help_text='Maximum word count for essay answers.',
    )

    # ── Tags & Classification ─────────────────────────────────────────────
    tags = models.ManyToManyField(
        QuestionTag,
        blank=True,
        related_name='questions',
        help_text='Skills tested by this question.',
    )
    difficulty = models.PositiveIntegerField(
        choices=DifficultyLevel.choices,
        default=DifficultyLevel.MEDIUM,
        db_index=True,
    )

    # ── Calibration Data (auto-updated from attempt statistics) ───────────
    discrimination_index = models.DecimalField(
        max_digits=4, decimal_places=3, default=0.000,
        help_text='Item discrimination index (-1 to +1). '
                  'Measures how well this question separates '
                  'high-performing from low-performing test-takers.',
    )
    avg_time_seconds = models.PositiveIntegerField(
        default=0,
        help_text='Average time candidates spend on this question.',
    )
    times_used = models.PositiveIntegerField(
        default=0,
        help_text='Number of times this question has been served in assessments.',
    )
    times_correct = models.PositiveIntegerField(
        default=0,
        help_text='Number of times answered correctly.',
    )
    times_incorrect = models.PositiveIntegerField(
        default=0,
        help_text='Number of times answered incorrectly.',
    )
    times_skipped = models.PositiveIntegerField(
        default=0,
        help_text='Number of times skipped / unanswered.',
    )

    # ── Lifecycle ─────────────────────────────────────────────────────────
    is_active = models.BooleanField(default=True, db_index=True)
    is_approved = models.BooleanField(
        default=False,
        help_text='Questions require approval before use in published assessments.',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_questions',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Question'
        verbose_name_plural = 'Questions'
        ordering = ['bank', 'difficulty', '-created_at']
        indexes = [
            models.Index(
                fields=['bank', 'question_type', 'difficulty'],
                name='idx_q_bank_type_diff',
            ),
            models.Index(
                fields=['bank', 'is_active', 'is_approved'],
                name='idx_q_bank_active_approved',
            ),
            models.Index(
                fields=['question_type', 'difficulty', 'is_active'],
                name='idx_q_type_diff_active',
            ),
        ]

    def __str__(self):
        return f'[{self.get_question_type_display()}] {self.title[:80]}'

    @property
    def success_rate(self) -> float:
        """Percentage of correct answers (0-100)."""
        total = self.times_correct + self.times_incorrect
        if total == 0:
            return 0.0
        return round(self.times_correct / total * 100, 1)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. QUESTION OPTION — For MCQ / Multi-Select
# ═══════════════════════════════════════════════════════════════════════════════

class QuestionOption(models.Model):
    """
    An answer option for MCQ or multi-select questions.
    Supports rich content (text + optional image/code).
    Position is explicit for deterministic ordering.
    """
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='options',
    )
    text = models.CharField(
        max_length=1000,
        help_text='Option text (Markdown supported).',
    )
    image = models.ImageField(
        upload_to='assessments/options/',
        null=True, blank=True,
    )
    is_correct = models.BooleanField(
        default=False,
        help_text='Whether this option is correct.',
    )
    position = models.PositiveIntegerField(
        default=0,
        help_text='Display order. Options are shuffled at runtime; '
                  'position is the canonical order for answer keys.',
    )
    explanation = models.TextField(
        blank=True,
        help_text='Why this option is correct/incorrect (shown in review mode).',
    )

    class Meta:
        verbose_name = 'Question Option'
        verbose_name_plural = 'Question Options'
        ordering = ['position']
        unique_together = ('question', 'position')

    def __str__(self):
        mark = '✓' if self.is_correct else '✗'
        return f'{mark} {self.text[:60]}'


# ═══════════════════════════════════════════════════════════════════════════════
# 5. ASSESSMENT — The Assessment Container
# ═══════════════════════════════════════════════════════════════════════════════

class Assessment(models.Model):
    """
    A timed, structured assessment composed of sections.

    Lifecycle: draft → published → archived
    Types:
        - SKILL_TEST: Validates a specific skill (earns a badge on pass)
        - HIRING: Company-specific pre-hire assessment
        - PRACTICE: Untimed practice mode with explanations
        - CERTIFICATION: Proctored, formal certification exam
    """

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PUBLISHED = 'published', 'Published'
        ARCHIVED = 'archived', 'Archived'

    class AssessmentType(models.TextChoices):
        SKILL_TEST = 'skill_test', 'Skill Verification Test'
        HIRING = 'hiring', 'Hiring Assessment'
        PRACTICE = 'practice', 'Practice Test'
        CERTIFICATION = 'certification', 'Certification Exam'

    class AccessLevel(models.TextChoices):
        PUBLIC = 'public', 'Public (anyone can take)'
        INVITE_ONLY = 'invite_only', 'Invite Only'
        COMPANY = 'company', 'Company Members Only'
        PREMIUM = 'premium', 'Premium Subscribers Only'

    # ── Identity ──────────────────────────────────────────────────────────
    title = models.CharField(max_length=300, db_index=True)
    slug = models.SlugField(max_length=320, unique=True)
    description = models.TextField(
        help_text='Full description shown before starting (Markdown).',
    )
    short_description = models.CharField(
        max_length=300, blank=True,
        help_text='One-liner for cards and search results.',
    )
    thumbnail = models.ImageField(
        upload_to='assessments/thumbnails/',
        null=True, blank=True,
    )

    # ── Classification ────────────────────────────────────────────────────
    assessment_type = models.CharField(
        max_length=20,
        choices=AssessmentType.choices,
        default=AssessmentType.SKILL_TEST,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    access_level = models.CharField(
        max_length=20,
        choices=AccessLevel.choices,
        default=AccessLevel.PUBLIC,
        db_index=True,
    )
    primary_skill = models.ForeignKey(
        QuestionTag,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='primary_assessments',
        help_text='Primary skill being assessed (used for badge issuance).',
    )
    skills_tested = models.ManyToManyField(
        QuestionTag,
        blank=True,
        related_name='assessments',
        help_text='All skills covered across sections.',
    )
    difficulty_level = models.PositiveIntegerField(
        choices=Question.DifficultyLevel.choices,
        default=Question.DifficultyLevel.MEDIUM,
    )

    # ── Ownership ─────────────────────────────────────────────────────────
    owner_company = models.ForeignKey(
        'accounts.CompanyProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assessments',
        help_text='Owning company. NULL = platform assessment.',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_assessments',
    )

    # ── Timing & Rules ────────────────────────────────────────────────────
    total_time_minutes = models.PositiveIntegerField(
        help_text='Total time limit for the entire assessment (minutes). '
                  'If sections have individual time limits, this is the maximum.',
    )
    passing_score_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=70.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='Minimum percentage to pass.',
    )
    max_attempts = models.PositiveIntegerField(
        default=3,
        help_text='Maximum number of attempts allowed. 0 = unlimited.',
    )
    cooldown_hours = models.PositiveIntegerField(
        default=24,
        help_text='Minimum hours between attempts.',
    )
    show_results_immediately = models.BooleanField(
        default=True,
        help_text='Show score/answers immediately after submission.',
    )
    show_correct_answers = models.BooleanField(
        default=False,
        help_text='Reveal correct answers after submission (for practice mode).',
    )
    allow_review = models.BooleanField(
        default=True,
        help_text='Allow candidates to review answers before final submission.',
    )
    shuffle_sections = models.BooleanField(
        default=False,
        help_text='Randomise section order per attempt.',
    )
    shuffle_questions = models.BooleanField(
        default=True,
        help_text='Randomise question order within sections.',
    )
    shuffle_options = models.BooleanField(
        default=True,
        help_text='Randomise option order for MCQ/multi-select.',
    )

    # ── Proctoring ────────────────────────────────────────────────────────
    proctoring_enabled = models.BooleanField(
        default=False,
        help_text='Enable client-side proctoring (tab-switch detection, '
                  'copy/paste blocking, webcam monitoring).',
    )
    max_tab_switches = models.PositiveIntegerField(
        default=3,
        help_text='Maximum allowed tab switches before auto-submit. '
                  '0 = no limit (just log).',
    )
    webcam_required = models.BooleanField(
        default=False,
        help_text='Require webcam access for identity verification.',
    )
    fullscreen_required = models.BooleanField(
        default=False,
        help_text='Force fullscreen mode during the assessment.',
    )
    block_copy_paste = models.BooleanField(
        default=True,
        help_text='Block copy/paste (except in code editor).',
    )

    # ── Denormalised Analytics ────────────────────────────────────────────
    total_questions = models.PositiveIntegerField(default=0)
    total_points = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    attempt_count = models.PositiveIntegerField(default=0)
    pass_count = models.PositiveIntegerField(default=0)
    average_score_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00,
    )
    average_completion_minutes = models.DecimalField(
        max_digits=7, decimal_places=2, default=0.00,
    )

    # ── Version tracking ──────────────────────────────────────────────────
    version = models.PositiveIntegerField(
        default=1,
        help_text='Assessment version. Incremented on structural changes.',
    )

    # ── Timestamps ────────────────────────────────────────────────────────
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Assessment'
        verbose_name_plural = 'Assessments'
        ordering = ['-published_at', '-created_at']
        indexes = [
            models.Index(
                fields=['status', '-published_at'],
                name='idx_assess_status_pub',
            ),
            models.Index(
                fields=['assessment_type', 'status'],
                name='idx_assess_type_status',
            ),
            models.Index(
                fields=['owner_company', 'status'],
                name='idx_assess_company_status',
            ),
            models.Index(
                fields=['access_level', 'status'],
                name='idx_assess_access_status',
            ),
            models.Index(
                fields=['primary_skill', 'status'],
                name='idx_assess_skill_status',
            ),
        ]

    def __str__(self):
        status_icon = {'draft': '📝', 'published': '✅', 'archived': '📦'}
        return f'{status_icon.get(self.status, "?")} {self.title}'

    def save(self, *args, **kwargs):
        if self.status == self.Status.PUBLISHED and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    @property
    def pass_rate(self) -> float:
        if self.attempt_count == 0:
            return 0.0
        return round(self.pass_count / self.attempt_count * 100, 1)


# ═══════════════════════════════════════════════════════════════════════════════
# 6. ASSESSMENT SECTION — Time-Boxed Sections
# ═══════════════════════════════════════════════════════════════════════════════

class AssessmentSection(models.Model):
    """
    A section within an assessment. Each section can:
        - Draw from a specific question bank
        - Have its own time limit
        - Select a random subset of N questions from the bank
        - Target a specific difficulty range
    """
    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name='sections',
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    position = models.PositiveIntegerField(
        default=0,
        help_text='Display order within the assessment.',
    )

    # ── Question source ───────────────────────────────────────────────────
    question_bank = models.ForeignKey(
        QuestionBank,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sections',
        help_text='Source bank for random question selection. '
                  'If NULL, questions are manually assigned via SectionQuestionLink.',
    )
    random_question_count = models.PositiveIntegerField(
        default=0,
        help_text='Number of questions to randomly select from the bank. '
                  '0 = use all manually linked questions.',
    )
    min_difficulty = models.PositiveIntegerField(
        choices=Question.DifficultyLevel.choices,
        default=Question.DifficultyLevel.VERY_EASY,
    )
    max_difficulty = models.PositiveIntegerField(
        choices=Question.DifficultyLevel.choices,
        default=Question.DifficultyLevel.VERY_HARD,
    )
    question_types_filter = models.JSONField(
        default=list, blank=True,
        help_text='Limit to specific question types: ["mcq", "code"]. '
                  'Empty = all types.',
    )

    # ── Timing ────────────────────────────────────────────────────────────
    time_limit_minutes = models.PositiveIntegerField(
        default=0,
        help_text='Section-specific time limit (0 = shares assessment global timer).',
    )
    is_timed_independently = models.BooleanField(
        default=False,
        help_text='If True, this section has its own countdown. '
                  'When time expires, the section auto-submits and '
                  'the candidate moves to the next section. '
                  'Cannot go back.',
    )

    # ── Rules ─────────────────────────────────────────────────────────────
    allow_navigation = models.BooleanField(
        default=True,
        help_text='Allow candidates to navigate between questions in this section.',
    )
    mandatory = models.BooleanField(
        default=True,
        help_text='If False, candidates can skip this section entirely.',
    )
    instructions = models.TextField(
        blank=True,
        help_text='Section-specific instructions shown before starting.',
    )

    # ── Denormalised ──────────────────────────────────────────────────────
    total_questions = models.PositiveIntegerField(default=0)
    total_points = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)

    class Meta:
        verbose_name = 'Assessment Section'
        verbose_name_plural = 'Assessment Sections'
        ordering = ['position']
        unique_together = ('assessment', 'position')
        indexes = [
            models.Index(
                fields=['assessment', 'position'],
                name='idx_asection_assess_pos',
            ),
        ]

    def __str__(self):
        return f'§{self.position + 1} {self.title} ({self.assessment.title})'


# ═══════════════════════════════════════════════════════════════════════════════
# 7. SECTION ↔ QUESTION LINK — Through Table
# ═══════════════════════════════════════════════════════════════════════════════

class SectionQuestionLink(models.Model):
    """
    Explicit M2M through table linking questions to sections.
    Used when questions are manually curated rather than randomly drawn.
    Position determines display order (may be shuffled at runtime).
    """
    section = models.ForeignKey(
        AssessmentSection,
        on_delete=models.CASCADE,
        related_name='question_links',
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='section_links',
    )
    position = models.PositiveIntegerField(default=0)
    points_override = models.DecimalField(
        max_digits=6, decimal_places=2,
        null=True, blank=True,
        help_text='Override the question\'s default point value for this section.',
    )
    is_required = models.BooleanField(
        default=False,
        help_text='Always include this question (even in random selection mode).',
    )

    class Meta:
        verbose_name = 'Section ↔ Question Link'
        verbose_name_plural = 'Section ↔ Question Links'
        ordering = ['position']
        unique_together = ('section', 'question')

    def __str__(self):
        return f'{self.section} → Q{self.position}: {self.question.title[:40]}'

    @property
    def effective_points(self):
        return self.points_override if self.points_override is not None else self.question.points


# ═══════════════════════════════════════════════════════════════════════════════
# 8. ASSESSMENT INVITATION — Company-Initiated
# ═══════════════════════════════════════════════════════════════════════════════

class AssessmentInvitation(models.Model):
    """
    An invitation from a company to a candidate to take an assessment.
    Supports both registered users (by FK) and external candidates (by email).

    Flow:
        1. Company creates invitation → candidate receives email
        2. Candidate clicks link → registers (if needed) → starts assessment
        3. Results are shared with the inviting company
    """

    class InvitationStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACCEPTED = 'accepted', 'Accepted (opened)'
        COMPLETED = 'completed', 'Completed'
        EXPIRED = 'expired', 'Expired'
        REVOKED = 'revoked', 'Revoked'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name='invitations',
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sent_assessment_invitations',
    )
    company = models.ForeignKey(
        'accounts.CompanyProfile',
        on_delete=models.CASCADE,
        related_name='assessment_invitations',
    )

    # ── Candidate (either registered or external email) ───────────────────
    candidate = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assessment_invitations',
        help_text='Registered user. NULL if invited by email before registration.',
    )
    candidate_email = models.EmailField(
        help_text='Email of the invited candidate (used for external invites).',
    )
    candidate_name = models.CharField(max_length=255, blank=True)

    # ── Metadata ──────────────────────────────────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=InvitationStatus.choices,
        default=InvitationStatus.PENDING,
        db_index=True,
    )
    personal_message = models.TextField(
        blank=True,
        help_text='Personal message from the recruiter.',
    )
    job_post = models.ForeignKey(
        'jobs.JobPost',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assessment_invitations',
        help_text='Linked job post (if this assessment is part of a hiring pipeline).',
    )
    token = models.CharField(
        max_length=64,
        unique=True,
        help_text='Secure token for the invitation URL.',
    )
    expires_at = models.DateTimeField(
        help_text='Invitation expiry timestamp.',
    )

    # ── Result linkage ────────────────────────────────────────────────────
    attempt = models.ForeignKey(
        'AssessmentAttempt',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invitation',
        help_text='The attempt created from this invitation.',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Assessment Invitation'
        verbose_name_plural = 'Assessment Invitations'
        ordering = ['-created_at']
        indexes = [
            models.Index(
                fields=['candidate_email', 'status'],
                name='idx_ainvite_email_status',
            ),
            models.Index(
                fields=['company', 'status'],
                name='idx_ainvite_company_status',
            ),
            models.Index(
                fields=['assessment', 'status'],
                name='idx_ainvite_assess_status',
            ),
            models.Index(
                fields=['token'],
                name='idx_ainvite_token',
            ),
        ]

    def __str__(self):
        return f'Invite: {self.candidate_email} → {self.assessment.title}'

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(48)
        super().save(*args, **kwargs)

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at


# ═══════════════════════════════════════════════════════════════════════════════
# 9. ASSESSMENT ATTEMPT — A User's Test Session
# ═══════════════════════════════════════════════════════════════════════════════

class AssessmentAttempt(models.Model):
    """
    Represents a single attempt at an assessment by a user.

    Lifecycle: in_progress → submitted → graded → (invalidated)

    The attempt stores:
        - Timing (start, end, per-section timestamps)
        - Randomisation seed (for reproducible question/option order on resume)
        - Proctoring flags (aggregated from ProctorEvent records)
        - IP + user-agent fingerprint for security auditing
    """

    class AttemptStatus(models.TextChoices):
        IN_PROGRESS = 'in_progress', 'In Progress'
        SUBMITTED = 'submitted', 'Submitted (pending grading)'
        GRADED = 'graded', 'Graded'
        TIMED_OUT = 'timed_out', 'Timed Out (auto-submitted)'
        INVALIDATED = 'invalidated', 'Invalidated (cheating detected)'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name='attempts',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='assessment_attempts',
    )
    attempt_number = models.PositiveIntegerField(
        default=1,
        help_text='Nth attempt by this user for this assessment.',
    )

    # ── Timing ────────────────────────────────────────────────────────────
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    time_remaining_seconds = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Remaining time at last heartbeat (for resume support).',
    )
    current_section_index = models.PositiveIntegerField(
        default=0,
        help_text='Index of the section the candidate is currently on.',
    )
    section_timestamps = models.JSONField(
        default=dict, blank=True,
        help_text='Per-section start/end timestamps: '
                  '{"0": {"started": "...", "ended": "..."}, ...}',
    )

    # ── Randomisation ─────────────────────────────────────────────────────
    randomisation_seed = models.CharField(
        max_length=32,
        help_text='Seed for deterministic question/option shuffling. '
                  'Ensures the same order on resume.',
    )
    question_order = models.JSONField(
        default=dict, blank=True,
        help_text='Snapshot of actual question order per section: '
                  '{"0": [q_id, q_id, ...], ...}',
    )

    # ── Status ────────────────────────────────────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=AttemptStatus.choices,
        default=AttemptStatus.IN_PROGRESS,
        db_index=True,
    )

    # ── Proctoring aggregation ────────────────────────────────────────────
    tab_switch_count = models.PositiveIntegerField(default=0)
    copy_paste_count = models.PositiveIntegerField(default=0)
    fullscreen_exit_count = models.PositiveIntegerField(default=0)
    suspicious_activity_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00,
        help_text='Weighted suspicion score (0-100). '
                  'Computed from proctor events. >80 triggers review.',
    )
    is_flagged = models.BooleanField(
        default=False,
        help_text='Flagged for manual review due to suspicious activity.',
    )
    flag_reason = models.TextField(blank=True)

    # ── Security fingerprint ──────────────────────────────────────────────
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    browser_fingerprint = models.CharField(
        max_length=64, blank=True,
        help_text='SHA-256 of browser fingerprint data.',
    )

    class Meta:
        verbose_name = 'Assessment Attempt'
        verbose_name_plural = 'Assessment Attempts'
        ordering = ['-started_at']
        unique_together = ('assessment', 'user', 'attempt_number')
        indexes = [
            models.Index(
                fields=['assessment', 'user', '-started_at'],
                name='idx_attempt_assess_user',
            ),
            models.Index(
                fields=['user', 'status'],
                name='idx_attempt_user_status',
            ),
            models.Index(
                fields=['status', '-started_at'],
                name='idx_attempt_status_start',
            ),
            models.Index(
                fields=['is_flagged', 'status'],
                name='idx_attempt_flagged',
            ),
        ]

    def __str__(self):
        return f'{self.user.email} — {self.assessment.title} (#{self.attempt_number})'

    def save(self, *args, **kwargs):
        if not self.randomisation_seed:
            self.randomisation_seed = secrets.token_hex(16)
        super().save(*args, **kwargs)

    @property
    def duration_seconds(self) -> int | None:
        """Total time spent on this attempt."""
        if self.submitted_at:
            return int((self.submitted_at - self.started_at).total_seconds())
        return None

    @property
    def is_expired(self) -> bool:
        """Whether the attempt has exceeded the time limit."""
        if self.status != self.AttemptStatus.IN_PROGRESS:
            return False
        from datetime import timedelta
        deadline = self.started_at + timedelta(minutes=self.assessment.total_time_minutes)
        return timezone.now() > deadline


# ═══════════════════════════════════════════════════════════════════════════════
# 10. ATTEMPT ANSWER — Individual Question Responses
# ═══════════════════════════════════════════════════════════════════════════════

class AttemptAnswer(models.Model):
    """
    An individual answer within an assessment attempt.

    Stores the raw response, the computed score, and timing information.
    Supports all question types with a flexible answer format.
    """
    attempt = models.ForeignKey(
        AssessmentAttempt,
        on_delete=models.CASCADE,
        related_name='answers',
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='attempt_answers',
    )
    section_index = models.PositiveIntegerField(
        help_text='Which section this answer belongs to.',
    )

    # ── Answer data (polymorphic based on question type) ──────────────────
    selected_option_ids = models.JSONField(
        default=list, blank=True,
        help_text='For MCQ/multi-select: list of selected QuestionOption IDs.',
    )
    text_answer = models.TextField(
        blank=True,
        help_text='For short_answer/essay: the text response.',
    )
    boolean_answer = models.BooleanField(
        null=True, blank=True,
        help_text='For true/false questions.',
    )
    code_answer = models.TextField(
        blank=True,
        help_text='For code questions: the submitted code.',
    )
    code_language = models.CharField(
        max_length=30, blank=True,
        help_text='Language of the submitted code.',
    )
    ordering_answer = models.JSONField(
        default=list, blank=True,
        help_text='For ordering questions: ordered list of items.',
    )

    # ── Code execution results ────────────────────────────────────────────
    code_execution_results = models.JSONField(
        default=list, blank=True,
        help_text='Results from code test case execution: '
                  '[{"test_case_id": 0, "passed": true, "output": "...", '
                  '"execution_time_ms": 120}]',
    )

    # ── Scoring ───────────────────────────────────────────────────────────
    points_earned = models.DecimalField(
        max_digits=6, decimal_places=2, default=0.00,
    )
    max_points = models.DecimalField(
        max_digits=6, decimal_places=2,
        help_text='Maximum possible points for this question in this attempt.',
    )
    is_correct = models.BooleanField(
        null=True,
        help_text='True = fully correct, False = incorrect, NULL = partially correct or ungraded.',
    )
    is_partial = models.BooleanField(
        default=False,
        help_text='True if partial credit was awarded.',
    )
    used_hint = models.BooleanField(
        default=False,
        help_text='Whether the candidate used the hint.',
    )

    # ── Timing ────────────────────────────────────────────────────────────
    time_spent_seconds = models.PositiveIntegerField(
        default=0,
        help_text='Time spent on this individual question.',
    )
    answered_at = models.DateTimeField(null=True, blank=True)
    is_bookmarked = models.BooleanField(
        default=False,
        help_text='Candidate bookmarked this for review.',
    )
    is_skipped = models.BooleanField(
        default=False,
        help_text='Candidate explicitly skipped this question.',
    )

    # ── Grading metadata ──────────────────────────────────────────────────
    graded_by = models.CharField(
        max_length=20, blank=True,
        help_text='auto | manual | ai',
    )
    grader_notes = models.TextField(
        blank=True,
        help_text='Notes from manual/AI grading (for essay questions).',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Attempt Answer'
        verbose_name_plural = 'Attempt Answers'
        ordering = ['section_index', 'question__id']
        unique_together = ('attempt', 'question')
        indexes = [
            models.Index(
                fields=['attempt', 'section_index'],
                name='idx_answer_attempt_section',
            ),
            models.Index(
                fields=['question', 'is_correct'],
                name='idx_answer_q_correct',
            ),
        ]

    def __str__(self):
        mark = {True: '✓', False: '✗', None: '?'}
        return f'{mark.get(self.is_correct, "?")} Q:{self.question_id} ({self.points_earned}/{self.max_points})'


# ═══════════════════════════════════════════════════════════════════════════════
# 11. ASSESSMENT RESULT — Scored Outcome
# ═══════════════════════════════════════════════════════════════════════════════

class AssessmentResult(models.Model):
    """
    Final scored result for a completed assessment attempt.
    Contains per-section breakdowns, per-skill breakdowns,
    and pass/fail determination.
    """
    attempt = models.OneToOneField(
        AssessmentAttempt,
        on_delete=models.CASCADE,
        related_name='result',
    )
    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name='results',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='assessment_results',
    )

    # ── Scores ────────────────────────────────────────────────────────────
    total_points_earned = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    total_points_possible = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    percentage_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    passed = models.BooleanField(default=False)

    # ── Breakdowns ────────────────────────────────────────────────────────
    section_scores = models.JSONField(
        default=list, blank=True,
        help_text='Per-section scores: [{"section_id": 1, "title": "...", '
                  '"earned": 45.0, "possible": 50.0, "percentage": 90.0}]',
    )
    skill_scores = models.JSONField(
        default=list, blank=True,
        help_text='Per-skill scores: [{"skill_tag_id": 1, "skill_name": "Python", '
                  '"earned": 30.0, "possible": 35.0, "percentage": 85.7}]',
    )
    difficulty_breakdown = models.JSONField(
        default=dict, blank=True,
        help_text='Breakdown by difficulty level: '
                  '{"1": {"correct": 5, "total": 5}, "3": {"correct": 8, "total": 10}}',
    )

    # ── Statistics ────────────────────────────────────────────────────────
    questions_answered = models.PositiveIntegerField(default=0)
    questions_correct = models.PositiveIntegerField(default=0)
    questions_incorrect = models.PositiveIntegerField(default=0)
    questions_partial = models.PositiveIntegerField(default=0)
    questions_skipped = models.PositiveIntegerField(default=0)
    total_time_seconds = models.PositiveIntegerField(default=0)
    avg_time_per_question_seconds = models.DecimalField(
        max_digits=7, decimal_places=2, default=0.00,
    )

    # ── Percentile ranking ────────────────────────────────────────────────
    percentile_rank = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        help_text='Percentile rank among all attempts for this assessment.',
    )

    # ── Timestamps ────────────────────────────────────────────────────────
    graded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Assessment Result'
        verbose_name_plural = 'Assessment Results'
        ordering = ['-graded_at']
        indexes = [
            models.Index(
                fields=['assessment', 'user', '-percentage_score'],
                name='idx_result_assess_user_score',
            ),
            models.Index(
                fields=['user', 'passed'],
                name='idx_result_user_passed',
            ),
            models.Index(
                fields=['assessment', 'passed'],
                name='idx_result_assess_passed',
            ),
        ]

    def __str__(self):
        icon = '✅' if self.passed else '❌'
        return f'{icon} {self.user.email} — {self.assessment.title} ({self.percentage_score}%)'


# ═══════════════════════════════════════════════════════════════════════════════
# 12. SKILL BADGE — Verified Skill Credentials
# ═══════════════════════════════════════════════════════════════════════════════

class SkillBadge(models.Model):
    """
    Tamper-proof skill verification badge earned by passing an assessment.
    Verifiable via UUID + HMAC signature (identical to course certificates).

    Badges are:
        - Tied to a specific skill tag and assessment
        - Visible on the user's public profile
        - Shareable via verification URL
        - Revocable by admins
        - Time-limited (optional expiry for rapidly-evolving skills)
    """

    class BadgeLevel(models.TextChoices):
        FOUNDATIONAL = 'foundational', 'Foundational'
        INTERMEDIATE = 'intermediate', 'Intermediate'
        ADVANCED = 'advanced', 'Advanced'
        EXPERT = 'expert', 'Expert'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='skill_badges',
    )
    result = models.OneToOneField(
        AssessmentResult,
        on_delete=models.SET_NULL,
        null=True,
        related_name='badge',
        help_text='The assessment result that earned this badge.',
    )
    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.SET_NULL,
        null=True,
        related_name='badges_issued',
    )
    skill_tag = models.ForeignKey(
        QuestionTag,
        on_delete=models.SET_NULL,
        null=True,
        related_name='badges',
        help_text='The verified skill.',
    )

    # ── Credential data ──────────────────────────────────────────────────
    holder_name = models.CharField(max_length=255)
    holder_email = models.EmailField()
    skill_name = models.CharField(
        max_length=100,
        help_text='Denormalised skill name at time of issuance.',
    )
    assessment_title = models.CharField(
        max_length=300,
        help_text='Denormalised assessment title at time of issuance.',
    )
    level = models.CharField(
        max_length=20,
        choices=BadgeLevel.choices,
        default=BadgeLevel.FOUNDATIONAL,
    )
    score_percent = models.DecimalField(max_digits=5, decimal_places=2)
    issued_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text='Badge expiry date. NULL = never expires.',
    )

    # ── Verification ──────────────────────────────────────────────────────
    signature = models.CharField(
        max_length=64,
        editable=False,
        help_text='HMAC-SHA256 signature for tamper-proof verification.',
    )
    is_revoked = models.BooleanField(default=False)
    revoked_reason = models.TextField(blank=True)

    # ── Display ───────────────────────────────────────────────────────────
    is_public = models.BooleanField(
        default=True,
        help_text='Whether this badge is visible on the user\'s public profile.',
    )

    class Meta:
        verbose_name = 'Skill Badge'
        verbose_name_plural = 'Skill Badges'
        ordering = ['-issued_at']
        indexes = [
            models.Index(
                fields=['user', 'skill_tag', '-issued_at'],
                name='idx_badge_user_skill',
            ),
            models.Index(
                fields=['skill_tag', 'level'],
                name='idx_badge_skill_level',
            ),
        ]

    def __str__(self):
        icon = '🚫' if self.is_revoked else '🏅'
        return f'{icon} {self.holder_name} — {self.skill_name} ({self.get_level_display()})'

    def save(self, *args, **kwargs):
        if not self.signature:
            self.signature = self._generate_signature()
        super().save(*args, **kwargs)

    def _generate_signature(self) -> str:
        """Generate HMAC-SHA256 signature over the badge's canonical data."""
        payload = '|'.join([
            str(self.id),
            self.holder_email,
            self.skill_name,
            self.assessment_title,
            self.level,
            str(self.score_percent),
            str(self.issued_at or ''),
        ])
        return hmac.new(
            settings.SECRET_KEY.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()

    def verify_signature(self) -> bool:
        """Verify badge integrity."""
        return hmac.compare_digest(self.signature, self._generate_signature())

    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at

    @property
    def is_valid(self) -> bool:
        return not self.is_revoked and not self.is_expired and self.verify_signature()


# ═══════════════════════════════════════════════════════════════════════════════
# 13. PROCTOR EVENT — Anti-Cheating Event Log
# ═══════════════════════════════════════════════════════════════════════════════

class ProctorEvent(models.Model):
    """
    Event-sourced proctoring log. Every suspicious client-side event
    is recorded here with full metadata.

    Events are immutable (append-only). Aggregation into suspicious_activity_score
    happens on the AssessmentAttempt model.

    Types of events tracked:
        - TAB_SWITCH: Candidate left the assessment tab
        - COPY: Copy operation detected
        - PASTE: Paste operation detected (except in code editor)
        - FULLSCREEN_EXIT: Exited fullscreen mode
        - RIGHT_CLICK: Context menu invocation
        - DEVTOOLS_OPEN: Browser devtools opened
        - FOCUS_LOST: Window lost focus
        - FOCUS_GAINED: Window regained focus
        - WEBCAM_BLOCKED: Webcam access blocked during proctored exam
        - MULTIPLE_FACES: Multiple faces detected via webcam
        - NO_FACE: No face detected via webcam
        - IP_CHANGE: Client IP address changed mid-session
        - RAPID_ANSWERS: Suspiciously fast answer submission
        - IDLE_TIMEOUT: No activity for extended period
    """

    class EventType(models.TextChoices):
        TAB_SWITCH = 'tab_switch', 'Tab Switch'
        COPY = 'copy', 'Copy Detected'
        PASTE = 'paste', 'Paste Detected'
        FULLSCREEN_EXIT = 'fullscreen_exit', 'Fullscreen Exit'
        RIGHT_CLICK = 'right_click', 'Right Click'
        DEVTOOLS_OPEN = 'devtools_open', 'DevTools Opened'
        FOCUS_LOST = 'focus_lost', 'Window Focus Lost'
        FOCUS_GAINED = 'focus_gained', 'Window Focus Gained'
        WEBCAM_BLOCKED = 'webcam_blocked', 'Webcam Blocked'
        MULTIPLE_FACES = 'multiple_faces', 'Multiple Faces Detected'
        NO_FACE = 'no_face', 'No Face Detected'
        IP_CHANGE = 'ip_change', 'IP Address Changed'
        RAPID_ANSWERS = 'rapid_answers', 'Rapid Answer Submission'
        IDLE_TIMEOUT = 'idle_timeout', 'Extended Idle Period'

    class Severity(models.IntegerChoices):
        LOW = 1, 'Low'
        MEDIUM = 2, 'Medium'
        HIGH = 3, 'High'
        CRITICAL = 4, 'Critical'

    attempt = models.ForeignKey(
        AssessmentAttempt,
        on_delete=models.CASCADE,
        related_name='proctor_events',
    )
    event_type = models.CharField(
        max_length=30,
        choices=EventType.choices,
        db_index=True,
    )
    severity = models.PositiveIntegerField(
        choices=Severity.choices,
        default=Severity.MEDIUM,
    )
    timestamp = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )

    # ── Context ───────────────────────────────────────────────────────────
    metadata = models.JSONField(
        default=dict, blank=True,
        help_text='Event-specific context: duration of tab switch, '
                  'paste content length, IP addresses, etc.',
    )
    question_id = models.IntegerField(
        null=True, blank=True,
        help_text='Question being viewed when event occurred.',
    )
    section_index = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Section being taken when event occurred.',
    )
    client_timestamp = models.DateTimeField(
        null=True, blank=True,
        help_text='Timestamp reported by the client (may differ from server).',
    )

    class Meta:
        verbose_name = 'Proctor Event'
        verbose_name_plural = 'Proctor Events'
        ordering = ['timestamp']
        indexes = [
            models.Index(
                fields=['attempt', 'event_type', 'timestamp'],
                name='idx_proctor_attempt_type',
            ),
            models.Index(
                fields=['attempt', 'severity'],
                name='idx_proctor_severity',
            ),
        ]

    def __str__(self):
        return f'[{self.get_severity_display()}] {self.get_event_type_display()} @ {self.timestamp}'


# ═══════════════════════════════════════════════════════════════════════════════
# 14. QUESTION REPORT — User-Submitted Issue Reports
# ═══════════════════════════════════════════════════════════════════════════════

class QuestionReport(models.Model):
    """
    Allows candidates to report issues with questions (typos, wrong answers,
    ambiguous wording, etc.) during or after an assessment.
    """

    class ReportType(models.TextChoices):
        WRONG_ANSWER = 'wrong_answer', 'Correct answer is wrong'
        AMBIGUOUS = 'ambiguous', 'Question is ambiguous'
        TYPO = 'typo', 'Typo or formatting issue'
        MISSING_INFO = 'missing_info', 'Missing information'
        OFFENSIVE = 'offensive', 'Offensive or inappropriate'
        TECHNICAL = 'technical', 'Technical issue (code runner, etc.)'
        OTHER = 'other', 'Other'

    class ReportStatus(models.TextChoices):
        PENDING = 'pending', 'Pending Review'
        INVESTIGATING = 'investigating', 'Under Investigation'
        RESOLVED = 'resolved', 'Resolved'
        DISMISSED = 'dismissed', 'Dismissed'

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='reports',
    )
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='question_reports',
    )
    attempt = models.ForeignKey(
        AssessmentAttempt,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text='Attempt during which the report was submitted.',
    )
    report_type = models.CharField(
        max_length=20,
        choices=ReportType.choices,
    )
    description = models.TextField(
        max_length=2000,
        help_text='Detailed description of the issue.',
    )
    status = models.CharField(
        max_length=20,
        choices=ReportStatus.choices,
        default=ReportStatus.PENDING,
        db_index=True,
    )
    resolution_notes = models.TextField(blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_question_reports',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Question Report'
        verbose_name_plural = 'Question Reports'
        ordering = ['-created_at']
        indexes = [
            models.Index(
                fields=['question', 'status'],
                name='idx_qreport_q_status',
            ),
            models.Index(
                fields=['status', '-created_at'],
                name='idx_qreport_status_date',
            ),
        ]

    def __str__(self):
        return f'[{self.get_report_type_display()}] Q:{self.question_id} by {self.reported_by}'
