"""
accounts/crypto.py
TOTP secret signing for at-rest protection.
Uses Django's Signer (HMAC-based) — no extra dependencies needed.
"""
from django.core.signing import Signer, BadSignature

_signer = Signer(salt='talentorbit-totp-secret-v1')


def sign_totp(secret):
    """Sign a TOTP secret before storing in the database."""
    if not secret:
        return secret
    # Don't double-sign
    try:
        _signer.unsign(secret)
        return secret  # Already signed
    except BadSignature:
        return _signer.sign(secret)


def unsign_totp(signed_secret):
    """Recover the plaintext TOTP secret. Falls back gracefully for legacy unsigned values."""
    if not signed_secret:
        return signed_secret
    try:
        return _signer.unsign(signed_secret)
    except BadSignature:
        # Legacy unsigned value from before this migration — return as-is
        return signed_secret
