from decimal import Decimal

from django.conf import settings
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import CompanyProfile, TalentProfile, User
from assessments.models import (
    Assessment,
    AssessmentAttempt,
    AssessmentInvitation,
    AssessmentResult,
    QuestionTag,
    SkillBadge,
)
from courses.models import Course, CourseEnrollment, CourseModule, Lesson


_UNTHROTTLED_RATES = {
    'anon': '9999/minute',
    'user': '9999/minute',
    'assessment_invite': '9999/minute',
}

_TEST_REST_FRAMEWORK = {
    **settings.REST_FRAMEWORK,
    'DEFAULT_THROTTLE_RATES': {
        **settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {}),
        **_UNTHROTTLED_RATES,
    },
}


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    REST_FRAMEWORK=_TEST_REST_FRAMEWORK,
)
class CourseProgressWorkflowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='learner@example.com',
            password='StrongPass123!',
            full_name='Learner User',
            role=User.Role.TALENT,
            is_verified=True,
        )
        TalentProfile.objects.create(
            user=self.user,
            bio='',
            location='Remote',
            skills=['python'],
            is_open_to_work=True,
        )
        self.course = Course.objects.create(
            title='Python Path',
            slug='python-path',
            description='Learn Python fundamentals.',
            short_description='Python basics',
            status=Course.Status.PUBLISHED,
            access_level=Course.AccessLevel.FREE,
        )
        self.module = CourseModule.objects.create(
            course=self.course,
            title='Basics',
            position=0,
        )
        self.intro_lesson = Lesson.objects.create(
            module=self.module,
            title='Intro',
            slug='intro',
            position=0,
            content_type=Lesson.ContentType.TEXT,
            estimated_duration_minutes=15,
        )
        self.control_flow_lesson = Lesson.objects.create(
            module=self.module,
            title='Control Flow',
            slug='control-flow',
            position=1,
            content_type=Lesson.ContentType.TEXT,
            estimated_duration_minutes=25,
        )
        self.enrollment = CourseEnrollment.objects.create(
            user=self.user,
            course=self.course,
        )

    def test_marking_lesson_complete_updates_course_progress_overview(self):
        self.client.force_authenticate(self.user)

        response = self.client.post(
            '/api/v1/courses/python-path/lessons/intro/progress/',
            {
                'time_spent_seconds': 90,
                'mark_completed': True,
                'notes': 'Finished the intro lesson.',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.progress_percentage, Decimal('50.00'))
        self.assertEqual(self.enrollment.lessons_completed, 1)
        self.assertEqual(self.enrollment.total_time_spent_seconds, 90)

        overview = self.client.get('/api/v1/courses/python-path/progress/')

        self.assertEqual(overview.status_code, status.HTTP_200_OK)
        payload = overview.json()
        self.assertEqual(payload['overall_progress'], 50.0)
        self.assertEqual(payload['completed_lessons'], 1)
        self.assertEqual(payload['total_lessons'], 2)
        self.assertEqual(payload['modules'][0]['completed_lessons'], 1)
        self.assertEqual(payload['modules'][0]['total_lessons'], 2)
        self.assertEqual(payload['modules'][0]['percentage'], 50.0)
        self.assertEqual(payload['next_lesson']['lesson_slug'], 'control-flow')
        self.assertTrue(payload['lesson_statuses'][str(self.intro_lesson.id)]['completed'])
        self.assertEqual(
            payload['lesson_statuses'][str(self.control_flow_lesson.id)]['lesson_slug'],
            'control-flow',
        )

    def test_course_detail_loads_enrollment_and_annotated_counts(self):
        self.client.force_authenticate(self.user)

        detail_response = self.client.get('/api/v1/courses/python-path/')

        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        detail_payload = detail_response.json()
        self.assertEqual(detail_payload['slug'], 'python-path')
        self.assertTrue(detail_payload['is_enrolled'])
        self.assertEqual(detail_payload['enrollment']['status'], CourseEnrollment.Status.ACTIVE)
        self.assertEqual(len(detail_payload['modules']), 1)
        self.assertEqual(detail_payload['modules'][0]['lesson_count'], 2)
        self.assertEqual(detail_payload['modules'][0]['total_duration_minutes'], 40)

        list_response = self.client.get('/api/v1/courses/')

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        list_payload = list_response.json()
        list_items = list_payload.get('results', list_payload)
        self.assertEqual(list_items[0]['module_count'], 1)
        self.assertEqual(list_items[0]['lesson_count'], 2)


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    REST_FRAMEWORK=_TEST_REST_FRAMEWORK,
)
class AssessmentInvitationWorkflowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.company_user = User.objects.create_user(
            email='company@example.com',
            password='StrongPass123!',
            full_name='Company User',
            role=User.Role.COMPANY,
            is_verified=True,
        )
        self.company_profile = CompanyProfile.objects.create(
            user=self.company_user,
            legal_name='Acme Corp',
            subscription_tier='professional',
        )
        self.other_company_user = User.objects.create_user(
            email='other-company@example.com',
            password='StrongPass123!',
            full_name='Other Company User',
            role=User.Role.COMPANY,
            is_verified=True,
        )
        CompanyProfile.objects.create(
            user=self.other_company_user,
            legal_name='Other Corp',
            subscription_tier='professional',
        )
        self.talent_user = User.objects.create_user(
            email='talent@example.com',
            password='StrongPass123!',
            full_name='Talent User',
            role=User.Role.TALENT,
            is_verified=True,
        )
        TalentProfile.objects.create(
            user=self.talent_user,
            bio='',
            location='Remote',
            skills=['python'],
            is_open_to_work=True,
        )
        self.candidate_user = User.objects.create_user(
            email='candidate@example.com',
            password='StrongPass123!',
            full_name='Candidate User',
            role=User.Role.TALENT,
            is_verified=True,
        )
        TalentProfile.objects.create(
            user=self.candidate_user,
            bio='',
            location='Remote',
            skills=['django'],
            is_open_to_work=True,
        )
        self.assessment = Assessment.objects.create(
            title='Backend Screen',
            slug='backend-screen',
            description='Hiring screen for backend candidates.',
            short_description='Backend screening',
            assessment_type=Assessment.AssessmentType.HIRING,
            status=Assessment.Status.PUBLISHED,
            access_level=Assessment.AccessLevel.INVITE_ONLY,
            owner_company=self.company_profile,
            created_by=self.company_user,
            total_time_minutes=30,
        )

    def test_talent_user_cannot_send_assessment_invitation(self):
        self.client.force_authenticate(self.talent_user)

        response = self.client.post(
            '/api/v1/assessments/invitations/send/',
            {
                'assessment_id': self.assessment.id,
                'candidate_email': self.candidate_user.email,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_company_cannot_send_invitation_for_other_company_assessment(self):
        self.client.force_authenticate(self.other_company_user)

        response = self.client.post(
            '/api/v1/assessments/invitations/send/',
            {
                'assessment_id': self.assessment.id,
                'candidate_email': self.candidate_user.email,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(AssessmentInvitation.objects.exists())

    def test_company_can_send_invitation_and_link_existing_candidate(self):
        self.client.force_authenticate(self.company_user)

        response = self.client.post(
            '/api/v1/assessments/invitations/send/',
            {
                'assessment_id': self.assessment.id,
                'candidate_email': self.candidate_user.email,
                'candidate_name': 'Candidate User',
                'personal_message': 'Please complete this screen.',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        invitation = AssessmentInvitation.objects.get(assessment=self.assessment)
        self.assertEqual(invitation.company, self.company_profile)
        self.assertEqual(invitation.invited_by, self.company_user)
        self.assertEqual(invitation.candidate, self.candidate_user)
        self.assertEqual(invitation.candidate_email, self.candidate_user.email)


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    REST_FRAMEWORK=_TEST_REST_FRAMEWORK,
)
class AssessmentResultWorkflowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='learner-results@example.com',
            password='StrongPass123!',
            full_name='Learner Results',
            role=User.Role.TALENT,
            is_verified=True,
        )
        TalentProfile.objects.create(
            user=self.user,
            bio='',
            location='Remote',
            skills=['python'],
            is_open_to_work=True,
        )
        self.skill_tag = QuestionTag.objects.create(
            name='Python',
            slug='python',
            is_active=True,
        )
        self.assessment = Assessment.objects.create(
            title='Python Screen',
            slug='python-screen',
            description='Screening assessment for Python roles.',
            short_description='Python screening',
            assessment_type=Assessment.AssessmentType.SKILL_TEST,
            status=Assessment.Status.PUBLISHED,
            access_level=Assessment.AccessLevel.PUBLIC,
            primary_skill=self.skill_tag,
            created_by=self.user,
            total_time_minutes=30,
            show_results_immediately=True,
            allow_review=True,
        )
        self.attempt = AssessmentAttempt.objects.create(
            assessment=self.assessment,
            user=self.user,
            attempt_number=1,
            status=AssessmentAttempt.AttemptStatus.GRADED,
            question_order={'0': []},
            time_remaining_seconds=0,
        )
        self.result = AssessmentResult.objects.create(
            attempt=self.attempt,
            assessment=self.assessment,
            user=self.user,
            total_points_earned=Decimal('84.00'),
            total_points_possible=Decimal('100.00'),
            percentage_score=Decimal('84.00'),
            passed=True,
            skill_scores={'Python': 92},
            questions_answered=5,
            questions_correct=4,
            questions_incorrect=1,
            questions_partial=0,
            questions_skipped=0,
            total_time_seconds=620,
        )
        self.badge = SkillBadge.objects.create(
            user=self.user,
            result=self.result,
            assessment=self.assessment,
            skill_tag=self.skill_tag,
            holder_name=self.user.full_name,
            holder_email=self.user.email,
            skill_name=self.skill_tag.name,
            assessment_title=self.assessment.title,
            level=SkillBadge.BadgeLevel.INTERMEDIATE,
            score_percent=Decimal('84.00'),
        )

    def test_result_list_and_detail_expose_attempt_key_and_totals(self):
        self.client.force_authenticate(self.user)

        list_response = self.client.get('/api/v1/assessments/my-results/')

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        list_payload = list_response.json()
        list_items = list_payload.get('results', list_payload)
        self.assertEqual(list_items[0]['attempt_id'], str(self.attempt.id))
        self.assertEqual(list_items[0]['assessment'], self.assessment.id)

        detail_response = self.client.get(f'/api/v1/assessments/attempts/{self.attempt.id}/result/')

        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        detail_payload = detail_response.json()
        self.assertEqual(detail_payload['attempt_id'], str(self.attempt.id))
        self.assertEqual(detail_payload['total_questions'], 5)
        self.assertEqual(detail_payload['skill_breakdown'][0]['name'], 'Python')
        self.assertEqual(detail_payload['answers'], [])
        self.assertEqual(detail_payload['badge']['id'], str(self.badge.id))

    def test_result_detail_supports_list_based_skill_scores(self):
        self.result.skill_scores = [
            {
                'skill_tag_id': self.skill_tag.id,
                'skill_name': self.skill_tag.name,
                'earned': 42.0,
                'possible': 50.0,
                'percentage': 84.0,
            }
        ]
        self.result.save(update_fields=['skill_scores'])
        self.client.force_authenticate(self.user)

        detail_response = self.client.get(f'/api/v1/assessments/attempts/{self.attempt.id}/result/')

        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        detail_payload = detail_response.json()
        self.assertEqual(detail_payload['skill_breakdown'][0]['name'], 'Python')
        self.assertEqual(detail_payload['skill_breakdown'][0]['score'], 84.0)
        self.assertEqual(detail_payload['badge']['name'], 'Python')

