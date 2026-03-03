"""
talentorbit/health.py
Deep Health Check System

Provides granular health probes for Kubernetes/Docker/Render:
    - /health/          — Shallow probe (DB connectivity only, fast, for load balancers)
    - /health/ready/    — Readiness probe (all critical services, K8s readinessProbe)
    - /health/live/     — Liveness probe (process alive, K8s livenessProbe)
    - /health/detailed/ — Full diagnostics (admin-only, includes latency measurements)

Design decisions:
    - Each check has a timeout to prevent one slow service from blocking the response
    - Checks run in parallel using concurrent.futures for speed
    - Results are cached for 5 seconds to prevent health checks from becoming a DDoS vector
    - Detailed endpoint requires admin authentication to prevent info leakage
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse

logger = logging.getLogger(__name__)

# How long each individual check can take before we mark it degraded
_CHECK_TIMEOUT_SECONDS = 5.0

# Cache health results to prevent thundering herd from monitoring tools
_CACHE_KEY = 'health:detailed'
_CACHE_TTL = 5  # seconds


# ═══════════════════════════════════════════════════════════════════════════════
# Individual Service Checks
# ═══════════════════════════════════════════════════════════════════════════════

def _check_database() -> dict:
    """Verify PostgreSQL connectivity and measure round-trip latency."""
    start = time.monotonic()
    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        return {
            'status': 'healthy',
            'latency_ms': latency_ms,
            'backend': connection.vendor,
        }
    except Exception as exc:
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        logger.error('Health check — database FAILED: %s', exc)
        return {
            'status': 'unhealthy',
            'latency_ms': latency_ms,
            'error': str(exc),
        }


def _check_cache() -> dict:
    """Verify Redis/cache connectivity via SET + GET + DELETE round-trip."""
    start = time.monotonic()
    sentinel_key = 'health:probe:sentinel'
    sentinel_value = f'probe-{time.time()}'
    try:
        cache.set(sentinel_key, sentinel_value, timeout=10)
        retrieved = cache.get(sentinel_key)
        cache.delete(sentinel_key)
        if retrieved != sentinel_value:
            raise ValueError(f'Cache read-back mismatch: wrote {sentinel_value!r}, got {retrieved!r}')
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        return {
            'status': 'healthy',
            'latency_ms': latency_ms,
            'backend': settings.CACHES['default']['BACKEND'].rsplit('.', 1)[-1],
        }
    except Exception as exc:
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        logger.error('Health check — cache FAILED: %s', exc)
        return {
            'status': 'unhealthy',
            'latency_ms': latency_ms,
            'error': str(exc),
        }


def _check_celery() -> dict:
    """Verify Celery broker connectivity by inspecting active workers."""
    start = time.monotonic()
    try:
        from talentorbit.celery import app as celery_app
        inspector = celery_app.control.inspect(timeout=3.0)
        ping_response = inspector.ping()
        latency_ms = round((time.monotonic() - start) * 1000, 2)

        if ping_response is None:
            return {
                'status': 'degraded',
                'latency_ms': latency_ms,
                'error': 'No workers responded to ping (broker may be unreachable or no workers running)',
                'workers': 0,
            }

        worker_count = len(ping_response)
        return {
            'status': 'healthy',
            'latency_ms': latency_ms,
            'workers': worker_count,
            'worker_names': list(ping_response.keys()),
        }
    except Exception as exc:
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        logger.error('Health check — celery FAILED: %s', exc)
        return {
            'status': 'unhealthy',
            'latency_ms': latency_ms,
            'error': str(exc),
        }


def _check_channels() -> dict:
    """Verify the Channels layer (Redis) by sending + receiving a test message."""
    start = time.monotonic()
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        channel_layer = get_channel_layer()
        if channel_layer is None:
            return {'status': 'skipped', 'reason': 'No channel layer configured'}

        test_channel = 'health.probe'
        test_message = {'type': 'health.check', 'ts': time.time()}

        async_to_sync(channel_layer.send)(test_channel, test_message)
        received = async_to_sync(channel_layer.receive)(test_channel)

        latency_ms = round((time.monotonic() - start) * 1000, 2)

        if received.get('ts') != test_message['ts']:
            return {
                'status': 'degraded',
                'latency_ms': latency_ms,
                'error': 'Channel layer round-trip message mismatch',
            }

        backend = settings.CHANNEL_LAYERS['default']['BACKEND'].rsplit('.', 1)[-1]
        return {
            'status': 'healthy',
            'latency_ms': latency_ms,
            'backend': backend,
        }
    except Exception as exc:
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        logger.error('Health check — channels FAILED: %s', exc)
        return {
            'status': 'unhealthy',
            'latency_ms': latency_ms,
            'error': str(exc),
        }


def _check_storage() -> dict:
    """Verify object storage (R2/S3/local filesystem) is writable."""
    start = time.monotonic()
    try:
        from django.core.files.storage import default_storage
        from django.core.files.base import ContentFile

        probe_name = 'health_probe/.health_check'
        content = ContentFile(b'health-check-probe')

        # Write
        saved_name = default_storage.save(probe_name, content)
        # Read-back existence
        exists = default_storage.exists(saved_name)
        # Cleanup
        default_storage.delete(saved_name)

        latency_ms = round((time.monotonic() - start) * 1000, 2)

        if not exists:
            return {
                'status': 'degraded',
                'latency_ms': latency_ms,
                'error': 'File saved but existence check returned False',
            }

        backend = settings.STORAGES.get('default', {}).get('BACKEND', 'unknown').rsplit('.', 1)[-1]
        return {
            'status': 'healthy',
            'latency_ms': latency_ms,
            'backend': backend,
        }
    except Exception as exc:
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        logger.error('Health check — storage FAILED: %s', exc)
        return {
            'status': 'unhealthy',
            'latency_ms': latency_ms,
            'error': str(exc),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Check Registry & Parallel Execution
# ═══════════════════════════════════════════════════════════════════════════════

# Critical checks: if any fail, readiness probe fails
_CRITICAL_CHECKS = {
    'database': _check_database,
    'cache': _check_cache,
}

# Non-critical checks: degradation doesn't fail readiness
_OPTIONAL_CHECKS = {
    'celery': _check_celery,
    'channels': _check_channels,
    'storage': _check_storage,
}

_ALL_CHECKS = {**_CRITICAL_CHECKS, **_OPTIONAL_CHECKS}


def _run_checks(checks: dict, timeout: float = _CHECK_TIMEOUT_SECONDS) -> dict:
    """
    Execute multiple health checks in parallel, respecting per-check timeouts.

    Returns:
        {
            'checks': {'database': {...}, 'cache': {...}, ...},
            'overall': 'healthy' | 'degraded' | 'unhealthy',
            'total_latency_ms': float,
        }
    """
    start = time.monotonic()
    results = {}

    with ThreadPoolExecutor(max_workers=len(checks)) as executor:
        future_to_name = {
            executor.submit(fn): name
            for name, fn in checks.items()
        }
        for future in as_completed(future_to_name, timeout=timeout + 1):
            name = future_to_name[future]
            try:
                results[name] = future.result(timeout=timeout)
            except Exception as exc:
                results[name] = {
                    'status': 'unhealthy',
                    'error': f'Check timed out or raised: {exc}',
                }

    # Determine overall status
    statuses = [r.get('status', 'unknown') for r in results.values()]
    if 'unhealthy' in statuses:
        overall = 'unhealthy'
    elif 'degraded' in statuses:
        overall = 'degraded'
    else:
        overall = 'healthy'

    total_ms = round((time.monotonic() - start) * 1000, 2)
    return {
        'checks': results,
        'overall': overall,
        'total_latency_ms': total_ms,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# HTTP Views
# ═══════════════════════════════════════════════════════════════════════════════

def health_shallow(request):
    """
    GET /health/
    Shallow probe — only checks DB. Fast. Used by load balancers and uptime monitors.
    Replaces the original health_check view in urls.py.
    """
    result = _check_database()
    status_code = 200 if result['status'] == 'healthy' else 503
    return JsonResponse({'status': result['status'], 'database': result}, status=status_code)


def health_ready(request):
    """
    GET /health/ready/
    Readiness probe — checks all critical services (DB + cache).
    Returns 503 if any critical service is unhealthy.
    Used by Kubernetes readinessProbe / Render zero-downtime deploys.
    """
    result = _run_checks(_CRITICAL_CHECKS)
    status_code = 200 if result['overall'] != 'unhealthy' else 503
    return JsonResponse({
        'status': result['overall'],
        'checks': result['checks'],
        'total_latency_ms': result['total_latency_ms'],
    }, status=status_code)


def health_live(request):
    """
    GET /health/live/
    Liveness probe — just confirms the process is running and can serve HTTP.
    Always returns 200 unless the process is truly dead.
    Used by Kubernetes livenessProbe.
    """
    return JsonResponse({'status': 'alive'})


def health_detailed(request):
    """
    GET /health/detailed/
    Full diagnostic endpoint — runs ALL checks including non-critical ones.
    ADMIN-ONLY: Requires authenticated admin user (prevents info leakage).
    Results are cached for 5 seconds to prevent health-check-as-DDoS.
    """
    # Auth check: only admins can see detailed health
    if not (request.user and request.user.is_authenticated and request.user.is_staff):
        return JsonResponse({'detail': 'Authentication required.'}, status=401)

    # Check cache first
    cached = cache.get(_CACHE_KEY)
    if cached:
        cached['cached'] = True
        return JsonResponse(cached)

    result = _run_checks(_ALL_CHECKS)
    response_data = {
        'status': result['overall'],
        'checks': result['checks'],
        'total_latency_ms': result['total_latency_ms'],
        'cached': False,
        'debug': settings.DEBUG,
        'environment': 'development' if settings.DEBUG else 'production',
    }

    # Cache the result
    cache.set(_CACHE_KEY, response_data, timeout=_CACHE_TTL)

    status_code = 200 if result['overall'] != 'unhealthy' else 503
    return JsonResponse(response_data, status=status_code)
