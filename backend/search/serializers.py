"""
search/serializers.py
Serializers for search API responses — unified results, suggestions, analytics.
Designed for zero N+1 queries via eager-loaded querysets from the views.
"""
from rest_framework import serializers
from jobs.models import JobPost
from accounts.models import TalentProfile, CompanyProfile
from .models import SearchAnalytics


# ─── Job search result ───────────────────────────────────────────────────────

class JobSearchResultSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for job search results.
    Includes rank, company info, and skill match — all from pre-annotated queryset.
    """
    company_name = serializers.SerializerMethodField()
    company_logo = serializers.SerializerMethodField()
    salary_display = serializers.ReadOnlyField()
    rank = serializers.FloatField(read_only=True, default=0.0)
    headline = serializers.CharField(read_only=True, default='')
    match_score = serializers.SerializerMethodField()

    class Meta:
        model = JobPost
        fields = (
            'id', 'title', 'description', 'job_type', 'work_mode',
            'experience_level', 'location', 'salary_min', 'salary_max',
            'salary_currency', 'salary_display', 'skills_required',
            'application_deadline', 'views_count', 'company_name',
            'company_logo', 'rank', 'headline', 'match_score',
            'created_at',
        )

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

    def get_match_score(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return 0
        if request.user.role != 'TALENT':
            return 0
        try:
            from intelligence.engine.hybrid import compute_match_score
            result = compute_match_score(request.user, obj)
            return int(result.get('final_score', 0))
        except Exception:
            # Graceful fallback — simple intersection if intelligence engine unavailable
            try:
                talent_skills = set(s.lower() for s in request.user.talent_profile.skills)
            except Exception:
                return 0
            job_skills = set(s.lower() for s in (obj.skills_required or []))
            if not job_skills:
                return 0
            return min(int((len(talent_skills & job_skills) / len(job_skills)) * 100), 100)


# ─── Talent search result ────────────────────────────────────────────────────

class TalentSearchResultSerializer(serializers.ModelSerializer):
    """Serializer for talent profile search results."""
    full_name = serializers.CharField(source='user.full_name', read_only=True)
    avatar = serializers.SerializerMethodField()
    rank = serializers.FloatField(read_only=True, default=0.0)

    class Meta:
        model = TalentProfile
        fields = (
            'id', 'full_name', 'avatar', 'bio', 'location',
            'skills', 'is_open_to_work', 'linkedin_url',
            'portfolio_url', 'rank',
        )

    def get_avatar(self, obj):
        try:
            avatar = obj.user.avatar
            if avatar:
                request = self.context.get('request')
                return request.build_absolute_uri(avatar.url) if request else avatar.url
        except Exception:
            pass
        return None


# ─── Company search result ───────────────────────────────────────────────────

class CompanySearchResultSerializer(serializers.ModelSerializer):
    """Serializer for company profile search results."""
    logo_url = serializers.SerializerMethodField()
    rank = serializers.FloatField(read_only=True, default=0.0)

    class Meta:
        model = CompanyProfile
        fields = (
            'id', 'legal_name', 'industry', 'mission_statement',
            'headquarters', 'website', 'logo_url', 'is_verified',
            'rank',
        )

    def get_logo_url(self, obj):
        try:
            if obj.logo:
                request = self.context.get('request')
                return request.build_absolute_uri(obj.logo.url) if request else obj.logo.url
        except Exception:
            pass
        return None


# ─── Unified search result ───────────────────────────────────────────────────

class UnifiedSearchResultSerializer(serializers.Serializer):
    """
    Wrapper serializer for unified search across all entity types.
    Returns typed results with a consistent structure.
    """
    entity_type = serializers.CharField()
    id = serializers.IntegerField()
    title = serializers.CharField()
    subtitle = serializers.CharField(allow_blank=True, default='')
    description = serializers.CharField(allow_blank=True, default='')
    image_url = serializers.CharField(allow_null=True, default=None)
    rank = serializers.FloatField(default=0.0)
    url = serializers.CharField(default='')
    meta = serializers.DictField(default=dict)


# ─── Autocomplete suggestion ─────────────────────────────────────────────────

class SearchSuggestionSerializer(serializers.Serializer):
    """Serializer for autocomplete suggestions."""
    text = serializers.CharField()
    entity_type = serializers.CharField()
    count = serializers.IntegerField(default=0)


# ─── Search analytics ────────────────────────────────────────────────────────

class SearchAnalyticsSerializer(serializers.ModelSerializer):
    """Read-only serializer for search analytics (admin use)."""
    class Meta:
        model = SearchAnalytics
        fields = '__all__'
        read_only_fields = ('id', 'created_at')


class SearchClickSerializer(serializers.Serializer):
    """Serializer for recording search result clicks."""
    query = serializers.CharField(max_length=500)
    entity_type = serializers.ChoiceField(choices=SearchAnalytics.EntityType.choices)
    result_id = serializers.IntegerField()
    position = serializers.IntegerField(min_value=1)


class TrendingSearchSerializer(serializers.Serializer):
    """Serializer for trending search response items."""
    query = serializers.CharField()
    count = serializers.IntegerField()
    entity_type = serializers.CharField(default='all')
