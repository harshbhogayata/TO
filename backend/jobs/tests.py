"""
jobs/tests.py
Tests for the Job Board API — listing, detail, apply, save, company CRUD.
"""
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import User, CompanyProfile, TalentProfile
from .models import JobPost, Application, SavedJob


class _JobTestMixin:
    """Shared setup for jobs tests."""

    def _setup_users_and_job(self):
        self.client = APIClient()

        # Company user + profile (verified, starter tier so CRUD tests can create jobs)
        self.company = User.objects.create_user(
            email='co@test.com', password='pass123',
            full_name='Test Corp', role=User.Role.COMPANY,
            is_verified=True,
        )
        CompanyProfile.objects.create(
            user=self.company, legal_name='Test Corp Inc',
            industry='Tech', headquarters='Remote',
            subscription_tier='starter',
        )

        # Talent user (verified + profile for tier checks)
        self.talent = User.objects.create_user(
            email='talent@test.com', password='pass123',
            full_name='Test Talent', role=User.Role.TALENT,
            is_verified=True,
        )
        TalentProfile.objects.create(
            user=self.talent, skills=['React', 'TypeScript'],
            subscription_tier='free',
        )

        # Open job
        self.job = JobPost.objects.create(
            company=self.company,
            title='Senior React Developer',
            description='Build great UIs.',
            job_type=JobPost.JobType.FULL_TIME,
            work_mode=JobPost.WorkMode.REMOTE,
            status=JobPost.Status.OPEN,
            experience_level=JobPost.ExperienceLevel.SENIOR,
            location='Remote',
            salary_min=100000, salary_max=150000,
            skills_required=['React', 'TypeScript'],
        )


class JobListingTestCase(_JobTestMixin, TestCase):
    """Tests for public job listing and detail endpoints."""

    def setUp(self):
        self._setup_users_and_job()

    def test_list_returns_open_jobs(self):
        resp = self.client.get(reverse('job_list'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data['results']), 1)

    def test_list_excludes_draft_jobs(self):
        draft = JobPost.objects.create(
            company=self.company, title='Draft Job',
            description='Not yet.', status=JobPost.Status.DRAFT,
        )
        resp = self.client.get(reverse('job_list'))
        ids = [j['id'] for j in resp.data['results']]
        self.assertNotIn(draft.id, ids)

    def test_filter_by_work_mode(self):
        resp = self.client.get(reverse('job_list'), {'work_mode': 'remote'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for job in resp.data['results']:
            self.assertEqual(job['work_mode'], 'remote')

    def test_search_by_title(self):
        resp = self.client.get(reverse('job_list'), {'search': 'React'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data['results']), 1)

    def test_detail_returns_job(self):
        resp = self.client.get(reverse('job_detail', args=[self.job.pk]))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['title'], 'Senior React Developer')

    def test_detail_increments_view_count(self):
        initial = self.job.views_count
        self.client.get(reverse('job_detail', args=[self.job.pk]))
        self.job.refresh_from_db()
        self.assertEqual(self.job.views_count, initial + 1)


class ApplicationTestCase(_JobTestMixin, TestCase):
    """Tests for job application endpoints."""

    def setUp(self):
        self._setup_users_and_job()

    def test_apply_as_talent(self):
        self.client.force_authenticate(user=self.talent)
        resp = self.client.post(
            reverse('job_apply', args=[self.job.pk]),
            {'cover_letter': 'I am perfect.'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Application.objects.filter(applicant=self.talent, job=self.job).exists())

    def test_apply_requires_auth(self):
        resp = self.client.post(reverse('job_apply', args=[self.job.pk]), {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cannot_apply_twice(self):
        self.client.force_authenticate(user=self.talent)
        self.client.post(
            reverse('job_apply', args=[self.job.pk]),
            {'cover_letter': 'First try.'}, format='json',
        )
        resp = self.client.post(
            reverse('job_apply', args=[self.job.pk]),
            {'cover_letter': 'Second try.'}, format='json',
        )
        self.assertIn(resp.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT])

    def test_company_cannot_apply(self):
        self.client.force_authenticate(user=self.company)
        resp = self.client.post(
            reverse('job_apply', args=[self.job.pk]),
            {'cover_letter': 'Not a talent.'}, format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_my_applications_returns_own(self):
        Application.objects.create(applicant=self.talent, job=self.job)
        self.client.force_authenticate(user=self.talent)
        resp = self.client.get(reverse('my_applications'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['results']), 1)

    def test_withdraw_application(self):
        app = Application.objects.create(applicant=self.talent, job=self.job)
        self.client.force_authenticate(user=self.talent)
        resp = self.client.delete(reverse('withdraw_application', args=[app.pk]))
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT])
        app.refresh_from_db()
        self.assertEqual(app.status, Application.Status.WITHDRAWN)


class SavedJobTestCase(_JobTestMixin, TestCase):
    """Tests for saved/bookmarked jobs."""

    def setUp(self):
        self._setup_users_and_job()

    def test_save_job(self):
        self.client.force_authenticate(user=self.talent)
        resp = self.client.post(reverse('saved_jobs'), {'job_id': self.job.pk}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(SavedJob.objects.filter(user=self.talent, job=self.job).exists())

    def test_list_saved_jobs(self):
        SavedJob.objects.create(user=self.talent, job=self.job)
        self.client.force_authenticate(user=self.talent)
        resp = self.client.get(reverse('saved_jobs'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_unsave_job(self):
        saved = SavedJob.objects.create(user=self.talent, job=self.job)
        self.client.force_authenticate(user=self.talent)
        resp = self.client.delete(reverse('unsave_job', args=[saved.pk]))
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(SavedJob.objects.filter(pk=saved.pk).exists())


class CompanyJobCRUDTestCase(_JobTestMixin, TestCase):
    """Tests for company job management CRUD."""

    def setUp(self):
        self._setup_users_and_job()

    def test_company_list_own_jobs(self):
        self.client.force_authenticate(user=self.company)
        resp = self.client.get(reverse('company_jobs'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['results']), 1)

    def test_company_create_job(self):
        self.client.force_authenticate(user=self.company)
        data = {
            'title': 'New Position',
            'description': 'A new role.',
            'job_type': 'full_time',
            'work_mode': 'remote',
            'experience_level': 'mid',
            'location': 'New York',
            'skills_required': ['Python', 'Django'],
        }
        resp = self.client.post(reverse('company_jobs'), data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(JobPost.objects.filter(title='New Position').exists())

    def test_company_update_job(self):
        self.client.force_authenticate(user=self.company)
        resp = self.client.patch(
            reverse('company_job_detail', args=[self.job.pk]),
            {'title': 'Updated Title'}, format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.job.refresh_from_db()
        self.assertEqual(self.job.title, 'Updated Title')

    def test_talent_cannot_create_job(self):
        self.client.force_authenticate(user=self.talent)
        resp = self.client.post(
            reverse('company_jobs'),
            {'title': 'Nope', 'description': 'Not allowed.'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_company_view_applications(self):
        Application.objects.create(applicant=self.talent, job=self.job)
        self.client.force_authenticate(user=self.company)
        resp = self.client.get(reverse('job_applications', args=[self.job.pk]))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['results']), 1)

    def test_update_application_status(self):
        app = Application.objects.create(applicant=self.talent, job=self.job)
        self.client.force_authenticate(user=self.company)
        resp = self.client.patch(
            reverse('update_application_status', args=[app.pk]),
            {'status': 'shortlisted'}, format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        app.refresh_from_db()
        self.assertEqual(app.status, Application.Status.SHORTLISTED)


class JobModelTestCase(TestCase):
    """Tests for JobPost model properties."""

    def setUp(self):
        self.company = User.objects.create_user(
            email='model_co@test.com', password='pass123',
            full_name='Model Corp', role=User.Role.COMPANY,
        )
        CompanyProfile.objects.create(user=self.company, legal_name='Model Corp')

    def test_salary_display_with_range(self):
        job = JobPost.objects.create(
            company=self.company, title='Test',
            description='d', salary_min=50000, salary_max=80000,
        )
        self.assertIn('50,000', job.salary_display)
        self.assertIn('80,000', job.salary_display)

    def test_salary_display_undisclosed(self):
        job = JobPost.objects.create(
            company=self.company, title='Test', description='d',
        )
        self.assertEqual(job.salary_display, 'Undisclosed')

    def test_application_count(self):
        job = JobPost.objects.create(
            company=self.company, title='Test', description='d',
        )
        self.assertEqual(job.application_count, 0)
        talent = User.objects.create_user(
            email='count_t@test.com', password='p', role=User.Role.TALENT,
        )
        Application.objects.create(applicant=talent, job=job)
        self.assertEqual(job.application_count, 1)
