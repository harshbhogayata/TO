"""
tests/test_tier_limits.py
Unit tests for the subscription tier enforcement module.
"""
from django.test import TestCase, override_settings
from accounts.models import User, TalentProfile, CompanyProfile
from accounts.tier_limits import (
    get_talent_limits, get_company_limits,
    check_talent_application_limit,
    check_talent_saved_job_limit,
    check_company_job_post_limit,
    TALENT_TIER_LIMITS, COMPANY_TIER_LIMITS,
)
from jobs.models import JobPost, Application, SavedJob


class TierLimitDefinitionTests(TestCase):
    """Verify tier limit definitions are consistent."""

    def test_talent_tiers_have_required_keys(self):
        for tier, limits in TALENT_TIER_LIMITS.items():
            self.assertIn('max_applications_per_month', limits)
            self.assertIn('max_saved_jobs', limits)
            self.assertIn('label', limits)

    def test_company_tiers_have_required_keys(self):
        for tier, limits in COMPANY_TIER_LIMITS.items():
            self.assertIn('max_active_job_posts', limits)
            self.assertIn('max_applications_visible', limits)
            self.assertIn('label', limits)

    def test_free_talent_has_finite_limits(self):
        limits = TALENT_TIER_LIMITS['free']
        self.assertEqual(limits['max_applications_per_month'], 3)
        self.assertEqual(limits['max_saved_jobs'], 10)

    def test_premium_talent_has_no_limits(self):
        limits = TALENT_TIER_LIMITS['premium']
        self.assertIsNone(limits['max_applications_per_month'])
        self.assertIsNone(limits['max_saved_jobs'])

    def test_free_company_has_1_job_post(self):
        self.assertEqual(COMPANY_TIER_LIMITS['free']['max_active_job_posts'], 1)

    def test_starter_company_has_5_job_posts(self):
        self.assertEqual(COMPANY_TIER_LIMITS['starter']['max_active_job_posts'], 5)

    def test_professional_company_unlimited(self):
        self.assertIsNone(COMPANY_TIER_LIMITS['professional']['max_active_job_posts'])

    def test_enterprise_company_unlimited(self):
        self.assertIsNone(COMPANY_TIER_LIMITS['enterprise']['max_active_job_posts'])


class GetLimitsTests(TestCase):
    """Tests for get_talent_limits and get_company_limits helpers."""

    def test_get_talent_limits_default(self):
        user = User.objects.create_user(
            email='t@test.com', password='p', role=User.Role.TALENT,
        )
        TalentProfile.objects.create(user=user, subscription_tier='free')
        limits = get_talent_limits(user)
        self.assertEqual(limits['max_applications_per_month'], 3)

    def test_get_talent_limits_premium(self):
        user = User.objects.create_user(
            email='tp@test.com', password='p', role=User.Role.TALENT,
        )
        TalentProfile.objects.create(user=user, subscription_tier='premium')
        limits = get_talent_limits(user)
        self.assertIsNone(limits['max_applications_per_month'])

    def test_get_company_limits_default(self):
        user = User.objects.create_user(
            email='c@test.com', password='p', role=User.Role.COMPANY,
        )
        CompanyProfile.objects.create(user=user, legal_name='Test', subscription_tier='free')
        limits = get_company_limits(user)
        self.assertEqual(limits['max_active_job_posts'], 1)

    def test_get_company_limits_unknown_tier_falls_back_to_free(self):
        user = User.objects.create_user(
            email='cu@test.com', password='p', role=User.Role.COMPANY,
        )
        CompanyProfile.objects.create(user=user, legal_name='Test', subscription_tier='nonexistent')
        limits = get_company_limits(user)
        self.assertEqual(limits['max_active_job_posts'], 1)


class CheckTalentApplicationLimitTests(TestCase):

    def setUp(self):
        self.talent = User.objects.create_user(
            email='app_limit@test.com', password='p', role=User.Role.TALENT,
        )
        TalentProfile.objects.create(user=self.talent, subscription_tier='free')
        self.company = User.objects.create_user(
            email='co_limit@test.com', password='p', role=User.Role.COMPANY,
        )
        CompanyProfile.objects.create(user=self.company, legal_name='Limit Corp')

    def test_allowed_under_limit(self):
        allowed, msg, count, limit = check_talent_application_limit(self.talent)
        self.assertTrue(allowed)
        self.assertEqual(count, 0)
        self.assertEqual(limit, 3)

    def test_blocked_at_limit(self):
        # Create 3 applications
        for i in range(3):
            job = JobPost.objects.create(
                company=self.company, title=f'Job {i}',
                description='d', status='open',
            )
            Application.objects.create(applicant=self.talent, job=job)

        allowed, msg, count, limit = check_talent_application_limit(self.talent)
        self.assertFalse(allowed)
        self.assertIn('limit', msg.lower())
        self.assertEqual(count, 3)

    def test_withdrawn_applications_dont_count(self):
        # Create 3 withdrawn applications
        for i in range(3):
            job = JobPost.objects.create(
                company=self.company, title=f'Withdrawn Job {i}',
                description='d', status='open',
            )
            Application.objects.create(
                applicant=self.talent, job=job, status='withdrawn',
            )

        allowed, msg, count, limit = check_talent_application_limit(self.talent)
        self.assertTrue(allowed)
        self.assertEqual(count, 0)

    def test_premium_always_allowed(self):
        self.talent.talent_profile.subscription_tier = 'premium'
        self.talent.talent_profile.save()
        allowed, msg, count, limit = check_talent_application_limit(self.talent)
        self.assertTrue(allowed)
        self.assertIsNone(limit)


class CheckCompanyJobPostLimitTests(TestCase):

    def setUp(self):
        self.company = User.objects.create_user(
            email='post_limit@test.com', password='p', role=User.Role.COMPANY,
        )
        CompanyProfile.objects.create(
            user=self.company, legal_name='Post Limit Corp',
            subscription_tier='free',
        )

    def test_allowed_with_no_posts(self):
        allowed, msg, count, limit = check_company_job_post_limit(self.company)
        self.assertTrue(allowed)
        self.assertEqual(count, 0)
        self.assertEqual(limit, 1)

    def test_blocked_at_limit(self):
        JobPost.objects.create(
            company=self.company, title='Existing',
            description='d', status='open',
        )
        allowed, msg, count, limit = check_company_job_post_limit(self.company)
        self.assertFalse(allowed)
        self.assertEqual(count, 1)

    def test_closed_jobs_dont_count(self):
        JobPost.objects.create(
            company=self.company, title='Closed',
            description='d', status='closed',
        )
        allowed, msg, count, limit = check_company_job_post_limit(self.company)
        self.assertTrue(allowed)

    def test_starter_gets_5(self):
        self.company.company_profile.subscription_tier = 'starter'
        self.company.company_profile.save()
        for i in range(5):
            JobPost.objects.create(
                company=self.company, title=f'Starter {i}',
                description='d', status='open',
            )
        allowed, msg, count, limit = check_company_job_post_limit(self.company)
        self.assertFalse(allowed)
        self.assertEqual(count, 5)
        self.assertEqual(limit, 5)


class CheckTalentSavedJobLimitTests(TestCase):

    def setUp(self):
        self.talent = User.objects.create_user(
            email='save_limit@test.com', password='p', role=User.Role.TALENT,
        )
        TalentProfile.objects.create(user=self.talent, subscription_tier='free')
        self.company = User.objects.create_user(
            email='co_save@test.com', password='p', role=User.Role.COMPANY,
        )
        CompanyProfile.objects.create(user=self.company, legal_name='Save Corp')

    def test_allowed_under_limit(self):
        allowed, msg = check_talent_saved_job_limit(self.talent)
        self.assertTrue(allowed)

    def test_blocked_at_limit(self):
        for i in range(10):
            job = JobPost.objects.create(
                company=self.company, title=f'Save {i}',
                description='d', status='open',
            )
            SavedJob.objects.create(user=self.talent, job=job)
        allowed, msg = check_talent_saved_job_limit(self.talent)
        self.assertFalse(allowed)

    def test_premium_unlimited(self):
        self.talent.talent_profile.subscription_tier = 'premium'
        self.talent.talent_profile.save()
        allowed, msg = check_talent_saved_job_limit(self.talent)
        self.assertTrue(allowed)
