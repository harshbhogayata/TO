from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from rest_framework import status
from rest_framework.test import APIClient

from .models import User


class AuthAPITestCase(TestCase):
    """Smoke tests for auth endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.talent = User.objects.create_user(
            email='talent@test.com',
            password='testpass123',
            full_name='Test Talent',
            role=User.Role.TALENT,
        )

    def test_login_returns_tokens(self):
        url = reverse('token_obtain_pair')
        resp = self.client.post(url, {'email': 'talent@test.com', 'password': 'testpass123'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('access', resp.data)
        self.assertIn('refresh', resp.data)

    def test_login_invalid_credentials(self):
        url = reverse('token_obtain_pair')
        resp = self.client.post(url, {'email': 'talent@test.com', 'password': 'wrong'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_requires_auth(self):
        url = reverse('me')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_returns_user(self):
        self.client.force_authenticate(user=self.talent)
        url = reverse('me')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data.get('email'), 'talent@test.com')
        self.assertEqual(resp.data.get('role'), 'TALENT')


class RegistrationTestCase(TestCase):
    """Tests for talent and company registration endpoints."""

    def setUp(self):
        self.client = APIClient()

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_register_talent_returns_tokens(self):
        url = reverse('register_talent')
        data = {
            'email': 'new_talent@test.com',
            'password': 'securepass123',
            'password_confirm': 'securepass123',
            'full_name': 'New Talent',
        }
        resp = self.client.post(url, data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn('tokens', resp.data)
        self.assertIn('access', resp.data['tokens'])
        self.assertTrue(User.objects.filter(email='new_talent@test.com').exists())

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_register_company_returns_tokens(self):
        url = reverse('register_company')
        data = {
            'email': 'company@test.com',
            'password': 'securepass123',
            'password_confirm': 'securepass123',
            'full_name': 'Test Company Inc',
            'legal_name': 'Test Company Inc',
        }
        resp = self.client.post(url, data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email='company@test.com')
        self.assertEqual(user.role, User.Role.COMPANY)

    def test_register_duplicate_email_fails(self):
        User.objects.create_user(email='dup@test.com', password='pass123')
        url = reverse('register_talent')
        data = {
            'email': 'dup@test.com',
            'password': 'securepass123',
            'password_confirm': 'securepass123',
            'full_name': 'Dup User',
        }
        resp = self.client.post(url, data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    FRONTEND_URL='http://localhost:5173',
)
class PasswordResetTestCase(TestCase):
    """Tests for password reset request and confirm endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='reset@test.com',
            password='oldpass123',
            full_name='Reset User',
            role=User.Role.TALENT,
        )

    def test_request_reset_returns_200_for_existing_email(self):
        url = reverse('password_reset_request')
        resp = self.client.post(url, {'email': 'reset@test.com'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_request_reset_returns_200_for_nonexistent_email(self):
        """Should not leak whether the email exists."""
        url = reverse('password_reset_request')
        resp = self.client.post(url, {'email': 'nobody@test.com'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_confirm_reset_with_valid_token(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        url = reverse('password_reset_confirm')
        resp = self.client.post(url, {
            'uid': uid, 'token': token, 'new_password': 'newpass456!'
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('newpass456!'))

    def test_confirm_reset_with_invalid_token(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        url = reverse('password_reset_confirm')
        resp = self.client.post(url, {
            'uid': uid, 'token': 'bad-token', 'new_password': 'newpass456!'
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirm_reset_rejects_short_password(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        url = reverse('password_reset_confirm')
        resp = self.client.post(url, {
            'uid': uid, 'token': token, 'new_password': 'short'
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class EmailVerificationTestCase(TestCase):
    """Tests for email verification endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='verify@test.com',
            password='testpass123',
            full_name='Verify User',
            role=User.Role.TALENT,
            is_verified=False,
        )

    def test_verify_email_with_valid_token(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        url = reverse('verify_email')
        resp = self.client.post(url, {'uid': uid, 'token': token}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_verified)

    def test_verify_email_with_invalid_token(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        url = reverse('verify_email')
        resp = self.client.post(url, {'uid': uid, 'token': 'invalid'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_verified)

    def test_verify_already_verified_user(self):
        self.user.is_verified = True
        self.user.save()
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        url = reverse('verify_email')
        resp = self.client.post(url, {'uid': uid, 'token': token}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('already', resp.data['message'].lower())

    def test_resend_verification_requires_auth(self):
        url = reverse('resend_verification')
        resp = self.client.post(url, format='json')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_resend_verification_for_unverified_user(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('resend_verification')
        resp = self.client.post(url, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class ChangePasswordTestCase(TestCase):
    """Tests for the change password endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='chpw@test.com',
            password='oldpass123',
            full_name='Change PW',
            role=User.Role.TALENT,
        )
        self.client.force_authenticate(user=self.user)

    def test_change_password_success(self):
        url = reverse('change_password')
        resp = self.client.post(url, {
            'old_password': 'oldpass123',
            'new_password': 'brandnew456!',
            'new_password_confirm': 'brandnew456!',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('brandnew456!'))

    def test_change_password_wrong_current(self):
        url = reverse('change_password')
        resp = self.client.post(url, {
            'old_password': 'wrongpass',
            'new_password': 'brandnew456!',
            'new_password_confirm': 'brandnew456!',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class UserModelTestCase(TestCase):
    """Tests for the custom User model."""

    def test_create_talent_user(self):
        user = User.objects.create_user(
            email='model@test.com',
            password='pass123',
            full_name='Model User',
            role=User.Role.TALENT,
        )
        self.assertTrue(user.is_talent)
        self.assertFalse(user.is_company)
        self.assertFalse(user.is_staff)

    def test_create_superuser(self):
        su = User.objects.create_superuser(
            email='admin@test.com',
            password='adminpass',
        )
        self.assertTrue(su.is_staff)
        self.assertTrue(su.is_superuser)
        self.assertEqual(su.role, User.Role.ADMIN)

    def test_email_is_required(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email='', password='pass123')

    def test_str_representation(self):
        user = User.objects.create_user(email='str@test.com', password='p', role=User.Role.TALENT)
        self.assertEqual(str(user), 'str@test.com (TALENT)')
