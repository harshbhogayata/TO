"""accounts/urls.py"""
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    CustomTokenObtainPairView,
    RegisterTalentView,
    RegisterCompanyView,
    MeView,
    TalentProfileView,
    CompanyProfileView,
    logout_view,
    change_password,
    password_reset_request,
    password_reset_confirm,
    verify_email,
    resend_verification,
    ContactMessageView,
    ExtractResumeView,
    TwoFactorSetupView,
    TwoFactorVerifyView,
    TwoFactorDisableView,
    deactivate_account,
)

urlpatterns = [
    # Auth
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', logout_view, name='logout'),
    path('register/talent/', RegisterTalentView.as_view(), name='register_talent'),
    path('register/company/', RegisterCompanyView.as_view(), name='register_company'),

    # Current user
    path('me/', MeView.as_view(), name='me'),
    # Security
    path('change-password/', change_password, name='change_password'),
    path('password-reset/', password_reset_request, name='password_reset_request'),
    path('password-reset/confirm/', password_reset_confirm, name='password_reset_confirm'),
    path('verify-email/', verify_email, name='verify_email'),
    path('resend-verification/', resend_verification, name='resend_verification'),
    path('extract-resume/', ExtractResumeView.as_view(), name='extract_resume'),
    path('2fa/setup/', TwoFactorSetupView.as_view(), name='2fa_setup'),
    path('2fa/verify/', TwoFactorVerifyView.as_view(), name='2fa_verify'),
    path('2fa/disable/', TwoFactorDisableView.as_view(), name='2fa_disable'),
    path('deactivate/', deactivate_account, name='deactivate_account'),

    # Profiles
    path('profile/talent/', TalentProfileView.as_view(), name='talent_profile'),
    path('profile/company/', CompanyProfileView.as_view(), name='company_profile'),
    
    # Support & Contact
    path('contact/', ContactMessageView.as_view(), name='contact_message'),
]
