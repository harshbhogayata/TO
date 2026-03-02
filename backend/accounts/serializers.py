"""
accounts/serializers.py
Serializers for registration, login, and profile management.
"""
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User, TalentProfile, CompanyProfile, ContactMessage


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Extend the default JWT payload to include user role,
    full_name, and is_verified — so the frontend can set up
    the correct dashboard immediately after login.
    Also injects a 'user' object into the response body so the
    frontend can populate auth state without a separate /me call.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['email'] = user.email
        token['full_name'] = user.full_name
        token['role'] = user.role
        token['is_verified'] = user.is_verified
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        # self.user is set by the parent's validate() after authentication
        data['user'] = {
            'id': self.user.id,
            'email': self.user.email,
            'full_name': self.user.full_name,
            'role': self.user.role,
            'is_verified': self.user.is_verified,
        }
        return data


# ─── Registration ──────────────────────────────────────────────────────────────

class TalentRegistrationSerializer(serializers.ModelSerializer):
    """Register a new Talent (job-seeker) account."""
    password = serializers.CharField(
        write_only=True, required=True, validators=[validate_password]
    )
    password_confirm = serializers.CharField(write_only=True, required=True)
    bio = serializers.CharField(required=False, allow_blank=True)
    skills = serializers.JSONField(required=False, default=list)
    location = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ('email', 'full_name', 'password', 'password_confirm', 'bio', 'skills', 'location')

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({'password': 'Passwords do not match.'})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        bio = validated_data.pop('bio', '')
        skills = validated_data.pop('skills', [])
        location = validated_data.pop('location', '')

        user = User.objects.create_user(
            role=User.Role.TALENT, **validated_data
        )
        TalentProfile.objects.create(user=user, bio=bio, skills=skills, location=location)
        return user


class CompanyRegistrationSerializer(serializers.ModelSerializer):
    """Register a new Company account and its profile simultaneously."""
    password = serializers.CharField(
        write_only=True, required=True, validators=[validate_password]
    )
    password_confirm = serializers.CharField(write_only=True, required=True)
    legal_name = serializers.CharField(required=True)
    industry = serializers.CharField(required=False, allow_blank=True)
    registration_number = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = (
            'email', 'full_name', 'password', 'password_confirm',
            'legal_name', 'industry', 'registration_number'
        )

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({'password': 'Passwords do not match.'})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        legal_name = validated_data.pop('legal_name')
        industry = validated_data.pop('industry', '')
        registration_number = validated_data.pop('registration_number', '') or None

        user = User.objects.create_user(role=User.Role.COMPANY, **validated_data)
        CompanyProfile.objects.create(
            user=user,
            legal_name=legal_name,
            industry=industry,
            registration_number=registration_number,
        )
        return user


# ─── Profiles ──────────────────────────────────────────────────────────────────

class TalentProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    full_name = serializers.CharField(source='user.full_name', read_only=True)
    avatar = serializers.ImageField(source='user.avatar', read_only=True)
    is_verified = serializers.BooleanField(source='user.is_verified', read_only=True)

    class Meta:
        model = TalentProfile
        fields = (
            'id', 'email', 'full_name', 'avatar', 'is_verified',
            'bio', 'location', 'resume', 'linkedin_url',
            'portfolio_url', 'skills', 'is_open_to_work',
            'subscription_tier', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at', 'subscription_tier')


class CompanyProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    is_verified = serializers.BooleanField(source='user.is_verified', read_only=True)

    class Meta:
        model = CompanyProfile
        fields = (
            'id', 'email', 'legal_name', 'industry', 'registration_number',
            'mission_statement', 'logo', 'headquarters', 'website',
            'is_verified', 'subscription_tier', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'is_verified', 'subscription_tier', 'created_at', 'updated_at')


class UserMeSerializer(serializers.ModelSerializer):
    """Read-only serializer returning authenticated user's full context."""
    profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'email', 'full_name', 'role', 'is_verified', 'is_active', 'is_2fa_enabled', 'date_joined', 'avatar', 'profile')

    def get_profile(self, obj):
        if obj.role == User.Role.TALENT and hasattr(obj, 'talent_profile'):
            return TalentProfileSerializer(obj.talent_profile).data
        if obj.role == User.Role.COMPANY and hasattr(obj, 'company_profile'):
            return CompanyProfileSerializer(obj.company_profile).data
        return None


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({'new_password': 'Passwords do not match.'})
        return attrs


class ContactMessageSerializer(serializers.ModelSerializer):
    message = serializers.CharField(max_length=5000)

    class Meta:
        model = ContactMessage
        fields = ('id', 'name', 'email', 'subject', 'message', 'is_resolved', 'created_at')
        read_only_fields = ('id', 'is_resolved', 'created_at')
