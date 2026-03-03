"""
compliance/serializers.py
Phase 6 — Serializers for all compliance endpoints.
"""
from rest_framework import serializers
from django.utils import timezone

from .models import (
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

class AuditLogSerializer(serializers.ModelSerializer):
    """Read-only serializer for the admin audit log viewer."""

    actor_display = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = (
            'id', 'actor', 'actor_email', 'actor_role', 'actor_display',
            'action', 'category', 'description',
            'resource_type', 'resource_id', 'changes',
            'ip_address', 'user_agent', 'request_id',
            'checksum', 'previous_checksum',
            'created_at',
        )
        read_only_fields = fields

    def get_actor_display(self, obj):
        if obj.actor:
            return obj.actor.full_name or obj.actor.email
        return obj.actor_email or 'System'


class AuditLogFilterSerializer(serializers.Serializer):
    """Query parameter validation for audit log list endpoint."""
    action = serializers.CharField(required=False, allow_blank=True)
    category = serializers.CharField(required=False, allow_blank=True)
    actor = serializers.IntegerField(required=False)
    resource_type = serializers.CharField(required=False, allow_blank=True)
    resource_id = serializers.CharField(required=False, allow_blank=True)
    ip_address = serializers.CharField(required=False, allow_blank=True)
    date_from = serializers.DateTimeField(required=False)
    date_to = serializers.DateTimeField(required=False)
    search = serializers.CharField(required=False, allow_blank=True)


# ═══════════════════════════════════════════════════════════════════════════════
# POLICY VERSIONING
# ═══════════════════════════════════════════════════════════════════════════════

class PolicyVersionListSerializer(serializers.ModelSerializer):
    """Light serializer for listing policies."""

    class Meta:
        model = PolicyVersion
        fields = (
            'id', 'policy_type', 'version', 'title', 'summary',
            'effective_date', 'is_active', 'requires_re_consent',
            'published_at',
        )
        read_only_fields = fields


class PolicyVersionDetailSerializer(serializers.ModelSerializer):
    """Full serializer including content."""

    class Meta:
        model = PolicyVersion
        fields = (
            'id', 'policy_type', 'version', 'title', 'summary',
            'content', 'effective_date', 'is_active',
            'requires_re_consent', 'published_at', 'created_by',
        )
        read_only_fields = ('id', 'published_at', 'created_by')


class PolicyVersionCreateSerializer(serializers.ModelSerializer):
    """Admin serializer for creating policy versions."""

    class Meta:
        model = PolicyVersion
        fields = (
            'policy_type', 'version', 'title', 'summary',
            'content', 'effective_date', 'is_active',
            'requires_re_consent',
        )

    def validate(self, attrs):
        # Ensure version is unique for this policy type
        if PolicyVersion.objects.filter(
            policy_type=attrs['policy_type'],
            version=attrs['version'],
        ).exists():
            raise serializers.ValidationError({
                'version': f'Version {attrs["version"]} already exists for this policy type.',
            })
        return attrs


# ═══════════════════════════════════════════════════════════════════════════════
# CONSENT
# ═══════════════════════════════════════════════════════════════════════════════

class ConsentRecordSerializer(serializers.ModelSerializer):
    """Read-only serializer for viewing consent records."""
    policy_type = serializers.CharField(source='policy_version.policy_type', read_only=True)
    policy_version_str = serializers.CharField(source='policy_version.version', read_only=True)
    policy_title = serializers.CharField(source='policy_version.title', read_only=True)
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = ConsentRecord
        fields = (
            'id', 'policy_version', 'policy_type', 'policy_version_str',
            'policy_title', 'consented_at', 'is_active',
            'withdrawn_at', 'withdrawal_reason',
        )
        read_only_fields = fields


class GrantConsentSerializer(serializers.Serializer):
    """Input for granting consent to one or more policies."""
    policy_version_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        help_text='List of PolicyVersion IDs to consent to.',
    )

    def validate_policy_version_ids(self, value):
        existing = set(
            PolicyVersion.objects.filter(
                pk__in=value,
                is_active=True,
            ).values_list('pk', flat=True)
        )
        missing = set(value) - existing
        if missing:
            raise serializers.ValidationError(
                f'Policy versions not found or inactive: {sorted(missing)}'
            )
        return value


class WithdrawConsentSerializer(serializers.Serializer):
    """Input for withdrawing consent from a policy."""
    policy_version_id = serializers.IntegerField()
    reason = serializers.CharField(required=False, allow_blank=True, max_length=1000)


# ═══════════════════════════════════════════════════════════════════════════════
# GDPR DATA EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

class DataExportRequestSerializer(serializers.ModelSerializer):
    """Read-only serializer for viewing export requests."""
    is_downloadable = serializers.BooleanField(read_only=True)

    class Meta:
        model = DataExportRequest
        fields = (
            'id', 'status', 'requested_at', 'processing_started_at',
            'completed_at', 'file_size_bytes', 'expires_at',
            'is_downloadable', 'download_token', 'error_message',
        )
        read_only_fields = fields


# ═══════════════════════════════════════════════════════════════════════════════
# GDPR DATA DELETION
# ═══════════════════════════════════════════════════════════════════════════════

class DataDeletionRequestSerializer(serializers.ModelSerializer):
    """Read-only serializer for viewing deletion requests."""
    is_cancellable = serializers.BooleanField(read_only=True)
    cooling_off_remaining_seconds = serializers.SerializerMethodField()

    class Meta:
        model = DataDeletionRequest
        fields = (
            'id', 'status', 'reason', 'requested_at',
            'confirmed_at', 'cooling_off_ends_at', 'cancelled_at',
            'completed_at', 'is_cancellable', 'cancellation_token',
            'cooling_off_remaining_seconds', 'deletion_summary',
        )
        read_only_fields = fields

    def get_cooling_off_remaining_seconds(self, obj):
        remaining = obj.cooling_off_remaining
        if remaining is None:
            return None
        return int(remaining.total_seconds())


class CreateDeletionRequestSerializer(serializers.Serializer):
    """Input for creating a data deletion request."""
    reason = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    password = serializers.CharField(
        required=True,
        help_text='Current password for re-authentication.',
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TEAM
# ═══════════════════════════════════════════════════════════════════════════════

class TeamSerializer(serializers.ModelSerializer):
    """Team overview serializer."""
    max_seats = serializers.IntegerField(read_only=True)
    current_seat_count = serializers.IntegerField(read_only=True)
    seats_available = serializers.IntegerField(read_only=True)
    is_at_capacity = serializers.BooleanField(read_only=True)
    company_name = serializers.CharField(
        source='company.legal_name', read_only=True,
    )
    subscription_tier = serializers.CharField(
        source='company.subscription_tier', read_only=True,
    )

    class Meta:
        model = Team
        fields = (
            'id', 'name', 'company_name', 'subscription_tier',
            'max_seats', 'current_seat_count', 'seats_available',
            'is_at_capacity', 'created_at', 'updated_at',
        )
        read_only_fields = (
            'id', 'company_name', 'subscription_tier',
            'max_seats', 'current_seat_count', 'seats_available',
            'is_at_capacity', 'created_at', 'updated_at',
        )


class TeamMemberSerializer(serializers.ModelSerializer):
    """Serializer for team member listing."""
    email = serializers.EmailField(source='user.email', read_only=True)
    full_name = serializers.CharField(source='user.full_name', read_only=True)
    avatar = serializers.ImageField(source='user.avatar', read_only=True)
    is_owner = serializers.BooleanField(read_only=True)
    can_manage_members = serializers.BooleanField(read_only=True)
    can_manage_jobs = serializers.BooleanField(read_only=True)
    invited_by_email = serializers.EmailField(
        source='invited_by.email', read_only=True, default=None,
    )

    class Meta:
        model = TeamMember
        fields = (
            'id', 'user', 'email', 'full_name', 'avatar',
            'role', 'is_owner', 'can_manage_members', 'can_manage_jobs',
            'invited_by', 'invited_by_email', 'is_active',
            'joined_at', 'deactivated_at',
        )
        read_only_fields = (
            'id', 'user', 'email', 'full_name', 'avatar',
            'is_owner', 'can_manage_members', 'can_manage_jobs',
            'invited_by', 'invited_by_email', 'is_active',
            'joined_at', 'deactivated_at',
        )


class ChangeTeamMemberRoleSerializer(serializers.Serializer):
    """Input for changing a team member's role."""
    role = serializers.ChoiceField(choices=TeamMember.Role.choices)

    def validate_role(self, value):
        if value == TeamMember.Role.OWNER:
            raise serializers.ValidationError(
                'Cannot assign OWNER role directly. Use the transfer-ownership endpoint.'
            )
        return value


class TeamInvitationSerializer(serializers.ModelSerializer):
    """Read-only serializer for viewing invitations."""
    invited_by_email = serializers.EmailField(
        source='invited_by.email', read_only=True, default=None,
    )
    team_name = serializers.CharField(source='team.name', read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    is_actionable = serializers.BooleanField(read_only=True)

    class Meta:
        model = TeamInvitation
        fields = (
            'id', 'email', 'role', 'team_name',
            'invited_by', 'invited_by_email', 'message',
            'status', 'is_expired', 'is_actionable',
            'created_at', 'expires_at', 'responded_at',
        )
        read_only_fields = fields


class CreateTeamInvitationSerializer(serializers.Serializer):
    """Input for creating a team invitation."""
    email = serializers.EmailField()
    role = serializers.ChoiceField(
        choices=[
            (TeamMember.Role.ADMIN, 'Admin'),
            (TeamMember.Role.RECRUITER, 'Recruiter'),
            (TeamMember.Role.VIEWER, 'Viewer'),
        ],
        default=TeamMember.Role.RECRUITER,
    )
    message = serializers.CharField(required=False, allow_blank=True, max_length=500)

    def validate_email(self, value):
        return value.lower().strip()


# ═══════════════════════════════════════════════════════════════════════════════
# SECURITY.TXT
# ═══════════════════════════════════════════════════════════════════════════════

class SecurityInfoSerializer(serializers.Serializer):
    """Output for bug bounty / security info endpoint."""
    contact = serializers.CharField()
    policy = serializers.URLField()
    acknowledgements = serializers.URLField()
    bug_bounty = serializers.URLField()
    preferred_languages = serializers.CharField()
    scope = serializers.ListField(child=serializers.CharField())
    out_of_scope = serializers.ListField(child=serializers.CharField())
    severity_levels = serializers.DictField()
