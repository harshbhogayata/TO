"""
compliance/decorators.py
Phase 6 — Audit action decorator for DRF views.

Usage:
    @audit_action(
        action=AuditAction.CREATE,
        category=AuditCategory.JOB,
        description='Created a new job post',
    )
    def create(self, request, *args, **kwargs):
        ...

The decorator captures the request context (IP, user-agent, request ID)
and creates an AuditLog entry after the view executes successfully.

For views that modify resources, pass `resource_type` and use
`get_resource_id` to dynamically extract the resource ID from the response.
"""
import functools
import logging

from compliance.constants import AuditAction, AuditCategory

logger = logging.getLogger(__name__)


def audit_action(
    action: str,
    category: str,
    description: str = '',
    resource_type: str = '',
    get_resource_id: callable = None,
    get_description: callable = None,
    get_changes: callable = None,
):
    """
    Decorator that creates an AuditLog entry after a successful DRF view call.

    Args:
        action: AuditAction constant (e.g. AuditAction.CREATE).
        category: AuditCategory constant (e.g. AuditCategory.JOB).
        description: Static description string.
        resource_type: Django model label (e.g. 'jobs.JobPost').
        get_resource_id: Callable(request, response) -> str that extracts
            the resource ID from the response data.
        get_description: Callable(request, response) -> str for dynamic description.
        get_changes: Callable(request, response) -> dict for structured changes.
    """

    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(*args, **kwargs):
            # Support both function-based views (request is first arg)
            # and class-based views (request is second arg after self)
            request = None
            for arg in args:
                if hasattr(arg, 'method') and hasattr(arg, 'user'):
                    request = arg
                    break

            response = view_func(*args, **kwargs)

            # Only audit successful responses (2xx)
            status_code = getattr(response, 'status_code', 200)
            if 200 <= status_code < 300 and request:
                try:
                    _create_audit_entry(
                        request=request,
                        response=response,
                        action=action,
                        category=category,
                        description=description,
                        resource_type=resource_type,
                        get_resource_id=get_resource_id,
                        get_description=get_description,
                        get_changes=get_changes,
                    )
                except Exception:
                    # Never let audit logging failure break the view
                    logger.exception('audit_action decorator: failed to create audit log')

            return response

        return wrapper

    return decorator


def _create_audit_entry(
    request,
    response,
    action,
    category,
    description,
    resource_type,
    get_resource_id,
    get_description,
    get_changes,
):
    """
    Internal helper — creates the AuditLog record with full context.
    """
    from compliance.models import AuditLog
    from compliance.middleware import get_audit_context

    ctx = get_audit_context()

    # Resolve dynamic values
    final_description = description
    if get_description:
        try:
            final_description = get_description(request, response)
        except Exception:
            pass

    final_resource_id = ''
    if get_resource_id:
        try:
            final_resource_id = str(get_resource_id(request, response))
        except Exception:
            pass

    final_changes = {}
    if get_changes:
        try:
            final_changes = get_changes(request, response)
        except Exception:
            pass

    AuditLog.objects.create(
        actor=request.user if request.user.is_authenticated else None,
        action=action,
        category=category,
        description=final_description,
        resource_type=resource_type,
        resource_id=final_resource_id,
        changes=final_changes,
        ip_address=ctx.get('ip_address'),
        user_agent=ctx.get('user_agent', ''),
        request_id=ctx.get('request_id'),
    )


def create_audit_log(
    *,
    actor=None,
    action: str,
    category: str,
    description: str,
    resource_type: str = '',
    resource_id: str = '',
    changes: dict = None,
    ip_address: str = None,
    user_agent: str = '',
    request_id=None,
):
    """
    Programmatic audit log creation — use from signals, tasks, or
    management commands where the decorator approach doesn't fit.

    Automatically fills in context from the AuditContextMiddleware
    if not explicitly provided.
    """
    from compliance.models import AuditLog
    from compliance.middleware import get_audit_context

    ctx = get_audit_context()

    AuditLog.objects.create(
        actor=actor,
        action=action,
        category=category,
        description=description,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id else '',
        changes=changes or {},
        ip_address=ip_address or ctx.get('ip_address') or None,
        user_agent=user_agent or ctx.get('user_agent') or '',
        request_id=request_id or ctx.get('request_id') or None,
    )
