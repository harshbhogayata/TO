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
    'daphne',
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
    'django_celery_results',
    'django_celery_beat',
    'channels',
    'drf_spectacular',
    'oauth2_provider',

    # PostgreSQL extensions
    'django.contrib.postgres',

    # TalentOrbit apps
    'accounts',
    'jobs',
    'messaging',
    'admin_api',
    'blog',
    'notifications',
    'courses',
    'payments',
    'realtime',
    'search',
    'intelligence',
    'compliance',
    'assessments',
    'reviews',
    'developer',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'talentorbit.middleware.correlation.CorrelationIdMiddleware',  # Distributed tracing
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Efficient static file serving
    'corsheaders.middleware.CorsMiddleware',       # Must be before CommonMiddleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'compliance.middleware.AuditContextMiddleware',
    'compliance.middleware.ConsentEnforcementMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'intelligence.experiments.middleware.ExperimentMiddleware',
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
ASGI_APPLICATION = 'talentorbit.asgi.application'

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

# ─── Read Replica (optional) ─────────────────────────────────────────────────
# When DATABASE_REPLICA_URL is set, reads are routed to the replica automatically
# via PrimaryReplicaRouter. Compliance, payments, and auth tables always read
# from the primary to guarantee strong consistency.
_replica_url = os.environ.get('DATABASE_REPLICA_URL', '')
if _replica_url:
    DATABASES['replica'] = _dju.parse(_replica_url, conn_max_age=600)
    DATABASE_ROUTERS = ['talentorbit.db_router.PrimaryReplicaRouter']

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

# ─── Channel Layers (Django Channels — WebSocket backend) ─────────────────────
_channels_redis_url = os.environ.get('CHANNELS_REDIS_URL', _redis_url or '')
if _channels_redis_url:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {
                'hosts': [_channels_redis_url],
                'capacity': 1500,
                'expiry': 60,
            },
        },
    }
else:
    # In-memory channel layer for local development (single-process only)
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        },
    }

# ─── Firebase Cloud Messaging (push notifications) ────────────────────────────
FIREBASE_CREDENTIALS_PATH = os.environ.get('FIREBASE_CREDENTIALS_PATH', '')

# ─── WebSocket rate limiting ──────────────────────────────────────────────────
WS_CONNECT_RATE_LIMIT = int(os.environ.get('WS_CONNECT_RATE_LIMIT', 20))   # max connects per IP per window
WS_CONNECT_RATE_WINDOW = int(os.environ.get('WS_CONNECT_RATE_WINDOW', 60)) # seconds
WS_MESSAGE_RATE_LIMIT = int(os.environ.get('WS_MESSAGE_RATE_LIMIT', 60))   # max messages per user per window
WS_MESSAGE_RATE_WINDOW = int(os.environ.get('WS_MESSAGE_RATE_WINDOW', 60)) # seconds
WS_MAX_CONNECTIONS_PER_USER = int(os.environ.get('WS_MAX_CONNECTIONS_PER_USER', 5))

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
        'developer.authentication.APIKeyAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.URLPathVersioning',
    'DEFAULT_VERSION': 'v1',
    'ALLOWED_VERSIONS': ['v1'],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '2000/day',
        'auth': '20/hour',     # Strict — login, password-reset, verify-email
        'contact': '5/hour',   # Contact form submissions
        # ── Compliance per-endpoint throttles ─────────────────────────────
        'compliance_export': '5/day',
        'compliance_export_download': '20/hour',
        'compliance_deletion': '3/day',
        'compliance_deletion_confirm': '10/hour',
        'compliance_consent_write': '30/hour',
        'compliance_team_invite': '20/hour',
        'compliance_team_invite_action': '30/hour',
        'compliance_audit': '60/hour',
        'compliance_audit_integrity': '5/hour',
        'compliance_policy_create': '10/hour',
        # ── Developer Platform per-endpoint throttles ───────────────────
        'developer_key_create': '10/hour',
        'developer_key_rotate': '10/hour',
        'developer_webhook_create': '10/hour',
        'developer_webhook_test': '20/hour',
        'developer_oauth_create': '5/hour',
        'developer_oauth_revoke': '10/hour',
        # ── Jobs per-endpoint throttles ──────────────────────────────────
        'job_create': '20/hour',
        'job_apply': '30/hour',
        'job_search': '120/hour',
        # ── Reviews per-endpoint throttles ───────────────────────────────
        'review_create': '5/hour',
        'review_helpful': '60/hour',
        'review_respond': '10/hour',
        # ── Messaging per-endpoint throttles ─────────────────────────────
        'message_send': '120/hour',
        'thread_create': '30/hour',
        # ── Notifications per-endpoint throttles ─────────────────────────
        'notification_read': '300/hour',
        # ── Blog per-endpoint throttles ──────────────────────────────────
        'blog_list': '120/hour',
        # ── Payments per-endpoint throttles ──────────────────────────────
        'payment_checkout': '10/hour',
        'payment_portal': '10/hour',
        # ── Admin per-endpoint throttles ─────────────────────────────────
        'admin_action': '60/hour',
        # ── Realtime per-endpoint throttles ──────────────────────────────
        'push_subscribe': '30/hour',
        # ── AI per-endpoint throttles ────────────────────────────────────
        'ai_generate': '20/hour',
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

# ─── drf-spectacular (OpenAPI schema + docs) ──────────────────────────────────
SPECTACULAR_SETTINGS = {
    'TITLE': 'TalentOrbit API',
    'DESCRIPTION': 'Enterprise talent management platform — jobs, courses, assessments, messaging, compliance, intelligence.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'CONTACT': {'email': 'api@talentorbit.com'},
    'LICENSE': {'name': 'Proprietary'},
    'SCHEMA_PATH_PREFIX': r'/api/v[0-9]+/',
    'COMPONENT_SPLIT_REQUEST': True,
    'ENUM_NAME_OVERRIDES': {},
    'POSTPROCESSING_HOOKS': [],
    'TAGS': [
        {'name': 'Auth', 'description': 'Authentication, registration, 2FA'},
        {'name': 'Jobs', 'description': 'Job posts, applications, saved jobs'},
        {'name': 'Messaging', 'description': 'Threads, messages, unread counts'},
        {'name': 'Courses', 'description': 'Catalog, enrollment, progress, certificates'},
        {'name': 'Assessments', 'description': 'Question banks, assessments, grading'},
        {'name': 'Payments', 'description': 'Subscriptions, billing, invoices, referrals'},
        {'name': 'Search', 'description': 'Unified search, autocomplete, trending'},
        {'name': 'Intelligence', 'description': 'Recommendations, analytics, resume parsing'},
        {'name': 'Compliance', 'description': 'Audit logs, GDPR, teams, policies'},
        {'name': 'Reviews', 'description': 'Company reviews, ratings'},
        {'name': 'Developer', 'description': 'API keys, webhooks, OAuth apps'},
        {'name': 'Notifications', 'description': 'In-app notifications'},
        {'name': 'Blog', 'description': 'Articles, categories'},
        {'name': 'Admin', 'description': 'Platform administration'},
        {'name': 'Realtime', 'description': 'Push tokens, presence'},
    ],
}

# ─── OpenAI (AI features) ────────────────────────────────────────────────────
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')

# ─── OAuth2 Provider ──────────────────────────────────────────────────────────
OAUTH2_PROVIDER = {
    'SCOPES': {
        'read': 'Read-only access',
        'write': 'Read and write access',
        'jobs:read': 'Read job posts',
        'jobs:write': 'Create and manage job posts',
        'applications:read': 'Read applications',
        'applications:write': 'Manage applications',
        'profile:read': 'Read user profile',
        'profile:write': 'Update user profile',
        'messaging:read': 'Read messages',
        'messaging:write': 'Send messages',
        'assessments:read': 'Read assessments',
        'assessments:write': 'Manage assessments',
    },
    'DEFAULT_SCOPES': ['read'],
    'ACCESS_TOKEN_EXPIRE_SECONDS': 3600,
    'REFRESH_TOKEN_EXPIRE_SECONDS': 86400 * 30,
    'ROTATE_REFRESH_TOKEN': True,
    'ALLOWED_REDIRECT_URI_SCHEMES': ['https'] if not DEBUG else ['http', 'https'],
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

# Always set — applies in both dev and prod
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True

if not DEBUG:
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    if not STRIPE_WEBHOOK_SECRET:
        import warnings
        warnings.warn(
            'STRIPE_WEBHOOK_SECRET is not set — Stripe webhook will reject all events.',
            stacklevel=1,
        )

# ─── Logging ──────────────────────────────────────────────────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'json': {
            '()': 'talentorbit.middleware.correlation.StructuredJsonFormatter',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json' if not DEBUG else 'verbose',
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
        'celery': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'realtime': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'search': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'intelligence': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'compliance': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# ─── Celery (async task queue) ────────────────────────────────────────────────
# Broker: reuse the same Upstash Redis instance used for caching.
# Falls back to an in-memory broker for local development (eager mode).
_celery_broker = os.environ.get('CELERY_BROKER_URL', _redis_url or '')

if _celery_broker:
    CELERY_BROKER_URL = _celery_broker
    CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
    CELERY_BROKER_TRANSPORT_OPTIONS = {
        'visibility_timeout': 3600,     # 1 hour — long enough for email retries
        'socket_timeout': 15,
        'socket_connect_timeout': 15,
    }
else:
    # No broker available — run tasks synchronously in-process.
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True

# Result backend — store task results in the Django ORM
CELERY_RESULT_BACKEND = 'django-db'
CELERY_RESULT_EXTENDED = True
CELERY_RESULT_EXPIRES = 60 * 60 * 24 * 7   # 7 days

# Serialisation — JSON-only for security (no pickle)
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'

# Time zone — match Django
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True

# Reliability — late ack + reject on worker crash
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True

# Prefetch — pull only 1 task at a time per worker process
# (prevents one slow task from blocking the queue)
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# Task execution limits
CELERY_TASK_SOFT_TIME_LIMIT = 120   # seconds — raises SoftTimeLimitExceeded
CELERY_TASK_TIME_LIMIT = 180        # seconds — hard kill
CELERY_TASK_TRACK_STARTED = True

# Queue routing — explicit queues keep workloads isolated
CELERY_TASK_DEFAULT_QUEUE = 'default'
CELERY_TASK_QUEUES = {
    'default': {},
    'emails': {},
    'notifications': {},
    'intelligence': {},
    'analytics': {},
    'compliance': {},                  # GDPR export/deletion, team invites
    'assessments': {},               # Code grading, result computation
    'dlq': {},                       # Dead-letter queue for manual triage
}
CELERY_TASK_ROUTES = {
    'accounts.send_verification_email': {'queue': 'emails'},
    'accounts.send_password_reset_email': {'queue': 'emails'},
    'accounts.send_generic_email': {'queue': 'emails'},
    'notifications.create_notification': {'queue': 'notifications'},
    'notifications.create_bulk_notifications': {'queue': 'notifications'},
    'notifications.send_application_notification': {'queue': 'notifications'},
    'notifications.send_message_notification': {'queue': 'notifications'},
    # Intelligence — recommendation engine
    'intelligence.retrain_tfidf_vectorizer': {'queue': 'intelligence'},
    'intelligence.rebuild_interaction_matrix': {'queue': 'intelligence'},
    'intelligence.warm_recommendation_cache': {'queue': 'intelligence'},
    'intelligence.parse_resume_async': {'queue': 'intelligence'},
    # Intelligence — NLP / taxonomy
    'intelligence.rebuild_skill_entity_ruler': {'queue': 'intelligence'},
    'intelligence.update_skill_taxonomy': {'queue': 'intelligence'},
    'intelligence.discover_new_skills': {'queue': 'intelligence'},
    # Intelligence — analytics / warehouse
    'intelligence.compute_daily_funnel_snapshots': {'queue': 'analytics'},
    'intelligence.compute_daily_platform_metrics': {'queue': 'analytics'},
    'intelligence.compute_platform_benchmarks': {'queue': 'analytics'},
    'intelligence.aggregate_period_snapshots': {'queue': 'analytics'},
    # Intelligence — cleanup
    'intelligence.cleanup_old_recommendation_logs': {'queue': 'default'},
    'intelligence.cleanup_old_interactions': {'queue': 'default'},
    # Compliance — GDPR, teams
    'compliance.tasks.process_data_export_task': {'queue': 'compliance'},
    'compliance.tasks.process_data_deletion_task': {'queue': 'compliance'},
    'compliance.tasks.send_team_invitation_email_task': {'queue': 'emails'},
    'compliance.tasks.send_deletion_confirmation_email_task': {'queue': 'emails'},
    'compliance.tasks.process_expired_deletions_task': {'queue': 'compliance'},
    'compliance.tasks.cleanup_expired_exports_task': {'queue': 'compliance'},
    'compliance.tasks.expire_team_invitations_task': {'queue': 'compliance'},
    'compliance.tasks.audit_chain_integrity_check_task': {'queue': 'compliance'},
    'compliance.tasks.ip_anomaly_detection_task': {'queue': 'compliance'},
    # Assessments — grading, results, housekeeping
    'assessments.tasks.grade_code_answer': {'queue': 'assessments'},
    'assessments.tasks.compute_attempt_result': {'queue': 'assessments'},
    'assessments.tasks.recompute_assessment_stats': {'queue': 'assessments'},
    'assessments.tasks.auto_submit_expired_attempts': {'queue': 'assessments'},
    'assessments.tasks.expire_invitations': {'queue': 'assessments'},
    'assessments.tasks.cleanup_abandoned_attempts': {'queue': 'default'},
    # Payments — dunning, referrals, campaigns, revenue
    'payments.tasks.handle_payment_failure': {'queue': 'default'},
    'payments.tasks.process_expired_grace_periods': {'queue': 'default'},
    'payments.tasks.check_referral_qualification': {'queue': 'default'},
    'payments.tasks.expire_stale_referrals': {'queue': 'default'},
    'payments.tasks.process_campaign_budgets': {'queue': 'default'},
    'payments.tasks.compute_revenue_metrics': {'queue': 'analytics'},
}

# Celery Beat schedule — periodic housekeeping tasks
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# Default periodic tasks — seeded in code so deploys start clean.
# The DatabaseScheduler will merge these with any admin-created schedules.
from celery.schedules import crontab  # noqa: E402

CELERY_BEAT_SCHEDULE = {
    # Clean up read notifications older than 90 days (daily at 03:00 UTC)
    'cleanup-old-notifications': {
        'task': 'notifications.tasks.cleanup_old_notifications_task',
        'schedule': crontab(hour=3, minute=0),
        'options': {'queue': 'default'},
    },
    # Celery health-check heartbeat (every 5 minutes)
    'celery-health-heartbeat': {
        'task': 'talentorbit.tasks.celery_health_heartbeat',
        'schedule': crontab(minute='*/5'),
        'options': {'queue': 'default'},
    },

    # ── Intelligence — Recommendation Engine ──────────────────────────────
    'retrain-tfidf-vectorizer': {
        'task': 'intelligence.retrain_tfidf_vectorizer',
        'schedule': crontab(hour=2, minute=0),
        'options': {'queue': 'intelligence'},
    },
    'rebuild-interaction-matrix': {
        'task': 'intelligence.rebuild_interaction_matrix',
        'schedule': crontab(hour=2, minute=30),
        'options': {'queue': 'intelligence'},
    },
    'warm-recommendation-cache': {
        'task': 'intelligence.warm_recommendation_cache',
        'schedule': crontab(minute=0, hour='*/4'),
        'options': {'queue': 'intelligence'},
    },

    # ── Intelligence — NLP / Taxonomy ─────────────────────────────────────
    'rebuild-skill-entity-ruler': {
        'task': 'intelligence.rebuild_skill_entity_ruler',
        'schedule': crontab(hour=2, minute=15),
        'options': {'queue': 'intelligence'},
    },
    'update-skill-taxonomy': {
        'task': 'intelligence.update_skill_taxonomy',
        'schedule': crontab(hour=3, minute=0, day_of_week=0),  # Sunday
        'options': {'queue': 'intelligence'},
    },
    'discover-new-skills': {
        'task': 'intelligence.discover_new_skills',
        'schedule': crontab(hour=3, minute=0, day_of_week=3),  # Wednesday
        'options': {'queue': 'intelligence'},
    },

    # ── Intelligence — Analytics / Warehouse ──────────────────────────────
    'compute-daily-funnel-snapshots': {
        'task': 'intelligence.compute_daily_funnel_snapshots',
        'schedule': crontab(hour=1, minute=0),
        'options': {'queue': 'analytics'},
    },
    'compute-daily-platform-metrics': {
        'task': 'intelligence.compute_daily_platform_metrics',
        'schedule': crontab(hour=1, minute=30),
        'options': {'queue': 'analytics'},
    },
    'compute-platform-benchmarks': {
        'task': 'intelligence.compute_platform_benchmarks',
        'schedule': crontab(hour=4, minute=0, day_of_week=1),  # Monday
        'options': {'queue': 'analytics'},
    },
    'aggregate-period-snapshots': {
        'task': 'intelligence.aggregate_period_snapshots',
        'schedule': crontab(hour=5, minute=0, day_of_week=1),  # Monday
        'options': {'queue': 'analytics'},
    },

    # ── Intelligence — Cleanup ────────────────────────────────────────────
    'cleanup-old-recommendation-logs': {
        'task': 'intelligence.cleanup_old_recommendation_logs',
        'schedule': crontab(hour=4, minute=0, day_of_week=6),  # Saturday
        'options': {'queue': 'default'},
    },
    'cleanup-old-interactions': {
        'task': 'intelligence.cleanup_old_interactions',
        'schedule': crontab(hour=4, minute=30, day_of_week=6),  # Saturday
        'options': {'queue': 'default'},
    },

    # ── Compliance — GDPR & Housekeeping ──────────────────────────────────
    'process-expired-deletions': {
        'task': 'compliance.tasks.process_expired_deletions_task',
        'schedule': crontab(hour='*/4', minute=15),  # Every 4 hours
        'options': {'queue': 'compliance'},
    },
    'cleanup-expired-exports': {
        'task': 'compliance.tasks.cleanup_expired_exports_task',
        'schedule': crontab(hour=5, minute=0),  # Daily at 05:00
        'options': {'queue': 'compliance'},
    },
    'expire-team-invitations': {
        'task': 'compliance.tasks.expire_team_invitations_task',
        'schedule': crontab(hour=6, minute=0),  # Daily at 06:00
        'options': {'queue': 'compliance'},
    },
    'audit-chain-integrity': {
        'task': 'compliance.tasks.audit_chain_integrity_check_task',
        'schedule': crontab(hour=3, minute=30),  # Daily at 03:30
        'options': {'queue': 'compliance'},
    },
    'ip-anomaly-detection': {
        'task': 'compliance.tasks.ip_anomaly_detection_task',
        'schedule': crontab(minute='*/30'),  # Every 30 minutes
        'options': {'queue': 'compliance'},
    },

    # ── Assessments — Grading & Housekeeping ──────────────────────────────
    'auto-submit-expired-attempts': {
        'task': 'assessments.tasks.auto_submit_expired_attempts',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
        'options': {'queue': 'assessments'},
    },
    'expire-assessment-invitations': {
        'task': 'assessments.tasks.expire_invitations',
        'schedule': crontab(hour='*/6', minute=10),  # Every 6 hours
        'options': {'queue': 'assessments'},
    },
    'cleanup-abandoned-attempts': {
        'task': 'assessments.tasks.cleanup_abandoned_attempts',
        'schedule': crontab(hour=4, minute=45),  # Daily at 04:45
        'options': {'queue': 'default'},
    },

    # ── Payments — Dunning, Referrals, Campaigns, Revenue ─────────────
    'process-expired-grace-periods': {
        'task': 'payments.tasks.process_expired_grace_periods',
        'schedule': crontab(hour='*/4', minute=20),  # Every 4 hours
        'options': {'queue': 'default'},
    },
    'check-referral-qualification': {
        'task': 'payments.tasks.check_referral_qualification',
        'schedule': crontab(hour='*/6', minute=30),  # Every 6 hours
        'options': {'queue': 'default'},
    },
    'expire-stale-referrals': {
        'task': 'payments.tasks.expire_stale_referrals',
        'schedule': crontab(hour=5, minute=30),  # Daily at 05:30
        'options': {'queue': 'default'},
    },
    'process-campaign-budgets': {
        'task': 'payments.tasks.process_campaign_budgets',
        'schedule': crontab(hour='*/2', minute=0),  # Every 2 hours
        'options': {'queue': 'default'},
    },
    'compute-revenue-metrics': {
        'task': 'payments.tasks.compute_revenue_metrics',
        'schedule': crontab(minute=0, hour='*/1'),  # Every hour
        'options': {'queue': 'analytics'},
    },
}

# ─── Judge0 CE (sandboxed code execution) ─────────────────────────────────────
JUDGE0_API_URL = os.environ.get('JUDGE0_API_URL', 'http://judge0:2358')
JUDGE0_API_KEY = os.environ.get('JUDGE0_API_KEY', '')

# ─── OpenAI API ───────────────────────────────────────────────────────────────
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')

# ─── Firebase Push Notifications ──────────────────────────────────────────────
FIREBASE_CREDENTIALS_JSON = os.environ.get('FIREBASE_CREDENTIALS_JSON', '')
FIREBASE_CREDENTIALS_PATH = os.environ.get('FIREBASE_CREDENTIALS_PATH', '')
