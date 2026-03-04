"""
accounts/views.py
Authentication and user profile management views.
"""
import io
import logging
import base64

try:
    import PyPDF2
    from docx import Document
except ImportError:
    PyPDF2 = None
    Document = None

from django.contrib.auth import update_session_auth_hash
from django.core.cache import cache
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.exceptions import TokenError

from compliance.constants import AuditAction, AuditCategory
from compliance.decorators import audit_action

from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.conf import settings as django_settings
from django.contrib.auth.password_validation import validate_password as _validate_pw
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired

from compliance.constants import AuditAction, AuditCategory
from compliance.decorators import audit_action, create_audit_log

from .models import User, TalentProfile, CompanyProfile
from .throttling import AuthEndpointThrottle, ContactEndpointThrottle
from .permissions import IsEmailVerified
from .crypto import sign_totp, unsign_totp
from .utils import blacklist_all_tokens
from .serializers import (
    CustomTokenObtainPairSerializer,
    TalentRegistrationSerializer,
    CompanyRegistrationSerializer,
    TalentProfileSerializer,
    CompanyProfileSerializer,
    UserMeSerializer,
    ChangePasswordSerializer,
    ContactMessageSerializer,
)

logger = logging.getLogger(__name__)


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Login endpoint — returns JWT pair with enriched payload.

    Enterprise security:
        - Locks account after 5 failed login attempts for 15 minutes
        - Tracks failed attempts per email via cache
        - Resets counter on successful login
        - Audit logs lockout events
    """
    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [AuthEndpointThrottle]

    _MAX_ATTEMPTS = 5
    _LOCKOUT_SECONDS = 900  # 15 minutes

    @audit_action(
        action=AuditAction.LOGIN,
        category=AuditCategory.AUTH,
        description='User logged in',
        resource_type='accounts.User',
        get_resource_id=lambda req, res: res.data.get('user', {}).get('id', '') if res.data else '',
    )
    def post(self, request, *args, **kwargs):
        from django.core.cache import cache

        email = (request.data.get('email') or '').lower().strip()
        if not email:
            return super().post(request, *args, **kwargs)

        cache_key = f'login_lockout:{email}'
        attempts = cache.get(cache_key, 0)

        if attempts >= self._MAX_ATTEMPTS:
            logger.warning('Account locked out: email=%s attempts=%d', email, attempts)
            return Response(
                {
                    'error': 'Account temporarily locked due to too many failed login attempts. '
                             'Please try again in 15 minutes or reset your password.',
                    'locked_until_seconds': self._LOCKOUT_SECONDS,
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={'Retry-After': str(self._LOCKOUT_SECONDS)},
            )

        response = super().post(request, *args, **kwargs)

        if response.status_code == 200:
            # Successful login — reset counter
            cache.delete(cache_key)
        elif response.status_code == 401:
            # Failed login — increment counter
            new_count = attempts + 1
            cache.set(cache_key, new_count, self._LOCKOUT_SECONDS)
            remaining = self._MAX_ATTEMPTS - new_count
            if remaining > 0:
                response.data['attempts_remaining'] = remaining
            else:
                logger.warning(
                    'Account lockout triggered: email=%s',
                    email,
                )

        return response


class RegisterTalentView(generics.CreateAPIView):
    """POST /api/auth/register/talent — Create a new Talent account."""
    serializer_class = TalentRegistrationSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthEndpointThrottle]

    @audit_action(
        action=AuditAction.CREATE,
        category=AuditCategory.AUTH,
        description='Talent account registered',
        resource_type='accounts.User',
        get_resource_id=lambda req, res: res.data.get('user', {}).get('id', ''),
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Send verification email asynchronously via Celery
        from accounts.tasks import send_verification_email_task
        try:
            send_verification_email_task.delay(user_id=user.pk)
        except Exception:
            logger.warning('Failed to dispatch verification email task for user %s', user.email, exc_info=True)

        # Issue tokens immediately after registration
        refresh = RefreshToken.for_user(user)
        return Response({
            'message': 'Talent account created successfully. Please verify your email.',
            'user': UserMeSerializer(user).data,
            'tokens': {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }
        }, status=status.HTTP_201_CREATED)


class RegisterCompanyView(generics.CreateAPIView):
    """POST /api/auth/register/company — Create a new Company account."""
    serializer_class = CompanyRegistrationSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthEndpointThrottle]

    @audit_action(
        action=AuditAction.CREATE,
        category=AuditCategory.AUTH,
        description='Company account registered',
        resource_type='accounts.User',
        get_resource_id=lambda req, res: res.data.get('user', {}).get('id', ''),
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Send verification email asynchronously via Celery
        from accounts.tasks import send_verification_email_task
        try:
            send_verification_email_task.delay(user_id=user.pk)
        except Exception:
            logger.warning('Failed to dispatch verification email task for user %s', user.email, exc_info=True)

        refresh = RefreshToken.for_user(user)
        return Response({
            'message': 'Company account created successfully. Please verify your email.',
            'user': UserMeSerializer(user).data,
            'tokens': {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }
        }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def logout_view(request):
    """
    POST /api/auth/logout — Blacklists the refresh token.
    Intentionally AllowAny: the client sends the refresh token in the body to blacklist it;
    the access token may already be cleared, so the request is often unauthenticated.
    """
    try:
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response({'error': 'Invalid token.'}, status=status.HTTP_400_BAD_REQUEST)
        token = RefreshToken(refresh_token)
        token.blacklist()
        return Response({'message': 'Successfully logged out.'}, status=status.HTTP_200_OK)
    except TokenError:
        # Invalid or expired refresh token; return generic message to avoid enumeration
        return Response({'error': 'Invalid token.'}, status=status.HTTP_400_BAD_REQUEST)


class MeView(generics.RetrieveAPIView):
    """GET /api/auth/me — Returns the authenticated user's full profile."""
    serializer_class = UserMeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class TalentProfileView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/profile/talent — Retrieve or update Talent profile."""
    serializer_class = TalentProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsEmailVerified]
    parser_classes = [MultiPartParser, FormParser]

    def get_object(self):
        if not self.request.user.is_talent:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Only talent accounts can access this profile.')
        profile, _ = TalentProfile.objects.get_or_create(user=self.request.user)
        return profile

    def perform_update(self, serializer):
        # Handle avatar upload — it lives on the User model, not TalentProfile
        avatar = self.request.FILES.get('avatar')
        full_name = self.request.data.get('full_name')
        user_changed = False
        if avatar:
            self.request.user.avatar = avatar
            user_changed = True
        if full_name:
            self.request.user.full_name = full_name
            user_changed = True
        if user_changed:
            self.request.user.save()
        serializer.save()


class CompanyProfileView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/profile/company — Retrieve or update Company profile."""
    serializer_class = CompanyProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsEmailVerified]
    parser_classes = [MultiPartParser, FormParser]

    def get_object(self):
        if not self.request.user.is_company:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Only company accounts can access this profile.')
        profile, _ = CompanyProfile.objects.get_or_create(user=self.request.user)
        return profile

    def perform_update(self, serializer):
        avatar = self.request.FILES.get('avatar')
        if avatar:
            self.request.user.avatar = avatar
            self.request.user.save()
        serializer.save()


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([AuthEndpointThrottle])
@audit_action(
    action=AuditAction.PASSWORD_CHANGE,
    category=AuditCategory.AUTH,
    description='Password changed',
    resource_type='accounts.User',
)
def change_password(request):
    """POST /api/auth/change-password"""
    serializer = ChangePasswordSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    user = request.user
    if not user.check_password(serializer.validated_data['old_password']):
        return Response({'error': 'Current password is incorrect.'}, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(serializer.validated_data['new_password'])
    user.save()
    update_session_auth_hash(request, user)

    # Blacklist all existing refresh tokens for this user to force re-login on other devices
    blacklist_all_tokens(user)

    return Response({'message': 'Password changed successfully. Please log in again.'})


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
@throttle_classes([AuthEndpointThrottle])
@audit_action(
    action=AuditAction.PASSWORD_RESET_REQUEST,
    category=AuditCategory.AUTH,
    description='Password reset requested',
    resource_type='accounts.User',
)
def password_reset_request(request):
    """
    POST /api/auth/password-reset/
    Generates a one-time token and emails a reset link to the user.
    Always returns 200 to prevent email enumeration.
    """
    email = request.data.get('email', '').strip().lower()
    if not email:
        return Response({'error': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)

    # Always return success to prevent email enumeration
    try:
        user = User.objects.get(email=email, is_active=True)
        from accounts.tasks import send_password_reset_email_task
        send_password_reset_email_task.delay(user_id=user.pk)
    except User.DoesNotExist:
        pass  # Silent — no info leak
    except Exception:
        logger.exception('Password reset email dispatch failed')

    return Response({'message': 'If an account with that email exists, a reset link has been sent.'})


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
@throttle_classes([AuthEndpointThrottle])
@audit_action(
    action=AuditAction.PASSWORD_RESET_CONFIRM,
    category=AuditCategory.AUTH,
    description='Password reset confirmed',
    resource_type='accounts.User',
)
def password_reset_confirm(request):
    """
    POST /api/auth/password-reset/confirm/
    Accepts uid, token, and new_password to complete the reset flow.
    """
    uid = request.data.get('uid', '')
    token = request.data.get('token', '')
    new_password = request.data.get('new_password', '')

    if not uid or not token or not new_password:
        return Response({'error': 'uid, token, and new_password are required.'}, status=status.HTTP_400_BAD_REQUEST)

    # Run the full Django password validator suite (length, common, numeric, similarity)
    try:
        _validate_pw(new_password)
    except DjangoValidationError as e:
        return Response({'error': e.messages}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user_id = force_str(urlsafe_base64_decode(uid))
        user = User.objects.get(pk=user_id, is_active=True)
    except (User.DoesNotExist, ValueError, OverflowError):
        return Response({'error': 'Invalid or expired reset link.'}, status=status.HTTP_400_BAD_REQUEST)

    if not default_token_generator.check_token(user, token):
        return Response({'error': 'Invalid or expired reset link.'}, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(new_password)
    user.save()

    # Blacklist all existing refresh tokens
    blacklist_all_tokens(user)

    return Response({'message': 'Password has been reset. You can now log in with your new password.'})


class ContactMessageView(generics.CreateAPIView):
    """POST /api/v1/auth/contact/ — Submit a contact/support form."""
    serializer_class = ContactMessageSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ContactEndpointThrottle]


# ─── Email Verification ──────────────────────────────────────────────────────

def _send_verification_email(user):
    """Helper — sends a verification email with a one-time token link."""
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    verify_url = f"{django_settings.FRONTEND_URL}/verify-email?uid={uid}&token={token}"

    send_mail(
        subject='TalentOrbit — Verify Your Email',
        message=(
            f'Hi {user.full_name or "there"},\n\n'
            f'Welcome to TalentOrbit! Please verify your email address by clicking the link below:\n\n'
            f'{verify_url}\n\n'
            f'This link will expire in approximately 15 minutes.\n\n'
            f'If you didn\'t create this account, you can safely ignore this email.\n\n'
            f'— TalentOrbit'
        ),
        from_email=django_settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
@throttle_classes([AuthEndpointThrottle])
def verify_email(request):
    """
    POST /api/v1/auth/verify-email/
    Accepts uid + token, marks user.is_verified = True.
    """
    uid = request.data.get('uid', '')
    token = request.data.get('token', '')

    if not uid or not token:
        return Response({'error': 'uid and token are required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user_id = force_str(urlsafe_base64_decode(uid))
        user = User.objects.get(pk=user_id)
    except (User.DoesNotExist, ValueError, OverflowError):
        return Response({'error': 'Invalid verification link.'}, status=status.HTTP_400_BAD_REQUEST)

    if user.is_verified:
        return Response({'message': 'Email is already verified.'})

    if not default_token_generator.check_token(user, token):
        return Response({'error': 'Invalid or expired verification link.'}, status=status.HTTP_400_BAD_REQUEST)

    user.is_verified = True
    user.save(update_fields=['is_verified'])
    return Response({'message': 'Email verified successfully. You can now use all features.'})


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([AuthEndpointThrottle])
def resend_verification(request):
    """
    POST /api/v1/auth/resend-verification/
    Resends the verification email for the authenticated user.
    """
    user = request.user
    if user.is_verified:
        return Response({'message': 'Email is already verified.'})

    from accounts.tasks import send_verification_email_task
    try:
        send_verification_email_task.delay(user_id=user.pk)
    except Exception:
        logger.exception('Verification email task dispatch failed')

    return Response({'message': 'Verification email sent. Check your inbox and spam folder.'})


# ─── Two-Factor Authentication ────────────────────────────────────────────────

class TwoFactorSetupView(APIView):
    """GET /api/v1/auth/2fa/setup/ — Generate TOTP QR code securely"""
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [AuthEndpointThrottle]

    def get(self, request):
        import pyotp
        import qrcode
        user = request.user

        if not user.totp_secret:
            raw_secret = pyotp.random_base32()
            user.totp_secret = sign_totp(raw_secret)
            user.save(update_fields=['totp_secret'])
            plain_secret = raw_secret
        else:
            plain_secret = unsign_totp(user.totp_secret)
        
        totp = pyotp.TOTP(plain_secret)
        uri = totp.provisioning_uri(name=user.email, issuer_name="TalentOrbit")
        
        qr = qrcode.make(uri)
        buf = io.BytesIO()
        qr.save(buf, format="PNG")
        qr_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        
        return Response({
            'qr_code': f"data:image/png;base64,{qr_b64}",
            'is_enabled': user.is_2fa_enabled
        })

class TwoFactorVerifyView(APIView):
    """POST /api/v1/auth/2fa/verify/ — Confirm an OTP to enable 2FA"""
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [AuthEndpointThrottle]

    def post(self, request):
        import pyotp
        token = request.data.get('token')
        if not token:
            return Response({'error': 'Token required'}, status=400)
            
        if not request.user.totp_secret:
            return Response({'error': '2FA not setup'}, status=400)

        # Brute-force protection: lock after 5 failed attempts for 15 minutes
        cache_key = f'2fa_attempts:{request.user.pk}'
        attempts = cache.get(cache_key, 0)
        if attempts >= 5:
            return Response(
                {'error': 'Too many failed attempts. Please try again in 15 minutes.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        plain_secret = unsign_totp(request.user.totp_secret)
        totp = pyotp.TOTP(plain_secret)
        if totp.verify(token):
            cache.delete(cache_key)  # Reset on success
            request.user.is_2fa_enabled = True
            # Re-sign the secret if it was a legacy unsigned value
            request.user.totp_secret = sign_totp(plain_secret)
            request.user.save(update_fields=['is_2fa_enabled', 'totp_secret'])
            return Response({'success': True, 'message': '2FA Enabled'})

        cache.set(cache_key, attempts + 1, 900)  # 15-min lockout window
        return Response({'success': False, 'error': 'Invalid 6-digit PIN'}, status=400)


class TwoFactorDisableView(APIView):
    """POST /api/v1/auth/2fa/disable/ — Disable 2FA for the authenticated user.
    Requires current password for re-authentication."""
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [AuthEndpointThrottle]

    def post(self, request):
        user = request.user
        if not user.is_2fa_enabled:
            return Response({'message': '2FA is already disabled.'})

        # Re-authentication: require current password
        password = request.data.get('password', '')
        if not password or not user.check_password(password):
            return Response(
                {'error': 'Current password is required to disable 2FA.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        user.is_2fa_enabled = False
        user.totp_secret = None
        user.save(update_fields=['is_2fa_enabled', 'totp_secret'])
        return Response({'message': '2FA has been disabled.'})


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([AuthEndpointThrottle])
@audit_action(
    action=AuditAction.ACCOUNT_DEACTIVATE,
    category=AuditCategory.USER,
    description='Account deactivated by user',
    resource_type='accounts.User',
)
def deactivate_account(request):
    """POST /api/v1/auth/deactivate/ — Deactivate the current user's account.
    Requires current password for re-authentication."""
    password = request.data.get('password', '')
    user = request.user
    if not password or not user.check_password(password):
        return Response(
            {'error': 'Current password is required to deactivate your account.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    user.is_active = False
    user.save(update_fields=['is_active'])

    # Blacklist all outstanding refresh tokens so the user is logged out everywhere
    blacklist_all_tokens(user)

    return Response({'message': 'Account deactivated.'}, status=status.HTTP_200_OK)


# ─── 2FA Login Step ───────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
@throttle_classes([AuthEndpointThrottle])
def two_factor_login(request):
    """
    POST /api/v1/auth/2fa/login/
    Complete login for users with 2FA enabled.
    Accepts temp_token (from initial login) + totp_code, returns full JWT pair.
    """
    import pyotp

    temp_token = request.data.get('temp_token', '')
    totp_code = request.data.get('totp_code', '')

    if not temp_token or not totp_code:
        return Response(
            {'error': 'temp_token and totp_code are required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Verify the temporary token (valid for 5 minutes)
    signer = TimestampSigner(salt='2fa-login')
    try:
        user_pk = signer.unsign(temp_token, max_age=300)
    except (BadSignature, SignatureExpired):
        return Response(
            {'error': 'Invalid or expired login session. Please log in again.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        user = User.objects.get(pk=user_pk, is_active=True)
    except User.DoesNotExist:
        return Response(
            {'error': 'Invalid or expired login session.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Brute-force protection
    cache_key = f'2fa_login_attempts:{user.pk}'
    attempts = cache.get(cache_key, 0)
    if attempts >= 5:
        return Response(
            {'error': 'Too many failed attempts. Please try again in 15 minutes.'},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    if not user.totp_secret:
        return Response({'error': '2FA is not configured.'}, status=status.HTTP_400_BAD_REQUEST)

    plain_secret = unsign_totp(user.totp_secret)
    totp = pyotp.TOTP(plain_secret)

    if not totp.verify(totp_code):
        cache.set(cache_key, attempts + 1, 900)
        return Response(
            {'error': 'Invalid 2FA code.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    cache.delete(cache_key)

    # Issue full JWT pair
    refresh = RefreshToken.for_user(user)
    avatar_url = None
    if user.avatar:
        avatar_url = user.avatar.url

    return Response({
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'user': {
            'id': user.id,
            'email': user.email,
            'full_name': user.full_name,
            'role': user.role,
            'is_verified': user.is_verified,
            'avatar': avatar_url,
        },
    })
