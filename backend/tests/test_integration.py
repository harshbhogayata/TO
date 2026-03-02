"""
tests/test_integration.py
End-to-end integration tests for the complete TalentOrbit hiring pipeline:
  Register → Verify Email → Create Job → Apply → Review → Hire

Also covers subscription tier enforcement across the full lifecycle.
"""
from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from rest_framework.test import APIClient
from rest_framework import status

from accounts.models import User, TalentProfile, CompanyProfile
from jobs.models import JobPost, Application, SavedJob


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    DEFAULT_THROTTLE_RATES={
        'anon': '1000/min', 'user': '1000/min',
        'auth': '1000/min', 'contact': '1000/min',
    },
)
class FullHiringPipelineTest(TestCase):
    """
    Integration test: walks through the complete lifecycle.
    1. Company registers + verifies email
    2. Company creates a job post
    3. Talent registers + verifies email
    4. Talent applies to the job
    5. Company reviews and shortlists
    6. Company extends offer
    7. Verify final states are consistent
    """

    def setUp(self):
        self.company_client = APIClient()
        self.talent_client = APIClient()

    # ── Step helpers ──────────────────────────────────────────────────────────

    def _register_and_verify_company(self):
        resp = self.company_client.post(reverse('register_company'), {
            'email': 'hiring@acme.com',
            'full_name': 'Acme HR',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
            'legal_name': 'Acme Corporation',
            'industry': 'Technology',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.company_user = User.objects.get(email='hiring@acme.com')

        # Verify email via token
        uid = urlsafe_base64_encode(force_bytes(self.company_user.pk))
        token = default_token_generator.make_token(self.company_user)
        verify_resp = self.company_client.post(reverse('verify_email'), {
            'uid': uid, 'token': token,
        }, format='json')
        self.assertEqual(verify_resp.status_code, status.HTTP_200_OK)
        self.company_user.refresh_from_db()
        self.assertTrue(self.company_user.is_verified)

        # Authenticate for subsequent requests
        self.company_client.force_authenticate(user=self.company_user)
        return self.company_user

    def _register_and_verify_talent(self, email='dev@talent.com'):
        resp = self.talent_client.post(reverse('register_talent'), {
            'email': email,
            'full_name': 'Jane Developer',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
            'bio': 'Full-stack engineer with 5 years experience',
            'skills': ['Python', 'Django', 'React', 'TypeScript'],
            'location': 'Remote',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        talent_user = User.objects.get(email=email)

        # Verify email
        uid = urlsafe_base64_encode(force_bytes(talent_user.pk))
        token = default_token_generator.make_token(talent_user)
        verify_resp = self.talent_client.post(reverse('verify_email'), {
            'uid': uid, 'token': token,
        }, format='json')
        self.assertEqual(verify_resp.status_code, status.HTTP_200_OK)
        talent_user.refresh_from_db()
        self.assertTrue(talent_user.is_verified)

        self.talent_client.force_authenticate(user=talent_user)
        return talent_user

    def _create_job_post(self):
        resp = self.company_client.post(reverse('company_jobs'), {
            'title': 'Senior Python Developer',
            'description': 'Build scalable APIs for our talent platform.',
            'requirements': '5+ years Python, Django REST experience',
            'responsibilities': 'Design and build API endpoints',
            'job_type': 'full_time',
            'work_mode': 'remote',
            'experience_level': 'senior',
            'location': 'Remote — Worldwide',
            'salary_min': 120000,
            'salary_max': 180000,
            'salary_currency': 'USD',
            'skills_required': ['Python', 'Django', 'PostgreSQL', 'REST'],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        return JobPost.objects.get(title='Senior Python Developer')

    # ── The test ──────────────────────────────────────────────────────────────

    def test_full_hiring_pipeline(self):
        # 1. Company registers + verifies
        company_user = self._register_and_verify_company()
        self.assertEqual(company_user.role, User.Role.COMPANY)
        self.assertTrue(hasattr(company_user, 'company_profile'))
        self.assertEqual(company_user.company_profile.legal_name, 'Acme Corporation')

        # 2. Company creates a job post
        job = self._create_job_post()
        self.assertEqual(job.status, JobPost.Status.OPEN)
        self.assertEqual(job.company, company_user)

        # 3. Talent registers + verifies
        talent_user = self._register_and_verify_talent()
        self.assertEqual(talent_user.role, User.Role.TALENT)
        self.assertIn('Python', talent_user.talent_profile.skills)

        # 4. Job appears in public listing
        listing_resp = self.talent_client.get(reverse('job_list'))
        self.assertEqual(listing_resp.status_code, status.HTTP_200_OK)
        job_ids = [j['id'] for j in listing_resp.data['results']]
        self.assertIn(job.pk, job_ids)

        # 5. Talent applies to the job
        apply_resp = self.talent_client.post(
            reverse('job_apply', args=[job.pk]),
            {'cover_letter': 'I have 6 years of Python/Django experience and would love to join Acme.'},
            format='json',
        )
        self.assertEqual(apply_resp.status_code, status.HTTP_201_CREATED)
        application = Application.objects.get(applicant=talent_user, job=job)
        self.assertEqual(application.status, Application.Status.PENDING)

        # 6. Talent sees application in their list
        my_apps_resp = self.talent_client.get(reverse('my_applications'))
        self.assertEqual(my_apps_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(my_apps_resp.data['results']), 1)
        self.assertEqual(my_apps_resp.data['results'][0]['status'], 'pending')

        # 7. Company sees the applicant
        apps_resp = self.company_client.get(reverse('job_applications', args=[job.pk]))
        self.assertEqual(apps_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(apps_resp.data['results']), 1)
        self.assertEqual(apps_resp.data['results'][0]['applicant_email'], 'dev@talent.com')

        # 8. Company shortlists the applicant
        shortlist_resp = self.company_client.patch(
            reverse('update_application_status', args=[application.pk]),
            {'status': 'shortlisted'},
            format='json',
        )
        self.assertEqual(shortlist_resp.status_code, status.HTTP_200_OK)
        application.refresh_from_db()
        self.assertEqual(application.status, Application.Status.SHORTLISTED)

        # 9. Company moves to interviewing
        interview_resp = self.company_client.patch(
            reverse('update_application_status', args=[application.pk]),
            {'status': 'interviewing'},
            format='json',
        )
        self.assertEqual(interview_resp.status_code, status.HTTP_200_OK)
        application.refresh_from_db()
        self.assertEqual(application.status, Application.Status.INTERVIEWING)

        # 10. Company extends offer
        offer_resp = self.company_client.patch(
            reverse('update_application_status', args=[application.pk]),
            {'status': 'offered', 'notes': 'Offer: $150k/yr + equity'},
            format='json',
        )
        self.assertEqual(offer_resp.status_code, status.HTTP_200_OK)
        application.refresh_from_db()
        self.assertEqual(application.status, Application.Status.OFFERED)
        self.assertIn('150k', application.notes)

        # 11. Verify final state consistency
        job.refresh_from_db()
        self.assertEqual(job.applications.count(), 1)
        self.assertEqual(Application.objects.filter(job=job, status='offered').count(), 1)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    DEFAULT_THROTTLE_RATES={
        'anon': '1000/min', 'user': '1000/min',
        'auth': '1000/min', 'contact': '1000/min',
    },
)
class TierEnforcementIntegrationTest(TestCase):
    """
    Integration tests verifying subscription tier limits are enforced
    across the application, job posting, and saved job flows.
    """

    def setUp(self):
        self.client = APIClient()

        # Create and verify a free-tier talent
        self.talent = User.objects.create_user(
            email='free_talent@test.com', password='TestPass123!',
            full_name='Free Talent', role=User.Role.TALENT,
            is_verified=True,
        )
        TalentProfile.objects.create(
            user=self.talent, bio='Testing', skills=['Python'],
            subscription_tier='free',
        )

        # Create and verify a free-tier company
        self.company = User.objects.create_user(
            email='free_company@test.com', password='TestPass123!',
            full_name='Free Corp', role=User.Role.COMPANY,
            is_verified=True,
        )
        CompanyProfile.objects.create(
            user=self.company, legal_name='Free Corp Inc',
            subscription_tier='free',
        )

        # Create a second company for additional jobs
        self.company2 = User.objects.create_user(
            email='company2@test.com', password='TestPass123!',
            full_name='Other Corp', role=User.Role.COMPANY,
            is_verified=True,
        )
        CompanyProfile.objects.create(
            user=self.company2, legal_name='Other Corp Inc',
            subscription_tier='professional',
        )

    def _create_open_job(self, company, title='Test Job'):
        return JobPost.objects.create(
            company=company, title=title,
            description='A test job posting.',
            job_type=JobPost.JobType.FULL_TIME,
            work_mode=JobPost.WorkMode.REMOTE,
            status=JobPost.Status.OPEN,
            skills_required=['Python'],
        )

    # ── Talent Application Limits ─────────────────────────────────────────────

    def test_free_talent_limited_to_3_applications_per_month(self):
        """Free talent can apply to 3 jobs, 4th is blocked."""
        self.client.force_authenticate(user=self.talent)

        # Create 4 jobs
        jobs = [self._create_open_job(self.company2, f'Job {i}') for i in range(4)]

        # First 3 applications should succeed
        for i in range(3):
            resp = self.client.post(
                reverse('job_apply', args=[jobs[i].pk]),
                {'cover_letter': f'Application {i+1}'},
                format='json',
            )
            self.assertEqual(resp.status_code, status.HTTP_201_CREATED, f'Application {i+1} should succeed')

        # 4th application should be blocked
        resp = self.client.post(
            reverse('job_apply', args=[jobs[3].pk]),
            {'cover_letter': 'This should fail'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(resp.data.get('upgrade_required'))

    def test_premium_talent_unlimited_applications(self):
        """Premium talent has no application limit."""
        self.talent.talent_profile.subscription_tier = 'premium'
        self.talent.talent_profile.save()
        self.client.force_authenticate(user=self.talent)

        # Create 5 jobs and apply to all
        jobs = [self._create_open_job(self.company2, f'Premium Job {i}') for i in range(5)]
        for i in range(5):
            resp = self.client.post(
                reverse('job_apply', args=[jobs[i].pk]),
                {'cover_letter': f'Premium application {i+1}'},
                format='json',
            )
            self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    # ── Talent Saved Job Limits ───────────────────────────────────────────────

    def test_free_talent_limited_saved_jobs(self):
        """Free talent can save up to 10 jobs."""
        self.client.force_authenticate(user=self.talent)

        # Create 11 jobs
        jobs = [self._create_open_job(self.company2, f'Saved Job {i}') for i in range(11)]

        # Save first 10
        for i in range(10):
            resp = self.client.post(
                reverse('saved_jobs'),
                {'job_id': jobs[i].pk},
                format='json',
            )
            self.assertEqual(resp.status_code, status.HTTP_201_CREATED, f'Save {i+1} should succeed')

        # 11th save should be blocked
        resp = self.client.post(
            reverse('saved_jobs'),
            {'job_id': jobs[10].pk},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(resp.data.get('upgrade_required'))

    # ── Company Job Post Limits ───────────────────────────────────────────────

    def test_free_company_limited_to_1_active_job_post(self):
        """Free company can create 1 active job, 2nd is blocked."""
        self.client.force_authenticate(user=self.company)

        # First job post should succeed
        resp = self.client.post(reverse('company_jobs'), {
            'title': 'First Job',
            'description': 'Our first posting.',
            'job_type': 'full_time',
            'work_mode': 'remote',
            'experience_level': 'mid',
            'skills_required': ['Python'],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        # Second job post should be blocked
        resp = self.client.post(reverse('company_jobs'), {
            'title': 'Second Job',
            'description': 'Too many for free tier.',
            'job_type': 'full_time',
            'work_mode': 'remote',
            'experience_level': 'mid',
            'skills_required': ['React'],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(resp.data.get('upgrade_required'))

    def test_starter_company_limited_to_5_active_job_posts(self):
        """Starter company can create 5 active jobs."""
        self.company.company_profile.subscription_tier = 'starter'
        self.company.company_profile.save()
        self.client.force_authenticate(user=self.company)

        for i in range(5):
            resp = self.client.post(reverse('company_jobs'), {
                'title': f'Starter Job {i+1}',
                'description': f'Job posting {i+1}.',
                'job_type': 'full_time',
                'work_mode': 'remote',
                'experience_level': 'mid',
                'skills_required': ['Python'],
            }, format='json')
            self.assertEqual(resp.status_code, status.HTTP_201_CREATED, f'Job {i+1} should succeed')

        # 6th should be blocked
        resp = self.client.post(reverse('company_jobs'), {
            'title': 'One Too Many',
            'description': 'Over the limit.',
            'job_type': 'full_time',
            'work_mode': 'remote',
            'experience_level': 'mid',
            'skills_required': ['Python'],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_professional_company_unlimited_job_posts(self):
        """Professional tier has no job post limit."""
        self.client.force_authenticate(user=self.company2)  # professional tier

        for i in range(7):
            resp = self.client.post(reverse('company_jobs'), {
                'title': f'Pro Job {i+1}',
                'description': 'Unlimited posting.',
                'job_type': 'full_time',
                'work_mode': 'remote',
                'experience_level': 'mid',
                'skills_required': ['Python'],
            }, format='json')
            self.assertEqual(resp.status_code, status.HTTP_201_CREATED)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    DEFAULT_THROTTLE_RATES={
        'anon': '1000/min', 'user': '1000/min',
        'auth': '1000/min', 'contact': '1000/min',
    },
)
class RoleIsolationIntegrationTest(TestCase):
    """
    Verify that role-based access control is enforced end-to-end:
    - Talent cannot create job posts
    - Company cannot apply to jobs
    - Unverified users cannot apply/post
    - Unauthenticated users get 401
    """

    def setUp(self):
        self.client = APIClient()

        self.talent = User.objects.create_user(
            email='talent@role.com', password='TestPass123!',
            full_name='Talent User', role=User.Role.TALENT,
            is_verified=True,
        )
        TalentProfile.objects.create(user=self.talent, skills=['Python'])

        self.company = User.objects.create_user(
            email='company@role.com', password='TestPass123!',
            full_name='Company Admin', role=User.Role.COMPANY,
            is_verified=True,
        )
        CompanyProfile.objects.create(
            user=self.company, legal_name='Role Test Corp',
        )

        self.job = JobPost.objects.create(
            company=self.company,
            title='Role Test Job',
            description='Testing role isolation.',
            status=JobPost.Status.OPEN,
            skills_required=['Python'],
        )

    def test_talent_cannot_create_job(self):
        self.client.force_authenticate(user=self.talent)
        resp = self.client.post(reverse('company_jobs'), {
            'title': 'Nope',
            'description': 'Should fail.',
            'job_type': 'full_time',
            'work_mode': 'remote',
            'experience_level': 'mid',
            'skills_required': ['Python'],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_company_cannot_apply_to_job(self):
        self.client.force_authenticate(user=self.company)
        resp = self.client.post(
            reverse('job_apply', args=[self.job.pk]),
            {'cover_letter': 'Should fail.'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unverified_talent_cannot_apply(self):
        unverified = User.objects.create_user(
            email='unverified@test.com', password='TestPass123!',
            full_name='Unverified', role=User.Role.TALENT,
            is_verified=False,
        )
        TalentProfile.objects.create(user=unverified, skills=[])
        self.client.force_authenticate(user=unverified)
        resp = self.client.post(
            reverse('job_apply', args=[self.job.pk]),
            {'cover_letter': 'Unverified attempt'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_apply(self):
        resp = self.client.post(
            reverse('job_apply', args=[self.job.pk]),
            {'cover_letter': 'No auth'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_can_browse_jobs(self):
        resp = self.client.get(reverse('job_list'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_unauthenticated_can_view_job_detail(self):
        resp = self.client.get(reverse('job_detail', args=[self.job.pk]))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_talent_cannot_update_application_status(self):
        """Only the company that owns the job can update application status."""
        app = Application.objects.create(applicant=self.talent, job=self.job)
        self.client.force_authenticate(user=self.talent)
        resp = self.client.patch(
            reverse('update_application_status', args=[app.pk]),
            {'status': 'shortlisted'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_other_company_cannot_manage_job(self):
        """A different company cannot edit another company's job."""
        other = User.objects.create_user(
            email='other@company.com', password='TestPass123!',
            full_name='Other Co', role=User.Role.COMPANY,
            is_verified=True,
        )
        CompanyProfile.objects.create(user=other, legal_name='Other Co Inc')
        self.client.force_authenticate(user=other)
        resp = self.client.patch(
            reverse('company_job_detail', args=[self.job.pk]),
            {'title': 'Hacked Title'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    DEFAULT_THROTTLE_RATES={
        'anon': '1000/min', 'user': '1000/min',
        'auth': '1000/min', 'contact': '1000/min',
    },
)
class ApplicationWithdrawalIntegrationTest(TestCase):
    """
    Tests application withdrawal edge cases:
    - Can withdraw a pending application
    - Cannot withdraw after rejection/offer
    - Cannot apply again after withdrawal (unique_together)
    """

    def setUp(self):
        self.client = APIClient()
        self.talent = User.objects.create_user(
            email='withdraw@test.com', password='TestPass123!',
            full_name='Withdraw Test', role=User.Role.TALENT,
            is_verified=True,
        )
        TalentProfile.objects.create(user=self.talent, skills=['Python'])

        self.company = User.objects.create_user(
            email='co_withdraw@test.com', password='TestPass123!',
            full_name='Withdraw Corp', role=User.Role.COMPANY,
            is_verified=True,
        )
        CompanyProfile.objects.create(user=self.company, legal_name='Withdraw Corp')

        self.job = JobPost.objects.create(
            company=self.company, title='Withdrawal Test Job',
            description='Testing.', status=JobPost.Status.OPEN,
            skills_required=['Python'],
        )

    def test_withdraw_pending_application(self):
        app = Application.objects.create(applicant=self.talent, job=self.job)
        self.client.force_authenticate(user=self.talent)
        resp = self.client.delete(reverse('withdraw_application', args=[app.pk]))
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT])
        app.refresh_from_db()
        self.assertEqual(app.status, Application.Status.WITHDRAWN)

    def test_cannot_withdraw_rejected_application(self):
        app = Application.objects.create(
            applicant=self.talent, job=self.job, status=Application.Status.REJECTED,
        )
        self.client.force_authenticate(user=self.talent)
        resp = self.client.delete(reverse('withdraw_application', args=[app.pk]))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_withdraw_offered_application(self):
        app = Application.objects.create(
            applicant=self.talent, job=self.job, status=Application.Status.OFFERED,
        )
        self.client.force_authenticate(user=self.talent)
        resp = self.client.delete(reverse('withdraw_application', args=[app.pk]))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
