from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify

from accounts.models import CompanyProfile, TalentProfile
from assessments.models import (
    Assessment,
    AssessmentAttempt,
    AssessmentInvitation,
    AssessmentResult,
    AssessmentSection,
    AttemptAnswer,
    Question,
    QuestionBank,
    QuestionOption,
    QuestionTag,
    SectionQuestionLink,
    SkillBadge,
)
from courses.models import (
    Certificate,
    Course,
    CourseCategory,
    CourseEnrollment,
    CourseInstructor,
    CourseModule,
    Lesson,
    LessonProgress,
)
from jobs.models import Application, JobPost
from payments.models import SponsoredJobCampaign, TalentPoolCandidate, TalentPoolPipeline


User = get_user_model()


class Command(BaseCommand):
    help = 'Seed local QA data for login, learning, assessments, and company growth workflows.'

    def handle(self, *args, **options):
        now = timezone.now()

        admin = self.ensure_user(
            email='admin@talentorbit.io',
            role='ADMIN',
            full_name='Platform Admin',
            password='admin123',
            is_staff=True,
            is_superuser=True,
        )
        company = self.ensure_user(
            email='techflow@example.com',
            role='COMPANY',
            full_name='TechFlow Admin',
            password='password123',
        )
        talent = self.ensure_user(
            email='alex.rivera@example.com',
            role='TALENT',
            full_name='Alex Rivera',
            password='password123',
        )

        company_profile, _ = CompanyProfile.objects.update_or_create(
            user=company,
            defaults={
                'legal_name': 'TechFlow',
                'industry': 'Software Engineering',
                'registration_number': 'qa-techflow-001',
                'mission_statement': 'Build reliable hiring systems without losing product depth.',
                'headquarters': 'San Francisco, CA',
                'website': 'https://techflow.example.com',
                'is_verified': True,
                'subscription_tier': 'professional',
            },
        )
        TalentProfile.objects.update_or_create(
            user=talent,
            defaults={
                'bio': 'Full-stack developer focused on React, Django, and workflow reliability.',
                'location': 'Austin, TX',
                'linkedin_url': 'https://linkedin.com/in/alex-rivera',
                'portfolio_url': 'https://alexrivera.dev',
                'skills': ['React', 'Django', 'Python', 'Testing'],
                'is_open_to_work': True,
                'subscription_tier': 'premium',
            },
        )

        job = self.ensure_job(company)
        application, _ = Application.objects.update_or_create(
            applicant=talent,
            job=job,
            defaults={
                'cover_letter': 'I build durable workflow fixes and test them at the contract layer.',
                'status': Application.Status.REVIEWING,
                'notes': 'Strong local QA discipline.',
            },
        )

        learning = self.ensure_learning(admin, talent, now)
        assessment = self.ensure_assessment(company, company_profile, talent, job, now)
        growth = self.ensure_growth(company, talent, job, application, now)

        self.stdout.write('Local QA data ready.')
        self.stdout.write('')
        self.stdout.write('Credentials:')
        self.stdout.write('- Admin:   admin@talentorbit.io / admin123')
        self.stdout.write('- Company: techflow@example.com / password123')
        self.stdout.write('- Talent:  alex.rivera@example.com / password123')
        self.stdout.write('')
        self.stdout.write('Suggested manual routes:')
        self.stdout.write('- /auth')
        self.stdout.write('- /my-learning')
        self.stdout.write(f"- {learning['continue_route']}")
        self.stdout.write(f"- {assessment['attempt_route']}")
        self.stdout.write(f"- {assessment['results_route']}")
        self.stdout.write('- /my-assessments')
        self.stdout.write('- /company/sponsored')
        self.stdout.write('- /company/crm')
        self.stdout.write('- /company/analytics')
        self.stdout.write('')
        self.stdout.write('Seed summary:')
        self.stdout.write(f"- Active course: {learning['active_course'].title}")
        self.stdout.write(f"- Completed course: {learning['completed_course'].title}")
        self.stdout.write(f"- Assessment: {assessment['assessment'].title}")
        self.stdout.write(f"- Sponsored campaign status: {growth['campaign'].status}")
        self.stdout.write(f"- CRM pipeline: {growth['pipeline'].name}")

    def ensure_user(self, email, role, full_name, password, is_staff=False, is_superuser=False):
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'role': role,
                'full_name': full_name,
                'is_verified': True,
                'is_staff': is_staff,
                'is_superuser': is_superuser,
            },
        )
        changed = False
        if user.role != role:
            user.role = role
            changed = True
        if user.full_name != full_name:
            user.full_name = full_name
            changed = True
        if not user.is_verified:
            user.is_verified = True
            changed = True
        if user.is_staff != is_staff:
            user.is_staff = is_staff
            changed = True
        if user.is_superuser != is_superuser:
            user.is_superuser = is_superuser
            changed = True
        if created:
            user.set_password(password)
            changed = True
        if changed:
            user.save()
        return user

    def ensure_job(self, company):
        job = JobPost.objects.filter(company=company, title='Platform Frontend Engineer').first()
        if job is None:
            job = JobPost(company=company, title='Platform Frontend Engineer')
        job.description = 'Own the workflow surfaces that connect growth, learning, and enterprise hiring.'
        job.requirements = 'React, Django, product thinking, and contract-level testing.'
        job.responsibilities = 'Ship reliable fixes, maintain QA data, and protect route contracts.'
        job.job_type = JobPost.JobType.FULL_TIME
        job.work_mode = JobPost.WorkMode.REMOTE
        job.status = JobPost.Status.OPEN
        job.experience_level = JobPost.ExperienceLevel.SENIOR
        job.location = 'Remote'
        job.salary_min = 140000
        job.salary_max = 180000
        job.salary_currency = 'USD'
        job.skills_required = ['React', 'Django', 'Testing', 'APIs']
        job.save()
        return job

    def ensure_learning(self, admin, talent, now):
        category, _ = CourseCategory.objects.update_or_create(
            slug='workflow-quality',
            defaults={
                'name': 'Workflow Quality',
                'description': 'Manual verification and reliability training.',
                'icon': 'shield-check',
                'position': 0,
                'is_active': True,
            },
        )
        instructor, _ = CourseInstructor.objects.update_or_create(
            slug='talentorbit-qa-instructor',
            defaults={
                'display_name': 'TalentOrbit QA Instructor',
                'bio': 'Guides enterprise workflow validation and release discipline.',
                'credentials': [{'title': 'Platform Reliability Lead', 'issuer': 'TalentOrbit', 'year': 2026}],
                'is_verified': True,
                'is_active': True,
                'user': admin,
            },
        )

        active_course, _ = Course.objects.update_or_create(
            slug='workflow-state-restoration',
            defaults={
                'title': 'Workflow State Restoration',
                'subtitle': 'Resume learning, assessment history, and route recovery.',
                'description': 'Learn how to restore user progress without breaking enterprise workflow state.',
                'short_description': 'Resume-state patterns for learning surfaces.',
                'category': category,
                'skills': ['React', 'State Restoration', 'Routing'],
                'tags': ['learning', 'resume-state', 'routes'],
                'level': Course.Level.INTERMEDIATE,
                'access_level': Course.AccessLevel.FREE,
                'status': Course.Status.PUBLISHED,
                'estimated_duration_minutes': 50,
                'created_by': admin,
            },
        )
        active_course.instructors.set([instructor])
        active_module, _ = CourseModule.objects.update_or_create(
            course=active_course,
            position=0,
            defaults={
                'title': 'Resume Progress Fundamentals',
                'description': 'How course and lesson state drive the continue-learning experience.',
                'is_preview': False,
            },
        )
        first_lesson, _ = Lesson.objects.update_or_create(
            module=active_module,
            position=0,
            defaults={
                'title': 'Restore the Last Lesson',
                'slug': 'restore-the-last-lesson',
                'content_type': Lesson.ContentType.TEXT,
                'text_content': 'The continue-learning card should land on the last lesson the learner touched.',
                'estimated_duration_minutes': 20,
                'is_preview': False,
                'is_mandatory': True,
            },
        )
        resume_lesson, _ = Lesson.objects.update_or_create(
            module=active_module,
            position=1,
            defaults={
                'title': 'Keep Partial Assessment State',
                'slug': 'keep-partial-assessment-state',
                'content_type': Lesson.ContentType.TEXT,
                'text_content': 'Assessment routes should preserve the active attempt and render pending results safely.',
                'estimated_duration_minutes': 30,
                'is_preview': False,
                'is_mandatory': True,
            },
        )
        active_enrollment, _ = CourseEnrollment.objects.update_or_create(
            user=talent,
            course=active_course,
            defaults={
                'status': CourseEnrollment.Status.ACTIVE,
                'last_lesson': resume_lesson,
                'last_accessed_at': now,
                'total_time_spent_seconds': 1800,
            },
        )
        LessonProgress.objects.update_or_create(
            enrollment=active_enrollment,
            lesson=first_lesson,
            defaults={
                'is_completed': True,
                'completed_at': now - timedelta(days=1),
                'time_spent_seconds': 900,
                'video_position_seconds': 0,
                'attempts': 1,
                'best_score': Decimal('100.00'),
            },
        )
        LessonProgress.objects.update_or_create(
            enrollment=active_enrollment,
            lesson=resume_lesson,
            defaults={
                'is_completed': False,
                'completed_at': None,
                'time_spent_seconds': 450,
                'video_position_seconds': 180,
                'attempts': 1,
                'best_score': Decimal('0.00'),
            },
        )
        active_enrollment.recalculate_progress()
        active_enrollment.last_lesson = resume_lesson
        active_enrollment.last_accessed_at = now
        active_enrollment.total_time_spent_seconds = 1350
        active_enrollment.save(update_fields=['last_lesson', 'last_accessed_at', 'total_time_spent_seconds', 'updated_at'])

        completed_course, _ = Course.objects.update_or_create(
            slug='assessment-results-review',
            defaults={
                'title': 'Assessment Results Review',
                'subtitle': 'Interpret scores and earned credentials.',
                'description': 'Walk through result summaries, skill breakdowns, and certificate issuance.',
                'short_description': 'Result interpretation for learners.',
                'category': category,
                'skills': ['Assessment Review', 'Verification'],
                'tags': ['results', 'badges', 'certificates'],
                'level': Course.Level.BEGINNER,
                'access_level': Course.AccessLevel.FREE,
                'status': Course.Status.PUBLISHED,
                'estimated_duration_minutes': 30,
                'created_by': admin,
            },
        )
        completed_course.instructors.set([instructor])
        completed_module, _ = CourseModule.objects.update_or_create(
            course=completed_course,
            position=0,
            defaults={
                'title': 'Review and Certify',
                'description': 'Complete a course and verify its certificate path.',
                'is_preview': False,
            },
        )
        completed_lesson, _ = Lesson.objects.update_or_create(
            module=completed_module,
            position=0,
            defaults={
                'title': 'Understand Your Result Summary',
                'slug': 'understand-your-result-summary',
                'content_type': Lesson.ContentType.TEXT,
                'text_content': 'Results should explain what was earned and what remains pending.',
                'estimated_duration_minutes': 30,
                'is_preview': False,
                'is_mandatory': True,
            },
        )
        completed_enrollment, _ = CourseEnrollment.objects.update_or_create(
            user=talent,
            course=completed_course,
            defaults={
                'status': CourseEnrollment.Status.ACTIVE,
                'last_lesson': completed_lesson,
                'last_accessed_at': now - timedelta(days=2),
                'total_time_spent_seconds': 3600,
            },
        )
        LessonProgress.objects.update_or_create(
            enrollment=completed_enrollment,
            lesson=completed_lesson,
            defaults={
                'is_completed': True,
                'completed_at': now - timedelta(days=2),
                'time_spent_seconds': 1800,
                'video_position_seconds': 0,
                'attempts': 1,
                'best_score': Decimal('100.00'),
            },
        )
        completed_enrollment.recalculate_progress()
        completed_enrollment.last_lesson = completed_lesson
        completed_enrollment.last_accessed_at = now - timedelta(days=2)
        completed_enrollment.total_time_spent_seconds = 3600
        completed_enrollment.save(update_fields=['last_lesson', 'last_accessed_at', 'total_time_spent_seconds', 'updated_at'])

        certificate = Certificate.objects.filter(enrollment=completed_enrollment).first()
        if certificate is None:
            certificate = Certificate(enrollment=completed_enrollment)
        certificate.holder_name = talent.full_name
        certificate.holder_email = talent.email
        certificate.course_title = completed_course.title
        certificate.course_version = str(completed_course.version)
        certificate.instructor_names = [instructor.display_name]
        certificate.completion_date = (now - timedelta(days=2)).date()
        certificate.total_hours = Decimal('1.0')
        certificate.skills_earned = completed_course.skills
        certificate.signature = ''
        certificate.is_revoked = False
        certificate.revoked_reason = ''
        certificate.save()

        return {
            'active_course': active_course,
            'completed_course': completed_course,
            'continue_route': f'/courses/{active_course.slug}/lessons/{resume_lesson.slug}',
        }

    def ensure_assessment(self, company, company_profile, talent, job, now):
        skill_tag, _ = QuestionTag.objects.update_or_create(
            slug='react-state-management',
            defaults={
                'name': 'React State Management',
                'description': 'Questions about local component state and workflow UI state.',
                'icon': 'component',
                'is_active': True,
            },
        )
        bank, _ = QuestionBank.objects.update_or_create(
            slug='workflow-ui-bank',
            defaults={
                'name': 'Workflow UI Bank',
                'description': 'Local QA assessment bank for learning and hiring flows.',
                'visibility': QuestionBank.Visibility.PUBLIC,
                'owner_company': company_profile,
                'primary_tag': skill_tag,
                'version': 1,
                'question_count': 1,
                'avg_difficulty': Decimal('2.00'),
                'is_active': True,
                'created_by': company,
            },
        )
        bank.tags.set([skill_tag])

        question, _ = Question.objects.update_or_create(
            bank=bank,
            title='Which React hook manages local component state?',
            defaults={
                'question_type': Question.QuestionType.MCQ,
                'explanation': 'useState is the standard hook for local state in a function component.',
                'hint': 'Think about the smallest hook that stores a value between renders.',
                'points': Decimal('10.00'),
                'negative_points': Decimal('0.00'),
                'partial_scoring': False,
                'difficulty': Question.DifficultyLevel.EASY,
                'is_active': True,
                'is_approved': True,
                'created_by': company,
            },
        )
        question.tags.set([skill_tag])
        correct_option, _ = QuestionOption.objects.update_or_create(
            question=question,
            position=0,
            defaults={'text': 'useState', 'is_correct': True, 'explanation': 'Stores local component state.'},
        )
        QuestionOption.objects.update_or_create(
            question=question,
            position=1,
            defaults={'text': 'useEffect', 'is_correct': False, 'explanation': 'Handles side effects, not local state storage.'},
        )
        QuestionOption.objects.update_or_create(
            question=question,
            position=2,
            defaults={'text': 'useMemo', 'is_correct': False, 'explanation': 'Caches derived values, not mutable state.'},
        )

        assessment, _ = Assessment.objects.update_or_create(
            slug='workflow-state-check',
            defaults={
                'title': 'Workflow State Check',
                'description': 'Verify that assessment attempts, results, and badges render correctly.',
                'short_description': 'A one-question local QA assessment.',
                'assessment_type': Assessment.AssessmentType.SKILL_TEST,
                'status': Assessment.Status.PUBLISHED,
                'access_level': Assessment.AccessLevel.PUBLIC,
                'primary_skill': skill_tag,
                'difficulty_level': Question.DifficultyLevel.EASY,
                'owner_company': company_profile,
                'created_by': company,
                'total_time_minutes': 20,
                'passing_score_percent': Decimal('70.00'),
                'max_attempts': 3,
                'cooldown_hours': 1,
                'show_results_immediately': True,
                'show_correct_answers': True,
                'allow_review': True,
                'shuffle_sections': False,
                'shuffle_questions': False,
                'shuffle_options': False,
                'proctoring_enabled': False,
                'block_copy_paste': False,
                'total_questions': 1,
                'total_points': Decimal('10.00'),
                'attempt_count': 2,
                'pass_count': 1,
                'average_score_percent': Decimal('100.00'),
                'average_completion_minutes': Decimal('6.00'),
            },
        )
        assessment.skills_tested.set([skill_tag])
        section, _ = AssessmentSection.objects.update_or_create(
            assessment=assessment,
            position=0,
            defaults={
                'title': 'React Basics',
                'description': 'Foundational UI state question.',
                'question_bank': bank,
                'random_question_count': 0,
                'min_difficulty': Question.DifficultyLevel.EASY,
                'max_difficulty': Question.DifficultyLevel.EASY,
                'question_types_filter': ['mcq'],
                'time_limit_minutes': 0,
                'is_timed_independently': False,
                'allow_navigation': True,
                'mandatory': True,
                'instructions': 'Answer the question and confirm the result screen renders correctly.',
                'total_questions': 1,
                'total_points': Decimal('10.00'),
            },
        )
        SectionQuestionLink.objects.update_or_create(
            section=section,
            question=question,
            defaults={'position': 0, 'points_override': Decimal('10.00')},
        )

        graded_attempt, _ = AssessmentAttempt.objects.update_or_create(
            assessment=assessment,
            user=talent,
            attempt_number=1,
            defaults={
                'submitted_at': now - timedelta(days=1, minutes=54),
                'time_remaining_seconds': 0,
                'current_section_index': 0,
                'section_timestamps': {'0': {'started': (now - timedelta(days=1, hours=1)).isoformat(), 'ended': (now - timedelta(days=1, minutes=54)).isoformat()}},
                'question_order': {'0': [question.id]},
                'status': AssessmentAttempt.AttemptStatus.GRADED,
                'tab_switch_count': 0,
                'copy_paste_count': 0,
                'fullscreen_exit_count': 0,
                'suspicious_activity_score': Decimal('0.00'),
                'is_flagged': False,
                'flag_reason': '',
                'ip_address': '127.0.0.1',
                'user_agent': 'Local QA Browser',
                'browser_fingerprint': 'local-qa-browser',
            },
        )
        AttemptAnswer.objects.update_or_create(
            attempt=graded_attempt,
            question=question,
            defaults={
                'section_index': 0,
                'selected_option_ids': [correct_option.id],
                'points_earned': Decimal('10.00'),
                'max_points': Decimal('10.00'),
                'is_correct': True,
                'is_partial': False,
                'used_hint': False,
                'time_spent_seconds': 75,
                'answered_at': now - timedelta(days=1, minutes=55),
                'is_bookmarked': False,
                'is_skipped': False,
                'graded_by': 'auto',
                'grader_notes': '',
            },
        )
        result, _ = AssessmentResult.objects.update_or_create(
            attempt=graded_attempt,
            defaults={
                'assessment': assessment,
                'user': talent,
                'total_points_earned': Decimal('10.00'),
                'total_points_possible': Decimal('10.00'),
                'percentage_score': Decimal('100.00'),
                'passed': True,
                'section_scores': [{'section_id': section.id, 'title': section.title, 'earned': 10.0, 'possible': 10.0, 'percentage': 100.0}],
                'skill_scores': [{'skill_tag_id': skill_tag.id, 'skill_name': skill_tag.name, 'earned': 10.0, 'possible': 10.0, 'percentage': 100.0}],
                'difficulty_breakdown': {'2': {'correct': 1, 'total': 1}},
                'questions_answered': 1,
                'questions_correct': 1,
                'questions_incorrect': 0,
                'questions_partial': 0,
                'questions_skipped': 0,
                'total_time_seconds': 360,
                'avg_time_per_question_seconds': Decimal('75.00'),
                'percentile_rank': Decimal('92.00'),
            },
        )
        badge = SkillBadge.objects.filter(result=result).first()
        if badge is None:
            badge = SkillBadge(result=result)
        badge.user = talent
        badge.assessment = assessment
        badge.skill_tag = skill_tag
        badge.holder_name = talent.full_name
        badge.holder_email = talent.email
        badge.skill_name = skill_tag.name
        badge.assessment_title = assessment.title
        badge.level = SkillBadge.BadgeLevel.FOUNDATIONAL
        badge.score_percent = Decimal('100.00')
        badge.expires_at = None
        badge.signature = ''
        badge.is_revoked = False
        badge.revoked_reason = ''
        badge.is_public = True
        badge.save()

        live_attempt, _ = AssessmentAttempt.objects.update_or_create(
            assessment=assessment,
            user=talent,
            attempt_number=2,
            defaults={
                'time_remaining_seconds': 840,
                'current_section_index': 0,
                'section_timestamps': {'0': {'started': (now - timedelta(minutes=6)).isoformat()}},
                'question_order': {'0': [question.id]},
                'status': AssessmentAttempt.AttemptStatus.IN_PROGRESS,
                'tab_switch_count': 0,
                'copy_paste_count': 0,
                'fullscreen_exit_count': 0,
                'suspicious_activity_score': Decimal('0.00'),
                'is_flagged': False,
                'flag_reason': '',
                'ip_address': '127.0.0.1',
                'user_agent': 'Local QA Browser',
                'browser_fingerprint': 'local-qa-browser-live',
            },
        )
        invitation, _ = AssessmentInvitation.objects.update_or_create(
            assessment=assessment,
            candidate_email=talent.email,
            defaults={
                'invited_by': company,
                'company': company_profile,
                'candidate': talent,
                'candidate_name': talent.full_name,
                'status': AssessmentInvitation.InvitationStatus.COMPLETED,
                'personal_message': 'Use this record to manually verify assessment result and history routes.',
                'job_post': job,
                'expires_at': now + timedelta(days=14),
                'attempt': graded_attempt,
            },
        )
        if invitation.attempt_id != graded_attempt.id:
            invitation.attempt = graded_attempt
            invitation.save(update_fields=['attempt', 'updated_at'])

        return {
            'assessment': assessment,
            'attempt_route': f'/assessments/{assessment.id}/attempt/{live_attempt.id}',
            'results_route': f'/assessments/{assessment.id}/results/{graded_attempt.id}',
        }

    def ensure_growth(self, company, talent, job, application, now):
        campaign, _ = SponsoredJobCampaign.objects.update_or_create(
            job=job,
            company=company,
            defaults={
                'bid_type': SponsoredJobCampaign.BidType.CPC,
                'bid_amount': Decimal('2.50'),
                'daily_budget': Decimal('25.00'),
                'total_budget': Decimal('150.00'),
                'amount_spent': Decimal('48.75'),
                'status': SponsoredJobCampaign.Status.ACTIVE,
                'target_locations': ['Remote', 'Austin, TX'],
                'target_skills': ['React', 'Django', 'Testing'],
                'target_experience_levels': ['mid', 'senior'],
                'impressions': 12400,
                'clicks': 318,
                'applications': 9,
                'starts_at': now - timedelta(days=3),
                'ends_at': now + timedelta(days=14),
                'stripe_payment_intent_id': 'pi_local_qa_campaign',
            },
        )
        stages = [
            {'id': 'sourced', 'label': 'Sourced', 'color': '#94A3B8'},
            {'id': 'screening', 'label': 'Screening', 'color': '#60A5FA'},
            {'id': 'interview', 'label': 'Interview', 'color': '#FBBF24'},
            {'id': 'offer', 'label': 'Offer', 'color': '#34D399'},
            {'id': 'hired', 'label': 'Hired', 'color': '#10B981'},
        ]
        pipeline, _ = TalentPoolPipeline.objects.update_or_create(
            company=company,
            name='Product Engineering Pipeline',
            defaults={
                'description': 'Local QA pipeline for CRM rendering and movement checks.',
                'stages': stages,
                'is_archived': False,
            },
        )
        TalentPoolCandidate.objects.update_or_create(
            pipeline=pipeline,
            user=talent,
            defaults={
                'external_name': '',
                'external_email': '',
                'external_phone': '',
                'external_resume_url': '',
                'external_linkedin_url': '',
                'stage_id': 'screening',
                'source': TalentPoolCandidate.Source.APPLICATION,
                'rating': 4,
                'notes': 'Strong workflow reasoning and API contract discipline.',
                'tags': ['frontend', 'qa', 'workflow'],
                'application': application,
                'added_by': company,
                'last_contacted_at': now - timedelta(days=1),
            },
        )
        return {'campaign': campaign, 'pipeline': pipeline}
