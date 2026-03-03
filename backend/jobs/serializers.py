"""
jobs/serializers.py
"""
from rest_framework import serializers
from .models import JobPost, Application, SavedJob
from accounts.serializers import CompanyProfileSerializer


class JobPostSerializer(serializers.ModelSerializer):
    """Full serializer for reading job post data."""
    company_name = serializers.SerializerMethodField()
    company_logo = serializers.SerializerMethodField()
    salary_display = serializers.ReadOnlyField()
    application_count = serializers.ReadOnlyField()
    is_saved = serializers.SerializerMethodField()
    saved_record_id = serializers.SerializerMethodField()
    has_applied = serializers.SerializerMethodField()
    match_score = serializers.SerializerMethodField()

    class Meta:
        model = JobPost
        fields = (
            'id', 'title', 'description', 'requirements', 'responsibilities',
            'job_type', 'work_mode', 'status', 'experience_level', 'location',
            'salary_min', 'salary_max', 'salary_currency', 'salary_display',
            'skills_required', 'application_deadline', 'views_count',
            'application_count', 'company_name', 'company_logo',
            'is_saved', 'saved_record_id', 'has_applied', 'match_score',
            'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'views_count', 'created_at', 'updated_at')

    def get_company_name(self, obj):
        try:
            return obj.company.company_profile.legal_name
        except Exception:
            return obj.company.full_name

    def get_company_logo(self, obj):
        try:
            logo = obj.company.company_profile.logo
            if logo:
                request = self.context.get('request')
                return request.build_absolute_uri(logo.url) if request else logo.url
        except Exception:
            pass
        return None

    def get_is_saved(self, obj):
        # Use annotation from _annotate_user_relations when available (N+1 safe)
        if hasattr(obj, '_is_saved'):
            return obj._is_saved
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return SavedJob.objects.filter(user=request.user, job=obj).exists()

    def get_saved_record_id(self, obj):
        """Return the SavedJob PK so the frontend can DELETE it to unsave."""
        # Use annotation from _annotate_user_relations when available (N+1 safe)
        if hasattr(obj, '_saved_record_id'):
            return obj._saved_record_id
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        try:
            return SavedJob.objects.get(user=request.user, job=obj).pk
        except SavedJob.DoesNotExist:
            return None

    def get_has_applied(self, obj):
        # Use annotation from _annotate_user_relations when available (N+1 safe)
        if hasattr(obj, '_has_applied'):
            return obj._has_applied
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return Application.objects.filter(applicant=request.user, job=obj).exists()

    def get_match_score(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return 0
        if request.user.role != 'TALENT' or not hasattr(request.user, 'talent_profile'):
            return 0

        try:
            from intelligence.engine.hybrid import compute_match_score
            result = compute_match_score(request.user, obj)
            return int(result.get('final_score', 0))
        except Exception:
            # Graceful fallback — simple intersection if intelligence engine unavailable
            talent_skills = set(s.lower() for s in request.user.talent_profile.skills)
            job_skills = set(s.lower() for s in obj.skills_required)
            if not job_skills:
                return 0
            match_count = len(talent_skills.intersection(job_skills))
            return min(int((match_count / len(job_skills)) * 100), 100)


class JobPostWriteSerializer(serializers.ModelSerializer):
    """Write serializer used when a company creates/updates a job post."""
    class Meta:
        model = JobPost
        fields = (
            'title', 'description', 'requirements', 'responsibilities',
            'job_type', 'work_mode', 'status', 'experience_level', 'location',
            'salary_min', 'salary_max', 'salary_currency',
            'skills_required', 'application_deadline',
        )

    def create(self, validated_data):
        validated_data['company'] = self.context['request'].user
        return super().create(validated_data)

    def validate(self, data):
        salary_min = data.get('salary_min')
        salary_max = data.get('salary_max')
        if salary_min and salary_max and salary_min > salary_max:
            raise serializers.ValidationError({'salary_min': 'Min salary cannot exceed Max salary.'})
        return data


class ApplicationSerializer(serializers.ModelSerializer):
    """Used by Talent to submit and view applications."""
    job_title = serializers.ReadOnlyField(source='job.title')
    company_name = serializers.SerializerMethodField()
    applicant_name = serializers.ReadOnlyField(source='applicant.full_name')
    applicant_email = serializers.ReadOnlyField(source='applicant.email')
    resume_url = serializers.SerializerMethodField()
    applicant_bio = serializers.SerializerMethodField()
    applicant_skills = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = (
            'id', 'job', 'job_title', 'company_name',
            'applicant', 'applicant_name', 'applicant_email',
            'cover_letter', 'status', 'applied_at', 'updated_at',
            'resume_url', 'applicant_bio', 'applicant_skills',
        )
        read_only_fields = ('id', 'job', 'applicant', 'status', 'applied_at', 'updated_at')

    def get_company_name(self, obj):
        try:
            return obj.job.company.company_profile.legal_name
        except Exception:
            return ''

    def get_resume_url(self, obj):
        try:
            resume = obj.applicant.talent_profile.resume
            if resume:
                request = self.context.get('request')
                return request.build_absolute_uri(resume.url) if request else resume.url
        except Exception:
            pass
        return None

    def get_applicant_bio(self, obj):
        try:
            return obj.applicant.talent_profile.bio
        except Exception:
            return ''

    def get_applicant_skills(self, obj):
        try:
            return obj.applicant.talent_profile.skills
        except Exception:
            return []

    def create(self, validated_data):
        from django.db import IntegrityError
        from rest_framework.exceptions import ValidationError
        try:
            return super().create(validated_data)
        except IntegrityError:
            raise ValidationError({'detail': 'You have already applied to this job.'})


class ApplicationStatusSerializer(serializers.ModelSerializer):
    """Company-side serializer to update application status and notes."""
    class Meta:
        model = Application
        fields = ('status', 'notes')


class SavedJobSerializer(serializers.ModelSerializer):
    job = JobPostSerializer(read_only=True)
    job_id = serializers.PrimaryKeyRelatedField(
        queryset=JobPost.objects.all(), write_only=True, source='job'
    )

    class Meta:
        model = SavedJob
        fields = ('id', 'job', 'job_id', 'saved_at')
        read_only_fields = ('id', 'saved_at')

    def create(self, validated_data):
        from django.db import IntegrityError
        from rest_framework.exceptions import ValidationError
        validated_data['user'] = self.context['request'].user
        try:
            return super().create(validated_data)
        except IntegrityError:
            raise ValidationError({'detail': 'You have already saved this job.'})
