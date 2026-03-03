"""
compliance/anomaly.py
Enterprise IP anomaly detection for the audit subsystem.

Detects:
    1. Login from a previously-unseen IP address (per user)
    2. Rapid failed login attempts from a single IP (brute-force indicator)
    3. Bulk data access patterns (many export/download actions in a short window)

Detection runs as a periodic Celery task and flags suspicious activity
by creating high-severity audit log entries that surface in the admin dashboard.

Known IPs per user are stored in the Django cache (Redis) with a 30-day TTL
so that the set builds organically without a dedicated DB table.
"""
import logging
from datetime import timedelta
from collections import Counter

from django.core.cache import cache
from django.db.models import Count
from django.utils import timezone

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────

# How far back to look for anomalies (per scan).
ANOMALY_SCAN_WINDOW_MINUTES = 30

# Failed logins from a single IP within the scan window that trigger an alert.
FAILED_LOGIN_THRESHOLD = 10

# Bulk data access actions from a single user within the scan window.
BULK_ACCESS_THRESHOLD = 10

# How long we remember a user's known IPs (seconds).
KNOWN_IP_TTL = 30 * 24 * 3600  # 30 days

# Cache key prefix for known IPs.
_KNOWN_IP_PREFIX = 'compliance:known_ips'


def _known_ip_key(user_id: int) -> str:
    return f'{_KNOWN_IP_PREFIX}:{user_id}'


def record_known_ip(user_id: int, ip_address: str) -> None:
    """
    Add an IP to the user's set of known login IPs (cached).
    Called on successful login from signals.
    """
    if not ip_address:
        return
    key = _known_ip_key(user_id)
    known = cache.get(key) or set()
    if ip_address not in known:
        known.add(ip_address)
        cache.set(key, known, KNOWN_IP_TTL)


def is_new_ip(user_id: int, ip_address: str) -> bool:
    """Check if this IP has never been used by this user before."""
    if not ip_address:
        return False
    key = _known_ip_key(user_id)
    known = cache.get(key) or set()
    return ip_address not in known


def detect_anomalies() -> dict:
    """
    Scan recent audit logs for suspicious patterns.

    Returns a summary dict with counts of each anomaly type detected.
    Also creates AuditLog entries with category=SYSTEM for each alert.
    """
    from compliance.models import AuditLog
    from compliance.decorators import create_audit_log
    from compliance.constants import AuditAction, AuditCategory

    now = timezone.now()
    window_start = now - timedelta(minutes=ANOMALY_SCAN_WINDOW_MINUTES)

    alerts = {
        'new_ip_logins': 0,
        'brute_force_ips': 0,
        'bulk_access_users': 0,
    }

    # ── 1. Detect login from new IP ──────────────────────────────────────
    successful_logins = AuditLog.objects.filter(
        action=AuditLog.Action.LOGIN,
        created_at__gte=window_start,
        actor__isnull=False,
        ip_address__isnull=False,
    ).values_list('actor_id', 'actor_email', 'ip_address')

    for actor_id, actor_email, ip in successful_logins:
        if actor_id and ip and is_new_ip(actor_id, ip):
            # Record it as known now (so we don't alert again)
            record_known_ip(actor_id, ip)
            alerts['new_ip_logins'] += 1

            create_audit_log(
                action=AuditAction.LOGIN,
                category=AuditCategory.SYSTEM,
                description=(
                    f'[ANOMALY] Login from new IP {ip} '
                    f'for user {actor_email} (id={actor_id})'
                ),
                resource_type='accounts.User',
                resource_id=str(actor_id),
                ip_address=ip,
            )

    # ── 2. Rapid failed logins from a single IP ─────────────────────────
    failed_logins = (
        AuditLog.objects.filter(
            action=AuditLog.Action.LOGIN_FAILED,
            created_at__gte=window_start,
            ip_address__isnull=False,
        )
        .values('ip_address')
        .annotate(count=Count('id'))
        .filter(count__gte=FAILED_LOGIN_THRESHOLD)
    )

    for entry in failed_logins:
        ip = entry['ip_address']
        count = entry['count']
        alerts['brute_force_ips'] += 1

        create_audit_log(
            action=AuditAction.LOGIN_FAILED,
            category=AuditCategory.SYSTEM,
            description=(
                f'[ANOMALY] Brute-force indicator: {count} failed logins '
                f'from IP {ip} in the last {ANOMALY_SCAN_WINDOW_MINUTES} minutes'
            ),
            ip_address=ip,
        )

    # ── 3. Bulk data access (exports/downloads) per user ─────────────────
    data_access_actions = [
        AuditLog.Action.DATA_EXPORT_REQUEST,
        AuditLog.Action.DATA_EXPORT_DOWNLOAD,
    ]
    bulk_access = (
        AuditLog.objects.filter(
            action__in=data_access_actions,
            created_at__gte=window_start,
            actor__isnull=False,
        )
        .values('actor_id', 'actor_email')
        .annotate(count=Count('id'))
        .filter(count__gte=BULK_ACCESS_THRESHOLD)
    )

    for entry in bulk_access:
        alerts['bulk_access_users'] += 1

        create_audit_log(
            action=AuditAction.DATA_EXPORT_REQUEST,
            category=AuditCategory.SYSTEM,
            description=(
                f'[ANOMALY] Bulk data access: user {entry["actor_email"]} '
                f'(id={entry["actor_id"]}) made {entry["count"]} data access '
                f'requests in the last {ANOMALY_SCAN_WINDOW_MINUTES} minutes'
            ),
            resource_type='accounts.User',
            resource_id=str(entry['actor_id']),
        )

    total = sum(alerts.values())
    if total:
        logger.warning('IP anomaly detection: %d alerts — %s', total, alerts)
    else:
        logger.info('IP anomaly detection: no anomalies found.')

    return alerts
