"""
Local QA settings for manual browser verification.

This keeps the app close to normal runtime behavior while removing external
service dependencies that block local workflow checks:
- file-backed SQLite instead of production Postgres
- local filesystem media instead of R2/S3
- eager Celery tasks instead of a broker
- disabled Sentry/networked integrations

Usage:
    python manage.py migrate --run-syncdb --settings=talentorbit.local_qa_settings
    python manage.py seed --settings=talentorbit.local_qa_settings
    python manage.py runserver 127.0.0.1:8000 --settings=talentorbit.local_qa_settings --noreload
"""

import os

os.environ['DATABASE_URL'] = ''
os.environ['SENTRY_DSN'] = ''
os.environ.setdefault('SECRET_KEY', 'local-qa-secret-key-not-for-production')
os.environ.setdefault('DEBUG', 'True')

from talentorbit.settings import *  # noqa: F401, F403


ALLOWED_HOSTS = ['*']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'local-qa.sqlite3',
    }
}

# Keep local QA free of external stateful services.
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

STORAGES['default'] = {
    'BACKEND': 'django.core.files.storage.FileSystemStorage',
}
MEDIA_ROOT = BASE_DIR / 'local-qa-media'
MEDIA_URL = '/media/'

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_RESULT_BACKEND = 'django-db'

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    }
}

# Several apps contain PostgreSQL-specific migrations that are not needed for
# manual QA. Create tables from models instead so local verification stays
# self-contained.
class _DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = _DisableMigrations()

# OAuth toolkit uses swappable model settings in migration autodetection.
# Define the defaults explicitly so syncdb-mode local QA can bootstrap cleanly.
OAUTH2_PROVIDER_APPLICATION_MODEL = 'oauth2_provider.Application'
OAUTH2_PROVIDER_GRANT_MODEL = 'oauth2_provider.Grant'
OAUTH2_PROVIDER_ACCESS_TOKEN_MODEL = 'oauth2_provider.AccessToken'
OAUTH2_PROVIDER_REFRESH_TOKEN_MODEL = 'oauth2_provider.RefreshToken'
OAUTH2_PROVIDER_ID_TOKEN_MODEL = 'oauth2_provider.IDToken'
OAUTH2_PROVIDER_DEVICE_GRANT_MODEL = 'oauth2_provider.DeviceGrant'
