"""
talentorbit/db_router.py
Database Router — Read Replica Routing

Routes read queries to a read replica when one is configured, while ensuring
all writes (and reads within transactions) go to the primary database.

This is a zero-configuration upgrade path:
    - With no 'replica' in DATABASES: everything uses 'default' (no-op router)
    - With DATABASES['replica'] configured: reads automatically distribute

Configuration (settings.py):
    DATABASE_ROUTERS = ['talentorbit.db_router.PrimaryReplicaRouter']

    DATABASES = {
        'default': { ... },          # Primary (read + write)
        'replica': { ... },          # Read replica (read-only)
    }

Design decisions:
    - Writes ALWAYS go to 'default' (primary)
    - Reads go to 'replica' if:
        1. A 'replica' database is configured
        2. The current request is NOT inside a transaction (consistency)
        3. The model is NOT in the ALWAYS_PRIMARY_MODELS list
    - Certain models (audit logs, payments) always read from primary to ensure
      strong consistency for compliance and financial data
    - Migrations always run against 'default'
"""

import logging

from django.conf import settings
from django.db import connection

logger = logging.getLogger(__name__)

# Models that should ALWAYS read from primary for strong consistency.
# Use the 'app_label.ModelName' format.
ALWAYS_PRIMARY_MODELS = frozenset({
    # Compliance — audit chain integrity requires sequential reads from primary
    'compliance.AuditLog',
    'compliance.DataExportRequest',
    'compliance.DataDeletionRequest',
    'compliance.ConsentRecord',
    # Payments — financial data must be strongly consistent
    'payments.StripeEvent',
    # Auth — token blacklisting must be immediately visible
    'token_blacklist.BlacklistedToken',
    'token_blacklist.OutstandingToken',
    # Celery — task results and schedules
    'django_celery_results.TaskResult',
    'django_celery_beat.PeriodicTask',
    'django_celery_beat.CrontabSchedule',
    'django_celery_beat.IntervalSchedule',
})


def _replica_configured() -> bool:
    """Check if a read replica is configured in DATABASES."""
    return 'replica' in settings.DATABASES


def _model_key(model) -> str:
    """Return 'app_label.ModelName' for a given model class."""
    return f'{model._meta.app_label}.{model.__name__}'


class PrimaryReplicaRouter:
    """
    Routes database operations between primary and replica.

    Read queries go to the replica (when configured and safe).
    Write queries and migrations always go to the primary.
    """

    def db_for_read(self, model, **hints):
        """
        Determine which database to use for read operations.

        Returns:
            'replica' if:
                - A replica is configured
                - The model doesn't require strong consistency
                - We're not inside an explicit atomic() transaction
            'default' otherwise
        """
        if not _replica_configured():
            return 'default'

        # Models requiring strong consistency always read from primary
        if _model_key(model) in ALWAYS_PRIMARY_MODELS:
            return 'default'

        # If we're inside a transaction, read from primary for consistency
        # (prevents dirty reads of data we just wrote)
        if connection.in_atomic_block:
            return 'default'

        # Check for explicit routing hint
        instance = hints.get('instance')
        if instance is not None and hasattr(instance, '_state') and instance._state.db:
            return instance._state.db

        return 'replica'

    def db_for_write(self, model, **hints):
        """All writes go to the primary database. Always."""
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations between objects in the same database group.
        Since default and replica point to the same underlying database,
        all relations are allowed.
        """
        db_set = {'default', 'replica'}
        if obj1._state.db in db_set and obj2._state.db in db_set:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Migrations only run on the primary database."""
        return db == 'default'
