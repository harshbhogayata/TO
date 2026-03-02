"""
TalentOrbit — Django Settings
Production-ready configuration with environment-variable driven secrets.
"""

import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

# ─── Base ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env
load_dotenv(BASE_DIR / '.env')

DEBUG = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 'yes')

# ─── Sentry (error tracking) ─────────────────────────────────────────────────
_sentry_dsn = os.environ.get('SENTRY_DSN', '')
if _sentry_dsn:
    import sentry_sdk
    sentry_sdk.init(
        dsn=_sentry_dsn,
        traces_sample_rate=0.1 if not DEBUG else 1.0,
        send_default_pii=False,
        environment='production' if not DEBUG else 'development',
    )

# SECRET_KEY — always required. No insecure fallback.
_secret = os.environ.get('SECRET_KEY', '')
if not _secret:
    if DEBUG:
        import secrets as _s
        _secret = _s.token_urlsafe(50)
        import warnings
        warnings.warn('SECRET_KEY not set — using random ephemeral key. Set it in .env.', stacklevel=1)
    else:
        raise RuntimeError('SECRET_KEY must be set in environment when DEBUG is False.')
SECRET_KEY = _secret
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# ─── Application definition ───────────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'storages',

    # TalentOrbit apps
    'accounts',
    'jobs',
    'messaging',
    'admin_api',
    'blog',
    'notifications',
    'courses',
    'payments',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Efficient static file serving
    'corsheaders.middleware.CorsMiddleware',       # Must be before CommonMiddleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'talentorbit.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'talentorbit.wsgi.application'

# ─── Database ─────────────────────────────────────────────────────────────────
# Supports DATABASE_URL (e.g. postgres://user:pass@host/db) via dj-database-url,
# falls back to per-variable config, and finally to local SQLite.
import dj_database_url as _dju

_database_url = os.environ.get('DATABASE_URL')
if _database_url:
    DATABASES = {'default': _dju.parse(_database_url, conn_max_age=600)}
else:
    DB_ENGINE = os.environ.get('DB_ENGINE', 'django.db.backends.sqlite3')
    if DB_ENGINE == 'django.db.backends.sqlite3':
        DATABASES = {
            'default': {
                'ENGINE': DB_ENGINE,
                'NAME': BASE_DIR / os.environ.get('DB_NAME', 'db.sqlite3'),
            }
        }
    else:
        DATABASES = {
            'default': {
                'ENGINE': DB_ENGINE,
                'NAME': os.environ.get('DB_NAME', 'talentorbit'),
                'USER': os.environ.get('DB_USER', 'postgres'),
                'PASSWORD': os.environ.get('DB_PASSWORD', ''),
                'HOST': os.environ.get('DB_HOST', 'localhost'),
                'PORT': os.environ.get('DB_PORT', '5432'),
                'CONN_MAX_AGE': 600,
            }
        }

# ─── Cache (Upstash Redis) ────────────────────────────────────────────────────
_redis_url = os.environ.get('UPSTASH_REDIS_URL', '')
if _redis_url:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': _redis_url,
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }

# ─── Custom User Model ────────────────────────────────────────────────────────
AUTH_USER_MODEL = 'accounts.User'

# ─── Password validation ──────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ─── Internationalisation ─────────────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ─── Static & Media files ─────────────────────────────────────────────────────
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

# Media storage — Cloudflare R2 (S3-compatible) when configured, else local filesystem
_r2_access_key = os.environ.get('R2_ACCESS_KEY_ID', '')
if _r2_access_key:
    _r2_custom_domain = os.environ.get('R2_CUSTOM_DOMAIN', '')  # e.g. media.talentorbit.com
    STORAGES['default'] = {
        'BACKEND': 'storages.backends.s3boto3.S3Boto3Storage',
        'OPTIONS': {
            'access_key': _r2_access_key,
            'secret_key': os.environ.get('R2_SECRET_ACCESS_KEY', ''),
            'bucket_name': os.environ.get('R2_BUCKET_NAME', 'talentorbit-media'),
            'endpoint_url': os.environ.get('R2_ENDPOINT_URL', ''),
            'default_acl': None,
            'signature_version': 's3v4',
            'region_name': 'auto',
            # Use public CDN URL when a custom domain is configured (Cloudflare CDN);
            # otherwise fall back to signed URLs via R2 S3 endpoint.
            'querystring_auth': not bool(_r2_custom_domain),
            'custom_domain': _r2_custom_domain or None,
            'file_overwrite': False,
        },
    }
    if _r2_custom_domain:
        MEDIA_URL = f"https://{_r2_custom_domain}/"
    else:
        MEDIA_URL = f"{os.environ.get('R2_ENDPOINT_URL', '')}/{os.environ.get('R2_BUCKET_NAME', '')}/"
else:
    STORAGES['default'] = {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    }
    MEDIA_URL = '/media/'

MEDIA_ROOT = BASE_DIR / 'media'

# ─── Email (auto-detects Resend when API key is present) ──────────────────────
_resend_key = os.environ.get('RESEND_API_KEY', '')
if _resend_key:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = 'smtp.resend.com'
    EMAIL_PORT = 465
    EMAIL_USE_SSL = True
    EMAIL_USE_TLS = False
    EMAIL_HOST_USER = 'resend'
    EMAIL_HOST_PASSWORD = _resend_key
else:
    EMAIL_BACKEND = os.environ.get(
        'EMAIL_BACKEND',
        'django.core.mail.backends.console.EmailBackend'
    )
    EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
    EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
    EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
    EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
    EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@talentorbit.com')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ─── Stripe ───────────────────────────────────────────────────────────────────
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
# Frontend base URL used for Stripe redirect URLs
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:5173')

# ─── Django REST Framework ────────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'talentorbit.pagination.StandardPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '2000/day',
        'auth': '20/hour',     # Strict — login, password-reset, verify-email
        'contact': '5/hour',   # Contact form submissions
    },
    'EXCEPTION_HANDLER': 'talentorbit.exceptions.custom_exception_handler',
}

# ─── Simple JWT ───────────────────────────────────────────────────────────────
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(
        minutes=int(os.environ.get('ACCESS_TOKEN_LIFETIME_MINUTES', 60))
    ),
    'REFRESH_TOKEN_LIFETIME': timedelta(
        days=int(os.environ.get('REFRESH_TOKEN_LIFETIME_DAYS', 7))
    ),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'TOKEN_OBTAIN_SERIALIZER': 'accounts.serializers.CustomTokenObtainPairSerializer',
}

# ─── CORS ─────────────────────────────────────────────────────────────────────
_cors_raw = os.environ.get('CORS_ALLOWED_ORIGINS', 'http://localhost:5173')
CORS_ALLOWED_ORIGINS = [o.strip() for o in _cors_raw.split(',') if o.strip()]

CORS_ALLOW_CREDENTIALS = True

# In production, tighten this up:
CORS_ALLOW_METHODS = ['DELETE', 'GET', 'OPTIONS', 'PATCH', 'POST', 'PUT']
CORS_ALLOW_HEADERS = [
    'accept', 'accept-encoding', 'authorization', 'content-type',
    'dnt', 'origin', 'user-agent', 'x-csrftoken', 'x-requested-with',
]

# ─── Security (production hardening) ─────────────────────────────────────────
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')  # Render terminates TLS
PASSWORD_RESET_TIMEOUT = 900  # 15 minutes (default is 3 days — too long)

# Upload size limits (protect against oversized payloads)
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024   # 10 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024   # 10 MB

if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    X_FRAME_OPTIONS = 'DENY'

# ─── Logging ──────────────────────────────────────────────────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO' if not DEBUG else 'DEBUG',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'WARNING' if not DEBUG else 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'accounts': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'jobs': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'payments': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
