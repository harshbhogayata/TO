from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from courses.models import (
    Certificate,
    Course,
    CourseCategory,
    CourseEnrollment,
    CourseInstructor,
    CourseModule,
    Lesson,
)
from courses.tasks import generate_certificate


User = get_user_model()


class GenerateCertificateTaskTests(TestCase):
    def test_generate_certificate_creates_valid_certificate_once(self):
        learner = User.objects.create_user(
            email='learner@example.com',
            password='password123',
            full_name='Learner Example',
            role='TALENT',
            is_verified=True,
        )
        category = CourseCategory.objects.create(name='QA', slug='qa')
        instructor = CourseInstructor.objects.create(
            display_name='QA Instructor',
            slug='qa-instructor',
            is_verified=True,
        )
        course = Course.objects.create(
            title='Certificate Workflow',
            slug='certificate-workflow',
            description='Exercise course certificate generation.',
            category=category,
            status=Course.Status.PUBLISHED,
            access_level=Course.AccessLevel.FREE,
            version=3,
            skills=['Testing', 'Certificates'],
        )
        course.instructors.set([instructor])
        module = CourseModule.objects.create(course=course, title='Module 1', position=0)
        lesson = Lesson.objects.create(
            module=module,
            title='Finish the course',
            slug='finish-the-course',
            position=0,
            content_type=Lesson.ContentType.TEXT,
            text_content='Done.',
            estimated_duration_minutes=45,
        )
        enrollment = CourseEnrollment.objects.create(
            user=learner,
            course=course,
            status=CourseEnrollment.Status.COMPLETED,
            progress_percentage=Decimal('100.00'),
            lessons_completed=1,
            total_time_spent_seconds=5400,
            last_lesson=lesson,
            last_accessed_at=timezone.now(),
            completed_at=timezone.now(),
        )

        certificate_id = generate_certificate.run(enrollment.id)

        certificate = Certificate.objects.get(enrollment=enrollment)
        self.assertEqual(str(certificate.id), certificate_id)
        self.assertEqual(certificate.holder_email, learner.email)
        self.assertEqual(certificate.course_version, '3')
        self.assertEqual(certificate.instructor_names, ['QA Instructor'])
        self.assertEqual(certificate.skills_earned, ['Testing', 'Certificates'])
        self.assertTrue(certificate.verify_signature())

        second_run = generate_certificate.run(enrollment.id)

        self.assertEqual(second_run, None)
        self.assertEqual(Certificate.objects.filter(enrollment=enrollment).count(), 1)
