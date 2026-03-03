"""
reviews/admin.py
"""
from django.contrib import admin

from .models import CompanyReview, CompanyReviewResponse, ReviewHelpful


class CompanyReviewResponseInline(admin.StackedInline):
    model = CompanyReviewResponse
    extra = 0
    readonly_fields = ('created_at',)


@admin.register(CompanyReview)
class CompanyReviewAdmin(admin.ModelAdmin):
    list_display = (
        'role_title', 'company', 'overall_rating', 'moderation_status',
        'is_verified', 'is_anonymous', 'helpful_count', 'created_at',
    )
    list_filter = ('moderation_status', 'is_verified', 'is_anonymous', 'employment_status')
    search_fields = ('role_title', 'department', 'pros', 'cons', 'company__legal_name')
    readonly_fields = ('id', 'helpful_count', 'created_at', 'updated_at')
    inlines = [CompanyReviewResponseInline]
    actions = ['approve_reviews', 'reject_reviews']

    @admin.action(description='Approve selected reviews')
    def approve_reviews(self, request, queryset):
        count = queryset.filter(moderation_status='pending').update(moderation_status='approved')
        self.message_user(request, f'{count} reviews approved.')

    @admin.action(description='Reject selected reviews')
    def reject_reviews(self, request, queryset):
        count = queryset.filter(moderation_status='pending').update(moderation_status='rejected')
        self.message_user(request, f'{count} reviews rejected.')


@admin.register(ReviewHelpful)
class ReviewHelpfulAdmin(admin.ModelAdmin):
    list_display = ('user', 'review', 'created_at')
    readonly_fields = ('created_at',)
