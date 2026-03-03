"""
compliance/tasks.py
Phase 6 — Async tasks for GDPR data export, data deletion,
team invitation emails, and periodic compliance housekeeping.

All tasks use the standard TalentOrbit retry/DLQ pattern:
    - JSON-only serialisation
    - Late ack + reject on worker lost
    - Exponential backoff with jitter
    - Routed to the 'compliance' queue
"""
import logging
from datetime import timedelta
from typing import Optional

from celery import shared_task
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.mail import send_mail
from django.db import OperationalError, InterfaceError, transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

# ─── Base retry parameters ───────────────────────────────────────────────────
_COMPLIANCE_RETRY_KWARGS = {
    'bind': True,
    'autoretry_for': (OperationalError, InterfaceError),
    'retry_backoff': 10,
    'retry_backoff_max': 300,
    'retry_jitter': True,
    'max_retries': 3,
    'acks_late': True,
    'reject_on_worker_lost': True,
    'queue': 'compliance',
}


# ═══════════════════════════════════════════════════════════════════════════════
# GDPR DATA EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

@shared_task(**_COMPLIANCE_RETRY_KWARGS, name='compliance.process_data_export')
def process_data_export_task(self, export_request_id: int) -> dict:
    """
    Compile all personal data for a user and save as a ZIP archive.

    Workflow:
        1. Mark request as PROCESSING
        2. Compile data via exporters.compile_user_data_as_zip()
        3. Save ZIP to storage (R2 or local)
        4. Update request with file path, size, expiry
        5. Send notification email

    Args:
        export_request_id: PK of the DataExportRequest.
    """
    from compliance.models import DataExportRequest
    from compliance.exporters import compile_user_data_as_zip
    from compliance.constants import DATA_EXPORT_LINK_TTL_HOURS
    from compliance.decorators import create_audit_log
    from compliance.constants import AuditAction, AuditCategory

    try:
        request_obj = DataExportRequest.objects.select_related('user').get(
            pk=export_request_id,
        )
    except DataExportRequest.DoesNotExist:
        logger.warning('process_data_export: request %s not found.', export_request_id)
        return {'status': 'skipped', 'reason': 'not_found'}

    if request_obj.status != DataExportRequest.Status.PENDING:
        logger.info(
            'process_data_export: request %s already %s — skipping.',
            export_request_id, request_obj.status,
        )
        return {'status': 'skipped', 'reason': 'already_processed'}

    user = request_obj.user
    if not user or not user.is_active:
        request_obj.status = DataExportRequest.Status.FAILED
        request_obj.error_message = 'User not found or inactive.'
        request_obj.save(update_fields=['status', 'error_message'])
        return {'status': 'failed', 'reason': 'user_inactive'}

    # Mark as processing
    request_obj.status = DataExportRequest.Status.PROCESSING
    request_obj.processing_started_at = timezone.now()
    request_obj.save(update_fields=['status', 'processing_started_at'])

    try:
        # Compile data
        zip_buffer, file_size = compile_user_data_as_zip(user)

        # Save to storage
        filename = f'gdpr-exports/user-{user.pk}/export-{request_obj.pk}.zip'

        from django.core.files.storage import default_storage
        saved_path = default_storage.save(filename, ContentFile(zip_buffer.read()))

        # Update request
        request_obj.status = DataExportRequest.Status.COMPLETED
        request_obj.completed_at = timezone.now()
        request_obj.file_path = saved_path
        request_obj.file_size_bytes = file_size
        request_obj.expires_at = timezone.now() + timedelta(hours=DATA_EXPORT_LINK_TTL_HOURS)
        request_obj.save(update_fields=[
            'status', 'completed_at', 'file_path',
            'file_size_bytes', 'expires_at',
        ])

        # Audit log
        create_audit_log(
            actor=user,
            action=AuditAction.DATA_EXPORT_REQUEST,
            category=AuditCategory.COMPLIANCE,
            description=f'Data export completed (request #{request_obj.pk}, {file_size} bytes).',
            resource_type='compliance.DataExportRequest',
            resource_id=str(request_obj.pk),
        )

        # Notify user via email
        _send_export_ready_email(user, request_obj)

        logger.info(
            'Data export completed: request=%s user=%s size=%s bytes.',
            request_obj.pk, user.email, file_size,
        )
        return {'status': 'completed', 'file_size': file_size}

    except Exception as exc:
        request_obj.status = DataExportRequest.Status.FAILED
        request_obj.error_message = str(exc)[:1000]
        request_obj.save(update_fields=['status', 'error_message'])
        logger.exception('Data export failed: request=%s', export_request_id)
        raise  # Allow Celery retry


# ═══════════════════════════════════════════════════════════════════════════════
# GDPR DATA DELETION
# ═══════════════════════════════════════════════════════════════════════════════

@shared_task(**_COMPLIANCE_RETRY_KWARGS, name='compliance.process_data_deletion')
def process_data_deletion_task(self, deletion_request_id: int) -> dict:
    """
    Execute permanent data deletion for a user.

    This task runs AFTER the cooling-off period has expired.

    Anonymisation strategy:
        - User account: email → deleted-<id>@redacted.talentorbit.com,
          full_name → 'Deleted User', avatar → null, password → unusable
        - Profile: all PII fields cleared
        - Messages: body → '[message deleted]', attachments removed
        - Applications: cover letter cleared, notes cleared
        - Notifications: deleted
        - Search history: user FK set to null
        - Push subscriptions: deleted
        - Consent records: preserved (GDPR requires this)
        - Audit logs: actor FK set to null, actor_email preserved (legal requirement)

    The user account itself is NOT deleted — it's anonymised and deactivated.
    This preserves referential integrity while removing all PII.
    """
    from compliance.models import DataDeletionRequest
    from compliance.decorators import create_audit_log
    from compliance.constants import AuditAction, AuditCategory

    try:
        request_obj = DataDeletionRequest.objects.select_related('user').get(
            pk=deletion_request_id,
        )
    except DataDeletionRequest.DoesNotExist:
        logger.warning('process_data_deletion: request %s not found.', deletion_request_id)
        return {'status': 'skipped', 'reason': 'not_found'}

    if request_obj.status != DataDeletionRequest.Status.COOLING_OFF:
        logger.info(
            'process_data_deletion: request %s status=%s — expected COOLING_OFF.',
            deletion_request_id, request_obj.status,
        )
        return {'status': 'skipped', 'reason': 'wrong_status'}

    # Verify cooling-off period has ended
    if request_obj.cooling_off_ends_at and timezone.now() < request_obj.cooling_off_ends_at:
        logger.info(
            'process_data_deletion: request %s cooling-off not yet expired.',
            deletion_request_id,
        )
        return {'status': 'skipped', 'reason': 'cooling_off_active'}

    user = request_obj.user
    if not user:
        request_obj.status = DataDeletionRequest.Status.FAILED
        request_obj.error_message = 'User no longer exists.'
        request_obj.save(update_fields=['status', 'error_message'])
        return {'status': 'failed', 'reason': 'user_not_found'}

    # Mark as processing
    request_obj.status = DataDeletionRequest.Status.PROCESSING
    request_obj.processing_started_at = timezone.now()
    request_obj.save(update_fields=['status', 'processing_started_at'])

    summary = {}
    completed_steps = []

    try:
        # ── All DB mutations run inside a single atomic transaction ──────
        # If ANY step fails, the entire deletion is rolled back cleanly,
        # leaving user data intact rather than partially anonymised.
        with transaction.atomic():

            # 1. Delete notifications
            from notifications.models import Notification
            count, _ = Notification.objects.filter(user=user).delete()
            summary['notifications'] = count
            completed_steps.append('notifications')

            # 2. Anonymise messages
            from messaging.models import Message, Thread
            msg_count = Message.objects.filter(sender=user).update(
                body='[message deleted per user request]',
            )
            # Remove message attachments (file deletion is non-transactional
            # but safe — orphaned files are cleaned by storage lifecycle rules)
            for msg in Message.objects.filter(sender=user, attachment__isnull=False).exclude(attachment=''):
                if msg.attachment:
                    try:
                        msg.attachment.delete(save=False)
                    except Exception:
                        pass
                    msg.attachment = None
                    msg.save(update_fields=['attachment'])
            summary['messages_anonymised'] = msg_count
            completed_steps.append('messages')

            # 3. Anonymise applications
            from jobs.models import Application, SavedJob
            app_count = Application.objects.filter(applicant=user).update(
                cover_letter='[deleted per user request]',
                notes='[deleted per user request]',
            )
            summary['applications_anonymised'] = app_count
            completed_steps.append('applications')

            # 4. Delete saved jobs
            saved_count, _ = SavedJob.objects.filter(user=user).delete()
            summary['saved_jobs'] = saved_count
            completed_steps.append('saved_jobs')

            # 5. Nullify search history user FK
            from search.models import SearchAnalytics
            search_count = SearchAnalytics.objects.filter(user=user).update(user=None)
            summary['search_queries_anonymised'] = search_count
            completed_steps.append('search_history')

            # 6. Delete push subscriptions
            from realtime.models import PushSubscription
            push_count, _ = PushSubscription.objects.filter(user=user).delete()
            summary['push_subscriptions'] = push_count
            completed_steps.append('push_subscriptions')

            # 7. Delete data export files and requests
            from compliance.models import DataExportRequest
            exports = DataExportRequest.objects.filter(user=user)
            export_file_paths = []
            for export in exports:
                if export.file_path:
                    export_file_paths.append(export.file_path)
            export_count, _ = exports.delete()
            summary['data_exports'] = export_count
            completed_steps.append('data_exports')

            # 8. Deactivate team memberships
            from compliance.models import TeamMember
            team_count = TeamMember.objects.filter(user=user).update(
                is_active=False,
                deactivated_at=timezone.now(),
            )
            summary['team_memberships_deactivated'] = team_count
            completed_steps.append('team_memberships')

            # 9. Nullify audit log actor references (preserve logs themselves)
            from compliance.models import AuditLog
            AuditLog.objects.filter(actor=user).update(actor=None)
            completed_steps.append('audit_log_refs')

            # 10. Anonymise the user account
            original_email = user.email
            user.email = f'deleted-{user.pk}@redacted.talentorbit.com'
            user.full_name = 'Deleted User'
            user.is_active = False
            user.is_verified = False
            user.is_2fa_enabled = False
            user.totp_secret = None
            user.set_unusable_password()
            if user.avatar:
                try:
                    user.avatar.delete(save=False)
                except Exception:
                    pass
                user.avatar = None
            user.save()
            completed_steps.append('user_account')

            # 11. Anonymise profile
            if hasattr(user, 'talent_profile'):
                p = user.talent_profile
                p.bio = ''
                p.location = ''
                p.linkedin_url = ''
                p.portfolio_url = ''
                p.skills = []
                p.is_open_to_work = False
                if p.resume:
                    try:
                        p.resume.delete(save=False)
                    except Exception:
                        pass
                    p.resume = None
                p.save()
                summary['talent_profile_anonymised'] = True

            if hasattr(user, 'company_profile'):
                p = user.company_profile
                p.legal_name = f'[Deleted Company #{user.pk}]'
                p.industry = ''
                p.registration_number = None
                p.mission_statement = ''
                p.headquarters = ''
                p.website = ''
                if p.logo:
                    try:
                        p.logo.delete(save=False)
                    except Exception:
                        pass
                    p.logo = None
                p.save()
                summary['company_profile_anonymised'] = True
            completed_steps.append('profile')

            # 12. Blacklist all tokens
            from accounts.utils import blacklist_all_tokens
            blacklist_all_tokens(user)
            completed_steps.append('token_blacklist')

            # Update deletion request (inside the same transaction)
            request_obj.status = DataDeletionRequest.Status.COMPLETED
            request_obj.completed_at = timezone.now()
            request_obj.deletion_summary = summary
            request_obj.user = None  # Detach from anonymised user
            request_obj.save(update_fields=[
                'status', 'completed_at', 'deletion_summary', 'user',
            ])

        # ── Post-transaction: non-DB side-effects ────────────────────────
        # Delete storage files AFTER the DB transaction commits successfully.
        # If these fail, orphaned files are cleaned by the periodic
        # cleanup_expired_exports_task or storage lifecycle rules.
        from django.core.files.storage import default_storage
        for file_path in export_file_paths:
            try:
                default_storage.delete(file_path)
            except Exception:
                logger.warning('Failed to delete export file: %s', file_path)

        # Audit log (actor is None since user is anonymised)
        create_audit_log(
            actor=None,
            action=AuditAction.DATA_DELETION_EXECUTE,
            category=AuditCategory.COMPLIANCE,
            description=(
                f'Data deletion completed for {request_obj.user_email} '
                f'(request #{request_obj.pk}). Summary: {summary}'
            ),
            resource_type='compliance.DataDeletionRequest',
            resource_id=str(request_obj.pk),
        )

        # Confirmation email (to original address)
        _send_deletion_complete_email(original_email)

        logger.info(
            'Data deletion completed: request=%s email=%s summary=%s',
            request_obj.pk, request_obj.user_email, summary,
        )
        return {'status': 'completed', 'summary': summary}

    except Exception as exc:
        # Transaction rolled back automatically — user data intact.
        logger.exception(
            'Data deletion failed (rolled back): request=%s completed_steps=%s',
            deletion_request_id, completed_steps,
        )
        request_obj.status = DataDeletionRequest.Status.FAILED
        request_obj.error_message = (
            f'{str(exc)[:800]} | '
            f'Completed steps before rollback: {completed_steps}'
        )
        request_obj.save(update_fields=['status', 'error_message'])
        raise  # Allow Celery retry


# ═══════════════════════════════════════════════════════════════════════════════
# TEAM INVITATION EMAIL
# ═══════════════════════════════════════════════════════════════════════════════

@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=10,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=5,
    acks_late=True,
    reject_on_worker_lost=True,
    queue='emails',
    name='compliance.send_team_invitation_email',
)
def send_team_invitation_email_task(
    self,
    invitation_id: int,
) -> dict:
    """
    Send a team invitation email to the invitee.
    """
    from compliance.models import TeamInvitation

    try:
        invitation = TeamInvitation.objects.select_related(
            'team', 'invited_by',
        ).get(pk=invitation_id)
    except TeamInvitation.DoesNotExist:
        return {'status': 'skipped', 'reason': 'invitation_not_found'}

    if invitation.status != TeamInvitation.Status.PENDING:
        return {'status': 'skipped', 'reason': 'not_pending'}

    inviter_name = invitation.invited_by.full_name if invitation.invited_by else 'Someone'
    team_name = invitation.team.name
    accept_url = (
        f"{settings.FRONTEND_URL}/team/invite/{invitation.token}"
    )

    message = (
        f'Hi,\n\n'
        f'{inviter_name} has invited you to join the "{team_name}" team '
        f'on TalentOrbit as a {invitation.get_role_display()}.\n\n'
    )

    if invitation.message:
        message += f'Personal message:\n"{invitation.message}"\n\n'

    message += (
        f'Accept the invitation:\n{accept_url}\n\n'
        f'This invitation expires on {invitation.expires_at.strftime("%B %d, %Y")}.\n\n'
        f'If you don\'t have a TalentOrbit account, you\'ll be able to create '
        f'one when you accept.\n\n'
        f'— TalentOrbit'
    )

    send_mail(
        subject=f'TalentOrbit — Team Invitation from {inviter_name}',
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[invitation.email],
        fail_silently=False,
    )

    logger.info(
        'Team invitation email sent: invitation=%s email=%s',
        invitation.pk, invitation.email,
    )
    return {'status': 'sent', 'email': invitation.email}


# ═══════════════════════════════════════════════════════════════════════════════
# GDPR DELETION CONFIRMATION EMAIL
# ═══════════════════════════════════════════════════════════════════════════════

@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=10,
    max_retries=3,
    queue='emails',
    name='compliance.send_deletion_confirmation_email',
)
def send_deletion_confirmation_email_task(
    self,
    deletion_request_id: int,
) -> dict:
    """
    Send the deletion confirmation email with confirm/cancel links.
    """
    from compliance.models import DataDeletionRequest

    try:
        req = DataDeletionRequest.objects.select_related('user').get(
            pk=deletion_request_id,
        )
    except DataDeletionRequest.DoesNotExist:
        return {'status': 'skipped', 'reason': 'not_found'}

    confirm_url = (
        f"{settings.FRONTEND_URL}/compliance/confirm-deletion"
        f"?token={req.confirmation_token}"
    )
    cancel_url = (
        f"{settings.FRONTEND_URL}/compliance/cancel-deletion"
        f"?token={req.cancellation_token}"
    )

    send_mail(
        subject='TalentOrbit — Data Deletion Request Confirmation',
        message=(
            f'Hi {req.user.full_name if req.user else "there"},\n\n'
            f'We received your request to permanently delete your TalentOrbit account '
            f'and all associated data.\n\n'
            f'⚠️ This action is IRREVERSIBLE. All your data will be permanently removed.\n\n'
            f'To CONFIRM deletion, click:\n{confirm_url}\n\n'
            f'After confirmation, there will be a 14-day cooling-off period during '
            f'which you can still cancel.\n\n'
            f'To CANCEL this request:\n{cancel_url}\n\n'
            f'If you didn\'t make this request, please secure your account immediately '
            f'and contact support@talentorbit.com.\n\n'
            f'— TalentOrbit Data Protection Team'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[req.user_email],
        fail_silently=False,
    )

    logger.info(
        'Deletion confirmation email sent: request=%s email=%s',
        req.pk, req.user_email,
    )
    return {'status': 'sent'}


# ═══════════════════════════════════════════════════════════════════════════════
# PERIODIC HOUSEKEEPING
# ═══════════════════════════════════════════════════════════════════════════════

@shared_task(
    name='compliance.process_expired_deletions',
    bind=True,
    max_retries=1,
    queue='compliance',
)
def process_expired_deletions_task(self) -> dict:
    """
    Periodic task: find deletion requests whose cooling-off has expired
    and trigger the actual deletion.
    """
    from compliance.models import DataDeletionRequest

    expired = DataDeletionRequest.objects.filter(
        status=DataDeletionRequest.Status.COOLING_OFF,
        cooling_off_ends_at__lte=timezone.now(),
    )

    count = 0
    for req in expired:
        process_data_deletion_task.delay(req.pk)
        count += 1

    if count:
        logger.info('Dispatched %d expired deletion requests for processing.', count)
    return {'dispatched': count}


@shared_task(
    name='compliance.cleanup_expired_exports',
    bind=True,
    max_retries=1,
    queue='compliance',
)
def cleanup_expired_exports_task(self) -> dict:
    """
    Periodic task: mark expired export requests and delete their files.
    """
    from compliance.models import DataExportRequest
    from django.core.files.storage import default_storage

    expired = DataExportRequest.objects.filter(
        status=DataExportRequest.Status.COMPLETED,
        expires_at__lte=timezone.now(),
    )

    count = 0
    for export in expired:
        if export.file_path:
            try:
                default_storage.delete(export.file_path)
            except Exception:
                logger.warning('Failed to delete export file: %s', export.file_path)
        export.status = DataExportRequest.Status.EXPIRED
        export.file_path = ''
        export.save(update_fields=['status', 'file_path'])
        count += 1

    # Safety net: also catch exports that have been COMPLETED for more than
    # 7 days (double the TTL) but somehow weren't caught by normal expiry.
    # This handles edge cases like clock skew or missing expires_at.
    hard_ceiling = timezone.now() - timedelta(days=7)
    stale = DataExportRequest.objects.filter(
        status=DataExportRequest.Status.COMPLETED,
        completed_at__lte=hard_ceiling,
    )
    stale_count = 0
    for export in stale:
        if export.file_path:
            try:
                default_storage.delete(export.file_path)
            except Exception:
                logger.warning('Safety-net: failed to delete stale export file: %s', export.file_path)
        export.status = DataExportRequest.Status.EXPIRED
        export.file_path = ''
        export.save(update_fields=['status', 'file_path'])
        stale_count += 1

    total = count + stale_count
    if total:
        logger.info('Cleaned up %d expired + %d stale data exports.', count, stale_count)
    return {'cleaned': count, 'stale_cleaned': stale_count}


@shared_task(
    name='compliance.expire_team_invitations',
    bind=True,
    max_retries=1,
    queue='compliance',
)
def expire_team_invitations_task(self) -> dict:
    """
    Periodic task: mark expired team invitations.
    """
    from compliance.models import TeamInvitation

    count = TeamInvitation.objects.filter(
        status=TeamInvitation.Status.PENDING,
        expires_at__lte=timezone.now(),
    ).update(status=TeamInvitation.Status.EXPIRED)

    if count:
        logger.info('Expired %d team invitations.', count)
    return {'expired': count}


@shared_task(
    name='compliance.audit_chain_integrity_check',
    bind=True,
    max_retries=0,
    queue='compliance',
)
def audit_chain_integrity_check_task(self) -> dict:
    """
    Periodic integrity check on the audit log chain.
    Alerts via logging if tampering is detected.
    """
    from compliance.models import AuditLog

    result = AuditLog.verify_chain(limit=5000)

    if not result['valid']:
        logger.critical(
            'AUDIT LOG INTEGRITY VIOLATION: chain broken at entry %s '
            '(checked %d entries). Investigate immediately.',
            result['first_broken_id'], result['checked'],
        )
    else:
        logger.info(
            'Audit log integrity check passed: %d entries verified.',
            result['checked'],
        )

    return result


@shared_task(
    name='compliance.ip_anomaly_detection',
    bind=True,
    max_retries=0,
    queue='compliance',
)
def ip_anomaly_detection_task(self) -> dict:
    """
    Periodic task: scan recent audit logs for IP-based anomalies.
    Flags new-IP logins, brute-force indicators, and bulk data access.
    """
    from compliance.anomaly import detect_anomalies
    return detect_anomalies()


# ═══════════════════════════════════════════════════════════════════════════════
# Email Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _send_export_ready_email(user, export_request):
    """Notify the user their data export is ready for download."""
    download_url = (
        f"{settings.FRONTEND_URL}/settings?tab=privacy"
        f"&export={export_request.download_token}"
    )
    try:
        send_mail(
            subject='TalentOrbit — Your Data Export is Ready',
            message=(
                f'Hi {user.full_name or "there"},\n\n'
                f'Your personal data export is ready for download.\n\n'
                f'Download it here:\n{download_url}\n\n'
                f'This link will expire on '
                f'{export_request.expires_at.strftime("%B %d, %Y at %H:%M UTC")}.\n\n'
                f'The export contains all data associated with your TalentOrbit account '
                f'in JSON format, packaged as a ZIP archive.\n\n'
                f'— TalentOrbit'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )
    except Exception:
        logger.exception('Failed to send export ready email to %s', user.email)


def _send_deletion_complete_email(email: str):
    """Confirm to the user that their data has been permanently deleted."""
    try:
        send_mail(
            subject='TalentOrbit — Account Data Deleted',
            message=(
                f'Hi,\n\n'
                f'Your TalentOrbit account and all associated personal data have been '
                f'permanently deleted as requested.\n\n'
                f'This action is irreversible. If you wish to use TalentOrbit again '
                f'in the future, you will need to create a new account.\n\n'
                f'If you have any questions, please contact privacy@talentorbit.com.\n\n'
                f'— TalentOrbit Data Protection Team'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=True,
        )
    except Exception:
        logger.exception('Failed to send deletion complete email to %s', email)
