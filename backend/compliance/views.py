"""
compliance/views.py
Phase 6 — Trust & Compliance API views.

Endpoints:
    Audit Log (Admin only):
        GET  /api/v1/compliance/audit-logs/           — Filtered, paginated audit trail
        GET  /api/v1/compliance/audit-logs/<pk>/       — Single audit entry detail
        GET  /api/v1/compliance/audit-logs/integrity/  — Chain integrity check
        GET  /api/v1/compliance/audit-logs/stats/      — Audit statistics

    Policies (Public read, Admin write):
        GET  /api/v1/compliance/policies/              — List active policies
        GET  /api/v1/compliance/policies/<pk>/         — Policy detail with content
        POST /api/v1/compliance/policies/              — Create policy version (admin)

    Consent (Authenticated):
        GET  /api/v1/compliance/consent/               — My consent records
        POST /api/v1/compliance/consent/grant/         — Grant consent
        POST /api/v1/compliance/consent/withdraw/      — Withdraw consent
        GET  /api/v1/compliance/consent/status/        — Consent status check

    GDPR Data Export (Authenticated):
        POST /api/v1/compliance/gdpr/export/           — Request data export
        GET  /api/v1/compliance/gdpr/export/           — List my export requests
        GET  /api/v1/compliance/gdpr/export/<token>/download/ — Download export

    GDPR Data Deletion (Authenticated):
        POST /api/v1/compliance/gdpr/deletion/         — Request account deletion
        GET  /api/v1/compliance/gdpr/deletion/         — List my deletion requests
        POST /api/v1/compliance/gdpr/deletion/confirm/ — Confirm deletion
        POST /api/v1/compliance/gdpr/deletion/cancel/  — Cancel deletion

    Teams (Company users):
        GET  /api/v1/compliance/team/                  — My team overview
        POST /api/v1/compliance/team/                  — Create team
        GET  /api/v1/compliance/team/members/          — List team members
        POST /api/v1/compliance/team/invite/           — Invite member
        POST /api/v1/compliance/team/invite/<token>/accept/  — Accept invite
        POST /api/v1/compliance/team/invite/<token>/decline/ — Decline invite
        DELETE /api/v1/compliance/team/invite/<pk>/    — Revoke invitation
        PATCH /api/v1/compliance/team/members/<pk>/role/ — Change member role
        DELETE /api/v1/compliance/team/members/<pk>/   — Remove member
        GET  /api/v1/compliance/team/invitations/      — List pending invitations

    Security (Public):
        GET  /.well-known/security.txt                 — RFC 9116 security.txt
        GET  /api/v1/compliance/security/              — Bug bounty program info
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.db.models import Q, Count
from django.http import HttpResponse, FileResponse
from django.core.files.storage import default_storage
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from admin_api.views import IsAdminUser
from compliance.constants import (
    AuditAction,
    AuditCategory,
    DELETION_COOLING_OFF_DAYS,
    MAX_EXPORT_REQUESTS_PER_MONTH,
    MAX_DELETION_REQUESTS_PER_MONTH,
    SECURITY_CONTACT,
    SECURITY_POLICY_URL,
    SECURITY_ACKNOWLEDGEMENTS_URL,
    BUG_BOUNTY_URL,
    SECURITY_PREFERRED_LANGUAGES,
)
from compliance.decorators import create_audit_log
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
from compliance.serializers import (
    AuditLogSerializer,
    AuditLogFilterSerializer,
    PolicyVersionListSerializer,
    PolicyVersionDetailSerializer,
    PolicyVersionCreateSerializer,
    ConsentRecordSerializer,
    GrantConsentSerializer,
    WithdrawConsentSerializer,
    DataExportRequestSerializer,
    DataDeletionRequestSerializer,
    CreateDeletionRequestSerializer,
    TeamSerializer,
    TeamMemberSerializer,
    ChangeTeamMemberRoleSerializer,
    TeamInvitationSerializer,
    CreateTeamInvitationSerializer,
    SecurityInfoSerializer,
)
from compliance.throttling import (
    AuditLogThrottle,
    AuditIntegrityThrottle,
    PolicyCreateThrottle,
    ConsentWriteThrottle,
    DataExportThrottle,
    DataExportDownloadThrottle,
    DataDeletionThrottle,
    DeletionConfirmThrottle,
    TeamInviteThrottle,
    TeamInviteActionThrottle,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# AUDIT LOG ENDPOINTS (Admin Only)
# ═══════════════════════════════════════════════════════════════════════════════

class AuditLogListView(generics.ListAPIView):
    """
    GET /api/v1/compliance/audit-logs/
    Admin-only paginated, filterable audit log list.
    """
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdminUser]
    throttle_classes = [AuditLogThrottle]

    def get_queryset(self):
        qs = AuditLog.objects.select_related('actor').all()

        # Apply filters
        params = self.request.query_params
        if params.get('action'):
            qs = qs.filter(action=params['action'])
        if params.get('category'):
            qs = qs.filter(category=params['category'])
        if params.get('actor'):
            qs = qs.filter(actor_id=params['actor'])
        if params.get('resource_type'):
            qs = qs.filter(resource_type=params['resource_type'])
        if params.get('resource_id'):
            qs = qs.filter(resource_id=params['resource_id'])
        if params.get('ip_address'):
            qs = qs.filter(ip_address=params['ip_address'])
        if params.get('date_from'):
            qs = qs.filter(created_at__gte=params['date_from'])
        if params.get('date_to'):
            qs = qs.filter(created_at__lte=params['date_to'])
        if params.get('search'):
            search = params['search']
            qs = qs.filter(
                Q(description__icontains=search)
                | Q(actor_email__icontains=search)
                | Q(resource_id__icontains=search)
            )

        return qs


class AuditLogDetailView(generics.RetrieveAPIView):
    """GET /api/v1/compliance/audit-logs/<pk>/"""
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdminUser]
    throttle_classes = [AuditLogThrottle]
    queryset = AuditLog.objects.select_related('actor')


@api_view(['GET'])
@permission_classes([IsAdminUser])
@throttle_classes([AuditIntegrityThrottle])
def audit_log_integrity(request):
    """
    GET /api/v1/compliance/audit-logs/integrity/
    Verify the tamper-evidence chain of the audit log.
    """
    limit = int(request.query_params.get('limit', 5000))
    result = AuditLog.verify_chain(limit=min(limit, 50000))
    return Response(result)


@api_view(['GET'])
@permission_classes([IsAdminUser])
@throttle_classes([AuditLogThrottle])
def audit_log_stats(request):
    """
    GET /api/v1/compliance/audit-logs/stats/
    Aggregate statistics for the audit log dashboard.
    """
    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)

    total = AuditLog.objects.count()
    last_24h_count = AuditLog.objects.filter(created_at__gte=last_24h).count()
    last_7d_count = AuditLog.objects.filter(created_at__gte=last_7d).count()

    # Top actions in last 7 days
    top_actions = list(
        AuditLog.objects.filter(created_at__gte=last_7d)
        .values('action')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )

    # Top categories in last 7 days
    top_categories = list(
        AuditLog.objects.filter(created_at__gte=last_7d)
        .values('category')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )

    # Failed login attempts in last 24h
    failed_logins_24h = AuditLog.objects.filter(
        action=AuditLog.Action.LOGIN_FAILED,
        created_at__gte=last_24h,
    ).count()

    return Response({
        'total_entries': total,
        'last_24h': last_24h_count,
        'last_7d': last_7d_count,
        'failed_logins_24h': failed_logins_24h,
        'top_actions': top_actions,
        'top_categories': top_categories,
    })


# ═══════════════════════════════════════════════════════════════════════════════
# POLICY ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

class PolicyVersionListView(generics.ListAPIView):
    """
    GET /api/v1/compliance/policies/
    Public — list active policy versions.
    """
    serializer_class = PolicyVersionListSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = PolicyVersion.objects.filter(is_active=True)
        policy_type = self.request.query_params.get('type')
        if policy_type:
            qs = qs.filter(policy_type=policy_type)
        return qs


class PolicyVersionDetailView(generics.RetrieveAPIView):
    """GET /api/v1/compliance/policies/<pk>/"""
    serializer_class = PolicyVersionDetailSerializer
    permission_classes = [permissions.AllowAny]
    queryset = PolicyVersion.objects.all()


class PolicyVersionCreateView(generics.CreateAPIView):
    """POST /api/v1/compliance/policies/ — Admin only."""
    serializer_class = PolicyVersionCreateSerializer
    permission_classes = [IsAdminUser]
    throttle_classes = [PolicyCreateThrottle]

    def perform_create(self, serializer):
        policy = serializer.save(created_by=self.request.user)

        # If the new policy requires re-consent, invalidate ALL cached consent
        if policy.requires_re_consent and policy.is_active:
            from compliance.middleware import invalidate_consent_cache_all
            invalidate_consent_cache_all()

        create_audit_log(
            actor=self.request.user,
            action=AuditAction.CREATE,
            category=AuditCategory.COMPLIANCE,
            description=(
                f'Policy version created: {policy.get_policy_type_display()} '
                f'v{policy.version}'
            ),
            resource_type='compliance.PolicyVersion',
            resource_id=str(policy.pk),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# CONSENT ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

class MyConsentRecordsView(generics.ListAPIView):
    """GET /api/v1/compliance/consent/ — List my consent records."""
    serializer_class = ConsentRecordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ConsentRecord.objects.filter(
            user=self.request.user,
        ).select_related('policy_version')


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([ConsentWriteThrottle])
def grant_consent(request):
    """
    POST /api/v1/compliance/consent/grant/
    Body: { "policy_version_ids": [1, 2] }
    """
    serializer = GrantConsentSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    from compliance.middleware import get_audit_context
    ctx = get_audit_context()

    created = []
    already_consented = []

    for pv_id in serializer.validated_data['policy_version_ids']:
        record, was_created = ConsentRecord.objects.get_or_create(
            user=request.user,
            policy_version_id=pv_id,
            defaults={
                'ip_address': ctx.get('ip_address'),
                'user_agent': ctx.get('user_agent', ''),
            },
        )
        if was_created:
            created.append(pv_id)
            create_audit_log(
                actor=request.user,
                action=AuditAction.CONSENT_GRANT,
                category=AuditCategory.COMPLIANCE,
                description=f'Consent granted for policy version #{pv_id}',
                resource_type='compliance.ConsentRecord',
                resource_id=str(record.pk),
            )
        elif record.withdrawn_at:
            # Re-consent after withdrawal
            record.withdrawn_at = None
            record.withdrawal_reason = ''
            record.ip_address = ctx.get('ip_address')
            record.user_agent = ctx.get('user_agent', '')
            record.save(update_fields=[
                'withdrawn_at', 'withdrawal_reason',
                'ip_address', 'user_agent',
            ])
            created.append(pv_id)
        else:
            already_consented.append(pv_id)

    # Invalidate consent cache so the middleware picks up the change immediately
    if created:
        from compliance.middleware import invalidate_consent_cache
        invalidate_consent_cache(request.user.pk)

    return Response({
        'granted': created,
        'already_consented': already_consented,
    })


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([ConsentWriteThrottle])
def withdraw_consent(request):
    """
    POST /api/v1/compliance/consent/withdraw/
    Body: { "policy_version_id": 1, "reason": "..." }
    """
    serializer = WithdrawConsentSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    pv_id = serializer.validated_data['policy_version_id']
    reason = serializer.validated_data.get('reason', '')

    try:
        record = ConsentRecord.objects.get(
            user=request.user,
            policy_version_id=pv_id,
            withdrawn_at__isnull=True,
        )
    except ConsentRecord.DoesNotExist:
        return Response(
            {'error': 'No active consent found for this policy version.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    record.withdrawn_at = timezone.now()
    record.withdrawal_reason = reason
    record.save(update_fields=['withdrawn_at', 'withdrawal_reason'])

    # Invalidate consent cache so middleware re-checks on next write request
    from compliance.middleware import invalidate_consent_cache
    invalidate_consent_cache(request.user.pk)

    create_audit_log(
        actor=request.user,
        action=AuditAction.CONSENT_WITHDRAW,
        category=AuditCategory.COMPLIANCE,
        description=f'Consent withdrawn for policy version #{pv_id}',
        resource_type='compliance.ConsentRecord',
        resource_id=str(record.pk),
    )

    return Response({'message': 'Consent withdrawn successfully.'})


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def consent_status(request):
    """
    GET /api/v1/compliance/consent/status/
    Returns the user's consent status for all active policies.
    """
    active_policies = PolicyVersion.objects.filter(is_active=True)
    consented = set(
        ConsentRecord.objects.filter(
            user=request.user,
            withdrawn_at__isnull=True,
        ).values_list('policy_version_id', flat=True)
    )

    policies = []
    all_consented = True
    for p in active_policies:
        has_consent = p.pk in consented
        if not has_consent and p.requires_re_consent:
            all_consented = False
        policies.append({
            'id': p.pk,
            'type': p.policy_type,
            'version': p.version,
            'title': p.title,
            'requires_re_consent': p.requires_re_consent,
            'has_consent': has_consent,
        })

    return Response({
        'all_consented': all_consented,
        'policies': policies,
    })


# ═══════════════════════════════════════════════════════════════════════════════
# GDPR DATA EXPORT ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

class MyDataExportRequestsView(generics.ListAPIView):
    """GET /api/v1/compliance/gdpr/export/ — List my export requests."""
    serializer_class = DataExportRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return DataExportRequest.objects.filter(user=self.request.user)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([DataExportThrottle])
def request_data_export(request):
    """
    POST /api/v1/compliance/gdpr/export/
    Request a personal data export (GDPR Article 20).
    """
    user = request.user

    # Rate limit: max N exports per month
    month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    recent_count = DataExportRequest.objects.filter(
        user=user,
        requested_at__gte=month_start,
    ).count()

    if recent_count >= MAX_EXPORT_REQUESTS_PER_MONTH:
        return Response(
            {
                'error': (
                    f'You can request a maximum of {MAX_EXPORT_REQUESTS_PER_MONTH} '
                    f'data exports per month.'
                ),
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    # Check if there's already a pending/processing request
    active = DataExportRequest.objects.filter(
        user=user,
        status__in=[
            DataExportRequest.Status.PENDING,
            DataExportRequest.Status.PROCESSING,
        ],
    ).exists()

    if active:
        return Response(
            {'error': 'You already have an active export request.'},
            status=status.HTTP_409_CONFLICT,
        )

    # Create the request
    export_req = DataExportRequest.objects.create(user=user)

    # Dispatch Celery task
    from compliance.tasks import process_data_export_task
    try:
        process_data_export_task.delay(export_req.pk)
    except Exception:
        logger.exception('Failed to dispatch data export task')
        export_req.status = DataExportRequest.Status.FAILED
        export_req.error_message = 'Failed to queue export task.'
        export_req.save(update_fields=['status', 'error_message'])

    create_audit_log(
        actor=user,
        action=AuditAction.DATA_EXPORT_REQUEST,
        category=AuditCategory.COMPLIANCE,
        description=f'Data export requested (#{export_req.pk})',
        resource_type='compliance.DataExportRequest',
        resource_id=str(export_req.pk),
    )

    return Response(
        DataExportRequestSerializer(export_req).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([DataExportDownloadThrottle])
def download_data_export(request, token):
    """
    GET /api/v1/compliance/gdpr/export/<token>/download/
    Download a completed data export.
    """
    try:
        export_req = DataExportRequest.objects.get(
            download_token=token,
            user=request.user,
        )
    except DataExportRequest.DoesNotExist:
        return Response(
            {'error': 'Export not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not export_req.is_downloadable:
        # Safety net: if the export has exceeded its TTL but wasn't cleaned up
        # by the periodic task, mark it as expired now and delete the file.
        if (
            export_req.status == DataExportRequest.Status.COMPLETED
            and export_req.expires_at
            and timezone.now() >= export_req.expires_at
        ):
            if export_req.file_path:
                try:
                    default_storage.delete(export_req.file_path)
                except Exception:
                    logger.warning('Safety-net cleanup failed: %s', export_req.file_path)
            export_req.status = DataExportRequest.Status.EXPIRED
            export_req.file_path = ''
            export_req.save(update_fields=['status', 'file_path'])
            logger.info(
                'Safety-net: expired export #%s cleaned up on download attempt.',
                export_req.pk,
            )

        return Response(
            {'error': 'Export is not available for download (expired or not yet ready).'},
            status=status.HTTP_410_GONE,
        )

    create_audit_log(
        actor=request.user,
        action=AuditAction.DATA_EXPORT_DOWNLOAD,
        category=AuditCategory.COMPLIANCE,
        description=f'Data export downloaded (#{export_req.pk})',
        resource_type='compliance.DataExportRequest',
        resource_id=str(export_req.pk),
    )

    # Serve the file
    try:
        file_obj = default_storage.open(export_req.file_path, 'rb')
        response = FileResponse(
            file_obj,
            as_attachment=True,
            filename=f'talentorbit-data-export-{request.user.pk}.zip',
        )
        response['Content-Type'] = 'application/zip'
        return response
    except Exception:
        logger.exception('Failed to serve export file: %s', export_req.file_path)
        return Response(
            {'error': 'Failed to retrieve export file.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# GDPR DATA DELETION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

class MyDataDeletionRequestsView(generics.ListAPIView):
    """GET /api/v1/compliance/gdpr/deletion/ — List my deletion requests."""
    serializer_class = DataDeletionRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return DataDeletionRequest.objects.filter(
            Q(user=self.request.user) | Q(user_email=self.request.user.email)
        )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([DataDeletionThrottle])
def request_data_deletion(request):
    """
    POST /api/v1/compliance/gdpr/deletion/
    Request permanent account & data deletion (GDPR Article 17).
    Requires password re-authentication.
    """
    serializer = CreateDeletionRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    user = request.user

    # Re-authenticate
    if not user.check_password(serializer.validated_data['password']):
        return Response(
            {'error': 'Invalid password.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Rate limit
    month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    recent_count = DataDeletionRequest.objects.filter(
        user=user,
        requested_at__gte=month_start,
    ).exclude(status=DataDeletionRequest.Status.CANCELLED).count()

    if recent_count >= MAX_DELETION_REQUESTS_PER_MONTH:
        return Response(
            {'error': 'Maximum deletion requests reached for this month.'},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    # Check for active request
    active = DataDeletionRequest.objects.filter(
        user=user,
        status__in=[
            DataDeletionRequest.Status.PENDING,
            DataDeletionRequest.Status.COOLING_OFF,
            DataDeletionRequest.Status.PROCESSING,
        ],
    ).exists()

    if active:
        return Response(
            {'error': 'You already have an active deletion request.'},
            status=status.HTTP_409_CONFLICT,
        )

    # Create the request
    deletion_req = DataDeletionRequest.objects.create(
        user=user,
        user_email=user.email,
        reason=serializer.validated_data.get('reason', ''),
    )

    # Send confirmation email
    from compliance.tasks import send_deletion_confirmation_email_task
    try:
        send_deletion_confirmation_email_task.delay(deletion_req.pk)
    except Exception:
        logger.exception('Failed to dispatch deletion confirmation email')

    create_audit_log(
        actor=user,
        action=AuditAction.DATA_DELETION_REQUEST,
        category=AuditCategory.COMPLIANCE,
        description=f'Data deletion requested (#{deletion_req.pk})',
        resource_type='compliance.DataDeletionRequest',
        resource_id=str(deletion_req.pk),
    )

    return Response(
        DataDeletionRequestSerializer(deletion_req).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
@throttle_classes([DeletionConfirmThrottle])
def confirm_data_deletion(request):
    """
    POST /api/v1/compliance/gdpr/deletion/confirm/
    Body: { "token": "..." }
    Confirms the deletion request and starts the cooling-off period.
    """
    token = request.data.get('token', '')
    if not token:
        return Response(
            {'error': 'Confirmation token is required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        req = DataDeletionRequest.objects.get(
            confirmation_token=token,
            status=DataDeletionRequest.Status.PENDING,
        )
    except DataDeletionRequest.DoesNotExist:
        return Response(
            {'error': 'Invalid or expired confirmation token.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    req.status = DataDeletionRequest.Status.COOLING_OFF
    req.confirmed_at = timezone.now()
    req.cooling_off_ends_at = timezone.now() + timedelta(days=DELETION_COOLING_OFF_DAYS)
    req.save(update_fields=['status', 'confirmed_at', 'cooling_off_ends_at'])

    create_audit_log(
        actor=req.user,
        action=AuditAction.DATA_DELETION_REQUEST,
        category=AuditCategory.COMPLIANCE,
        description=(
            f'Data deletion confirmed — cooling-off until '
            f'{req.cooling_off_ends_at.strftime("%Y-%m-%d %H:%M UTC")}'
        ),
        resource_type='compliance.DataDeletionRequest',
        resource_id=str(req.pk),
    )

    return Response({
        'message': (
            f'Deletion confirmed. Your data will be permanently deleted after '
            f'a {DELETION_COOLING_OFF_DAYS}-day cooling-off period. '
            f'You can cancel anytime before that.'
        ),
        'cooling_off_ends_at': req.cooling_off_ends_at.isoformat(),
    })


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
@throttle_classes([DeletionConfirmThrottle])
def cancel_data_deletion(request):
    """
    POST /api/v1/compliance/gdpr/deletion/cancel/
    Body: { "token": "..." }
    Cancels a pending or cooling-off deletion request.
    """
    token = request.data.get('token', '')
    if not token:
        return Response(
            {'error': 'Cancellation token is required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        req = DataDeletionRequest.objects.get(
            cancellation_token=token,
        )
    except DataDeletionRequest.DoesNotExist:
        return Response(
            {'error': 'Invalid cancellation token.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not req.is_cancellable:
        return Response(
            {'error': 'This deletion request can no longer be cancelled.'},
            status=status.HTTP_409_CONFLICT,
        )

    req.status = DataDeletionRequest.Status.CANCELLED
    req.cancelled_at = timezone.now()
    req.save(update_fields=['status', 'cancelled_at'])

    create_audit_log(
        actor=req.user,
        action=AuditAction.DATA_DELETION_CANCEL,
        category=AuditCategory.COMPLIANCE,
        description=f'Data deletion cancelled (#{req.pk})',
        resource_type='compliance.DataDeletionRequest',
        resource_id=str(req.pk),
    )

    return Response({'message': 'Deletion request cancelled. Your data is safe.'})


# ═══════════════════════════════════════════════════════════════════════════════
# TEAM ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@api_view(['GET', 'POST'])
@permission_classes([permissions.IsAuthenticated])
def team_overview(request):
    """
    GET  /api/v1/compliance/team/ — Get my team overview.
    POST /api/v1/compliance/team/ — Create a team (company users only).
    """
    if request.method == 'GET':
        return _get_team(request)
    return _create_team(request)


def _get_team(request):
    """Get the team for the current company user."""
    user = request.user
    if not user.is_company:
        return Response(
            {'error': 'Only company accounts can have teams.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    if not hasattr(user, 'company_profile'):
        return Response(
            {'error': 'Company profile not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        team = user.company_profile.team
    except Team.DoesNotExist:
        return Response({
            'has_team': False,
            'team': None,
        })

    return Response({
        'has_team': True,
        'team': TeamSerializer(team).data,
    })


def _create_team(request):
    """Create a new team for the current company."""
    user = request.user
    if not user.is_company:
        return Response(
            {'error': 'Only company accounts can create teams.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    if not hasattr(user, 'company_profile'):
        return Response(
            {'error': 'Company profile not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if hasattr(user.company_profile, 'team'):
        return Response(
            {'error': 'Team already exists.'},
            status=status.HTTP_409_CONFLICT,
        )

    name = request.data.get('name', '') or user.company_profile.legal_name

    team = Team.objects.create(
        company=user.company_profile,
        name=name,
    )

    # Add the company owner as the OWNER team member
    TeamMember.objects.create(
        team=team,
        user=user,
        role=TeamMember.Role.OWNER,
        invited_by=user,
    )

    create_audit_log(
        actor=user,
        action=AuditAction.TEAM_CREATE,
        category=AuditCategory.TEAM,
        description=f'Team created: "{name}"',
        resource_type='compliance.Team',
        resource_id=str(team.pk),
    )

    return Response(
        {'team': TeamSerializer(team).data},
        status=status.HTTP_201_CREATED,
    )


class TeamMemberListView(generics.ListAPIView):
    """GET /api/v1/compliance/team/members/ — List team members."""
    serializer_class = TeamMemberSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None  # Teams are capped at 50 seats — full list OK

    def get_queryset(self):
        user = self.request.user
        membership = TeamMember.objects.filter(
            user=user, is_active=True,
        ).select_related('team').first()

        if not membership:
            return TeamMember.objects.none()

        return TeamMember.objects.filter(
            team=membership.team,
            is_active=True,
        ).select_related('user', 'invited_by').order_by('role', '-joined_at')


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([TeamInviteThrottle])
def invite_team_member(request):
    """
    POST /api/v1/compliance/team/invite/
    Body: { "email": "...", "role": "recruiter", "message": "..." }
    """
    serializer = CreateTeamInvitationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    user = request.user
    email = serializer.validated_data['email']
    role = serializer.validated_data['role']

    # Get user's team
    membership = TeamMember.objects.filter(
        user=user, is_active=True,
        role__in=[TeamMember.Role.OWNER, TeamMember.Role.ADMIN],
    ).select_related('team').first()

    if not membership:
        return Response(
            {'error': 'You must be a team owner or admin to invite members.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    team = membership.team

    # Check seat capacity
    if team.is_at_capacity:
        return Response(
            {
                'error': (
                    f'Team is at capacity ({team.max_seats} seats). '
                    f'Upgrade your plan for more seats.'
                ),
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    # Check for existing active member with this email
    from django.contrib.auth import get_user_model
    User = get_user_model()
    existing_user = User.objects.filter(email=email).first()

    if existing_user:
        if TeamMember.objects.filter(team=team, user=existing_user, is_active=True).exists():
            return Response(
                {'error': 'This user is already a team member.'},
                status=status.HTTP_409_CONFLICT,
            )

    # Check for pending invitation
    if TeamInvitation.objects.filter(
        team=team, email=email,
        status=TeamInvitation.Status.PENDING,
        expires_at__gt=timezone.now(),
    ).exists():
        return Response(
            {'error': 'A pending invitation already exists for this email.'},
            status=status.HTTP_409_CONFLICT,
        )

    # Create invitation
    invitation = TeamInvitation.objects.create(
        team=team,
        email=email,
        role=role,
        invited_by=user,
        message=serializer.validated_data.get('message', ''),
    )

    # Send email
    from compliance.tasks import send_team_invitation_email_task
    try:
        send_team_invitation_email_task.delay(invitation.pk)
    except Exception:
        logger.exception('Failed to dispatch team invitation email')

    create_audit_log(
        actor=user,
        action=AuditAction.TEAM_INVITE,
        category=AuditCategory.TEAM,
        description=f'Team invitation sent to {email} (role: {role})',
        resource_type='compliance.TeamInvitation',
        resource_id=str(invitation.pk),
    )

    return Response(
        TeamInvitationSerializer(invitation).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([TeamInviteActionThrottle])
def accept_team_invitation(request, token):
    """POST /api/v1/compliance/team/invite/<token>/accept/"""
    # Verify HMAC signature before DB lookup (rejects forged tokens cheaply)
    from compliance.token_utils import verify_signed_token
    if not verify_signed_token(token):
        return Response(
            {'error': 'Invalid invitation token.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        invitation = TeamInvitation.objects.select_related('team').get(token=token)
    except TeamInvitation.DoesNotExist:
        return Response(
            {'error': 'Invitation not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not invitation.is_actionable:
        if invitation.is_expired:
            invitation.status = TeamInvitation.Status.EXPIRED
            invitation.save(update_fields=['status'])
            return Response(
                {'error': 'This invitation has expired.'},
                status=status.HTTP_410_GONE,
            )
        return Response(
            {'error': 'This invitation is no longer valid.'},
            status=status.HTTP_409_CONFLICT,
        )

    user = request.user
    if user.email.lower() != invitation.email.lower():
        return Response(
            {'error': 'This invitation was sent to a different email address.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Check seat capacity
    team = invitation.team
    if team.is_at_capacity:
        return Response(
            {'error': 'Team is at capacity. Contact the team admin.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Create membership
    member, created = TeamMember.objects.get_or_create(
        team=team,
        user=user,
        defaults={
            'role': invitation.role,
            'invited_by': invitation.invited_by,
        },
    )

    if not created and not member.is_active:
        # Reactivate previously removed member
        member.is_active = True
        member.role = invitation.role
        member.deactivated_at = None
        member.save(update_fields=['is_active', 'role', 'deactivated_at'])

    # Update invitation
    invitation.status = TeamInvitation.Status.ACCEPTED
    invitation.responded_at = timezone.now()
    invitation.save(update_fields=['status', 'responded_at'])

    create_audit_log(
        actor=user,
        action=AuditAction.TEAM_INVITE_ACCEPT,
        category=AuditCategory.TEAM,
        description=f'{user.email} accepted invitation to team "{team.name}"',
        resource_type='compliance.TeamInvitation',
        resource_id=str(invitation.pk),
    )

    return Response({
        'message': f'Welcome to {team.name}!',
        'team': TeamSerializer(team).data,
        'membership': TeamMemberSerializer(member).data,
    })


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([TeamInviteActionThrottle])
def decline_team_invitation(request, token):
    """POST /api/v1/compliance/team/invite/<token>/decline/"""
    from compliance.token_utils import verify_signed_token
    if not verify_signed_token(token):
        return Response(
            {'error': 'Invalid invitation token.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        invitation = TeamInvitation.objects.get(token=token)
    except TeamInvitation.DoesNotExist:
        return Response(
            {'error': 'Invitation not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if invitation.status != TeamInvitation.Status.PENDING:
        return Response(
            {'error': 'This invitation is no longer pending.'},
            status=status.HTTP_409_CONFLICT,
        )

    invitation.status = TeamInvitation.Status.DECLINED
    invitation.responded_at = timezone.now()
    invitation.save(update_fields=['status', 'responded_at'])

    create_audit_log(
        actor=request.user,
        action=AuditAction.TEAM_INVITE_DECLINE,
        category=AuditCategory.TEAM,
        description=f'Team invitation declined (#{invitation.pk})',
        resource_type='compliance.TeamInvitation',
        resource_id=str(invitation.pk),
    )

    return Response({'message': 'Invitation declined.'})


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def preview_team_invitation(request, token):
    """
    GET /api/v1/compliance/team/invite/<token>/preview/
    Public endpoint to preview invitation details before accepting/declining.
    """
    from compliance.token_utils import verify_signed_token
    if not verify_signed_token(token):
        return Response(
            {'error': 'Invalid invitation token.', 'valid': False},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        invitation = TeamInvitation.objects.select_related(
            'team', 'team__company', 'invited_by',
        ).get(token=token)
    except TeamInvitation.DoesNotExist:
        return Response(
            {'error': 'Invitation not found.', 'valid': False},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not invitation.is_actionable:
        msg = 'This invitation has expired.' if invitation.is_expired else 'This invitation is no longer valid.'
        return Response(
            {'error': msg, 'valid': False},
            status=status.HTTP_410_GONE,
        )

    return Response({
        'valid': True,
        'team_name': invitation.team.name,
        'company_name': getattr(invitation.team.company, 'legal_name', ''),
        'role': invitation.role,
        'invited_by_name': invitation.invited_by.full_name if invitation.invited_by else '',
        'invited_by_email': invitation.invited_by.email if invitation.invited_by else '',
        'email': invitation.email,
        'expires_at': invitation.expires_at.isoformat() if invitation.expires_at else None,
    })


@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
def revoke_team_invitation(request, pk):
    """DELETE /api/v1/compliance/team/invite/<pk>/ — Revoke a pending invitation."""
    try:
        invitation = TeamInvitation.objects.select_related('team').get(pk=pk)
    except TeamInvitation.DoesNotExist:
        return Response(
            {'error': 'Invitation not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Verify the revoker has permission
    membership = TeamMember.objects.filter(
        user=request.user, team=invitation.team,
        is_active=True, role__in=[TeamMember.Role.OWNER, TeamMember.Role.ADMIN],
    ).exists()

    if not membership:
        return Response(
            {'error': 'Only team owners and admins can revoke invitations.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    if invitation.status != TeamInvitation.Status.PENDING:
        return Response(
            {'error': 'Only pending invitations can be revoked.'},
            status=status.HTTP_409_CONFLICT,
        )

    invitation.status = TeamInvitation.Status.REVOKED
    invitation.responded_at = timezone.now()
    invitation.save(update_fields=['status', 'responded_at'])

    create_audit_log(
        actor=request.user,
        action=AuditAction.TEAM_INVITE_REVOKE,
        category=AuditCategory.TEAM,
        description=f'Team invitation to {invitation.email} revoked',
        resource_type='compliance.TeamInvitation',
        resource_id=str(invitation.pk),
    )

    return Response({'message': 'Invitation revoked.'})


@api_view(['PATCH'])
@permission_classes([permissions.IsAuthenticated])
def change_member_role(request, pk):
    """PATCH /api/v1/compliance/team/members/<pk>/role/"""
    serializer = ChangeTeamMemberRoleSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        target_member = TeamMember.objects.select_related('team', 'user').get(pk=pk)
    except TeamMember.DoesNotExist:
        return Response(
            {'error': 'Team member not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Verify actor's permission
    actor_membership = TeamMember.objects.filter(
        user=request.user, team=target_member.team,
        is_active=True, role__in=[TeamMember.Role.OWNER, TeamMember.Role.ADMIN],
    ).first()

    if not actor_membership:
        return Response(
            {'error': 'Insufficient permissions.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Admins can't modify owners
    if target_member.is_owner and actor_membership.role != TeamMember.Role.OWNER:
        return Response(
            {'error': 'Only the owner can modify the owner role.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    old_role = target_member.role
    new_role = serializer.validated_data['role']
    target_member.role = new_role
    target_member.save(update_fields=['role'])

    create_audit_log(
        actor=request.user,
        action=AuditAction.TEAM_MEMBER_ROLE_CHANGE,
        category=AuditCategory.TEAM,
        description=(
            f'{target_member.user.email} role changed: '
            f'{old_role} → {new_role}'
        ),
        resource_type='compliance.TeamMember',
        resource_id=str(target_member.pk),
        changes={'role': {'old': old_role, 'new': new_role}},
    )

    return Response({
        'message': f'Role updated to {new_role}.',
        'member': TeamMemberSerializer(target_member).data,
    })


@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
def remove_team_member(request, pk):
    """DELETE /api/v1/compliance/team/members/<pk>/ — Remove a team member."""
    try:
        target_member = TeamMember.objects.select_related('team', 'user').get(pk=pk)
    except TeamMember.DoesNotExist:
        return Response(
            {'error': 'Team member not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Can't remove the owner
    if target_member.is_owner:
        return Response(
            {'error': 'Cannot remove the team owner. Transfer ownership first.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Check permission
    actor_membership = TeamMember.objects.filter(
        user=request.user, team=target_member.team,
        is_active=True, role__in=[TeamMember.Role.OWNER, TeamMember.Role.ADMIN],
    ).exists()

    # Allow self-removal
    is_self = target_member.user_id == request.user.pk

    if not actor_membership and not is_self:
        return Response(
            {'error': 'Insufficient permissions.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    target_member.is_active = False
    target_member.deactivated_at = timezone.now()
    target_member.save(update_fields=['is_active', 'deactivated_at'])

    create_audit_log(
        actor=request.user,
        action=AuditAction.TEAM_MEMBER_REMOVE,
        category=AuditCategory.TEAM,
        description=(
            f'{target_member.user.email} removed from team '
            f'"{target_member.team.name}"'
        ),
        resource_type='compliance.TeamMember',
        resource_id=str(target_member.pk),
    )

    return Response({'message': 'Team member removed.'})


class TeamInvitationListView(generics.ListAPIView):
    """GET /api/v1/compliance/team/invitations/ — List team invitations."""
    serializer_class = TeamInvitationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None  # Bounded by team seat limit

    def get_queryset(self):
        membership = TeamMember.objects.filter(
            user=self.request.user, is_active=True,
        ).select_related('team').first()

        if not membership:
            return TeamInvitation.objects.none()

        return TeamInvitation.objects.filter(
            team=membership.team,
        ).select_related('invited_by').order_by('-created_at')


# ═══════════════════════════════════════════════════════════════════════════════
# SECURITY.TXT & BUG BOUNTY
# ═══════════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def security_txt(request):
    """
    GET /.well-known/security.txt
    RFC 9116 compliant security.txt response.
    """
    expires = (timezone.now() + timedelta(days=365)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    content = (
        f'Contact: {SECURITY_CONTACT}\n'
        f'Expires: {expires}\n'
        f'Preferred-Languages: {SECURITY_PREFERRED_LANGUAGES}\n'
        f'Policy: {SECURITY_POLICY_URL}\n'
        f'Acknowledgments: {SECURITY_ACKNOWLEDGEMENTS_URL}\n'
        f'Canonical: https://talentorbit.com/.well-known/security.txt\n'
    )
    return HttpResponse(content, content_type='text/plain; charset=utf-8')


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def bug_bounty_info(request):
    """
    GET /api/v1/compliance/security/
    Bug bounty program information for security researchers.
    """
    return Response({
        'program': 'TalentOrbit Security Bug Bounty Program',
        'contact': SECURITY_CONTACT,
        'policy': SECURITY_POLICY_URL,
        'acknowledgements': SECURITY_ACKNOWLEDGEMENTS_URL,
        'bug_bounty_url': BUG_BOUNTY_URL,
        'preferred_languages': SECURITY_PREFERRED_LANGUAGES,
        'scope': [
            '*.talentorbit.com',
            'TalentOrbit API (api.talentorbit.com)',
            'Authentication and authorisation flows',
            'Payment processing (Stripe integration)',
            'File upload handling',
            'WebSocket endpoints',
        ],
        'out_of_scope': [
            'Third-party services (Stripe, Cloudflare, Sentry, PostHog)',
            'Social engineering attacks',
            'Physical security',
            'Denial of service (DoS/DDoS)',
            'Issues already reported and pending fix',
        ],
        'severity_levels': {
            'critical': {
                'description': 'Remote code execution, SQL injection, authentication bypass',
                'response_time': '24 hours',
                'reward_range': '$500 - $5,000',
            },
            'high': {
                'description': 'Privilege escalation, IDOR, stored XSS',
                'response_time': '48 hours',
                'reward_range': '$200 - $1,000',
            },
            'medium': {
                'description': 'CSRF, reflected XSS, information disclosure',
                'response_time': '5 business days',
                'reward_range': '$50 - $200',
            },
            'low': {
                'description': 'Best practice violations, minor misconfigurations',
                'response_time': '10 business days',
                'reward_range': 'Acknowledgement',
            },
        },
        'rules': [
            'Do not access, modify, or delete data belonging to other users.',
            'Do not perform denial-of-service attacks.',
            'Do not use automated scanners without prior approval.',
            'Report vulnerabilities within 90 days of discovery.',
            'Allow reasonable time for fixes before public disclosure.',
        ],
        'safe_harbor': (
            'TalentOrbit will not pursue legal action against security researchers '
            'who follow these rules and report vulnerabilities in good faith.'
        ),
    })
