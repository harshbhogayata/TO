"""
compliance/token_utils.py
HMAC-based token generation and verification for security-critical tokens.

Provides tamper-proof tokens that embed the resource identifier and can be
verified without a DB lookup (though DB lookup is still done for status checks).

Token format: <resource_id>:<random_bytes>:<hmac_signature>
    - resource_id: the PK of the associated model instance (e.g. invitation ID)
    - random_bytes: 32 bytes of cryptographic randomness (URL-safe base64)
    - hmac_signature: HMAC-SHA256 of (resource_id + random_bytes) using SECRET_KEY

This prevents:
    - Token forgery (attacker can't produce valid HMAC without SECRET_KEY)
    - Token reuse across resources (resource_id is bound into the signature)
"""
import hashlib
import hmac
import secrets

from django.conf import settings


def _get_signing_key() -> bytes:
    """Derive a stable signing key from Django SECRET_KEY."""
    return hashlib.sha256(
        f'compliance-token-v1:{settings.SECRET_KEY}'.encode()
    ).digest()


def generate_signed_token(resource_id: int | str) -> str:
    """
    Generate an HMAC-signed token bound to the given resource ID.

    Returns a URL-safe string: "<resource_id>.<random>.<signature>"
    """
    resource_id = str(resource_id)
    random_part = secrets.token_urlsafe(32)
    payload = f'{resource_id}.{random_part}'
    signature = hmac.new(
        _get_signing_key(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()[:32]  # Truncate to 32 hex chars (128 bits — ample for HMAC tag)
    return f'{payload}.{signature}'


def verify_signed_token(token: str, expected_resource_id: int | str = None) -> bool:
    """
    Verify that a token's HMAC is valid and optionally that it matches
    the expected resource ID.

    Returns True if the token is structurally valid and the HMAC matches.
    """
    try:
        parts = token.rsplit('.', 1)
        if len(parts) != 2:
            return False
        payload, provided_sig = parts
        # Recompute HMAC
        expected_sig = hmac.new(
            _get_signing_key(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()[:32]
        if not hmac.compare_digest(provided_sig, expected_sig):
            return False
        # Optionally verify resource_id
        if expected_resource_id is not None:
            token_resource_id = payload.split('.', 1)[0]
            if token_resource_id != str(expected_resource_id):
                return False
        return True
    except Exception:
        return False


def extract_resource_id(token: str) -> str | None:
    """Extract the resource_id from a signed token (without verifying)."""
    try:
        return token.split('.', 1)[0]
    except Exception:
        return None
