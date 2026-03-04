"""
developer/validators.py
Webhook URL validation for the developer platform.

Enforces denylist rules that prevent webhook endpoints from targeting
internal infrastructure, cloud metadata endpoints, or localhost.

Security rationale (OWASP A10 — SSRF):
    Without URL validation, a malicious developer could register a webhook
    pointing at 169.254.169.254 (cloud metadata) or internal services,
    exfiltrating secrets or causing internal requests.

Denylist approach:
    - Localhost (127.0.0.0/8, ::1)
    - Private networks (10/8, 172.16-31/12, 192.168/16)
    - Link-local (169.254/16)
    - Cloud metadata (169.254.169.254)
    - Non-HTTPS schemes in production
"""
import ipaddress
import logging
import re
from urllib.parse import urlparse

from django.conf import settings

logger = logging.getLogger(__name__)

# Private/reserved IP ranges that MUST NOT be targeted by webhooks
_DENIED_NETWORKS = [
    ipaddress.ip_network('127.0.0.0/8'),       # Loopback
    ipaddress.ip_network('10.0.0.0/8'),         # Private Class A
    ipaddress.ip_network('172.16.0.0/12'),      # Private Class B
    ipaddress.ip_network('192.168.0.0/16'),     # Private Class C
    ipaddress.ip_network('169.254.0.0/16'),     # Link-local (includes cloud metadata)
    ipaddress.ip_network('0.0.0.0/8'),          # "This" network
    ipaddress.ip_network('100.64.0.0/10'),      # Shared address space (CGN)
    ipaddress.ip_network('198.18.0.0/15'),      # Benchmarking
    ipaddress.ip_network('::1/128'),            # IPv6 loopback
    ipaddress.ip_network('fc00::/7'),           # IPv6 unique local
    ipaddress.ip_network('fe80::/10'),          # IPv6 link-local
]

# Hostnames that are always denied regardless of IP resolution
_DENIED_HOSTNAMES = {
    'localhost',
    'localhost.localdomain',
    'metadata.google.internal',           # GCP metadata
    'metadata.internal',
    'instance-data',                      # AWS alternative
}

# Cloud metadata IP — explicit check beyond CIDR ranges
_CLOUD_METADATA_IPS = {'169.254.169.254', '169.254.170.2'}


class WebhookURLValidationError(ValueError):
    """Raised when a webhook URL fails validation."""
    pass


def validate_webhook_url(url: str) -> str:
    """
    Validate a webhook URL against the SSRF denylist.

    Args:
        url: The webhook delivery URL to validate.

    Returns:
        The validated URL (stripped/normalised).

    Raises:
        WebhookURLValidationError: If the URL targets a denied host.
    """
    if not url or not isinstance(url, str):
        raise WebhookURLValidationError('Webhook URL is required.')

    url = url.strip()

    # Parse URL
    try:
        parsed = urlparse(url)
    except Exception:
        raise WebhookURLValidationError('Invalid URL format.')

    # Scheme validation
    if parsed.scheme not in ('http', 'https'):
        raise WebhookURLValidationError(
            f'Unsupported scheme: {parsed.scheme}. Only HTTP/HTTPS allowed.'
        )

    # Enforce HTTPS in production
    if not settings.DEBUG and parsed.scheme != 'https':
        raise WebhookURLValidationError(
            'Webhook URLs must use HTTPS in production.'
        )

    hostname = (parsed.hostname or '').lower()
    if not hostname:
        raise WebhookURLValidationError('URL must include a hostname.')

    # Check denied hostnames
    if hostname in _DENIED_HOSTNAMES:
        raise WebhookURLValidationError(
            f'Webhook URL hostname "{hostname}" is not allowed '
            f'(internal/localhost targets are prohibited).'
        )

    # Check if hostname is an IP address
    try:
        ip = ipaddress.ip_address(hostname)

        # Check cloud metadata IPs
        if hostname in _CLOUD_METADATA_IPS:
            raise WebhookURLValidationError(
                'Webhook URL must not target cloud metadata endpoints.'
            )

        # Check denied CIDR ranges
        for network in _DENIED_NETWORKS:
            if ip in network:
                raise WebhookURLValidationError(
                    f'Webhook URL must not target private/reserved IP ranges '
                    f'({network}).'
                )
    except ValueError:
        # hostname is not an IP address — that's fine, it's a domain name
        pass

    # Port validation — block common internal service ports
    port = parsed.port
    if port and port in (6379, 5432, 3306, 27017, 9200, 11211):
        raise WebhookURLValidationError(
            f'Webhook URL port {port} is commonly used by internal services '
            f'and is not allowed.'
        )

    logger.debug('Webhook URL validated: %s', url)
    return url
