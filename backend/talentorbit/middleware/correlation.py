"""
talentorbit/middleware/correlation.py
Correlation ID middleware for distributed tracing.

Injects a unique UUID correlation ID into every HTTP request and propagates
it through the response headers. This enables end-to-end request tracing
across the API → Celery task → WebSocket pipeline.

Usage:
    - Access in views/signals: `get_correlation_id()`
    - Access in Celery tasks: pass via task headers
    - Frontend: read `X-Correlation-ID` response header for error reports

Thread-safety:
    Uses threading.local() for per-request isolation in sync Django.
    For async views, use contextvar-based approach.
"""
import json
import logging
import threading
import uuid

_local = threading.local()


def get_correlation_id() -> str:
    """Retrieve the current request's correlation ID from thread-local storage."""
    return getattr(_local, 'correlation_id', 'unknown')


def set_correlation_id(correlation_id: str) -> None:
    """
    Manually set the correlation ID (useful in Celery tasks).

    Example in a Celery task:
        @shared_task
        def my_task(data, correlation_id=None):
            if correlation_id:
                set_correlation_id(correlation_id)
            ...
    """
    _local.correlation_id = correlation_id


def clear_correlation_id() -> None:
    """Remove correlation ID from thread-local storage."""
    _local.correlation_id = None


class CorrelationIdMiddleware:
    """
    Django middleware that:
        1. Reads X-Correlation-ID from incoming request headers (or generates one)
        2. Stores it in thread-local for access throughout the request lifecycle
        3. Adds it to the response headers for client-side tracing
        4. Adds it to Sentry context (if Sentry is configured)
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Read existing correlation ID or generate new one
        correlation_id = (
            request.META.get('HTTP_X_CORRELATION_ID')
            or str(uuid.uuid4())
        )

        # Store in thread-local
        _local.correlation_id = correlation_id

        # Attach to request object for easy access in views
        request.correlation_id = correlation_id

        # Add to Sentry context if available
        try:
            import sentry_sdk
            sentry_sdk.set_tag('correlation_id', correlation_id)
        except (ImportError, Exception):
            pass

        response = self.get_response(request)

        # Add to response headers
        response['X-Correlation-ID'] = correlation_id

        # Cleanup thread-local
        clear_correlation_id()

        return response


class StructuredJsonFormatter(logging.Formatter):
    """
    JSON log formatter that includes correlation_id for structured logging.

    Output format:
        {"timestamp": "...", "level": "INFO", "correlation_id": "abc-123",
         "logger": "payments", "message": "...", "module": "views", "line": 42}
    """

    def format(self, record):
        log_entry = {
            'timestamp': self.formatTime(record),
            'level': record.levelname,
            'correlation_id': get_correlation_id(),
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'line': record.lineno,
        }

        # Add user_id if available
        user_id = getattr(record, 'user_id', None)
        if user_id:
            log_entry['user_id'] = user_id

        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)
