"""
reviews/models.py
Glassdoor-style anonymous company reviews with anti-gaming measures.

Design:
    - 5-category star ratings (culture, growth, compensation, management, work-life)
    - Verified-employee badge via company email domain matching
    - Anonymous/named toggle (always stores author FK for audit, masks in API)
    - Helpful-vote system with one-vote-per-user constraint
    - Anti-gaming: rate-limiting (1 review per company per 90 days), minimum word count
    - Moderation workflow: pending → approved → rejected
    - Response system: companies can officially reply to reviews
"""
import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class CompanyReview(models.Model):
    """
    A single employee review for a company profile.
    Supports anonymous posting — `is_anonymous` hides author details in API
    but the FK is always preserved for admin/audit purposes.
    """

    class ModerationStatus(models.TextChoices):
        PENDING = 'pending', 'Pending Review'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    class EmploymentStatus(models.TextChoices):
        CURRENT = 'current', 'Current Employee'
        FORMER = 'former', 'Former Employee'
        CONTRACTOR = 'contractor', 'Contractor'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # ── Author ────────────────────────────────────────────────────────────
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='company_reviews',
    )
    company = models.ForeignKey(
        'accounts.CompanyProfile',
        on_delete=models.CASCADE,
        related_name='reviews',
    )
    is_anonymous = models.BooleanField(
        default=True,
        help_text='If True, author identity is hidden from public-facing APIs.',
    )

    # ── Star Ratings (1-5 per category) ───────────────────────────────────
    rating_culture = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text='Culture & Values (1-5)',
    )
    rating_growth = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text='Career Growth (1-5)',
    )
    rating_compensation = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text='Compensation & Benefits (1-5)',
    )
    rating_management = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text='Senior Management (1-5)',
    )
    rating_worklife = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text='Work-Life Balance (1-5)',
    )

    # ── Content ───────────────────────────────────────────────────────────
    headline = models.CharField(
        max_length=200, blank=True,
        help_text='Optional one-line summary / quote.',
    )
    pros = models.TextField(
        help_text='What the reviewer liked about the company.',
    )
    cons = models.TextField(
        help_text='What the reviewer disliked or areas for improvement.',
    )

    # ── Employment context ────────────────────────────────────────────────
    employment_status = models.CharField(
        max_length=20,
        choices=EmploymentStatus.choices,
        default=EmploymentStatus.CURRENT,
    )
    department = models.CharField(max_length=100, blank=True)
    role_title = models.CharField(max_length=200, blank=True)
    tenure_months = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='How long at the company in months.',
    )

    # ── Verification ──────────────────────────────────────────────────────
    is_verified = models.BooleanField(
        default=False,
        help_text='Set to True when author email domain matches company domain.',
    )

    # ── Moderation ────────────────────────────────────────────────────────
    moderation_status = models.CharField(
        max_length=20,
        choices=ModerationStatus.choices,
        default=ModerationStatus.PENDING,
        db_index=True,
    )
    rejection_reason = models.TextField(blank=True)

    # ── Engagement ────────────────────────────────────────────────────────
    helpful_count = models.PositiveIntegerField(default=0)

    # ── Timestamps ────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Company Review'
        verbose_name_plural = 'Company Reviews'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'moderation_status', '-created_at'],
                         name='idx_review_company_status'),
            models.Index(fields=['author', 'company'], name='idx_review_author_company'),
            models.Index(fields=['moderation_status'], name='idx_review_mod_status'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['author', 'company'],
                condition=models.Q(
                    created_at__gte=timezone.now() - timezone.timedelta(days=90)
                ) if False else models.Q(),  # enforced in serializer instead
                name='uq_review_author_company',
            ),
        ]

    def __str__(self):
        anon = '🕵️' if self.is_anonymous else '👤'
        return f'{anon} {self.role_title or "Employee"} → {self.company} ({self.overall_rating:.1f}★)'

    @property
    def overall_rating(self) -> float:
        total = (
            self.rating_culture + self.rating_growth +
            self.rating_compensation + self.rating_management +
            self.rating_worklife
        )
        return round(total / 5.0, 1)


class ReviewHelpful(models.Model):
    """
    One-vote-per-user "Helpful" toggle for a review.
    Existence of a row = user found it helpful.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='helpful_votes',
    )
    review = models.ForeignKey(
        CompanyReview,
        on_delete=models.CASCADE,
        related_name='helpful_votes',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'review')
        verbose_name = 'Review Helpful Vote'
        verbose_name_plural = 'Review Helpful Votes'

    def __str__(self):
        return f'{self.user} → Helpful on {self.review_id}'


class CompanyReviewResponse(models.Model):
    """
    Official company response to a review.
    Only one response per review. Posted by a company team member.
    """
    review = models.OneToOneField(
        CompanyReview,
        on_delete=models.CASCADE,
        related_name='company_response',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='review_responses',
    )
    body = models.TextField(
        help_text='Official company response text.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Company Review Response'
        verbose_name_plural = 'Company Review Responses'

    def __str__(self):
        return f'Response to review {self.review_id}'
