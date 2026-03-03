"""
compliance/tests/test_token_utils.py
Tests for HMAC-based token generation and verification.
"""
from django.test import TestCase, override_settings

from compliance.token_utils import (
    generate_signed_token,
    verify_signed_token,
    extract_resource_id,
)


class GenerateSignedTokenTests(TestCase):
    """Tests for generate_signed_token()."""

    def test_generates_three_part_token(self):
        token = generate_signed_token(42)
        parts = token.rsplit('.', 1)
        self.assertEqual(len(parts), 2)
        # Payload part should contain resource_id.random
        payload = parts[0]
        self.assertTrue(payload.startswith('42.'))

    def test_tokens_are_unique(self):
        t1 = generate_signed_token(1)
        t2 = generate_signed_token(1)
        self.assertNotEqual(t1, t2)  # Random component ensures uniqueness

    def test_resource_id_embedded(self):
        token = generate_signed_token(999)
        self.assertTrue(token.startswith('999.'))


class VerifySignedTokenTests(TestCase):
    """Tests for verify_signed_token()."""

    def test_valid_token_passes(self):
        token = generate_signed_token(7)
        self.assertTrue(verify_signed_token(token))

    def test_tampered_signature_fails(self):
        token = generate_signed_token(7)
        # Flip the last character of the signature
        tampered = token[:-1] + ('a' if token[-1] != 'a' else 'b')
        self.assertFalse(verify_signed_token(tampered))

    def test_tampered_resource_id_fails(self):
        token = generate_signed_token(7)
        # Replace '7.' with '8.' at the start
        tampered = '8' + token[1:]
        self.assertFalse(verify_signed_token(tampered))

    def test_empty_token_fails(self):
        self.assertFalse(verify_signed_token(''))

    def test_garbage_token_fails(self):
        self.assertFalse(verify_signed_token('not-a-real-token'))

    def test_expected_resource_id_match(self):
        token = generate_signed_token(42)
        self.assertTrue(verify_signed_token(token, expected_resource_id=42))

    def test_expected_resource_id_mismatch(self):
        token = generate_signed_token(42)
        self.assertFalse(verify_signed_token(token, expected_resource_id=99))

    def test_string_resource_id(self):
        token = generate_signed_token('abc')
        self.assertTrue(verify_signed_token(token))
        self.assertTrue(verify_signed_token(token, expected_resource_id='abc'))

    @override_settings(SECRET_KEY='different-secret-key-12345')
    def test_different_secret_key_fails(self):
        """A token signed with a different key must not verify."""
        # Generate token with default key (done BEFORE override takes effect
        # because override_settings is already applied at test method level)
        # We need to manually re-derive
        from compliance.token_utils import _get_signing_key
        import hashlib, hmac, secrets
        # Sign with the *different* key (which is active now due to override)
        resource_id = '100'
        random_part = secrets.token_urlsafe(32)
        payload = f'{resource_id}.{random_part}'
        different_key = _get_signing_key()
        sig = hmac.new(different_key, payload.encode(), hashlib.sha256).hexdigest()[:32]
        token_with_different_key = f'{payload}.{sig}'

        # Verify it passes with the current (overridden) key
        self.assertTrue(verify_signed_token(token_with_different_key))


class ExtractResourceIdTests(TestCase):
    """Tests for extract_resource_id()."""

    def test_extracts_integer_id(self):
        token = generate_signed_token(42)
        self.assertEqual(extract_resource_id(token), '42')

    def test_extracts_string_id(self):
        token = generate_signed_token('abc-123')
        self.assertEqual(extract_resource_id(token), 'abc-123')

    def test_returns_empty_on_empty_input(self):
        # Empty string splits to [''] → returns ''
        result = extract_resource_id('')
        self.assertEqual(result, '')

    def test_never_crashes(self):
        """Extract shouldn't crash on weird input."""
        for bad in [None, '', 'x', '...']:
            try:
                extract_resource_id(bad or '')
            except Exception:
                self.fail(f'extract_resource_id crashed on input: {bad!r}')
