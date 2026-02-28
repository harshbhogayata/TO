"""
accounts/admin.py
Register models with the Django admin panel.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User, TalentProfile, CompanyProfile, ContactMessage


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ['-date_joined']
    list_display = ['email', 'full_name', 'role', 'is_verified', 'is_active', 'date_joined']
    list_filter = ['role', 'is_verified', 'is_active']
    search_fields = ['email', 'full_name']
    readonly_fields = ['date_joined', 'last_updated']

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('full_name', 'avatar', 'role')}),
        ('Status', {'fields': ('is_active', 'is_staff', 'is_superuser', 'is_verified')}),
        ('Timestamps', {'fields': ('date_joined', 'last_updated')}),
        ('Permissions', {'fields': ('groups', 'user_permissions')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name', 'role', 'password1', 'password2'),
        }),
    )

    # Note: filter_horizontal removed — custom User model does not have
    # groups/user_permissions M2M fields unless PermissionsMixin is used
    # with proper DB migration.


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'subject', 'is_resolved', 'created_at')
    list_filter = ('is_resolved', 'created_at')
    search_fields = ('name', 'email', 'subject')
    date_hierarchy = 'created_at'


@admin.register(TalentProfile)
class TalentProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'location', 'subscription_tier', 'is_open_to_work', 'created_at']
    list_filter = ['subscription_tier', 'is_open_to_work']
    search_fields = ['user__email', 'user__full_name']


@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
    list_display = ['legal_name', 'industry', 'is_verified', 'created_at']
    list_filter = ['is_verified', 'industry']
    search_fields = ['legal_name', 'user__email']
