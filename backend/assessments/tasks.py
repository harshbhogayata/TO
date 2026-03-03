"""
assessments/tasks.py
Celery tasks for the assessments app.

Handles async operations:
    - Code execution grading (Judge0 sandbox)
    - Attempt auto-submission on expiry
    - Result computation and badge issuance
    - Assessment statistics recomputation
    - Invitation expiry cleanup
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(
    name='assessments.grade_code_answer',
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    acks_late=True,
    queue='intelligence',
)
def grade_code_answer(self, answer_id: int):
    """
    Grade a code-type answer by running it against test cases in Judge0.

    Flow:
        1. Load the Answer + its Question (with test_cases JSON)
        2. Submit to Judge0 via CodeExecutionService
        3. Store execution results in Answer.execution_result
        4. Compute points earned based on test case pass ratio
        5. Mark answer as auto-graded
    """
    from assessments.models import Answer
    from assessments.code_runner import code_runner, Judge0Error

    try:
        answer = (
            Answer.objects
            .select_related('question', 'attempt', 'attempt__assessment')
            .get(pk=answer_id)
        )
    except Answer.DoesNotExist:
        logger.error('grade_code_answer: Answer %d not found', answer_id)
        return

    question = answer.question
    if question.question_type != 'code':
        logger.warning(
            'grade_code_answer: Answer %d is not a code question (type=%s)',
            answer_id, question.question_type,
        )
        return

    source_code = answer.text_answer or ''
    if not source_code.strip():
        answer.points_earned = 0
        answer.is_correct = False
        answer.grading_method = 'auto'
        answer.execution_result = {'error': 'Empty submission'}
        answer.save(update_fields=[
            'points_earned', 'is_correct', 'grading_method', 'execution_result',
        ])
        return

    test_cases = question.test_cases or []
    if not test_cases:
        logger.warning(
            'grade_code_answer: Question %d has no test cases',
            question.pk,
        )
        answer.grading_method = 'manual'
        answer.save(update_fields=['grading_method'])
        return

    language = (
        answer.code_language or
        question.code_language or
        'python'
    )

    try:
        result = code_runner.run_test_cases(
            source_code=source_code,
            language=language,
            test_cases=test_cases,
            time_limit_ms=question.time_limit_ms or 5000,
            memory_limit_mb=question.memory_limit_mb or 256,
        )
    except Judge0Error as exc:
        logger.error(
            'grade_code_answer: Judge0 error for answer %d: %s',
            answer_id, exc,
        )
        raise self.retry(exc=exc)
    except ValueError as exc:
        logger.error(
            'grade_code_answer: Invalid language for answer %d: %s',
            answer_id, exc,
        )
        answer.execution_result = {'error': str(exc)}
        answer.grading_method = 'manual'
        answer.save(update_fields=['execution_result', 'grading_method'])
        return

    # Store execution results
    answer.execution_result = {
        'passed': result.passed,
        'total_tests': result.total_tests,
        'passed_tests': result.passed_tests,
        'failed_tests': result.failed_tests,
        'score_percentage': result.score_percentage,
        'execution_time_s': result.execution_time_total_s,
        'peak_memory_kb': result.peak_memory_kb,
        'compilation_error': result.compilation_error,
        'test_results': [
            {
                'index': tr.test_case_index,
                'passed': tr.passed,
                'status': tr.status_description,
                'time_s': tr.time_seconds,
                'memory_kb': tr.memory_kb,
                'points': tr.points,
                'max_points': tr.max_points,
            }
            for tr in result.test_results
        ],
    }

    # Compute points: proportional to test case pass rate × question max points
    max_question_points = question.points or 1.0
    if result.max_points > 0:
        answer.points_earned = round(
            (result.total_points / result.max_points) * max_question_points, 2
        )
    else:
        answer.points_earned = max_question_points if result.passed else 0

    answer.is_correct = result.passed
    answer.grading_method = 'auto'
    answer.save(update_fields=[
        'points_earned', 'is_correct', 'grading_method', 'execution_result',
    ])

    logger.info(
        'grade_code_answer: Answer %d graded — %d/%d tests passed (%.1f%%)',
        answer_id, result.passed_tests, result.total_tests, result.score_percentage,
    )


@shared_task(
    name='assessments.auto_submit_expired_attempts',
    bind=True,
    max_retries=1,
    queue='default',
)
def auto_submit_expired_attempts(self):
    """
    Find in-progress attempts that have exceeded their time limit and
    auto-submit them. Runs periodically via Celery Beat.
    """
    from assessments.models import Attempt

    now = timezone.now()
    expired = Attempt.objects.filter(
        status='in_progress',
    ).select_related('assessment')

    submitted_count = 0
    for attempt in expired:
        time_limit = attempt.assessment.time_limit_minutes or 0
        if time_limit <= 0:
            continue
        deadline = attempt.started_at + timedelta(minutes=time_limit + 1)
        if now >= deadline:
            attempt.status = 'submitted'
            attempt.submitted_at = now
            attempt.save(update_fields=['status', 'submitted_at'])
            # Trigger grading
            compute_attempt_result.delay(attempt.pk)
            submitted_count += 1

    if submitted_count:
        logger.info(
            'auto_submit_expired_attempts: Submitted %d expired attempts',
            submitted_count,
        )


@shared_task(
    name='assessments.compute_attempt_result',
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
    queue='intelligence',
)
def compute_attempt_result(self, attempt_id: int):
    """
    Compute the final result for a submitted attempt.

    Aggregates answer scores across sections and skills, computes
    percentile ranking, and issues SkillBadge if threshold is met.
    """
    from assessments.models import (
        Attempt, Answer, AssessmentResult, SkillBadge,
        AssessmentSection, SectionQuestion,
    )

    try:
        attempt = (
            Attempt.objects
            .select_related('assessment', 'user')
            .get(pk=attempt_id)
        )
    except Attempt.DoesNotExist:
        logger.error('compute_attempt_result: Attempt %d not found', attempt_id)
        return

    if attempt.status not in ('submitted', 'in_progress'):
        logger.info(
            'compute_attempt_result: Attempt %d already graded (status=%s)',
            attempt_id, attempt.status,
        )
        return

    # Check if all code answers are graded
    ungraded_code = Answer.objects.filter(
        attempt=attempt,
        question__question_type='code',
        grading_method='',
    ).exists()

    if ungraded_code:
        logger.info(
            'compute_attempt_result: Attempt %d has ungraded code answers, retrying',
            attempt_id,
        )
        raise self.retry(countdown=15)

    answers = Answer.objects.filter(attempt=attempt).select_related('question')

    # ── Compute scores ────────────────────────────────────────────────
    total_points = 0.0
    max_points = 0.0
    section_breakdown = {}
    skill_breakdown = {}
    difficulty_breakdown = {}
    correct_count = 0

    for answer in answers:
        q = answer.question
        earned = float(answer.points_earned or 0)
        possible = float(q.points or 1)

        total_points += earned
        max_points += possible
        if answer.is_correct:
            correct_count += 1

        # Section breakdown
        section_id = str(answer.section_id) if hasattr(answer, 'section_id') and answer.section_id else 'default'
        if section_id not in section_breakdown:
            section_breakdown[section_id] = {'earned': 0, 'possible': 0, 'count': 0}
        section_breakdown[section_id]['earned'] += earned
        section_breakdown[section_id]['possible'] += possible
        section_breakdown[section_id]['count'] += 1

        # Skill breakdown (from question tags)
        for skill in (q.skills.all() if hasattr(q, 'skills') else []):
            sk = skill.name
            if sk not in skill_breakdown:
                skill_breakdown[sk] = {'earned': 0, 'possible': 0}
            skill_breakdown[sk]['earned'] += earned
            skill_breakdown[sk]['possible'] += possible

        # Difficulty breakdown
        diff = str(q.difficulty or 'unrated')
        if diff not in difficulty_breakdown:
            difficulty_breakdown[diff] = {'earned': 0, 'possible': 0}
        difficulty_breakdown[diff]['earned'] += earned
        difficulty_breakdown[diff]['possible'] += possible

    score_pct = round((total_points / max_points * 100) if max_points > 0 else 0, 2)

    # ── Percentile ranking ────────────────────────────────────────────
    previous_results = AssessmentResult.objects.filter(
        assessment=attempt.assessment,
    ).exclude(attempt=attempt)
    total_previous = previous_results.count()
    below_count = previous_results.filter(score_percentage__lt=score_pct).count()
    percentile = round((below_count / total_previous * 100) if total_previous > 0 else 50, 1)

    # ── Determine pass/fail ───────────────────────────────────────────
    passing_score = attempt.assessment.passing_score or 60
    passed = score_pct >= passing_score

    # ── Create or update result ───────────────────────────────────────
    with transaction.atomic():
        result, created = AssessmentResult.objects.update_or_create(
            attempt=attempt,
            defaults={
                'assessment': attempt.assessment,
                'user': attempt.user,
                'total_points': total_points,
                'max_points': max_points,
                'score_percentage': score_pct,
                'passed': passed,
                'percentile_rank': percentile,
                'section_breakdown': section_breakdown,
                'skill_breakdown': skill_breakdown,
                'difficulty_breakdown': difficulty_breakdown,
                'total_questions': answers.count(),
                'correct_answers': correct_count,
                'time_taken_seconds': (
                    (attempt.submitted_at - attempt.started_at).total_seconds()
                    if attempt.submitted_at and attempt.started_at else None
                ),
            },
        )

        attempt.status = 'graded'
        attempt.save(update_fields=['status'])

        # ── Issue badge if passed ─────────────────────────────────────
        if passed and attempt.assessment.assessment_type in ('skill_test', 'certification'):
            _issue_badge(attempt, result, score_pct)

    logger.info(
        'compute_attempt_result: Attempt %d scored %.1f%% (%s)',
        attempt_id, score_pct, 'PASS' if passed else 'FAIL',
    )


def _issue_badge(attempt, result, score_pct):
    """Issue a SkillBadge for a passing assessment result."""
    from assessments.models import SkillBadge

    # Determine badge level from score
    if score_pct >= 95:
        level = 'expert'
    elif score_pct >= 85:
        level = 'advanced'
    elif score_pct >= 75:
        level = 'intermediate'
    else:
        level = 'foundational'

    # Don't downgrade existing badges
    existing = SkillBadge.objects.filter(
        user=attempt.user,
        assessment=attempt.assessment,
    ).first()

    level_order = {'foundational': 0, 'intermediate': 1, 'advanced': 2, 'expert': 3}
    if existing and level_order.get(existing.level, 0) >= level_order.get(level, 0):
        return  # Keep higher badge

    badge_defaults = {
        'result': result,
        'level': level,
        'score_percentage': score_pct,
        'expires_at': timezone.now() + timedelta(days=365 * 2),
    }

    SkillBadge.objects.update_or_create(
        user=attempt.user,
        assessment=attempt.assessment,
        defaults=badge_defaults,
    )

    logger.info(
        'Badge issued: user=%d assessment=%d level=%s score=%.1f%%',
        attempt.user.pk, attempt.assessment.pk, level, score_pct,
    )


@shared_task(
    name='assessments.recompute_assessment_stats',
    queue='analytics',
)
def recompute_assessment_stats(assessment_id: int):
    """Recompute aggregate statistics for an assessment."""
    from assessments.models import Assessment, AssessmentResult

    try:
        assessment = Assessment.objects.get(pk=assessment_id)
    except Assessment.DoesNotExist:
        return

    results = AssessmentResult.objects.filter(assessment=assessment)
    total = results.count()
    if total == 0:
        return

    from django.db.models import Avg, Count, Q
    stats = results.aggregate(
        avg_score=Avg('score_percentage'),
        pass_count=Count('pk', filter=Q(passed=True)),
        avg_time=Avg('time_taken_seconds'),
    )

    assessment.attempt_count = total
    assessment.average_score = round(stats['avg_score'] or 0, 2)
    assessment.pass_rate = round((stats['pass_count'] / total) * 100, 2)
    assessment.average_completion_time = round(stats['avg_time'] or 0)
    assessment.save(update_fields=[
        'attempt_count', 'average_score', 'pass_rate', 'average_completion_time',
    ])


@shared_task(
    name='assessments.expire_invitations',
    queue='default',
)
def expire_invitations():
    """Mark expired invitations as expired."""
    from assessments.models import Invitation

    expired = Invitation.objects.filter(
        status='pending',
        expires_at__lt=timezone.now(),
    ).update(status='expired')

    if expired:
        logger.info('expire_invitations: Expired %d invitations', expired)


@shared_task(
    name='assessments.cleanup_abandoned_attempts',
    queue='default',
)
def cleanup_abandoned_attempts():
    """Mark attempts abandoned after 24h of inactivity."""
    from assessments.models import Attempt

    threshold = timezone.now() - timedelta(hours=24)
    abandoned = Attempt.objects.filter(
        status='in_progress',
        started_at__lt=threshold,
    ).update(status='abandoned')

    if abandoned:
        logger.info('cleanup_abandoned_attempts: Marked %d as abandoned', abandoned)
