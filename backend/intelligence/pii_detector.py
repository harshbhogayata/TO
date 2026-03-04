"""
intelligence/pii_detector.py
Enterprise PII detection and input sanitisation for AI pipeline.

Detects and redacts personally identifiable information (PII) before
content is sent to third-party LLM providers (OpenAI). Also provides
prompt injection detection and input length validation.

Patterns:
    - SSN (US Social Security Number)
    - Credit card numbers (Visa, MC, Amex, Discover)
    - Email addresses
    - Phone numbers (US/international)
    - Passport numbers
    - IP addresses
    - Date of birth patterns

Security notes:
    - Detected PII types are logged, but the actual PII values are NEVER logged.
    - Redaction returns [TYPE_REDACTED] placeholders.
    - Prompt injection patterns are checked BEFORE any LLM call.
"""

import re
import logging
from typing import Tuple, List

logger = logging.getLogger(__name__)

# ─── PII Detection Patterns ──────────────────────────────────────────────────

PII_PATTERNS = {
    'ssn': re.compile(
        r'\b\d{3}-\d{2}-\d{4}\b'
    ),
    'credit_card': re.compile(
        r'\b(?:\d{4}[-\s]?){3}\d{4}\b'
    ),
    'email': re.compile(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    ),
    'phone': re.compile(
        r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'
    ),
    'passport': re.compile(
        r'\b[A-Z]{1,2}\d{6,9}\b'
    ),
    'ip_address': re.compile(
        r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
    ),
    'date_of_birth': re.compile(
        r'\b(?:0[1-9]|1[0-2])[/\-](?:0[1-9]|[12]\d|3[01])[/\-](?:19|20)\d{2}\b'
    ),
}


def strip_pii(text: str) -> Tuple[str, List[str]]:
    """
    Detect and redact PII from input text.

    Args:
        text: Raw input text potentially containing PII.

    Returns:
        Tuple of (cleaned_text, list_of_detected_pii_types).
        Detected types are strings like 'ssn', 'email', etc.
        Actual PII values are replaced with [TYPE_REDACTED] placeholders.
    """
    if not text:
        return text, []

    detected = []
    cleaned = text

    for pii_type, pattern in PII_PATTERNS.items():
        if pattern.search(cleaned):
            detected.append(pii_type)
            cleaned = pattern.sub(f'[{pii_type.upper()}_REDACTED]', cleaned)

    if detected:
        logger.warning(
            'PII detected and redacted: types=%s (values NOT logged)',
            ', '.join(detected),
        )

    return cleaned, detected


# ─── Prompt Injection Detection ───────────────────────────────────────────────

# Patterns that indicate prompt injection attempts.
# These are checked case-insensitively against user input.
_INJECTION_PATTERNS = [
    re.compile(r'ignore\s+(all\s+)?previous\s+instructions', re.IGNORECASE),
    re.compile(r'ignore\s+(all\s+)?above\s+instructions', re.IGNORECASE),
    re.compile(r'disregard\s+(all\s+)?previous', re.IGNORECASE),
    re.compile(r'forget\s+(all\s+)?previous', re.IGNORECASE),
    re.compile(r'override\s+system\s+prompt', re.IGNORECASE),
    re.compile(r'you\s+are\s+now\s+(?:a|an)\s+', re.IGNORECASE),
    re.compile(r'new\s+instructions?\s*:', re.IGNORECASE),
    re.compile(r'system\s*:\s*', re.IGNORECASE),
    re.compile(r'<\s*system\s*>', re.IGNORECASE),
    re.compile(r'\[\s*INST\s*\]', re.IGNORECASE),
    re.compile(r'ADMIN\s+MODE', re.IGNORECASE),
    re.compile(r'developer\s+mode', re.IGNORECASE),
    re.compile(r'jailbreak', re.IGNORECASE),
    re.compile(r'DAN\s+mode', re.IGNORECASE),
    re.compile(r'pretend\s+you\s+are', re.IGNORECASE),
    re.compile(r'act\s+as\s+if\s+you\s+have\s+no\s+restrictions', re.IGNORECASE),
]


def detect_prompt_injection(text: str) -> bool:
    """
    Check if the input text contains prompt injection patterns.

    Args:
        text: User input to check.

    Returns:
        True if a prompt injection pattern is detected.
    """
    if not text:
        return False

    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            logger.warning(
                'Prompt injection detected: pattern=%s',
                pattern.pattern[:40],
            )
            return True

    return False


# ─── Input Validation ─────────────────────────────────────────────────────────

_MAX_INPUT_LENGTH = 4000  # Characters


def validate_ai_input(
    text: str,
    max_length: int = _MAX_INPUT_LENGTH,
) -> Tuple[str, List[str]]:
    """
    Full input validation pipeline for AI endpoints:
        1. Length check
        2. Prompt injection detection
        3. PII stripping

    Args:
        text: Raw user input.
        max_length: Maximum allowed input length.

    Returns:
        Tuple of (cleaned_text, list_of_detected_pii_types).

    Raises:
        ValueError: If input is too long or contains prompt injection.
    """
    if not text:
        return '', []

    if len(text) > max_length:
        raise ValueError(
            f'Input exceeds maximum length of {max_length} characters '
            f'(received {len(text)}).'
        )

    if detect_prompt_injection(text):
        raise ValueError(
            'Input rejected: potentially harmful prompt detected. '
            'Please rephrase your request.'
        )

    cleaned, detected_pii = strip_pii(text)
    return cleaned, detected_pii


# ─── Content Moderation (Response) ────────────────────────────────────────────

_HARMFUL_PATTERNS = [
    re.compile(r'\b(?:hack|exploit|vulnerability|injection)\b.*(?:how\s+to|tutorial|guide)', re.IGNORECASE),
    re.compile(r'\b(?:steal|phish|scam|fraud)\b.*(?:how\s+to|tutorial|guide)', re.IGNORECASE),
]


def moderate_ai_response(response_text: str) -> Tuple[str, bool]:
    """
    Check AI-generated response for harmful content.

    Args:
        response_text: Text generated by the AI model.

    Returns:
        Tuple of (text, is_safe). If not safe, text is a replacement message.
    """
    if not response_text:
        return response_text, True

    for pattern in _HARMFUL_PATTERNS:
        if pattern.search(response_text):
            logger.warning('AI response flagged by content moderation')
            return (
                'I apologise, but I cannot provide that information. '
                'Please contact support for assistance.',
                False,
            )

    return response_text, True
