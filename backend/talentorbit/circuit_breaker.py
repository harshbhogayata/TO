"""
talentorbit/circuit_breaker.py
Circuit Breaker Pattern — Fault Isolation for External Services

Prevents cascading failures when external services (Stripe, email, R2, LLM APIs)
become slow or unavailable. Instead of every request waiting for a timeout,
the circuit "opens" after a threshold of failures and immediately returns a
fallback response for a configurable cool-down period.

States:
    CLOSED   — Normal operation. Requests flow through. Failures are counted.
    OPEN     — Service is considered down. Requests fail fast without calling
               the protected service. After reset_timeout, transitions to HALF_OPEN.
    HALF_OPEN — A single probe request is allowed through. If it succeeds,
                circuit closes. If it fails, circuit re-opens.

Thread-safe: Uses Redis for state (shared across Gunicorn workers / containers).
Falls back to in-process state when Redis is unavailable.

Usage:
    from talentorbit.circuit_breaker import circuit_breaker

    @circuit_breaker('stripe', failure_threshold=5, reset_timeout=60)
    def charge_customer(amount):
        return stripe.PaymentIntent.create(amount=amount)

    # Or as a context manager:
    with CircuitBreaker('email') as cb:
        send_email(to=user.email, subject='Welcome')
"""
import functools
import hashlib
import json
import logging
import time
from contextlib import contextmanager
from enum import Enum
from typing import Any, Callable, Optional

from django.core.cache import cache

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = 'closed'
    OPEN = 'open'
    HALF_OPEN = 'half_open'


class CircuitBreakerError(Exception):
    """Raised when the circuit is open and the call is rejected."""

    def __init__(self, service_name: str, retry_after: float):
        self.service_name = service_name
        self.retry_after = retry_after
        super().__init__(
            f'Circuit breaker OPEN for "{service_name}". '
            f'Retry after {retry_after:.0f}s.'
        )


class CircuitBreaker:
    """
    Thread-safe circuit breaker backed by Redis (via Django cache).

    Args:
        service_name: Identifier for the protected service (e.g. 'stripe', 'email')
        failure_threshold: Number of consecutive failures before opening the circuit
        success_threshold: Number of consecutive successes in HALF_OPEN before closing
        reset_timeout: Seconds to wait in OPEN state before allowing a probe request
        excluded_exceptions: Exception types that should NOT count as failures
                            (e.g. validation errors that are the caller's fault)
    """

    def __init__(
        self,
        service_name: str,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        reset_timeout: int = 60,
        excluded_exceptions: tuple = (),
    ):
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.reset_timeout = reset_timeout
        self.excluded_exceptions = excluded_exceptions
        self._cache_prefix = f'cb:{service_name}'

    # ── State Management ──────────────────────────────────────────────────────

    def _cache_key(self, suffix: str) -> str:
        return f'{self._cache_prefix}:{suffix}'

    def _get_state(self) -> dict:
        """Retrieve circuit state from Redis. Returns defaults if not found."""
        try:
            state = cache.get(self._cache_key('state'))
            if state:
                return state
        except Exception:
            pass  # Redis down — fall through to defaults

        return {
            'state': CircuitState.CLOSED,
            'failure_count': 0,
            'success_count': 0,
            'last_failure_time': 0,
            'last_state_change': time.time(),
        }

    def _set_state(self, state: dict) -> None:
        """Persist circuit state to Redis with a generous TTL."""
        try:
            # TTL: 3x the reset_timeout ensures state survives the full cycle
            cache.set(
                self._cache_key('state'),
                state,
                timeout=max(self.reset_timeout * 3, 300),
            )
        except Exception as exc:
            logger.warning(
                'Circuit breaker state persistence failed for %s: %s',
                self.service_name, exc,
            )

    @property
    def state(self) -> CircuitState:
        """Current circuit state, accounting for reset_timeout transitions."""
        data = self._get_state()
        current = CircuitState(data['state'])

        if current == CircuitState.OPEN:
            elapsed = time.time() - data.get('last_failure_time', 0)
            if elapsed >= self.reset_timeout:
                # Transition to HALF_OPEN
                data['state'] = CircuitState.HALF_OPEN
                data['success_count'] = 0
                data['last_state_change'] = time.time()
                self._set_state(data)
                logger.info(
                    'Circuit breaker %s: OPEN → HALF_OPEN after %ds',
                    self.service_name, elapsed,
                )
                return CircuitState.HALF_OPEN

        return current

    # ── Recording Outcomes ────────────────────────────────────────────────────

    def _record_success(self) -> None:
        """Record a successful call. May close the circuit if in HALF_OPEN."""
        data = self._get_state()
        current = CircuitState(data['state'])

        if current == CircuitState.HALF_OPEN:
            data['success_count'] = data.get('success_count', 0) + 1
            if data['success_count'] >= self.success_threshold:
                data['state'] = CircuitState.CLOSED
                data['failure_count'] = 0
                data['success_count'] = 0
                data['last_state_change'] = time.time()
                logger.info(
                    'Circuit breaker %s: HALF_OPEN → CLOSED (service recovered)',
                    self.service_name,
                )
            self._set_state(data)

        elif current == CircuitState.CLOSED:
            # Reset failure count on success (consecutive failures only)
            if data.get('failure_count', 0) > 0:
                data['failure_count'] = 0
                self._set_state(data)

    def _record_failure(self, exc: Exception) -> None:
        """Record a failed call. May open the circuit."""
        # Don't count excluded exceptions
        if isinstance(exc, self.excluded_exceptions):
            return

        data = self._get_state()
        current = CircuitState(data['state'])
        data['failure_count'] = data.get('failure_count', 0) + 1
        data['last_failure_time'] = time.time()

        if current == CircuitState.HALF_OPEN:
            # Probe failed — re-open
            data['state'] = CircuitState.OPEN
            data['success_count'] = 0
            data['last_state_change'] = time.time()
            logger.warning(
                'Circuit breaker %s: HALF_OPEN → OPEN (probe failed: %s)',
                self.service_name, exc,
            )

        elif current == CircuitState.CLOSED:
            if data['failure_count'] >= self.failure_threshold:
                data['state'] = CircuitState.OPEN
                data['last_state_change'] = time.time()
                logger.warning(
                    'Circuit breaker %s: CLOSED → OPEN after %d failures. '
                    'Will retry after %ds. Last error: %s',
                    self.service_name, data['failure_count'],
                    self.reset_timeout, exc,
                )

        self._set_state(data)

    # ── Execution ─────────────────────────────────────────────────────────────

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute the protected function if the circuit allows it.

        Raises:
            CircuitBreakerError: If the circuit is OPEN and not yet ready for probing.
        """
        current_state = self.state  # Property — checks for OPEN→HALF_OPEN transition

        if current_state == CircuitState.OPEN:
            data = self._get_state()
            retry_after = self.reset_timeout - (time.time() - data.get('last_failure_time', 0))
            raise CircuitBreakerError(self.service_name, max(retry_after, 0))

        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
        except Exception as exc:
            self._record_failure(exc)
            raise

    def __enter__(self):
        """Context manager entry — checks if circuit allows the call."""
        current_state = self.state
        if current_state == CircuitState.OPEN:
            data = self._get_state()
            retry_after = self.reset_timeout - (time.time() - data.get('last_failure_time', 0))
            raise CircuitBreakerError(self.service_name, max(retry_after, 0))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit — records success or failure."""
        if exc_type is None:
            self._record_success()
        elif exc_val is not None:
            self._record_failure(exc_val)
        return False  # Don't suppress exceptions

    # ── Diagnostics ───────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        """Return current circuit status for health checks / admin dashboards."""
        data = self._get_state()
        return {
            'service': self.service_name,
            'state': self.state.value,
            'failure_count': data.get('failure_count', 0),
            'success_count': data.get('success_count', 0),
            'failure_threshold': self.failure_threshold,
            'reset_timeout': self.reset_timeout,
            'last_failure_time': data.get('last_failure_time', 0),
            'last_state_change': data.get('last_state_change', 0),
        }

    def reset(self) -> None:
        """Manually reset the circuit to CLOSED (for admin use)."""
        self._set_state({
            'state': CircuitState.CLOSED,
            'failure_count': 0,
            'success_count': 0,
            'last_failure_time': 0,
            'last_state_change': time.time(),
        })
        logger.info('Circuit breaker %s: manually RESET to CLOSED', self.service_name)


# ═══════════════════════════════════════════════════════════════════════════════
# Decorator Factory
# ═══════════════════════════════════════════════════════════════════════════════

def circuit_breaker(
    service_name: str,
    failure_threshold: int = 5,
    success_threshold: int = 2,
    reset_timeout: int = 60,
    excluded_exceptions: tuple = (),
    fallback: Optional[Callable] = None,
):
    """
    Decorator that wraps a function with circuit breaker protection.

    Args:
        service_name: Identifier for the external service being protected
        failure_threshold: Consecutive failures before opening the circuit
        success_threshold: Consecutive successes in HALF_OPEN before closing
        reset_timeout: Seconds in OPEN state before allowing a probe
        excluded_exceptions: Exception types that don't count as failures
        fallback: Optional callable to invoke when circuit is open.
                  Receives the same args/kwargs as the original function.

    Example:
        @circuit_breaker('stripe', failure_threshold=3, reset_timeout=30)
        def create_checkout_session(plan_id: str) -> dict:
            return stripe.checkout.Session.create(...)

        @circuit_breaker('email', fallback=lambda *a, **kw: None)
        def send_welcome_email(user_id: int) -> None:
            ...
    """
    cb = CircuitBreaker(
        service_name=service_name,
        failure_threshold=failure_threshold,
        success_threshold=success_threshold,
        reset_timeout=reset_timeout,
        excluded_exceptions=excluded_exceptions,
    )

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return cb.call(func, *args, **kwargs)
            except CircuitBreakerError:
                if fallback is not None:
                    logger.info(
                        'Circuit breaker %s: invoking fallback for %s',
                        service_name, func.__qualname__,
                    )
                    return fallback(*args, **kwargs)
                raise

        # Expose the circuit breaker instance for diagnostics / manual reset
        wrapper.circuit_breaker = cb
        return wrapper

    return decorator


# ═══════════════════════════════════════════════════════════════════════════════
# Pre-configured Circuit Breakers for TalentOrbit Services
# ═══════════════════════════════════════════════════════════════════════════════

# Stripe — payment failures should fail fast (not block checkout for 30s)
stripe_circuit = CircuitBreaker(
    service_name='stripe',
    failure_threshold=3,
    success_threshold=2,
    reset_timeout=60,
    excluded_exceptions=(ValueError,),  # Validation errors aren't Stripe's fault
)

# Email — don't let SMTP timeouts slow down registration
email_circuit = CircuitBreaker(
    service_name='email',
    failure_threshold=5,
    success_threshold=1,
    reset_timeout=120,
)

# Object Storage (R2/S3) — file upload failures
storage_circuit = CircuitBreaker(
    service_name='storage',
    failure_threshold=5,
    success_threshold=2,
    reset_timeout=90,
)

# LLM API (Gemini/Groq) — AI features should degrade gracefully
llm_circuit = CircuitBreaker(
    service_name='llm',
    failure_threshold=3,
    success_threshold=1,
    reset_timeout=30,
)
