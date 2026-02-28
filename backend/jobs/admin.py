"""
jobs/admin.py
"""
from django.contrib import admin
from .models import JobPost, Application, SavedJob


@admin.register(JobPost)
class JobPostAdmin(admin.ModelAdmin):
    list_display = ['title', 'company_name', 'job_type', 'work_mode', 'status', 'views_count', 'created_at']
    list_filter = ['status', 'job_type', 'work_mode']
    search_fields = ['title', 'location', 'company__company_profile__legal_name']
    readonly_fields = ['views_count', 'created_at', 'updated_at']
    ordering = ['-created_at']

    def company_name(self, obj):
        try:
            return obj.company.company_profile.legal_name
        except Exception:
            return obj.company.email

    company_name.short_description = 'Company'


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ['applicant', 'job', 'status', 'applied_at']
    list_filter = ['status']
    search_fields = ['applicant__email', 'job__title']
    readonly_fields = ['applied_at', 'updated_at']


@admin.register(SavedJob)
class SavedJobAdmin(admin.ModelAdmin):
    list_display = ['user', 'job', 'saved_at']
