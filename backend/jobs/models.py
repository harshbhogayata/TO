"""
jobs/models.py
Job Board data models for TalentOrbit.
"""
from django.db import models
from django.conf import settings
from django.contrib.postgres.search import SearchVectorField


class JobPost(models.Model):
    """
    A job posting created by a Company.
    Includes salary, location, skills, and application tracking.
    """

    class JobType(models.TextChoices):
        FULL_TIME = 'full_time', 'Full-Time'
        PART_TIME = 'part_time', 'Part-Time'
        CONTRACT = 'contract', 'Contract'
        FREELANCE = 'freelance', 'Freelance'

    class WorkMode(models.TextChoices):
        REMOTE = 'remote', 'Remote'
        ON_SITE = 'on_site', 'On-Site'
        HYBRID = 'hybrid', 'Hybrid'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        OPEN = 'open', 'Open'
        CLOSED = 'closed', 'Closed'
        ARCHIVED = 'archived', 'Archived'

    class ExperienceLevel(models.TextChoices):
        JUNIOR = 'junior', 'Junior (1-2 years)'
        MID = 'mid', 'Mid-Level (3-5 years)'
        SENIOR = 'senior', 'Senior (5-8 years)'
        LEAD = 'lead', 'Lead / Director (8+ years)'

    company = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='job_posts',
        limit_choices_to={'role': 'COMPANY'}
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    requirements = models.TextField(blank=True)
    responsibilities = models.TextField(blank=True)

    job_type = models.CharField(max_length=20, choices=JobType.choices, default=JobType.FULL_TIME)
    work_mode = models.CharField(max_length=20, choices=WorkMode.choices, default=WorkMode.HYBRID)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN, db_index=True)
    experience_level = models.CharField(max_length=20, choices=ExperienceLevel.choices, default=ExperienceLevel.MID)

    location = models.CharField(max_length=200, blank=True)
    salary_min = models.PositiveIntegerField(null=True, blank=True)
    salary_max = models.PositiveIntegerField(null=True, blank=True)
    salary_currency = models.CharField(max_length=10, default='USD')
    skills_required = models.JSONField(default=list)

    # Pre-computed full-text search vector — updated via signal on save.
    # GIN-indexed for O(log n) lookups regardless of table size.
    search_vector = SearchVectorField(null=True, blank=True, editable=False)

    application_deadline = models.DateField(null=True, blank=True)
    views_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Job Post'
        verbose_name_plural = 'Job Posts'
        indexes = [
            models.Index(fields=['company', 'status'], name='idx_job_company_status'),
            models.Index(fields=['-created_at', 'status'], name='idx_job_created_status'),
        ]
        # NOTE: GIN index on search_vector is created via migration RunSQL
        # because Django's Index class doesn't natively support GIN on SearchVectorField.
        # See search/migrations/0002_gin_indexes.py

    def __str__(self):
        try:
            company_name = self.company.company_profile.legal_name
        except Exception:
            company_name = self.company.full_name or self.company.email
        return f'{self.title} @ {company_name}'

    @property
    def salary_display(self):
        if self.salary_min and self.salary_max:
            return f'${self.salary_min:,} – ${self.salary_max:,} {self.salary_currency}'
        return 'Undisclosed'

    @property
    def application_count(self):
        """Fallback for when queryset annotation is not available."""
        if hasattr(self, '_application_count'):
            return self._application_count
        return self.applications.count()


class Application(models.Model):
    """
    Tracks a Talent user applying to a JobPost.
    Includes a rich status workflow with timestamps.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending Review'
        REVIEWING = 'reviewing', 'Reviewing'
        SHORTLISTED = 'shortlisted', 'Shortlisted'
        INTERVIEWING = 'interviewing', 'Interviewing'
        OFFERED = 'offered', 'Offer Extended'
        REJECTED = 'rejected', 'Rejected'
        WITHDRAWN = 'withdrawn', 'Withdrawn by Applicant'

    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='applications',
        limit_choices_to={'role': 'TALENT'}
    )
    job = models.ForeignKey(
        'JobPost', on_delete=models.CASCADE, related_name='applications'
    )
    cover_letter = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )

    applied_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True, help_text='Internal recruiter notes.')

    class Meta:
        unique_together = ('applicant', 'job')
        ordering = ['-applied_at']
        verbose_name = 'Application'
        verbose_name_plural = 'Applications'

    def __str__(self):
        return f'{self.applicant.full_name} → {self.job.title}'


class SavedJob(models.Model):
    """Talent user's saved jobs (bookmarks)."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_jobs'
    )
    job = models.ForeignKey(
        JobPost, on_delete=models.CASCADE, related_name='saved_by'
    )
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'job')
        ordering = ['-saved_at']

    def __str__(self):
        return f'{self.user.email} saved "{self.job.title}"'
