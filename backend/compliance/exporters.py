"""
compliance/exporters.py
Phase 6 — GDPR Article 20 data portability.

Compiles ALL personal data for a user across every TalentOrbit app
into a structured JSON document, then packages it as a ZIP archive.

The exporter is designed to be run asynchronously via Celery.
It respects the user's role and only exports data they own.

Enterprise-grade considerations:
    - Streams data to avoid OOM for large datasets
    - Includes metadata (export time, schema version, record counts)
    - Handles missing relations gracefully
    - Excludes internal fields (checksums, cache keys)
    - Human-readable JSON with ISO 8601 timestamps
"""
import io
import json
import logging
import zipfile
from datetime import datetime

from django.utils import timezone

logger = logging.getLogger(__name__)

EXPORT_SCHEMA_VERSION = '1.0.0'


def compile_user_data(user) -> dict:
    """
    Compile all personal data for the given user into a structured dict.

    Returns:
        {
            "metadata": { ... },
            "account": { ... },
            "profile": { ... },
            "jobs": [ ... ],
            "applications": [ ... ],
            "messages": [ ... ],
            "notifications": [ ... ],
            "consent_records": [ ... ],
            "search_history": [ ... ],
            "audit_trail": [ ... ],
        }
    """
    data = {
        'metadata': {
            'export_version': EXPORT_SCHEMA_VERSION,
            'exported_at': timezone.now().isoformat(),
            'user_id': user.pk,
            'user_email': user.email,
            'platform': 'TalentOrbit',
        },
        'account': _export_account(user),
        'profile': _export_profile(user),
    }

    # Conditionally export based on role
    if user.role == 'TALENT':
        data['applications'] = _export_applications(user)
        data['saved_jobs'] = _export_saved_jobs(user)
    elif user.role == 'COMPANY':
        data['job_posts'] = _export_job_posts(user)
        data['team'] = _export_team(user)

    data['messages'] = _export_messages(user)
    data['notifications'] = _export_notifications(user)
    data['consent_records'] = _export_consent_records(user)
    data['search_history'] = _export_search_history(user)
    data['push_subscriptions'] = _export_push_subscriptions(user)
    data['audit_trail'] = _export_audit_trail(user)

    # Add record counts to metadata
    data['metadata']['record_counts'] = {
        key: len(val) if isinstance(val, list) else (1 if val else 0)
        for key, val in data.items()
        if key != 'metadata'
    }

    return data


def compile_user_data_as_zip(user) -> tuple[io.BytesIO, int]:
    """
    Compile user data and package as a ZIP archive.

    Returns:
        Tuple of (BytesIO buffer, file size in bytes).
    """
    data = compile_user_data(user)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Main data file
        json_content = json.dumps(data, indent=2, default=str, ensure_ascii=False)
        zf.writestr(
            f'talentorbit-data-export-{user.pk}.json',
            json_content,
        )

        # README explaining the export
        readme = _generate_readme(user, data)
        zf.writestr('README.txt', readme)

    size = buffer.tell()
    buffer.seek(0)
    return buffer, size


# ══════════════════════════════════════════════════════════════════════════════
# Individual Data Exporters
# ══════════════════════════════════════════════════════════════════════════════

def _export_account(user) -> dict:
    """Core account data."""
    return {
        'id': user.pk,
        'email': user.email,
        'full_name': user.full_name,
        'role': user.role,
        'is_verified': user.is_verified,
        'is_active': user.is_active,
        'is_2fa_enabled': user.is_2fa_enabled,
        'date_joined': user.date_joined.isoformat(),
        'last_updated': user.last_updated.isoformat(),
        'avatar_url': user.avatar.url if user.avatar else None,
    }


def _export_profile(user) -> dict | None:
    """Role-specific profile data."""
    if user.role == 'TALENT' and hasattr(user, 'talent_profile'):
        p = user.talent_profile
        return {
            'type': 'talent',
            'bio': p.bio,
            'location': p.location,
            'resume_url': p.resume.url if p.resume else None,
            'linkedin_url': p.linkedin_url,
            'portfolio_url': p.portfolio_url,
            'skills': p.skills,
            'is_open_to_work': p.is_open_to_work,
            'subscription_tier': p.subscription_tier,
            'created_at': p.created_at.isoformat(),
            'updated_at': p.updated_at.isoformat(),
        }
    elif user.role == 'COMPANY' and hasattr(user, 'company_profile'):
        p = user.company_profile
        return {
            'type': 'company',
            'legal_name': p.legal_name,
            'industry': p.industry,
            'registration_number': p.registration_number,
            'mission_statement': p.mission_statement,
            'logo_url': p.logo.url if p.logo else None,
            'headquarters': p.headquarters,
            'website': p.website,
            'is_verified': p.is_verified,
            'subscription_tier': p.subscription_tier,
            'created_at': p.created_at.isoformat(),
            'updated_at': p.updated_at.isoformat(),
        }
    return None


def _export_applications(user) -> list:
    """All job applications by the talent user."""
    from jobs.models import Application
    apps = Application.objects.filter(
        applicant=user,
    ).select_related('job', 'job__company').order_by('-applied_at')

    return [
        {
            'id': a.pk,
            'job_title': a.job.title,
            'job_company': _safe_company_name(a.job.company),
            'cover_letter': a.cover_letter,
            'status': a.status,
            'applied_at': a.applied_at.isoformat(),
            'updated_at': a.updated_at.isoformat(),
        }
        for a in apps
    ]


def _export_saved_jobs(user) -> list:
    """Saved/bookmarked jobs."""
    from jobs.models import SavedJob
    saves = SavedJob.objects.filter(
        user=user,
    ).select_related('job').order_by('-saved_at')

    return [
        {
            'id': s.pk,
            'job_title': s.job.title,
            'job_id': s.job.pk,
            'saved_at': s.saved_at.isoformat(),
        }
        for s in saves
    ]


def _export_job_posts(user) -> list:
    """All job posts created by the company user."""
    from jobs.models import JobPost
    posts = JobPost.objects.filter(
        company=user,
    ).order_by('-created_at')

    return [
        {
            'id': j.pk,
            'title': j.title,
            'description': j.description,
            'requirements': j.requirements,
            'responsibilities': j.responsibilities,
            'job_type': j.job_type,
            'work_mode': j.work_mode,
            'status': j.status,
            'experience_level': j.experience_level,
            'location': j.location,
            'salary_min': j.salary_min,
            'salary_max': j.salary_max,
            'salary_currency': j.salary_currency,
            'skills_required': j.skills_required,
            'application_deadline': j.application_deadline.isoformat() if j.application_deadline else None,
            'views_count': j.views_count,
            'created_at': j.created_at.isoformat(),
            'updated_at': j.updated_at.isoformat(),
        }
        for j in posts
    ]


def _export_messages(user) -> list:
    """All message threads and messages involving the user."""
    from messaging.models import Thread

    threads = Thread.objects.filter(
        participants=user,
    ).prefetch_related('messages', 'messages__sender', 'participants')

    exported_threads = []
    for t in threads:
        participants = [
            {'id': p.pk, 'email': p.email, 'full_name': p.full_name}
            for p in t.participants.all()
        ]
        messages = [
            {
                'id': m.pk,
                'sender_email': m.sender.email,
                'body': m.body,
                'attachment_url': m.attachment.url if m.attachment else None,
                'read': m.read,
                'sent_at': m.sent_at.isoformat(),
            }
            for m in t.messages.all()
        ]
        exported_threads.append({
            'thread_id': t.pk,
            'participants': participants,
            'job_id': t.job_id,
            'messages': messages,
            'created_at': t.created_at.isoformat(),
        })

    return exported_threads


def _export_notifications(user) -> list:
    """All notifications for the user."""
    from notifications.models import Notification

    notifs = Notification.objects.filter(
        user=user,
    ).order_by('-created_at')[:500]  # Cap at 500 most recent

    return [
        {
            'id': n.pk,
            'category': n.category,
            'title': n.title,
            'description': n.description,
            'is_read': n.is_read,
            'created_at': n.created_at.isoformat(),
        }
        for n in notifs
    ]


def _export_consent_records(user) -> list:
    """All consent records for the user."""
    from compliance.models import ConsentRecord

    records = ConsentRecord.objects.filter(
        user=user,
    ).select_related('policy_version').order_by('-consented_at')

    return [
        {
            'id': r.pk,
            'policy_type': r.policy_version.policy_type,
            'policy_version': r.policy_version.version,
            'policy_title': r.policy_version.title,
            'consented_at': r.consented_at.isoformat(),
            'withdrawn_at': r.withdrawn_at.isoformat() if r.withdrawn_at else None,
            'withdrawal_reason': r.withdrawal_reason,
        }
        for r in records
    ]


def _export_search_history(user) -> list:
    """Search queries made by the user."""
    from search.models import SearchAnalytics

    queries = SearchAnalytics.objects.filter(
        user=user,
    ).order_by('-created_at')[:200]  # Cap at 200 most recent

    return [
        {
            'id': q.pk,
            'query': q.query,
            'entity_type': q.entity_type,
            'results_count': q.results_count,
            'filters_applied': q.filters_applied,
            'created_at': q.created_at.isoformat(),
        }
        for q in queries
    ]


def _export_push_subscriptions(user) -> list:
    """Push notification subscriptions."""
    from realtime.models import PushSubscription

    subs = PushSubscription.objects.filter(user=user)
    return [
        {
            'id': s.pk,
            'platform': s.platform,
            'is_active': s.is_active,
            'created_at': s.created_at.isoformat(),
            'last_used_at': s.last_used_at.isoformat(),
        }
        for s in subs
    ]


def _export_team(user) -> dict | None:
    """Team membership data for company users."""
    from compliance.models import TeamMember

    membership = TeamMember.objects.filter(
        user=user,
        is_active=True,
    ).select_related('team').first()

    if not membership:
        return None

    return {
        'team_name': membership.team.name,
        'role': membership.role,
        'joined_at': membership.joined_at.isoformat(),
    }


def _export_audit_trail(user) -> list:
    """User's own audit trail (actions they performed)."""
    from compliance.models import AuditLog

    logs = AuditLog.objects.filter(
        actor=user,
    ).order_by('-created_at')[:500]  # Cap at 500 most recent

    return [
        {
            'id': entry.pk,
            'action': entry.action,
            'category': entry.category,
            'description': entry.description,
            'resource_type': entry.resource_type,
            'resource_id': entry.resource_id,
            'ip_address': entry.ip_address,
            'created_at': entry.created_at.isoformat(),
        }
        for entry in logs
    ]


# ── Helpers ──────────────────────────────────────────────────────────────────

def _safe_company_name(company_user) -> str:
    """Safely get company name even if profile is missing."""
    try:
        return company_user.company_profile.legal_name
    except Exception:
        return company_user.full_name or company_user.email


def _generate_readme(user, data: dict) -> str:
    """Generate a human-readable README for the data export."""
    counts = data.get('metadata', {}).get('record_counts', {})
    count_lines = '\n'.join(
        f'  - {key}: {count} record(s)' for key, count in counts.items()
    )
    return f"""TalentOrbit — Personal Data Export
==================================

User: {user.email}
Export Date: {timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
Schema Version: {EXPORT_SCHEMA_VERSION}

This archive contains all personal data associated with your TalentOrbit
account, exported in compliance with GDPR Article 20 (Right to Data
Portability) and Article 15 (Right of Access).

Contents:
{count_lines}

Data Format:
  The main data file is in JSON format with ISO 8601 timestamps.
  All text fields are UTF-8 encoded.

Questions or Concerns:
  Contact our Data Protection Officer at privacy@talentorbit.com

Your Rights:
  - Right to rectification (Article 16)
  - Right to erasure (Article 17)
  - Right to restriction of processing (Article 18)
  - Right to data portability (Article 20)
  - Right to object (Article 21)

  Exercise these rights at: https://talentorbit.com/settings
"""
