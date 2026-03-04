"""
assessments/views.py
Phase 7 — Enterprise Assessment API Views

Endpoint Groups
───────────────
  Tags             — Hierarchical skill taxonomy
  Question Banks   — CRUD for question pools
  Questions        — CRUD with approval workflow
  Assessments      — Catalog, detail, company CRUD
  Attempts         — Start, answer, submit, review
  Results          — User and company result retrieval
  Invitations      — Company invite workflow
  Skill Badges     — List, verify, public badge wall
  Proctor Events   — Client-side anti-cheat event logging
  Question Reports — Report erroneous questions

Patterns:
  - Throttle classes on every endpoint
  - IsEmailVerified on write endpoints
  - Structured logger
  - select_related / prefetch_related on all querysets
  - Graceful exception handling
"""
import hashlib
import logging
import random
import secrets

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models as db_models
from django.db.models import Avg, Count, F, Prefetch, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from accounts.permissions import IsEmailVerified

from compliance.constants import AuditAction, AuditCategory
from compliance.decorators import audit_action

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
from .permissions import (
    CanViewAttemptResults,
    IsAssessmentOwnerOrAdmin,
    IsAttemptOwner,
    IsQuestionBankOwner,
)
from .serializers import (
    AssessmentAttemptDetailSerializer,
    AssessmentAttemptListSerializer,
    AssessmentDetailSerializer,
    AssessmentInvitationCreateSerializer,
    AssessmentInvitationSerializer,
    AssessmentListSerializer,
    AssessmentResultCompactSerializer,
    AssessmentResultSerializer,
    AssessmentSectionSerializer,
    AssessmentSectionWriteSerializer,
    AssessmentWriteSerializer,
    AttemptAnswerSerializer,
    ProctorEventCreateSerializer,
    ProctorEventSerializer,
    QuestionBankListSerializer,
    QuestionBankWriteSerializer,
    QuestionDetailSerializer,
    QuestionListSerializer,
    QuestionReportCreateSerializer,
    QuestionReportSerializer,
    QuestionTagSerializer,
    QuestionWriteSerializer,
    SkillBadgeSerializer,
    StartAttemptSerializer,
    SubmitAnswerSerializer,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# QUESTION TAGS
# ═══════════════════════════════════════════════════════════════════════════════

class QuestionTagListView(generics.ListAPIView):
    """GET /api/v1/assessments/tags/ — Browse skill taxonomy."""
    serializer_class = QuestionTagSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [UserRateThrottle]
    pagination_class = None

    def get_queryset(self):
        qs = QuestionTag.objects.filter(is_active=True)
        root_only = self.request.query_params.get('root_only', '').lower()
        if root_only in ('true', '1'):
            qs = qs.filter(parent__isnull=True)
        return qs.prefetch_related('children').order_by('name')


class QuestionTagDetailView(generics.RetrieveAPIView):
    """GET /api/v1/assessments/tags/<slug>/ — Tag detail with children."""
    serializer_class = QuestionTagSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [UserRateThrottle]
    lookup_field = 'slug'

    def get_queryset(self):
        return QuestionTag.objects.filter(is_active=True).prefetch_related('children')


# ═══════════════════════════════════════════════════════════════════════════════
# QUESTION BANKS
# ═══════════════════════════════════════════════════════════════════════════════

class QuestionBankListView(generics.ListAPIView):
    """GET /api/v1/assessments/question-banks/ — List accessible banks."""
    serializer_class = QuestionBankListSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def get_queryset(self):
        user = self.request.user
        qs = QuestionBank.objects.filter(is_active=True).select_related(
            'primary_tag', 'owner_company',
        )

        if user.is_staff:
            pass  # admin sees all
        elif hasattr(user, 'company_profile') and user.company_profile:
            qs = qs.filter(
                Q(visibility='public') | Q(owner_company=user.company_profile)
            )
        else:
            qs = qs.filter(visibility='public')

        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))

        tag = self.request.query_params.get('tag')
        if tag:
            qs = qs.filter(Q(primary_tag__slug=tag) | Q(tags__slug=tag)).distinct()

        ordering = self.request.query_params.get('ordering', '-created_at')
        if ordering in ('-created_at', 'name', '-question_count', '-avg_difficulty'):
            qs = qs.order_by(ordering)

        return qs


class QuestionBankCreateView(generics.CreateAPIView):
    """POST /api/v1/assessments/question-banks/ — Create a question bank."""
    serializer_class = QuestionBankWriteSerializer
    permission_classes = [permissions.IsAuthenticated, IsEmailVerified]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'assessment_write'

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
        logger.info('Question bank created by user %s: %s',
                     self.request.user.id, serializer.instance.name)


class QuestionBankDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PATCH/DELETE /api/v1/assessments/question-banks/<id>/
    Bank owners or admins only for write operations.
    """
    permission_classes = [permissions.IsAuthenticated, IsQuestionBankOwner]
    throttle_classes = [UserRateThrottle]
    lookup_field = 'pk'

    def get_serializer_class(self):
        if self.request.method in ('PATCH', 'PUT'):
            return QuestionBankWriteSerializer
        return QuestionBankListSerializer

    def get_queryset(self):
        return QuestionBank.objects.filter(is_active=True).select_related(
            'primary_tag', 'owner_company',
        )

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=['is_active'])
        logger.info('Question bank soft-deleted by user %s: %s',
                     self.request.user.id, instance.id)


# ═══════════════════════════════════════════════════════════════════════════════
# QUESTIONS
# ═══════════════════════════════════════════════════════════════════════════════

class QuestionListView(generics.ListAPIView):
    """
    GET /api/v1/assessments/question-banks/<bank_id>/questions/
    List questions in a bank. Filtered by type, difficulty, approval.
    """
    serializer_class = QuestionListSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def get_queryset(self):
        bank_id = self.kwargs['bank_id']
        qs = Question.objects.filter(
            bank_id=bank_id, is_active=True,
        ).select_related('bank').prefetch_related('tags')

        # Apply filters
        qtype = self.request.query_params.get('type')
        if qtype:
            qs = qs.filter(question_type=qtype)

        difficulty = self.request.query_params.get('difficulty')
        if difficulty:
            try:
                qs = qs.filter(difficulty=int(difficulty))
            except (ValueError, TypeError):
                pass

        approved = self.request.query_params.get('approved')
        if approved in ('true', '1'):
            qs = qs.filter(is_approved=True)
        elif approved in ('false', '0'):
            qs = qs.filter(is_approved=False)

        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(Q(title__icontains=search) | Q(explanation__icontains=search))

        ordering = self.request.query_params.get('ordering', '-created_at')
        if ordering in ('-created_at', 'difficulty', '-difficulty', '-times_used', 'title'):
            qs = qs.order_by(ordering)

        return qs


class QuestionCreateView(generics.CreateAPIView):
    """POST /api/v1/assessments/question-banks/<bank_id>/questions/"""
    serializer_class = QuestionWriteSerializer
    permission_classes = [permissions.IsAuthenticated, IsEmailVerified]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'assessment_write'

    def perform_create(self, serializer):
        bank = get_object_or_404(QuestionBank, pk=self.kwargs['bank_id'], is_active=True)
        serializer.save(bank=bank, created_by=self.request.user)
        bank.recalculate_stats()
        logger.info('Question created in bank %s by user %s',
                     bank.id, self.request.user.id)


class QuestionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET/PATCH/DELETE /api/v1/assessments/questions/<id>/"""
    permission_classes = [permissions.IsAuthenticated, IsQuestionBankOwner]
    throttle_classes = [UserRateThrottle]

    def get_serializer_class(self):
        if self.request.method in ('PATCH', 'PUT'):
            return QuestionWriteSerializer
        return QuestionDetailSerializer

    def get_queryset(self):
        return Question.objects.filter(is_active=True).select_related(
            'bank', 'bank__owner_company',
        ).prefetch_related('tags', 'options')

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=['is_active'])
        instance.bank.recalculate_stats()
        logger.info('Question soft-deleted: %s', instance.id)


class QuestionApproveView(APIView):
    """POST /api/v1/assessments/questions/<id>/approve/ — Admin/bank-owner approval."""
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def post(self, request, pk):
        question = get_object_or_404(Question, pk=pk, is_active=True)
        # Check permission
        if not request.user.is_staff:
            bank = question.bank
            if not (
                hasattr(request.user, 'company_profile') and
                bank.owner_company and
                request.user.company_profile == bank.owner_company
            ):
                return Response(
                    {'detail': 'You do not have permission to approve this question.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        question.is_approved = True
        question.save(update_fields=['is_approved', 'updated_at'])
        logger.info('Question %s approved by user %s', pk, request.user.id)
        return Response(QuestionDetailSerializer(question).data)


class QuestionBulkApproveView(APIView):
    """POST /api/v1/assessments/questions/bulk-approve/ — Bulk approval."""
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'assessment_write'

    def post(self, request):
        question_ids = request.data.get('question_ids', [])
        if not isinstance(question_ids, list) or len(question_ids) == 0:
            return Response(
                {'detail': 'Provide a list of question_ids.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        qs = Question.objects.filter(id__in=question_ids, is_active=True, is_approved=False)

        # Permission check: admin can approve all, company can approve own bank questions
        if not request.user.is_staff:
            if hasattr(request.user, 'company_profile') and request.user.company_profile:
                qs = qs.filter(bank__owner_company=request.user.company_profile)
            else:
                return Response(
                    {'detail': 'Only admins or bank owners can approve questions.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        count = qs.update(is_approved=True)
        logger.info('Bulk approved %d questions by user %s', count, request.user.id)
        return Response({'approved_count': count})


# ═══════════════════════════════════════════════════════════════════════════════
# ASSESSMENT CATALOG
# ═══════════════════════════════════════════════════════════════════════════════

class AssessmentListView(generics.ListAPIView):
    """GET /api/v1/assessments/ — Public assessment catalog."""
    serializer_class = AssessmentListSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [UserRateThrottle]

    def get_queryset(self):
        qs = Assessment.objects.filter(
            status=Assessment.Status.PUBLISHED,
        ).select_related('primary_skill', 'owner_company').annotate(
            pass_rate=db_models.Case(
                db_models.When(attempt_count__gt=0,
                               then=F('pass_count') * 100.0 / F('attempt_count')),
                default=0.0,
                output_field=db_models.FloatField(),
            ),
        )

        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(title__icontains=search) | Q(description__icontains=search)
                | Q(short_description__icontains=search)
            )

        skill = self.request.query_params.get('skill')
        if skill:
            qs = qs.filter(
                Q(primary_skill__slug=skill) | Q(skills_tested__slug=skill)
            ).distinct()

        difficulty = self.request.query_params.get('difficulty')
        if difficulty and difficulty in dict(Assessment.DifficultyLevel.choices):
            qs = qs.filter(difficulty_level=difficulty)

        atype = self.request.query_params.get('type')
        if atype:
            qs = qs.filter(assessment_type=atype)

        ordering = self.request.query_params.get('ordering', '-published_at')
        ordering_map = {
            'popular': '-attempt_count',
            'newest': '-published_at',
            'title': 'title',
            'pass_rate': '-pass_rate',
        }
        qs = qs.order_by(ordering_map.get(ordering, '-published_at'))

        return qs


class AssessmentDetailView(generics.RetrieveAPIView):
    """GET /api/v1/assessments/<id>/ — Full assessment detail."""
    serializer_class = AssessmentDetailSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [UserRateThrottle]

    def get_queryset(self):
        return Assessment.objects.filter(
            status=Assessment.Status.PUBLISHED,
        ).select_related('primary_skill', 'owner_company').prefetch_related(
            'skills_tested',
            Prefetch(
                'sections',
                queryset=AssessmentSection.objects.order_by('position').select_related(
                    'question_bank',
                ),
            ),
        ).annotate(
            pass_rate=db_models.Case(
                db_models.When(attempt_count__gt=0,
                               then=F('pass_count') * 100.0 / F('attempt_count')),
                default=0.0,
                output_field=db_models.FloatField(),
            ),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# COMPANY ASSESSMENT CRUD
# ═══════════════════════════════════════════════════════════════════════════════

class CompanyAssessmentListView(generics.ListCreateAPIView):
    """
    GET  /api/v1/assessments/company/ — Company's own assessments
    POST /api/v1/assessments/company/ — Create a new assessment
    """
    permission_classes = [permissions.IsAuthenticated, IsEmailVerified]
    throttle_classes = [UserRateThrottle]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return AssessmentWriteSerializer
        return AssessmentListSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Assessment.objects.all().select_related(
                'primary_skill', 'owner_company',
            ).order_by('-created_at')

        if hasattr(user, 'company_profile') and user.company_profile:
            return Assessment.objects.filter(
                owner_company=user.company_profile,
            ).select_related('primary_skill', 'owner_company').order_by('-created_at')

        return Assessment.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        company = getattr(user, 'company_profile', None)
        serializer.save(owner_company=company)
        logger.info('Assessment created by user %s: %s',
                     user.id, serializer.instance.title)


class CompanyAssessmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PATCH/DELETE /api/v1/assessments/company/<id>/
    """
    permission_classes = [permissions.IsAuthenticated, IsAssessmentOwnerOrAdmin]
    throttle_classes = [UserRateThrottle]

    def get_serializer_class(self):
        if self.request.method in ('PATCH', 'PUT'):
            return AssessmentWriteSerializer
        return AssessmentDetailSerializer

    def get_queryset(self):
        return Assessment.objects.select_related(
            'primary_skill', 'owner_company',
        ).prefetch_related('sections', 'skills_tested')


# ═══════════════════════════════════════════════════════════════════════════════
# ASSESSMENT SECTIONS
# ═══════════════════════════════════════════════════════════════════════════════

class AssessmentSectionListView(generics.ListCreateAPIView):
    """
    GET  /api/v1/assessments/company/<assessment_id>/sections/
    POST /api/v1/assessments/company/<assessment_id>/sections/
    """
    permission_classes = [permissions.IsAuthenticated, IsEmailVerified]
    throttle_classes = [UserRateThrottle]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return AssessmentSectionWriteSerializer
        return AssessmentSectionSerializer

    def get_queryset(self):
        return AssessmentSection.objects.filter(
            assessment_id=self.kwargs['assessment_id'],
        ).select_related('question_bank').order_by('position')

    def perform_create(self, serializer):
        assessment = get_object_or_404(Assessment, pk=self.kwargs['assessment_id'])
        serializer.save(assessment=assessment)


# ═══════════════════════════════════════════════════════════════════════════════
# ATTEMPTS
# ═══════════════════════════════════════════════════════════════════════════════

class StartAttemptView(APIView):
    """
    POST /api/v1/assessments/<assessment_id>/start/
    Start a new assessment attempt. Returns the attempt ID and first section's questions.
    """
    permission_classes = [permissions.IsAuthenticated, IsEmailVerified]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'assessment_start'

    def post(self, request, assessment_id):
        serializer = StartAttemptSerializer(
            data={'assessment_id': assessment_id},
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)

        assessment = Assessment.objects.prefetch_related(
            Prefetch(
                'sections',
                queryset=AssessmentSection.objects.order_by('position').prefetch_related(
                    Prefetch(
                        'question_links',
                        queryset=SectionQuestionLink.objects.select_related('question'),
                    ),
                ),
            ),
        ).get(pk=assessment_id)

        # Count previous attempts
        previous_count = AssessmentAttempt.objects.filter(
            assessment=assessment, user=request.user,
        ).exclude(status=AssessmentAttempt.AttemptStatus.IN_PROGRESS).count()

        # Generate randomisation seed
        seed = random.randint(100000, 999999)

        # Build question order
        rng = random.Random(seed)
        question_order = {}
        for section in assessment.sections.all():
            q_ids = list(
                section.question_links.values_list('question_id', flat=True)
            )
            # Random draw from bank if configured
            if section.question_bank and section.random_question_count:
                pool = list(
                    Question.objects.filter(
                        bank=section.question_bank,
                        is_active=True,
                        is_approved=True,
                    ).values_list('id', flat=True)
                )
                if section.min_difficulty:
                    pool_qs = Question.objects.filter(
                        id__in=pool, difficulty__gte=section.min_difficulty,
                    )
                    if section.max_difficulty:
                        pool_qs = pool_qs.filter(difficulty__lte=section.max_difficulty)
                    pool = list(pool_qs.values_list('id', flat=True))

                draw_count = min(section.random_question_count, len(pool))
                q_ids = rng.sample(pool, draw_count)
            elif assessment.shuffle_questions:
                rng.shuffle(q_ids)

            question_order[str(section.position)] = q_ids

        attempt = AssessmentAttempt.objects.create(
            assessment=assessment,
            user=request.user,
            attempt_number=previous_count + 1,
            randomisation_seed=seed,
            question_order=question_order,
            status=AssessmentAttempt.AttemptStatus.IN_PROGRESS,
            ip_address=request.META.get('REMOTE_ADDR', ''),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
        )

        # Increment assessment attempt count
        Assessment.objects.filter(pk=assessment.pk).update(
            attempt_count=F('attempt_count') + 1,
        )

        logger.info(
            'Attempt started: user=%s assessment=%s attempt=%s',
            request.user.id, assessment.id, attempt.id,
        )

        return Response(
            AssessmentAttemptDetailSerializer(attempt).data,
            status=status.HTTP_201_CREATED,
        )


class AttemptDetailView(generics.RetrieveAPIView):
    """GET /api/v1/assessments/attempts/<attempt_id>/"""
    serializer_class = AssessmentAttemptDetailSerializer
    permission_classes = [permissions.IsAuthenticated, IsAttemptOwner]
    throttle_classes = [UserRateThrottle]

    def get_queryset(self):
        return AssessmentAttempt.objects.select_related('assessment')


class SubmitAnswerView(APIView):
    """
    POST /api/v1/assessments/attempts/<attempt_id>/answer/
    Submit an answer for a single question within an active attempt.
    """
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'assessment_answer'

    def post(self, request, attempt_id):
        attempt = get_object_or_404(
            AssessmentAttempt.objects.select_related('assessment'),
            pk=attempt_id,
            user=request.user,
            status=AssessmentAttempt.AttemptStatus.IN_PROGRESS,
        )

        # Check if time expired
        if attempt.assessment.total_time_minutes:
            deadline = attempt.started_at + timedelta(
                minutes=attempt.assessment.total_time_minutes,
            )
            if timezone.now() > deadline:
                attempt.status = AssessmentAttempt.AttemptStatus.EXPIRED
                attempt.submitted_at = deadline
                attempt.save(update_fields=['status', 'submitted_at'])
                return Response(
                    {'detail': 'Time has expired for this attempt.'},
                    status=status.HTTP_409_CONFLICT,
                )

        serializer = SubmitAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        question_id = data['question_id']
        question = get_object_or_404(Question, pk=question_id, is_active=True)

        # Upsert answer
        answer, created = AttemptAnswer.objects.update_or_create(
            attempt=attempt,
            question=question,
            defaults={
                'section_index': data['section_index'],
                'selected_option_ids': data.get('selected_option_ids', []),
                'text_answer': data.get('text_answer', ''),
                'boolean_answer': data.get('boolean_answer'),
                'code_answer': data.get('code_answer', ''),
                'code_language': data.get('code_language', ''),
                'ordering_answer': data.get('ordering_answer', []),
                'used_hint': data.get('used_hint', False),
                'is_bookmarked': data.get('is_bookmarked', False),
                'time_spent_seconds': data.get('time_spent_seconds', 0),
                'answered_at': timezone.now(),
                'is_skipped': False,
            },
        )

        # Trigger async code grading if code question
        if question.question_type == Question.QuestionType.CODE and data.get('code_answer'):
            from .tasks import grade_code_answer
            grade_code_answer.delay(answer.id)

        return Response(
            AttemptAnswerSerializer(answer).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class FinalSubmitView(APIView):
    """
    POST /api/v1/assessments/attempts/<attempt_id>/submit/
    Final submission — locks the attempt and triggers grading.
    """
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'assessment_answer'

    @audit_action(
        action=AuditAction.CREATE,
        category='ASSESSMENT',
        description='Assessment submitted for grading',
        resource_type='assessments.AssessmentAttempt',
        get_resource_id=lambda req, res: req.parser_context['kwargs'].get('attempt_id', ''),
    )
    def post(self, request, attempt_id):
        attempt = get_object_or_404(
            AssessmentAttempt.objects.select_related('assessment'),
            pk=attempt_id,
            user=request.user,
            status=AssessmentAttempt.AttemptStatus.IN_PROGRESS,
        )

        attempt.status = AssessmentAttempt.AttemptStatus.SUBMITTED
        attempt.submitted_at = timezone.now()
        attempt.save(update_fields=['status', 'submitted_at'])

        # Trigger async grading
        from .tasks import compute_attempt_result
        compute_attempt_result.delay(str(attempt.id))

        logger.info(
            'Attempt submitted: user=%s attempt=%s',
            request.user.id, attempt.id,
        )

        return Response({
            'detail': 'Assessment submitted successfully. Results are being computed.',
            'attempt_id': str(attempt.id),
            'status': 'submitted',
        })


# ═══════════════════════════════════════════════════════════════════════════════
# RESULTS
# ═══════════════════════════════════════════════════════════════════════════════

class AttemptResultView(generics.RetrieveAPIView):
    """GET /api/v1/assessments/attempts/<attempt_id>/result/"""
    serializer_class = AssessmentResultSerializer
    permission_classes = [permissions.IsAuthenticated, CanViewAttemptResults]
    throttle_classes = [UserRateThrottle]

    def get_object(self):
        attempt = get_object_or_404(
            AssessmentAttempt,
            pk=self.kwargs['attempt_id'],
        )
        self.check_object_permissions(self.request, attempt)
        result = get_object_or_404(AssessmentResult, attempt=attempt)
        return result


class MyResultsView(generics.ListAPIView):
    """GET /api/v1/assessments/my-results/ — All results for current user."""
    serializer_class = AssessmentResultCompactSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def get_queryset(self):
        return (
            AssessmentResult.objects
            .filter(user=self.request.user)
            .select_related('assessment')
            .order_by('-graded_at')
        )


class CompanyResultsView(generics.ListAPIView):
    """
    GET /api/v1/assessments/company/results/
    Results for the company's assessments — filterable by assessment, candidate, date.
    """
    serializer_class = AssessmentResultCompactSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            qs = AssessmentResult.objects.all()
        elif hasattr(user, 'company_profile') and user.company_profile:
            qs = AssessmentResult.objects.filter(
                assessment__owner_company=user.company_profile,
            )
        else:
            return AssessmentResult.objects.none()

        qs = qs.select_related('assessment', 'user').order_by('-graded_at')

        assessment_id = self.request.query_params.get('assessment')
        if assessment_id:
            qs = qs.filter(assessment_id=assessment_id)

        return qs


class CompanyResultsExportView(APIView):
    """GET /api/v1/assessments/company/results/export/ — CSV export."""
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'export'

    def get(self, request):
        import csv
        from django.http import HttpResponse

        user = request.user
        if user.is_staff:
            qs = AssessmentResult.objects.all()
        elif hasattr(user, 'company_profile') and user.company_profile:
            qs = AssessmentResult.objects.filter(
                assessment__owner_company=user.company_profile,
            )
        else:
            return Response(
                {'detail': 'Permission denied.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        qs = qs.select_related('assessment', 'user').order_by('-graded_at')

        assessment_id = request.query_params.get('assessment')
        if assessment_id:
            qs = qs.filter(assessment_id=assessment_id)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="assessment_results.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Assessment', 'Candidate', 'Email', 'Score %', 'Passed',
            'Questions Answered', 'Questions Correct', 'Time (seconds)',
            'Percentile', 'Graded At',
        ])

        for r in qs[:10000]:
            writer.writerow([
                r.assessment.title,
                r.user.full_name if hasattr(r.user, 'full_name') else r.user.email,
                r.user.email,
                float(r.percentage_score),
                'Yes' if r.passed else 'No',
                r.questions_answered,
                r.questions_correct,
                r.total_time_seconds,
                r.percentile_rank or '',
                r.graded_at.isoformat() if r.graded_at else '',
            ])

        return response


# ═══════════════════════════════════════════════════════════════════════════════
# INVITATIONS
# ═══════════════════════════════════════════════════════════════════════════════

class MyInvitationsView(generics.ListAPIView):
    """GET /api/v1/assessments/invitations/ — Invitations for the current user."""
    serializer_class = AssessmentInvitationSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def get_queryset(self):
        return (
            AssessmentInvitation.objects
            .filter(
                Q(candidate=self.request.user) |
                Q(candidate_email=self.request.user.email),
            )
            .select_related('assessment', 'company', 'invited_by')
            .order_by('-created_at')
        )


class SendInvitationView(APIView):
    """POST /api/v1/assessments/invitations/send/ — Company sends invitation."""
    permission_classes = [permissions.IsAuthenticated, IsEmailVerified]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'assessment_invite'

    def post(self, request):
        serializer = AssessmentInvitationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        assessment = Assessment.objects.get(pk=data['assessment_id'])
        user = request.user
        company = getattr(user, 'company_profile', None)

        # Resolve candidate
        from accounts.models import CustomUser
        candidate = None
        try:
            candidate = CustomUser.objects.get(email=data['candidate_email'])
        except CustomUser.DoesNotExist:
            pass

        invitation = AssessmentInvitation.objects.create(
            assessment=assessment,
            company=company,
            invited_by=user,
            candidate=candidate,
            candidate_email=data['candidate_email'],
            candidate_name=data.get('candidate_name', ''),
            personal_message=data.get('personal_message', ''),
            job_post_id=data.get('job_post_id'),
            expires_at=timezone.now() + timedelta(days=data.get('expires_in_days', 7)),
        )

        logger.info(
            'Invitation sent: company=%s assessment=%s candidate=%s',
            company, assessment.id, data['candidate_email'],
        )

        return Response(
            AssessmentInvitationSerializer(invitation).data,
            status=status.HTTP_201_CREATED,
        )


class AcceptInvitationView(APIView):
    """POST /api/v1/assessments/invitations/<token>/accept/"""
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def post(self, request, token):
        invitation = get_object_or_404(
            AssessmentInvitation,
            token=token,
            status=AssessmentInvitation.InvitationStatus.PENDING,
        )

        if invitation.is_expired:
            invitation.status = AssessmentInvitation.InvitationStatus.EXPIRED
            invitation.save(update_fields=['status'])
            return Response(
                {'detail': 'This invitation has expired.'},
                status=status.HTTP_410_GONE,
            )

        invitation.candidate = request.user
        invitation.status = AssessmentInvitation.InvitationStatus.ACCEPTED
        invitation.save(update_fields=['candidate', 'status', 'updated_at'])

        logger.info(
            'Invitation accepted: user=%s invitation=%s',
            request.user.id, invitation.id,
        )

        return Response({
            'detail': 'Invitation accepted.',
            'assessment_id': invitation.assessment_id,
        })


class DeclineInvitationView(APIView):
    """POST /api/v1/assessments/invitations/<token>/decline/"""
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def post(self, request, token):
        invitation = get_object_or_404(
            AssessmentInvitation,
            token=token,
            status=AssessmentInvitation.InvitationStatus.PENDING,
        )

        invitation.status = AssessmentInvitation.InvitationStatus.DECLINED
        invitation.save(update_fields=['status', 'updated_at'])

        return Response({'detail': 'Invitation declined.'})


# ═══════════════════════════════════════════════════════════════════════════════
# SKILL BADGES
# ═══════════════════════════════════════════════════════════════════════════════

class MyBadgesView(generics.ListAPIView):
    """GET /api/v1/assessments/badges/ — User's skill badges."""
    serializer_class = SkillBadgeSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def get_queryset(self):
        return (
            SkillBadge.objects
            .filter(user=self.request.user, is_revoked=False)
            .order_by('-issued_at')
        )


class BadgeVerifyView(APIView):
    """GET /api/v1/assessments/badges/verify/<uuid>/ — Public badge verification."""
    permission_classes = [permissions.AllowAny]
    throttle_classes = [UserRateThrottle]

    def get(self, request, badge_id):
        try:
            badge = SkillBadge.objects.get(pk=badge_id)
        except SkillBadge.DoesNotExist:
            return Response(
                {'valid': False, 'detail': 'Badge not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if badge.is_revoked:
            return Response(
                {'valid': False, 'detail': 'This badge has been revoked.'},
            )

        is_valid = badge.verify_signature()
        data = SkillBadgeSerializer(badge, context={'request': request}).data
        data['valid'] = is_valid
        if badge.is_expired:
            data['detail'] = 'This badge has expired.'
            data['valid'] = False

        return Response(data)


# ═══════════════════════════════════════════════════════════════════════════════
# PROCTOR EVENTS
# ═══════════════════════════════════════════════════════════════════════════════

class ProctorEventCreateView(APIView):
    """POST /api/v1/assessments/attempts/<attempt_id>/proctor-event/"""
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'proctor_event'

    def post(self, request, attempt_id):
        attempt = get_object_or_404(
            AssessmentAttempt,
            pk=attempt_id,
            user=request.user,
            status=AssessmentAttempt.AttemptStatus.IN_PROGRESS,
        )

        serializer = ProctorEventCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        event = ProctorEvent.objects.create(
            attempt=attempt,
            event_type=data['event_type'],
            metadata=data.get('metadata', {}),
            question_id=data.get('question_id'),
            section_index=data.get('section_index'),
            client_timestamp=data.get('client_timestamp'),
        )

        # Update attempt counters
        if data['event_type'] == ProctorEvent.EventType.TAB_SWITCH:
            AssessmentAttempt.objects.filter(pk=attempt.pk).update(
                tab_switch_count=F('tab_switch_count') + 1,
            )
            attempt.refresh_from_db()
            if (
                attempt.assessment.max_tab_switches and
                attempt.tab_switch_count >= attempt.assessment.max_tab_switches
            ):
                attempt.is_flagged = True
                attempt.flag_reason = f'Exceeded max tab switches ({attempt.assessment.max_tab_switches})'
                attempt.save(update_fields=['is_flagged', 'flag_reason'])

        elif data['event_type'] == ProctorEvent.EventType.COPY_PASTE:
            AssessmentAttempt.objects.filter(pk=attempt.pk).update(
                copy_paste_count=F('copy_paste_count') + 1,
            )

        elif data['event_type'] == ProctorEvent.EventType.FULLSCREEN_EXIT:
            AssessmentAttempt.objects.filter(pk=attempt.pk).update(
                fullscreen_exit_count=F('fullscreen_exit_count') + 1,
            )

        return Response(
            ProctorEventSerializer(event).data,
            status=status.HTTP_201_CREATED,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# QUESTION REPORTS
# ═══════════════════════════════════════════════════════════════════════════════

class QuestionReportCreateView(generics.CreateAPIView):
    """POST /api/v1/assessments/questions/<id>/report/"""
    serializer_class = QuestionReportCreateSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'report'

    def perform_create(self, serializer):
        serializer.save(reported_by=self.request.user)
        logger.info(
            'Question reported: question=%s by user=%s',
            serializer.instance.question_id,
            self.request.user.id,
        )


class QuestionReportListView(generics.ListAPIView):
    """GET /api/v1/assessments/reports/ — Admin view of question reports."""
    serializer_class = QuestionReportSerializer
    permission_classes = [permissions.IsAdminUser]
    throttle_classes = [UserRateThrottle]

    def get_queryset(self):
        qs = QuestionReport.objects.select_related(
            'question', 'reported_by',
        ).order_by('-created_at')

        report_status = self.request.query_params.get('status')
        if report_status:
            qs = qs.filter(status=report_status)

        return qs
