"""
Test settings â€” forces SQLite + disables Sentry for fast local test runs.
Usage: python manage.py test --settings=talentorbit.test_settings
"""
import os

# Prevent .env from setting DATABASE_URL before our main settings load
os.environ['DATABASE_URL'] = ''
os.environ['SENTRY_DSN'] = ''
os.environ.setdefault('SECRET_KEY', 'test-secret-key-not-for-production')
os.environ.setdefault('DEBUG', 'True')

from talentorbit.settings import *  # noqa: F401, F403

# Allow the default test client host
ALLOWED_HOSTS = ['*']

# Force SQLite for tests (fast, no external dependencies)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Fast password hashing for tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Disable throttling in tests â€” set rates to None or keep compliance rates
REST_FRAMEWORK['DEFAULT_THROTTLE_CLASSES'] = []
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {
    'anon': None,
    'user': None,
    'auth': None,
    'contact': None,
    # Compliance-specific rates (views use per-view throttle_classes)
    'compliance_export': '999/minute',
    'compliance_export_download': '999/minute',
    'compliance_deletion': '999/minute',
    'compliance_deletion_confirm': '999/minute',
    'compliance_consent_write': '999/minute',
    'compliance_team_invite': '999/minute',
    'compliance_team_invite_action': '999/minute',
    'compliance_audit': '999/minute',
    'compliance_audit_integrity': '999/minute',
    'compliance_policy_create': '999/minute',
    'resume_authenticated': '999/minute',
    'resume_public': '999/minute',
    'ai_resume_authenticated': '999/minute',
    'ai_resume_public': '999/minute',
    'developer_key_create': '999/minute',
    'developer_key_rotate': '999/minute',
    'developer_webhook_create': '999/minute',
    'developer_webhook_test': '999/minute',
    'developer_oauth_create': '999/minute',
    'developer_oauth_revoke': '999/minute',
}

# In-memory cache
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# In-memory email
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# Celery â€” run tasks synchronously in tests (no broker needed)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_RESULT_BACKEND = 'django-db'

# Channel layer â€” in-memory for tests
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    },
}


# Skip migrations entirely â€” create tables from models so SQLite works
# (avoids pg_trgm CREATE EXTENSION in search.0002_gin_indexes).
class _DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = _DisableMigrations()

