"""
realtime/push.py
Firebase Cloud Messaging (FCM) push notification service.

Sends push notifications to users who have registered their device tokens.
Falls back gracefully when Firebase is not configured (development).

Usage:
    from realtime.push import send_push_notification
    send_push_notification(user_id=42, title='New message', body='Hello!')
"""

import logging
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)

# ─── Firebase initialization (lazy, singleton) ───────────────────────────────
_firebase_app = None
_firebase_initialized = False


def _get_firebase_app():
    """
    Initialize Firebase Admin SDK once using the service account key
    specified in settings.FIREBASE_CREDENTIALS_PATH.

    Returns None if Firebase is not configured (development mode).
    """
    global _firebase_app, _firebase_initialized

    if _firebase_initialized:
        return _firebase_app

    _firebase_initialized = True

    cred_path = getattr(settings, 'FIREBASE_CREDENTIALS_PATH', '')
    if not cred_path:
        logger.info('Firebase not configured (FIREBASE_CREDENTIALS_PATH not set). Push notifications disabled.')
        return None

    try:
        import firebase_admin
        from firebase_admin import credentials

        cred = credentials.Certificate(cred_path)
        _firebase_app = firebase_admin.initialize_app(cred)
        logger.info('Firebase Admin SDK initialized successfully.')
        return _firebase_app
    except Exception:
        logger.exception('Failed to initialize Firebase Admin SDK.')
        return None


def send_push_notification(
    user_id: int,
    title: str,
    body: str,
    data: Optional[dict] = None,
    url: Optional[str] = None,
) -> dict:
    """
    Send a push notification to all registered devices for a user.

    Args:
        user_id: The user to notify.
        title: Notification title.
        body: Notification body text.
        data: Optional data payload (key-value strings).
        url: Optional click-through URL.

    Returns:
        dict with 'sent' count and 'failed' count.
    """
    from realtime.models import PushSubscription

    app = _get_firebase_app()
    if app is None:
        logger.debug('Push notification skipped (Firebase not configured): user=%s', user_id)
        return {'sent': 0, 'failed': 0, 'reason': 'firebase_not_configured'}

    tokens = list(
        PushSubscription.objects.filter(
            user_id=user_id, is_active=True
        ).values_list('token', flat=True)
    )

    if not tokens:
        return {'sent': 0, 'failed': 0, 'reason': 'no_tokens'}

    from firebase_admin import messaging

    notification = messaging.Notification(title=title, body=body)

    # Build web push config for click action
    web_push_data = data or {}
    if url:
        web_push_data['click_action'] = url

    webpush_config = messaging.WebpushConfig(
        notification=messaging.WebpushNotification(
            title=title,
            body=body,
            icon='/icon-192.svg',
            badge='/icon-192.svg',
        ),
        fcm_options=messaging.WebpushFCMOptions(link=url) if url else None,
    )

    sent = 0
    failed = 0
    stale_tokens = []

    for token in tokens:
        message = messaging.Message(
            notification=notification,
            data={k: str(v) for k, v in web_push_data.items()} if web_push_data else None,
            webpush=webpush_config,
            token=token,
        )
        try:
            messaging.send(message, app=app)
            sent += 1
        except messaging.UnregisteredError:
            stale_tokens.append(token)
            failed += 1
        except Exception:
            logger.exception('FCM send failed for token: %s...', token[:20])
            failed += 1

    # Clean up stale tokens
    if stale_tokens:
        PushSubscription.objects.filter(token__in=stale_tokens).update(is_active=False)
        logger.info('Deactivated %d stale push tokens for user %s', len(stale_tokens), user_id)

    return {'sent': sent, 'failed': failed}


def send_push_to_multiple_users(
    user_ids: list[int],
    title: str,
    body: str,
    data: Optional[dict] = None,
    url: Optional[str] = None,
) -> dict:
    """Send push notifications to multiple users."""
    total_sent = 0
    total_failed = 0

    for uid in user_ids:
        result = send_push_notification(uid, title, body, data, url)
        total_sent += result.get('sent', 0)
        total_failed += result.get('failed', 0)

    return {'sent': total_sent, 'failed': total_failed}
