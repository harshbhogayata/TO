"""
accounts/models.py
Custom User model with role-based access for TalentOrbit.
Supports three distinct account types: TALENT, COMPANY, ADMIN.
"""
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    """Custom manager for the TalentOrbit User model."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email address is required.')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('role', User.Role.ADMIN)
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Central User model for TalentOrbit.
    Uses email as the primary identifier.
    Role differentiates between Talent seekers, Companies, and platform Admins.
    """

    class Role(models.TextChoices):
        TALENT = 'TALENT', 'Talent'
        COMPANY = 'COMPANY', 'Company'
        ADMIN = 'ADMIN', 'Admin'

    email = models.EmailField(unique=True, verbose_name='Email Address')
    full_name = models.CharField(max_length=255, blank=True)
    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.TALENT
    )
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)

    # 2FA — signed at rest via accounts.crypto
    totp_secret = models.CharField(max_length=128, blank=True, null=True)
    is_2fa_enabled = models.BooleanField(default=False)

    date_joined = models.DateTimeField(default=timezone.now)
    last_updated = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-date_joined']

    def __str__(self):
        return f'{self.email} ({self.role})'

    @property
    def is_talent(self):
        return self.role == self.Role.TALENT

    @property
    def is_company(self):
        return self.role == self.Role.COMPANY


class TalentProfile(models.Model):
    """
    Extended profile for users with TALENT role.
    Tracks professional info, skills, bio, and resume.
    """
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='talent_profile'
    )
    bio = models.TextField(blank=True, max_length=500)
    location = models.CharField(max_length=150, blank=True)
    resume = models.FileField(upload_to='resumes/', null=True, blank=True)
    linkedin_url = models.URLField(blank=True)
    portfolio_url = models.URLField(blank=True)
    skills = models.JSONField(default=list, help_text='Flat list of skill strings')
    is_open_to_work = models.BooleanField(default=True)
    subscription_tier = models.CharField(
        max_length=50, default='free',
        choices=[('free', 'Free'), ('premium', 'Premium')]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Talent Profile'

    def __str__(self):
        return f'Talent: {self.user.full_name}'


class CompanyProfile(models.Model):
    """
    Extended profile for users with COMPANY role.
    Represents an onboarded organization on the platform.
    """
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='company_profile'
    )
    legal_name = models.CharField(max_length=255)
    industry = models.CharField(max_length=150, blank=True)
    registration_number = models.CharField(max_length=100, blank=True, null=True, unique=True)
    mission_statement = models.TextField(blank=True, max_length=500)
    logo = models.ImageField(upload_to='company_logos/', null=True, blank=True)
    headquarters = models.CharField(max_length=200, blank=True)
    website = models.URLField(blank=True)
    is_verified = models.BooleanField(default=False)
    subscription_tier = models.CharField(
        max_length=50, default='free',
        choices=[('free', 'Free'), ('starter', 'Starter'), ('professional', 'Professional'), ('enterprise', 'Enterprise')]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Company Profile'
        verbose_name_plural = 'Company Profiles'

    def __str__(self):
        return self.legal_name


class ContactMessage(models.Model):
    """
    General purpose contact model for HelpDesk, About Us, and Support inquiries.
    """
    name = models.CharField(max_length=150)
    email = models.EmailField()
    subject = models.CharField(max_length=255, blank=True)
    message = models.TextField(max_length=5000)
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Contact Message'
        verbose_name_plural = 'Contact Messages'
        ordering = ['-created_at']

    def __str__(self):
        return f"Message from {self.name} - {self.email}"
