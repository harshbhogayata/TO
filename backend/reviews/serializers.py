"""
reviews/serializers.py
Read/write serializers for company reviews.
"""
from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from .models import CompanyReview, CompanyReviewResponse, ReviewHelpful


class CompanyReviewResponseSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()

    class Meta:
        model = CompanyReviewResponse
        fields = ['id', 'author_name', 'body', 'created_at']
        read_only_fields = ['id', 'created_at']

    def get_author_name(self, obj):
        if obj.author:
            return obj.author.full_name or 'Company Representative'
        return 'Company Representative'


class CompanyReviewListSerializer(serializers.ModelSerializer):
    """
    Public-facing review list. Hides author identity when is_anonymous=True.
    """
    overall_rating = serializers.FloatField(read_only=True)
    author_display = serializers.SerializerMethodField()
    has_voted_helpful = serializers.SerializerMethodField()
    company_response = CompanyReviewResponseSerializer(read_only=True)

    class Meta:
        model = CompanyReview
        fields = [
            'id', 'company', 'author_display', 'is_anonymous', 'is_verified',
            'rating_culture', 'rating_growth', 'rating_compensation',
            'rating_management', 'rating_worklife', 'overall_rating',
            'headline', 'pros', 'cons',
            'employment_status', 'department', 'role_title', 'tenure_months',
            'helpful_count', 'has_voted_helpful',
            'company_response',
            'created_at',
        ]

    def get_author_display(self, obj):
        if obj.is_anonymous:
            return {
                'name': 'Anonymous Employee',
                'role': obj.role_title or 'Employee',
                'department': obj.department or '',
            }
        user = obj.author
        return {
            'name': user.full_name or 'Employee',
            'role': obj.role_title or 'Employee',
            'department': obj.department or '',
        }

    def get_has_voted_helpful(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return ReviewHelpful.objects.filter(
            user=request.user, review=obj,
        ).exists()


class CompanyReviewCreateSerializer(serializers.ModelSerializer):
    """
    Write serializer for creating a review.
    Enforces:
        - 1 review per company per 90 days
        - Minimum word count (20 words for pros + cons combined)
        - Rating bounds (1-5)
    """

    class Meta:
        model = CompanyReview
        fields = [
            'company', 'is_anonymous',
            'rating_culture', 'rating_growth', 'rating_compensation',
            'rating_management', 'rating_worklife',
            'headline', 'pros', 'cons',
            'employment_status', 'department', 'role_title', 'tenure_months',
        ]

    def validate(self, data):
        user = self.context['request'].user
        company = data.get('company')

        # Rate limit: 1 review per company per 90 days
        cutoff = timezone.now() - timedelta(days=90)
        recent = CompanyReview.objects.filter(
            author=user, company=company, created_at__gte=cutoff,
        ).exists()
        if recent:
            raise serializers.ValidationError(
                'You can only submit one review per company every 90 days.'
            )

        # Minimum content quality
        pros = data.get('pros', '')
        cons = data.get('cons', '')
        word_count = len(pros.split()) + len(cons.split())
        if word_count < 20:
            raise serializers.ValidationError(
                'Please write at least 20 words combined in pros and cons.'
            )

        return data

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['author'] = user

        # Auto-verify if user email domain matches company domain
        company = validated_data['company']
        if hasattr(company, 'website') and company.website:
            import re
            domain_match = re.search(r'(?:https?://)?(?:www\.)?([^/]+)', company.website)
            if domain_match:
                company_domain = domain_match.group(1).lower()
                user_domain = user.email.split('@')[-1].lower()
                if user_domain == company_domain or user_domain.endswith('.' + company_domain):
                    validated_data['is_verified'] = True

        return super().create(validated_data)


class CompanyReviewStatsSerializer(serializers.Serializer):
    """Aggregated review statistics for a company."""
    total_reviews = serializers.IntegerField()
    overall_rating = serializers.FloatField()
    avg_culture = serializers.FloatField()
    avg_growth = serializers.FloatField()
    avg_compensation = serializers.FloatField()
    avg_management = serializers.FloatField()
    avg_worklife = serializers.FloatField()
    distribution = serializers.DictField()
    department_breakdown = serializers.ListField()


class CompanyReviewResponseCreateSerializer(serializers.Serializer):
    """Create an official company response to a review."""
    body = serializers.CharField(min_length=10, max_length=2000)
