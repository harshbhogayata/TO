"""
compliance/admin.py
Phase 6 — Django Admin interfaces for compliance models.
"""
from django.contrib import admin
from django.utils.html import format_html, escape

from compliance.models import (
    AuditLog,
    PolicyVersion,
    ConsentRecord,
    DataExportRequest,
    DataDeletionRequest,
    Team,
    TeamMember,
    TeamInvitation,
)


# ═══════════════════════════════════════════════════════════════════════════════
# AUDIT LOG
# ═══════════════════════════════════════════════════════════════════════════════

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'created_at', 'actor_display', 'action', 'category',
        'resource_type', 'resource_id', 'ip_address', 'integrity_badge',
    ]
    list_filter = ['action', 'category', 'created_at']
    search_fields = [
        'description', 'actor_email', 'resource_id',
        'ip_address', 'request_id',
    ]
    readonly_fields = [
        'id', 'actor', 'actor_email', 'actor_role', 'action', 'category',
        'description', 'resource_type', 'resource_id', 'changes',
        'ip_address', 'user_agent', 'request_id', 'checksum',
        'previous_checksum', 'created_at', 'integrity_badge',
    ]
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description='Actor')
    def actor_display(self, obj):
        if obj.actor:
            return f'{obj.actor_email} ({obj.actor_role})'
        if obj.actor_email:
            return f'{obj.actor_email} [deleted]'
        return 'System'

    @admin.display(description='Integrity')
    def integrity_badge(self, obj):
        valid = obj.verify_integrity()
        if valid:
            return format_html(
                '<span style="color:green;font-weight:bold;">✓ Valid</span>'
            )
        return format_html(
            '<span style="color:red;font-weight:bold;">✗ Tampered</span>'
        )


# ═══════════════════════════════════════════════════════════════════════════════
# POLICIES & CONSENT
# ═══════════════════════════════════════════════════════════════════════════════

@admin.register(PolicyVersion)
class PolicyVersionAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'policy_type', 'version', 'title', 'is_active',
        'requires_re_consent', 'effective_date', 'published_at',
    ]
    list_filter = ['policy_type', 'is_active', 'requires_re_consent']
    search_fields = ['title', 'version']
    readonly_fields = ['published_at', 'created_by']

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ConsentRecord)
class ConsentRecordAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user', 'policy_display', 'consented_at',
        'status_badge', 'ip_address',
    ]
    list_filter = ['policy_version__policy_type', 'withdrawn_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    readonly_fields = [
        'user', 'policy_version', 'consented_at', 'ip_address',
        'user_agent', 'withdrawn_at', 'withdrawal_reason',
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description='Policy')
    def policy_display(self, obj):
        pv = obj.policy_version
        return f'{pv.get_policy_type_display()} v{pv.version}'

    @admin.display(description='Status')
    def status_badge(self, obj):
        if obj.withdrawn_at:
            return format_html(
                '<span style="color:orange;font-weight:bold;">Withdrawn</span>'
            )
        return format_html(
            '<span style="color:green;font-weight:bold;">Active</span>'
        )


# ═══════════════════════════════════════════════════════════════════════════════
# GDPR REQUESTS
# ═══════════════════════════════════════════════════════════════════════════════

@admin.register(DataExportRequest)
class DataExportRequestAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user', 'status', 'requested_at', 'completed_at',
        'file_size_display', 'expires_at',
    ]
    list_filter = ['status', 'requested_at']
    search_fields = ['user__email']
    readonly_fields = [
        'user', 'status', 'requested_at', 'completed_at', 'download_token',
        'file_path', 'file_size_bytes', 'expires_at', 'error_message',
    ]

    def has_add_permission(self, request):
        return False

    @admin.display(description='File size')
    def file_size_display(self, obj):
        if obj.file_size_bytes is None:
            return '—'
        kb = obj.file_size_bytes / 1024
        if kb < 1024:
            return f'{kb:.1f} KB'
        return f'{kb / 1024:.1f} MB'


@admin.register(DataDeletionRequest)
class DataDeletionRequestAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user_email', 'status', 'requested_at',
        'confirmed_at', 'cooling_off_ends_at', 'processing_started_at',
    ]
    list_filter = ['status', 'requested_at']
    search_fields = ['user__email', 'user_email']
    readonly_fields = [
        'user', 'user_email', 'status', 'reason', 'requested_at',
        'confirmed_at', 'cooling_off_ends_at', 'processing_started_at',
        'cancelled_at', 'confirmation_token', 'cancellation_token',
        'deletion_summary',
    ]

    def has_add_permission(self, request):
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# TEAMS
# ═══════════════════════════════════════════════════════════════════════════════

class TeamMemberInline(admin.TabularInline):
    model = TeamMember
    extra = 0
    readonly_fields = ['user', 'role', 'invited_by', 'joined_at', 'is_active']

    def has_add_permission(self, request, obj=None):
        return False


class TeamInvitationInline(admin.TabularInline):
    model = TeamInvitation
    extra = 0
    readonly_fields = [
        'email', 'role', 'invited_by', 'status', 'created_at', 'expires_at',
    ]
    fields = ['email', 'role', 'status', 'invited_by', 'created_at', 'expires_at']

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'name', 'company', 'member_count_display',
        'max_seats', 'created_at',
    ]
    search_fields = ['name', 'company__legal_name']
    readonly_fields = ['company', 'created_at']
    inlines = [TeamMemberInline, TeamInvitationInline]

    @admin.display(description='Members')
    def member_count_display(self, obj):
        active = obj.members.filter(is_active=True).count()
        return f'{active}/{obj.max_seats}'


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ['id', 'team', 'user', 'role', 'is_active', 'joined_at']
    list_filter = ['role', 'is_active']
    search_fields = ['user__email', 'team__name']
    readonly_fields = [
        'team', 'user', 'role', 'invited_by', 'joined_at',
        'is_active', 'deactivated_at',
    ]


@admin.register(TeamInvitation)
class TeamInvitationAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'team', 'email', 'role', 'status',
        'invited_by', 'created_at', 'expires_at',
    ]
    list_filter = ['status', 'role', 'created_at']
    search_fields = ['email', 'team__name']
    readonly_fields = [
        'team', 'email', 'role', 'token', 'invited_by',
        'status', 'message', 'created_at', 'expires_at', 'responded_at',
    ]
