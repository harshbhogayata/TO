"""
Test settings — forces SQLite + disables Sentry for fast local test runs.
Usage: python manage.py test --settings=talentorbit.test_settings
"""
import os

# Prevent .env from setting DATABASE_URL before our main settings load
os.environ['DATABASE_URL'] = ''
os.environ['SENTRY_DSN'] = ''
os.environ.setdefault('SECRET_KEY', 'test-secret-key-not-for-production')
os.environ.setdefault('DEBUG', 'True')

from talentorbit.settings import *  # noqa: F401, F403

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

# Disable throttling in tests — must patch inside REST_FRAMEWORK dict
REST_FRAMEWORK['DEFAULT_THROTTLE_CLASSES'] = []
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {
    'anon': None,
    'user': None,
    'auth': None,
    'contact': None,
}

# In-memory cache
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# In-memory email
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# Celery — run tasks synchronously in tests (no broker needed)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_RESULT_BACKEND = 'django-db'

# Channel layer — in-memory for tests
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    },
}
