"""
compliance/apps.py
Phase 6 — Trust & Compliance application configuration.
"""
from django.apps import AppConfig


class ComplianceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'compliance'
    verbose_name = 'Trust & Compliance'

    def ready(self):
        # Register signal handlers for automatic audit logging.
        import compliance.signals  # noqa: F401
