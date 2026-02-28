"""
accounts/views.py
Authentication and user profile management views.
"""
from django.contrib.auth import update_session_auth_hash
from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.exceptions import TokenError

from .models import User, TalentProfile, CompanyProfile
from .throttling import AuthEndpointThrottle
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


class CustomTokenObtainPairView(TokenObtainPairView):
    """Login endpoint — returns JWT pair with enriched payload."""
    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [AuthEndpointThrottle]


class RegisterTalentView(generics.CreateAPIView):
    """POST /api/auth/register/talent — Create a new Talent account."""
    serializer_class = TalentRegistrationSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthEndpointThrottle]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Issue tokens immediately after registration
        refresh = RefreshToken.for_user(user)
        return Response({
            'message': 'Talent account created successfully.',
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

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)
        return Response({
            'message': 'Company account created successfully. Verification pending.',
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
    permission_classes = [permissions.IsAuthenticated]
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
    permission_classes = [permissions.IsAuthenticated]
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
    try:
        from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
        tokens = OutstandingToken.objects.filter(user=user)
        for token in tokens:
            BlacklistedToken.objects.get_or_create(token=token)
    except Exception:
        pass  # token_blacklist may not be fully configured

    return Response({'message': 'Password changed successfully. Please log in again.'})


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
@throttle_classes([AuthEndpointThrottle])
def password_reset_request(request):
    """
    POST /api/auth/password-reset/
    Password reset is not yet implemented. Returns 503 so clients can show a clear message.
    When implemented: generate token (e.g. PasswordResetTokenGenerator), send email with
    FRONTEND_URL/reset?token=..., and add a confirm-reset endpoint.
    """
    email = request.data.get('email', '').strip().lower()
    if not email:
        return Response({'error': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)
    return Response(
        {
            'error': 'Password reset is not available yet. Please contact support.',
            'code': 'password_reset_not_implemented',
        },
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


class ContactMessageView(generics.CreateAPIView):
    """POST /api/v1/auth/contact/ — Submit a contact/support form."""
    serializer_class = ContactMessageSerializer
    permission_classes = [permissions.AllowAny]


import io
import logging
try:
    import PyPDF2
    from docx import Document
except ImportError:
    PyPDF2 = None
    Document = None
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser

logger = logging.getLogger(__name__)

# Max resume file size: 10 MB
RESUME_MAX_SIZE_BYTES = 10 * 1024 * 1024
# Allowed content-types for resume upload (extension is also checked)
RESUME_ALLOWED_CONTENT_TYPES = {
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'text/plain',
}
MAX_PDF_PAGES = 50

SKILLS_DB = ['UI Design', 'Figma', 'Art Direction', 'React', 'Python', 'Django', 'Node.js', 'AWS', 'Docker', 'Kubernetes', 'JavaScript', 'TypeScript', 'SQL', 'PostgreSQL', 'Machine Learning', 'Data Science', 'Data Analysis', 'Project Management', 'Agile', 'Scrum', 'Marketing', 'SEO', 'Adobe Creative Suite', 'Photoshop', 'Illustrator', 'UX', 'Graphic Design', 'Java', 'C++', 'Go', 'HTML', 'CSS']


class ExtractResumeView(APIView):
    """POST /api/v1/auth/extract-resume/ — Read file text and regex match skills natively."""
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        file = request.FILES.get('resume')
        if not file:
            return Response({'error': 'No file provided'}, status=400)

        if hasattr(file, 'size') and file.size > RESUME_MAX_SIZE_BYTES:
            return Response(
                {'error': f'File too large. Maximum size is {RESUME_MAX_SIZE_BYTES // (1024*1024)} MB.'},
                status=400,
            )
        content_type = (getattr(file, 'content_type') or '').split(';')[0].strip().lower()
        if content_type and content_type not in RESUME_ALLOWED_CONTENT_TYPES:
            return Response(
                {'error': 'Unsupported file type. Use PDF, DOCX, or plain text.'},
                status=400,
            )

        ext = file.name.lower().split('.')[-1] if file.name else ''
        text_content = ""

        try:
            if ext == 'pdf':
                if not PyPDF2:
                    return Response({'error': 'Resume parsing is not available. Please use DOCX or TXT.'}, status=503)
                reader = PyPDF2.PdfReader(file)
                pages = reader.pages[:MAX_PDF_PAGES]
                for page in pages:
                    text_content += page.extract_text() or ""
            elif ext == 'docx':
                if not Document:
                    return Response({'error': 'Resume parsing is not available. Please use PDF or TXT.'}, status=503)
                doc = Document(file)
                for para in doc.paragraphs:
                    text_content += para.text + " "
            elif ext == 'txt':
                text_content = file.read().decode('utf-8', errors='ignore')
            else:
                return Response({'error': 'Unsupported file format. Use .pdf, .docx, or .txt.'}, status=400)
        except Exception as e:
            logger.exception('Resume parsing failed')
            return Response(
                {'error': 'Resume parsing failed. Please use a valid PDF or DOCX file.'},
                status=500,
            )

        text_low = text_content.lower()
        extracted = []
        for s in SKILLS_DB:
            if s.lower() in text_low:
                extracted.append(s)

        cleaned_text = ' '.join(text_content.replace('\n', ' ').split())
        bio = cleaned_text[:200] + "..." if len(cleaned_text) > 200 else cleaned_text
        if len(bio) < 15:
            bio = "Experienced professional seeking opportunities."

        return Response({'skills': extracted, 'bio': bio})


import base64

class TwoFactorSetupView(APIView):
    """GET /api/v1/auth/2fa/setup/ — Generate TOTP QR code securely"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        import pyotp
        import qrcode
        user = request.user
        if not user.totp_secret:
            user.totp_secret = pyotp.random_base32()
            user.save()
        
        totp = pyotp.TOTP(user.totp_secret)
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

    def post(self, request):
        import pyotp
        token = request.data.get('token')
        if not token:
            return Response({'error': 'Token required'}, status=400)
            
        if not request.user.totp_secret:
            return Response({'error': '2FA not setup'}, status=400)
            
        totp = pyotp.TOTP(request.user.totp_secret)
        if totp.verify(token):
            request.user.is_2fa_enabled = True
            request.user.save()
            return Response({'success': True, 'message': '2FA Enabled'})
        return Response({'success': False, 'error': 'Invalid 6-digit PIN'}, status=400)


class TwoFactorDisableView(APIView):
    """POST /api/v1/auth/2fa/disable/ — Disable 2FA for the authenticated user."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if not user.is_2fa_enabled:
            return Response({'message': '2FA is already disabled.'})
        user.is_2fa_enabled = False
        user.totp_secret = None
        user.save(update_fields=['is_2fa_enabled', 'totp_secret'])
        return Response({'message': '2FA has been disabled.'})


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def deactivate_account(request):
    """POST /api/v1/auth/deactivate/ — Deactivate the current user's account."""
    user = request.user
    user.is_active = False
    user.save(update_fields=['is_active'])

    # Blacklist all outstanding refresh tokens so the user is logged out everywhere
    try:
        from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
        for token in OutstandingToken.objects.filter(user=user):
            BlacklistedToken.objects.get_or_create(token=token)
    except Exception:
        pass

    return Response({'message': 'Account deactivated.'}, status=status.HTTP_200_OK)
