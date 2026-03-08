"""
developer/tasks.py
Celery tasks for the Developer Platform.

All tasks use BaseTaskWithDLQ so permanently-failed tasks are routed
to the dead-letter queue instead of being silently dropped.

Tasks:
    1. deliver_webhook       â€” Async outbound HTTP POST with retry + HMAC signing
    2. prune_delivery_logs   â€” Periodic cleanup of old WebhookDelivery rows
"""
import hashlib
import hmac
import logging
import time

from celery import shared_task
from talentorbit.task_base import BaseTaskWithDLQ

logger = logging.getLogger(__name__)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# 1. Async Webhook Delivery with HMAC Signature
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@shared_task(
    base=BaseTaskWithDLQ,
    bind=True,
    name='developer.deliver_webhook',
    max_retries=3,
    default_retry_delay=30,
    queue='default',
)
def deliver_webhook(self, endpoint_id: str, event_type: str, payload: dict):
    """
    Deliver a single webhook event to a registered endpoint.

    Signs the payload with the endpoint's signing secret using HMAC-SHA256,
    includes the signature in the X-TalentOrbit-Signature header.

    On failure, retries up to 3 times with exponential backoff.
    On permanent failure, updates the endpoint's failure_count.
    """
    import json
    import requests as http_requests
    from django.utils import timezone

    # Lazy imports to avoid circular dependencies
    from developer.models import WebhookDelivery, WebhookEndpoint

    try:
        endpoint = WebhookEndpoint.objects.get(id=endpoint_id, is_active=True)
    except WebhookEndpoint.DoesNotExist:
        logger.warning('deliver_webhook: endpoint %s not found or inactive, skipping.', endpoint_id)
        return

    attempt_number = self.request.retries + 1
    # â”€â”€ SSRF Prevention: validate URL against denylist â”€â”€
    from developer.validators import validate_webhook_url, WebhookURLValidationError
    try:
        validate_webhook_url(endpoint.url)
    except WebhookURLValidationError as e:
        logger.error(
            'deliver_webhook: SSRF blocked for endpoint %s url=%s: %s',
            endpoint_id, endpoint.url, e,
        )
        WebhookDelivery.objects.create(
            endpoint=endpoint,
            event_type=event_type,
            payload=payload,
            attempt_number=attempt_number,
            error_message=f'URL validation failed (SSRF prevention): {e}',
            is_success=False,
        )
        return  # Do not retry SSRF-blocked URLs

    # Compute HMAC-SHA256 signature
    raw_secret = endpoint.get_signing_secret()
    payload_bytes = json.dumps(payload, separators=(',', ':'), sort_keys=True).encode('utf-8')
    timestamp = str(int(time.time()))
    signed_payload = f'{timestamp}.{payload_bytes.decode()}'.encode('utf-8')
    signature = hmac.new(
        raw_secret.encode('utf-8'),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()

    headers = {
        'Content-Type': 'application/json',
        'X-TalentOrbit-Event': event_type,
        'X-TalentOrbit-Timestamp': timestamp,
        'X-TalentOrbit-Signature': f'v1={signature}',
        'User-Agent': 'TalentOrbit-Webhook/1.0',
    }

    start = time.monotonic()
    try:
        resp = http_requests.post(
            endpoint.url,
            data=payload_bytes,
            headers=headers,
            timeout=10,
        )
        elapsed = int((time.monotonic() - start) * 1000)
        is_success = 200 <= resp.status_code < 300

        WebhookDelivery.objects.create(
            endpoint=endpoint,
            event_type=event_type,
            payload=payload,
            status_code=resp.status_code,
            response_body=resp.text[:2048],
            response_time_ms=elapsed,
            attempt_number=attempt_number,
            is_success=is_success,
        )

        if is_success:
            endpoint.failure_count = 0
        else:
            endpoint.failure_count += 1

        endpoint.last_delivery_at = timezone.now()
        endpoint.last_status_code = resp.status_code
        endpoint.save(update_fields=['failure_count', 'last_delivery_at', 'last_status_code'])

        if not is_success and resp.status_code >= 500:
            # Retry on 5xx server errors
            raise self.retry(
                exc=Exception(f'Webhook returned {resp.status_code}'),
                countdown=30 * (2 ** self.request.retries),  # Exponential backoff
            )

    except http_requests.RequestException as exc:
        elapsed = int((time.monotonic() - start) * 1000)

        WebhookDelivery.objects.create(
            endpoint=endpoint,
            event_type=event_type,
            payload=payload,
            response_time_ms=elapsed,
            attempt_number=attempt_number,
            error_message=str(exc)[:500],
            is_success=False,
        )

        endpoint.failure_count += 1
        endpoint.save(update_fields=['failure_count'])

        logger.warning(
            'deliver_webhook: endpoint %s failed (attempt %d): %s',
            endpoint_id, attempt_number, str(exc)[:200],
        )
        raise self.retry(
            exc=exc,
            countdown=30 * (2 ** self.request.retries),
        )


def compute_webhook_signature(secret: str, timestamp: str, payload_bytes: bytes) -> str:
    """
    Compute an HMAC-SHA256 signature for webhook payload verification.

    This function is exposed for use in the test ping view and in
    consumer-side verification documentation.

    Args:
        secret: The raw signing secret string.
        timestamp: Unix timestamp string.
        payload_bytes: The JSON payload as bytes.

    Returns:
        Hex-encoded HMAC-SHA256 signature string prefixed with 'v1='.
    """
    signed_payload = f'{timestamp}.{payload_bytes.decode()}'.encode('utf-8')
    sig = hmac.new(
        secret.encode('utf-8'),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()
    return f'v1={sig}'


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# 2. Periodic Cleanup â€” Prune Old Delivery Logs
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@shared_task(
    base=BaseTaskWithDLQ,
    bind=True,
    name='developer.prune_delivery_logs',
    max_retries=1,
    default_retry_delay=120,
    queue='default',
)
def prune_delivery_logs(self, retention_days: int = 30):
    """
    Delete WebhookDelivery records older than `retention_days`.
    Scheduled: daily via celery-beat.
    """
    from datetime import timedelta
    from django.utils import timezone
    from developer.models import WebhookDelivery

    cutoff = timezone.now() - timedelta(days=retention_days)
    deleted_count, _ = WebhookDelivery.objects.filter(
        delivered_at__lt=cutoff,
    ).delete()
    logger.info('prune_delivery_logs: deleted %d delivery records older than %d days.', deleted_count, retention_days)



