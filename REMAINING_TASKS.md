# TalentOrbit — Remaining Enterprise Tasks

> Everything that must ship to reach TRUE enterprise grade.  
> NO shortcuts. Every task includes acceptance criteria, security/performance implications, and rollback plan.  
> Status sourced from actual codebase audit — not guesswork.

---

## Master Status Dashboard

### Workstream Completion

| WS | Workstream | ✅ Done | 🟡 Partial | 🔴 Missing | Health |
|----|-----------|---------|-----------|------------|--------|
| WS1 | Infrastructure & DevOps | 5 | 1 | 3 | 🟡 56% |
| WS2 | Content & Assessments | 2 | 2 | 1 | 🟡 40% |
| WS3 | Developer Platform | 0 | 2 | 4 | 🔴 17% |
| WS4 | Revenue & Growth | 0 | 4 | 3 | 🔴 29% |
| WS5 | AI/ML Platform | 0 | 1 | 5 | 🔴 8% |
| **Σ** | **Totals** | **7** | **10** | **16** | **🔴 33%** |

### Cross-Cutting Debt

| ID | Gap | Scope | Severity |
|----|-----|-------|----------|
| C1 | AuditMiddleware only covers 2/15 apps explicitly | All apps | P0 |
| C2 | 4 apps have models with ZERO migration files | payments, assessments, developer, reviews | P0 |
| C3 | `drf-spectacular` installed but ZERO views have `@extend_schema` | All DRF views | P1 |
| C4 | 6 apps have ZERO test coverage | courses, intelligence, blog, notifications, search, realtime | P1 |
| C5 | Zero caching strategy (no Redis cache framework config) | All read-heavy endpoints | P1 |
| C6 | 9 apps use only global throttle — no per-endpoint rate limiting | All apps except compliance, developer | P2 |

---

## Table of Contents

1. [P0 — Critical Blockers (Ship-Stopping)](#p0--critical-blockers)
2. [P1 — Security & Compliance (Must-Have for Launch)](#p1--security--compliance)
3. [P2 — Reliability & Observability](#p2--reliability--observability)
4. [P3 — Performance & Scale](#p3--performance--scale)
5. [P4 — Developer Experience & Operational Excellence](#p4--developer-experience)
6. [WS1 — Infrastructure & DevOps Tasks](#ws1--infrastructure--devops)
7. [WS2 — Content & Assessments Tasks](#ws2--content--assessments)
8. [WS3 — Developer Platform Tasks](#ws3--developer-platform)
9. [WS4 — Revenue & Growth Tasks](#ws4--revenue--growth)
10. [WS5 — AI/ML Platform Tasks](#ws5--aiml-platform)
11. [Testing Strategy](#testing-strategy)
12. [Rollout Plan](#rollout-plan)

---

## P0 — Critical Blockers

### P0-1: Create Missing Database Migrations

**Gap**: C2 — 4 apps have Django models but zero migration files. Their database tables DO NOT EXIST.

| App | Models Without Tables | Impact |
|-----|----------------------|--------|
| `payments` | SubscriptionPlan, CustomerProfile (with dunning fields), PaymentHistory, Invoice, Coupon, CouponRedemption, ReferralProgram, Referral, ReferralReward, SponsoredJobCampaign, TalentPoolPipeline, TalentPoolCandidate (**12 models**) | All 6 WS4 frontend pages will 500-error |
| `assessments` | Assessment, Question, SubmissionAttempt, TestCase, SubmissionResult, AssessmentInvitation, CodingChallenge (**7+ models**) | WS2 assessment features broken |
| `developer` | APIKey, WebhookEndpoint, WebhookDelivery, OAuthApplication, APIChangelog (**5 models**) | Entire WS3 developer portal broken |
| `reviews` | CompanyReview, ReviewResponse (**2 models**) | Company review feature broken |

**Tasks**:
```
- [ ] P0-1a: Run `makemigrations payments` — verify 12 models get CreateModel ops
- [ ] P0-1b: Run `makemigrations assessments` — verify 7+ models
- [ ] P0-1c: Run `makemigrations developer` — verify 5 models
- [ ] P0-1d: Run `makemigrations reviews` — verify 2 models
- [ ] P0-1e: Review generated SQL with `sqlmigrate` before applying
- [ ] P0-1f: Run `migrate` in a staging DB first
- [ ] P0-1g: Apply to production with `--fake` dry-run, then real apply
- [ ] P0-1h: Verify with `showmigrations` — all [X]
```

**Rollback plan**:
```bash
python manage.py migrate payments zero    # Drops all payments tables
python manage.py migrate assessments zero
python manage.py migrate developer zero
python manage.py migrate reviews zero
```

**Acceptance criteria**: All 26+ models have matching database tables. `python manage.py check` returns zero errors.

---

### P0-2: Wire `@transaction.atomic()` on All Financial Write Operations

**Gap**: Payment views handle Stripe webhooks, checkout sessions, and invoice creation WITHOUT database transaction protection. A crash mid-write creates orphan records.

**Scope**: Every view/task in `payments/views.py` and `payments/tasks.py` that performs multi-model writes:

```python
# EVERY view that creates/updates payments, subscriptions, invoices, referrals:
from django.db import transaction

class CreateCheckoutSessionView(APIView):
    @transaction.atomic
    def post(self, request):
        # If Stripe call succeeds but DB save fails, the transaction rolls back
        # preventing orphan Stripe sessions without matching DB records
        ...

# Stripe webhook handler — CRITICAL:
@transaction.atomic
def handle_invoice_paid(event):
    invoice = Invoice.objects.select_for_update().get(stripe_id=event.data.object.id)
    invoice.status = 'paid'
    invoice.save()
    PaymentHistory.objects.create(...)
    CustomerProfile.objects.filter(user=invoice.user).update(dunning_count=0)
```

**Tasks**:
```
- [ ] P0-2a: Audit all views in payments/views.py — add @transaction.atomic to every POST/PUT/PATCH/DELETE
- [ ] P0-2b: Audit payments/tasks.py — wrap all Celery tasks that write to DB in transaction.atomic()
- [ ] P0-2c: Add select_for_update() on any object that could race (CustomerProfile, Invoice)
- [ ] P0-2d: Add idempotency key support for Stripe webhook processing (prevent double-processing)
- [ ] P0-2e: Write tests that simulate mid-transaction failure and verify rollback
```

**Acceptance criteria**: Zero orphan records possible. Webhook handler is idempotent (re-processing same event is safe).

---

### P0-3: Add Idempotency Keys for Payment Endpoints

**Gap**: Payment creation endpoints can be double-submitted (network retry, user double-click) creating duplicate charges.

**Implementation**:

```python
# payments/middleware.py or decorator:
import hashlib
from django.core.cache import cache

def idempotent(timeout=86400):
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            key = request.headers.get('Idempotency-Key')
            if not key:
                return Response({'error': 'Idempotency-Key header required'}, status=400)
            cache_key = f'idempotency:{request.user.id}:{hashlib.sha256(key.encode()).hexdigest()}'
            cached = cache.get(cache_key)
            if cached:
                return Response(cached['data'], status=cached['status'])
            response = view_func(request, *args, **kwargs)
            cache.set(cache_key, {'data': response.data, 'status': response.status_code}, timeout)
            return response
        return wrapper
    return decorator
```

**Tasks**:
```
- [ ] P0-3a: Create idempotency decorator/middleware
- [ ] P0-3b: Apply to: create-checkout-session, webhook handler, invoice creation, referral creation
- [ ] P0-3c: Frontend: Generate UUID idempotency key per mutation, send in headers
- [ ] P0-3d: Test: same key returns cached response, different key processes normally
```

---

### P0-4: Extend AuditMiddleware to All 15 Apps

**Gap**: C1 — `compliance.middleware.AuditMiddleware` creates `AuditLog` entries but only fully covers compliance and accounts routes. 13 other apps have unaudited mutations.

**Current state**: The middleware logs all requests, but the audit trail is shallow — it captures URL + method but not the business-level action or affected object IDs for most apps.

**Tasks**:
```
- [ ] P0-4a: Add DRF signals/mixins to capture model-level changes for all 15 apps:
      from compliance.signals import audit_model_change
      # In each model's save(): emit audit_model_change signal with old vs new fields
- [ ] P0-4b: Ensure AuditLog captures: user, action_type, resource_type, resource_id, changes_json, ip, timestamp
- [ ] P0-4c: Add SHA-256 hash chain to AuditLog (already exists in model — verify it's being computed on EVERY save)
- [ ] P0-4d: Add audit logging for: jobs, messaging, courses, assessments, payments, intelligence, search, blog, notifications, reviews, developer, admin_api, realtime
- [ ] P0-4e: Write test: verify every POST/PUT/PATCH/DELETE across all apps creates an AuditLog entry
```

**Acceptance criteria**: Compliance report can list every data mutation across the entire platform with who/what/when/from-where.

---

## P1 — Security & Compliance

### P1-1: OWASP Top 10 Audit

| # | OWASP Risk | Current Status | Required Action |
|---|-----------|---------------|-----------------|
| A01 | Broken Access Control | 🟡 `ProtectedRoute` + `allowedRoles` exists, but backend views inconsistently check `IsOwnerOrAdmin` | Audit every DRF view — ensure permission_classes are set. No view should use `AllowAny` in production. |
| A02 | Cryptographic Failures | 🟡 JWT with HS256 (should be RS256 for production). Passwords use Django's PBKDF2. | Switch to RS256 JWT. Ensure all secrets in env vars (not settings.py). |
| A03 | Injection | 🟡 Django ORM prevents SQL injection. But `code_runner.py` executes user code — needs sandboxing (Judge0 exists but verify isolation). `PolicyManager` rich text editor has zero XSS sanitization. | Add DOMPurify on ALL user/AI-generated HTML. Verify Judge0 sandboxing. No `raw()` SQL queries. |
| A04 | Insecure Design | 🟡 No rate-limit on referral creation (fraud vector). No rate-limit on password reset. | Add per-endpoint throttles. Add anti-fraud for referrals. |
| A05 | Security Misconfiguration | 🔴 `DEBUG` check in settings.py but verify production `.env`. CORS `ALLOWED_ORIGINS` must be explicit, not `*`. | Audit `settings.py` production config. No `*` in CORS. |
| A06 | Vulnerable Components | 🔴 No dependency scanning. | Add `pip-audit` + `npm audit` to CI. |
| A07 | Auth Failures | 🟡 2FA exists (pyotp + qrcode) but is optional. No brute-force lockout. | Add account lockout after 5 failed attempts. Make 2FA mandatory for ADMIN. |
| A08 | Software/Data Integrity | 🟡 No Subresource Integrity on CDN assets. Celery tasks don't verify message integrity. | Add SRI. Sign Celery task payloads. |
| A09 | Logging/Monitoring Failures | 🔴 Sentry captures errors but no structured logging, no correlation IDs, no security event alerts. | See P2-1 below. |
| A10 | SSRF | 🟡 Webhook delivery in developer app calls arbitrary URLs — needs allowlist/denylist. | Validate webhook URLs against denylist (no localhost, no internal IPs, no cloud metadata). |

**Tasks**:
```
- [ ] P1-1a: Audit ALL DRF views — verify permission_classes ≠ AllowAny (except public endpoints like plan listing)
- [ ] P1-1b: Switch JWT to RS256 (SIGNING_KEY → RSA keypair)
- [ ] P1-1c: Add DOMPurify sanitization to PolicyManager and any AI-generated content
- [ ] P1-1d: Add per-endpoint throttle scopes for: referral creation (5/hour), password reset (3/hour), checkout (10/hour)
- [ ] P1-1e: Audit CORS settings for production — explicit allowed origins only
- [ ] P1-1f: Add account lockout (5 failed attempts → 15 min lock)
- [ ] P1-1g: Make 2FA mandatory for ADMIN role users
- [ ] P1-1h: Add webhook URL validation (denylist: 127.0.0.1, 169.254.*, 10.*, 172.16-31.*, 192.168.*)
- [ ] P1-1i: Add pip-audit + npm audit to CI pipeline
- [ ] P1-1j: Run pip-audit NOW and fix all known vulnerabilities
```

---

### P1-2: PII Detection & Protection for AI Endpoints

**Gap**: W5-5 — AI chatbot and job writer send user content to OpenAI without PII stripping.

**Implementation**:

```python
# intelligence/pii_detector.py
import re

PII_PATTERNS = {
    'ssn': re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
    'credit_card': re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),
    'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
    'phone': re.compile(r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'),
    'passport': re.compile(r'\b[A-Z]{1,2}\d{6,9}\b'),
}

def strip_pii(text: str) -> tuple[str, list[str]]:
    """Returns (cleaned_text, list_of_detected_pii_types)"""
    detected = []
    cleaned = text
    for pii_type, pattern in PII_PATTERNS.items():
        if pattern.search(cleaned):
            detected.append(pii_type)
            cleaned = pattern.sub(f'[{pii_type.upper()}_REDACTED]', cleaned)
    return cleaned, detected
```

**Tasks**:
```
- [ ] P1-2a: Create intelligence/pii_detector.py with pattern-based PII detection
- [ ] P1-2b: Wire into AI chatbot view — strip PII before calling OpenAI
- [ ] P1-2c: Wire into AI job writer view — strip PII from input
- [ ] P1-2d: Log PII detection events to AuditLog (type detected, NOT the PII itself)
- [ ] P1-2e: Add content moderation on AI responses (reject harmful/off-topic content)
- [ ] P1-2f: Add prompt injection prevention (system prompt hardening, input length limits)
- [ ] P1-2g: Write tests with PII-laden inputs — verify 100% redaction
```

---

### P1-3: Add `@extend_schema` to ALL DRF Views

**Gap**: C3 — `drf-spectacular` is installed and configured, but ZERO views have schema decorators. The `/api/schema/` endpoint returns a skeleton with no request/response documentation.

**Scope**: Every `APIView`, `ViewSet`, and `@api_view` across all 15 apps.

**Tasks**:
```
- [ ] P1-3a: accounts/views.py — 12+ views
- [ ] P1-3b: jobs/views.py — all endpoints
- [ ] P1-3c: messaging/views.py — all endpoints
- [ ] P1-3d: payments/views.py — all endpoints (include Stripe webhook docs)
- [ ] P1-3e: compliance/views.py — all endpoints
- [ ] P1-3f: intelligence/views.py + ai_views.py — all endpoints
- [ ] P1-3g: developer/views.py — all endpoints
- [ ] P1-3h: courses/views.py, blog/views.py, notifications/views.py, search/views.py, reviews/views.py, assessments/views.py, realtime/views.py, admin_api/views.py
- [ ] P1-3i: Generate OpenAPI spec and validate: `python manage.py spectacular --validate`
- [ ] P1-3j: Serve Swagger UI at /api/docs/ and ReDoc at /api/redoc/
```

**Acceptance criteria**: `spectacular --validate` returns zero warnings. Every endpoint has documented request body, response schema, error codes, and authentication requirements.

---

### P1-4: GDPR & Data Compliance Hardening

**Current state**: `compliance/` app has models for DataExportRequest, DataDeletionRequest, ConsentRecord, PolicyVersion. Views exist.

**What's missing**:
```
- [ ] P1-4a: Verify data export actually collects data from ALL 15 apps (not just accounts)
- [ ] P1-4b: Verify data deletion cascade-deletes across ALL related models (messages, applications, reviews, etc.)
- [ ] P1-4c: Add consent gate on AI features (user must opt-in before data goes to OpenAI)
- [ ] P1-4d: Add data retention policies (auto-delete audit logs > 7 years, messages > 2 years)
- [ ] P1-4e: Add cookie consent banner integration with ConsentRecord model
- [ ] P1-4f: Verify RIGHT_TO_PORTABILITY — export must be machine-readable (JSON/CSV)
```

---

## P2 — Reliability & Observability

### P2-1: Structured Logging with Correlation IDs

**Gap**: Sentry captures exceptions but there's no structured logging, no correlation IDs for request tracing, and no way to trace a user's request across API → Celery task → WebSocket.

**Implementation**:

```python
# talentorbit/middleware/correlation.py
import uuid
import logging
import threading

_local = threading.local()

def get_correlation_id():
    return getattr(_local, 'correlation_id', 'unknown')

class CorrelationIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        correlation_id = request.headers.get('X-Correlation-ID', str(uuid.uuid4()))
        _local.correlation_id = correlation_id
        request.correlation_id = correlation_id
        response = self.get_response(request)
        response['X-Correlation-ID'] = correlation_id
        return response

# JSON log formatter:
class StructuredFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            'timestamp': self.formatTime(record),
            'level': record.levelname,
            'correlation_id': get_correlation_id(),
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'line': record.lineno,
            'user_id': getattr(record, 'user_id', None),
        })
```

**Tasks**:
```
- [ ] P2-1a: Create CorrelationIdMiddleware — inject UUID into every request
- [ ] P2-1b: Pass correlation_id to Celery tasks via headers
- [ ] P2-1c: Configure Django LOGGING dict with JSON formatter for production
- [ ] P2-1d: Add correlation_id to Sentry context (sentry_sdk.set_tag)
- [ ] P2-1e: Frontend: Generate correlation ID per request, send in X-Correlation-ID header
- [ ] P2-1f: Add to WebSocket consumers — include in all channel messages
```

**Acceptance criteria**: Given a user-facing error, support can trace the full request chain (API → task → DB) using a single correlation ID.

---

### P2-2: SLO/SLA Definitions

**Gap**: No defined performance targets. No alerting when targets are breached.

| Endpoint Tier | Latency SLO (p95) | Availability SLO | Error Rate SLO |
|--------------|-------------------|-------------------|----------------|
| Auth (login, register, token) | ≤ 200ms | 99.95% | ≤ 0.1% |
| Read (listings, profiles, search) | ≤ 500ms | 99.9% | ≤ 0.5% |
| Write (create, update, delete) | ≤ 1s | 99.9% | ≤ 0.5% |
| AI/ML (generation, chat, parse) | ≤ 10s | 99.5% | ≤ 2% |
| Payments (checkout, webhook) | ≤ 2s | 99.95% | ≤ 0.1% |
| Bulk (export, reports) | ≤ 30s | 99% | ≤ 1% |

**Tasks**:
```
- [ ] P2-2a: Define SLO document with the above targets
- [ ] P2-2b: Add Django middleware to track per-endpoint latency (histogram to Prometheus or log)
- [ ] P2-2c: Configure Sentry performance monitoring with these thresholds
- [ ] P2-2d: Set up alerting rules: page when SLO is breached for > 5 min
- [ ] P2-2e: Create error budget tracking (monthly SLO burn rate)
```

---

### P2-3: Circuit Breaker Verification & Extension

**Current state**: Circuit breaker exists in backend — Redis-backed, pre-configured for Stripe, Email, Storage, LLM in `talentorbit/circuit_breaker.py`.

**What's missing**:
```
- [ ] P2-3a: Verify circuit breaker is actually WIRED into payment views (not just defined)
- [ ] P2-3b: Verify circuit breaker is wired into AI views (OpenAI calls)
- [ ] P2-3c: Verify circuit breaker is wired into email sending (Resend)
- [ ] P2-3d: Verify circuit breaker is wired into storage operations (Cloudflare R2)
- [ ] P2-3e: Add circuit breaker for webhook delivery (developer/tasks.py)
- [ ] P2-3f: Add Prometheus metrics for circuit breaker state (open/half-open/closed)
- [ ] P2-3g: Add health check integration — /health/detailed/ should report circuit breaker states
- [ ] P2-3h: Configure alerting when any circuit breaker opens
```

---

### P2-4: Backup & Disaster Recovery Plan

**Gap**: Zero documented backup strategy.

| Component | Backup Strategy | RPO | RTO |
|-----------|----------------|-----|-----|
| PostgreSQL | Continuous WAL archiving + daily pg_dump to S3 | 5 min | 1 hour |
| Redis | RDB snapshots every 15 min + AOF appendonly | 15 min | 30 min |
| Cloudflare R2 | S3 versioning enabled + cross-region replication | 0 (immediate) | 15 min |
| Celery task state | celery-results in DB (covered by PG backup) | Same as PG | Same as PG |
| Application code | Git + container images in registry | 0 | 10 min (redeploy) |

**Tasks**:
```
- [ ] P2-4a: Configure PG WAL archiving to S3 (or Render's managed backup for now)
- [ ] P2-4b: Daily pg_dump cron job → S3 with 30-day retention
- [ ] P2-4c: Redis RDB snapshot schedule in redis.conf
- [ ] P2-4d: Test restore from backup quarterly
- [ ] P2-4e: Document runbook for disaster recovery
- [ ] P2-4f: Test failover procedure end-to-end
```

---

## P3 — Performance & Scale

### P3-1: Redis Cache Strategy (C5)

**Gap**: C5 — Zero caching. Every request hits PostgreSQL directly. No cache framework configured.

**Implementation**:

```python
# settings.py — Add cache backend:
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': env('REDIS_URL'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'SERIALIZER': 'django_redis.serializers.json.JSONSerializer',
        },
        'KEY_PREFIX': 'to',
        'TIMEOUT': 300,  # 5 min default
    }
}
```

**Cache targets** (highest impact):

| Endpoint | TTL | Invalidation Trigger | Stampede Prevention |
|----------|-----|---------------------|-------------------|
| `/api/payments/plans/` (plan listing) | 1 hour | Plan CRUD via signal | Lock-based refresh |
| `/api/search/companies/` (company directory) | 15 min | Company profile update | Lock-based refresh |
| `/api/intelligence/ai/compensation/` | 6 hours | Weekly batch job | Pre-warm cache |
| `/api/intelligence/experiments/flags/` | 5 min | Flag change webhook | Direct invalidation |
| `/api/compliance/policies/` (active policies) | 1 hour | Policy publish via signal | Lock-based refresh |
| User profile data | 10 min | Profile update signal | Direct invalidation |

**Stampede Prevention Pattern**:
```python
from django.core.cache import cache
import time

def cache_with_lock(key, timeout, generator_fn):
    """Prevents thundering herd on cache miss."""
    result = cache.get(key)
    if result is not None:
        return result

    lock_key = f'lock:{key}'
    if cache.add(lock_key, '1', timeout=30):  # 30s lock
        try:
            result = generator_fn()
            cache.set(key, result, timeout)
            return result
        finally:
            cache.delete(lock_key)
    else:
        # Another process is refreshing — wait and retry
        for _ in range(10):
            time.sleep(0.5)
            result = cache.get(key)
            if result is not None:
                return result
        # Fallback: generate anyway
        return generator_fn()
```

**Tasks**:
```
- [ ] P3-1a: Add django-redis to requirements.txt and configure CACHES in settings.py
- [ ] P3-1b: Implement cache_with_lock utility
- [ ] P3-1c: Add caching to plan listing endpoint
- [ ] P3-1d: Add caching to company directory endpoint
- [ ] P3-1e: Add caching to feature flag endpoint
- [ ] P3-1f: Add caching to compensation benchmark endpoint
- [ ] P3-1g: Add caching to active policies endpoint
- [ ] P3-1h: Add cache invalidation signals for each cached model
- [ ] P3-1i: Add cache hit/miss metrics (Prometheus counter or structured log)
- [ ] P3-1j: Write tests: verify cache hit, cache miss, cache invalidation, stampede prevention
```

---

### P3-2: N+1 Query Prevention

**Gap**: No `select_related` / `prefetch_related` audit. Every list endpoint likely has N+1 queries.

**High-priority targets** (pages with lists/tables):

| Endpoint | Model | Likely N+1 | Fix |
|----------|-------|-----------|-----|
| Pipeline candidates | `TalentPoolCandidate` | `.user`, `.user.talentprofile` | `select_related('user', 'user__talentprofile')` |
| Revenue dashboard | `PaymentHistory` | `.customer_profile.user` | `select_related('customer_profile__user')` |
| Company directory | `CompanyProfile` | `.user`, `.subscription_plan` | `select_related('user', 'subscription_plan')` |
| Talent search | `TalentProfile` | `.user`, `.skills` | `select_related('user')`, `prefetch_related('skills')` |
| Sponsored campaigns | `SponsoredJobCampaign` | `.job.company` | `select_related('job__company')` |
| Billing overview | `Invoice` + `PaymentHistory` | Multiple related objects | Optimize per query |
| Audit log list | `AuditLog` | `.user` | `select_related('user')` |

**Tasks**:
```
- [ ] P3-2a: Enable Django debug toolbar in dev (django-debug-toolbar already in requirements? Check and add if needed)
- [ ] P3-2b: Add django-query-inspector or django-silk for query profiling
- [ ] P3-2c: Audit EVERY ViewSet/ListView queryset — add select_related/prefetch_related
- [ ] P3-2d: Set max query count assertion in tests (no endpoint should exceed 10 queries)
- [ ] P3-2e: Add pagination to ALL list endpoints (max 50 items per page)
```

---

### P3-3: Per-Endpoint Throttle Scopes (C6)

**Gap**: C6 — 9 apps use only global `DEFAULT_THROTTLE_RATES`. Only `compliance` and `developer` have custom throttle classes.

**Implementation**:

```python
# In settings.py — add granular rates:
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
        # Granular scopes:
        'auth': '20/minute',          # Login, register, password reset
        'payments': '30/minute',       # Financial operations
        'ai_generation': '10/minute',  # LLM-powered endpoints
        'search': '60/minute',         # Search queries
        'export': '5/hour',            # Data exports
        'webhook_create': '10/hour',   # Webhook registration
        'referral': '5/hour',          # Referral creation (anti-fraud)
    },
}
```

**Tasks**:
```
- [ ] P3-3a: Define throttle scopes for all endpoint categories
- [ ] P3-3b: Add throttle_scope to accounts views (auth scope)
- [ ] P3-3c: Add throttle_scope to payments views (payments scope)
- [ ] P3-3d: Add throttle_scope to intelligence AI views (ai_generation scope)
- [ ] P3-3e: Add throttle_scope to search views (search scope)
- [ ] P3-3f: Add throttle_scope to compliance export views (export scope)
- [ ] P3-3g: Add throttle_scope to developer webhook views (webhook_create scope)
- [ ] P3-3h: Add throttle_scope to referral creation (referral scope)
- [ ] P3-3i: Add 429 response documentation to OpenAPI schema
- [ ] P3-3j: Frontend: Handle 429 responses with "Retry-After" header and user-friendly message
```

---

### P3-4: Database Index Strategy

**Gap**: No explicit index audit. Django auto-creates indexes for `ForeignKey`, `unique=True`, and `primary_key=True`, but composite indexes and partial indexes are missing.

**High-value indexes to add**:

```python
# payments/models.py:
class PaymentHistory(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=['user', '-created_at'], name='idx_payment_user_date'),
            models.Index(fields=['stripe_payment_intent_id'], name='idx_payment_stripe_id'),
        ]

class Invoice(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=['user', 'status', '-created_at'], name='idx_invoice_user_status'),
        ]

# compliance/models.py:
class AuditLog(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=['user', '-timestamp'], name='idx_audit_user_time'),
            models.Index(fields=['action_type', '-timestamp'], name='idx_audit_action_time'),
            models.Index(fields=['resource_type', 'resource_id'], name='idx_audit_resource'),
        ]

# jobs/models.py:
class Job(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=['company', 'status', '-created_at'], name='idx_job_company_status'),
            models.Index(fields=['status', '-created_at'], name='idx_job_status_date'),  # For public listing
        ]
```

**Tasks**:
```
- [ ] P3-4a: Audit all models — identify queries without supporting indexes
- [ ] P3-4b: Add composite indexes for common query patterns (see above)
- [ ] P3-4c: Add partial indexes for soft-deleted records (WHERE is_active=true)
- [ ] P3-4d: Run EXPLAIN ANALYZE on the 10 slowest queries
- [ ] P3-4e: Generate migration for new indexes
- [ ] P3-4f: Verify index creation doesn't lock tables in production (use CREATE INDEX CONCURRENTLY)
```

---

## P4 — Developer Experience

### P4-1: API Versioning Strategy

**Current state**: `DEFAULT_VERSIONING_CLASS = 'URLPathVersioning'` is configured in settings.py but NO views enforce versioning. URLs don't include `/v1/`.

**Tasks**:
```
- [ ] P4-1a: Decide versioning strategy: URL path (/api/v1/) vs header (Accept-Version: v1)
- [ ] P4-1b: Add /api/v1/ prefix to all URL patterns
- [ ] P4-1c: Create versioned serializers pattern (V1Serializer, V2Serializer)
- [ ] P4-1d: Add deprecation headers for sunset APIs
- [ ] P4-1e: Document versioning policy (minimum 6 months before version sunset)
```

---

### P4-2: Dependency Security Scanning

**Gap**: Zero automated dependency vulnerability scanning.

**Tasks**:
```
- [ ] P4-2a: Add pip-audit to requirements.txt (dev dependencies)
- [ ] P4-2b: Run `pip-audit` NOW — fix all critical/high severity issues
- [ ] P4-2c: Add `npm audit` to CI pipeline
- [ ] P4-2d: Run `npm audit` NOW — fix all critical/high severity issues
- [ ] P4-2e: Pin ALL dependencies to exact versions (no ^, no ~, no >=)
- [ ] P4-2f: Set up Dependabot or Renovate for automated PR creation on vulnerability disclosure
- [ ] P4-2g: Add SBOM (Software Bill of Materials) generation to build pipeline
```

---

## WS1 — Infrastructure & DevOps

### Status

| Item | Description | Status |
|------|------------|--------|
| WS1-1 | Docker multi-stage build (3-stage Dockerfile) | ✅ Done |
| WS1-2 | Docker Compose dev + prod | ✅ Done (dev: PG, Redis, MinIO, Judge0, API, Worker, Beat; prod: Nginx, API, Worker, Beat with resource limits) |
| WS1-3 | Celery with 8 queues + ~30 routed tasks + ~25 periodic tasks + DatabaseScheduler | ✅ Done |
| WS1-4 | 4-tier health checks (/health/, /ready/, /live/, /detailed/) | ✅ Done |
| WS1-5 | GitHub Actions CI/CD | ✅ Done |
| WS1-6 | Kubernetes manifests (Helm charts) | 🟡 Partial — `infra/helm/` exists but needs validation |
| WS1-7 | PgBouncer connection pooling | 🔴 Missing |
| WS1-8 | Database read-replica routing | 🔴 Missing |
| WS1-9 | Cloudflare Workers edge caching | 🔴 Missing |

### WS1-6: Validate Helm Charts

**Tasks**:
```
- [ ] WS1-6a: Review infra/helm/ directory — verify templates, values.yaml, Chart.yaml
- [ ] WS1-6b: Add resource limits and requests for all pods
- [ ] WS1-6c: Add HPA (Horizontal Pod Autoscaler) for API and Worker deployments
- [ ] WS1-6d: Add PodDisruptionBudget (PDB) for zero-downtime upgrades
- [ ] WS1-6e: Add NetworkPolicy to restrict inter-pod communication
- [ ] WS1-6f: Validate with `helm template . | kubectl apply --dry-run=client -f -`
- [ ] WS1-6g: Add Helm chart tests
```

### WS1-7: PgBouncer

**Tasks**:
```
- [ ] WS1-7a: Add PgBouncer to docker-compose.prod.yml
- [ ] WS1-7b: Configure transaction-level pooling (POOL_MODE=transaction)
- [ ] WS1-7c: Update Django DATABASES to connect through PgBouncer
- [ ] WS1-7d: Set max_client_conn and default_pool_size based on worker count
- [ ] WS1-7e: Add PgBouncer health check to /health/detailed/
```

### WS1-8: Read Replica Routing

**Tasks**:
```
- [ ] WS1-8a: Add 'replica' database config to DATABASES
- [ ] WS1-8b: Create DatabaseRouter class (writes → default, reads → replica)
- [ ] WS1-8c: Configure DATABASE_ROUTERS in settings.py
- [ ] WS1-8d: Test that all write operations go to primary
- [ ] WS1-8e: Handle replication lag for read-after-write scenarios (use primary for 5s after write)
```

### WS1-9: Cloudflare Workers Edge Caching

**Tasks**:
```
- [ ] WS1-9a: Design edge caching rules (public plans, company directory = cacheable; auth endpoints = never cache)
- [ ] WS1-9b: Create Cloudflare Worker script for intelligent cache routing
- [ ] WS1-9c: Add Cache-Control and Vary headers to Django responses
- [ ] WS1-9d: Add cache purge on content mutation (Cloudflare API)
- [ ] WS1-9e: Add infra/cloudflare/ worker scripts to repository
```

---

## WS2 — Content & Assessments

### Status

| Item | Description | Status |
|------|------------|--------|
| WS2-1 | Course CRUD + enrollment + progress tracking | ✅ Done (courses/ app with models, views, serializers, signals, tasks) |
| WS2-2 | Blog CMS with publishing workflow | ✅ Done (blog/ app) |
| WS2-3 | Assessment engine with coding challenges | 🟡 Partial — models exist (assessments/), Judge0 client exists (code_runner.py), but NO migrations |
| WS2-4 | Course video transcoding pipeline | 🔴 Missing |
| WS2-5 | Full-text search for courses/blog content | 🟡 Partial — search/ app exists, but unclear if course/blog content is indexed |

### W2-1: Video Transcoding Pipeline

**Gap**: Course model likely has a video field but no transcoding. Raw uploads mean variable quality, huge file sizes, and no HLS streaming.

**Tasks**:
```
- [ ] W2-1a: Decide transcoding service: FFmpeg worker (self-hosted), Cloudflare Stream, or Mux
- [ ] W2-1b: Add video upload endpoint to courses/ — accept raw upload → S3
- [ ] W2-1c: Create Celery task for transcoding (queue: 'intelligence' or new 'media' queue)
- [ ] W2-1d: Generate HLS segments (720p, 1080p) + thumbnail
- [ ] W2-1e: Update course model with video_url, thumbnail_url, duration, transcoding_status
- [ ] W2-1f: Frontend: Video player component with HLS.js + quality selector
- [ ] W2-1g: Add progress tracking (video watch percentage → course progress)
```

### W2-2: Full-Text Search Integration

**Tasks**:
```
- [ ] W2-2a: Verify search/ app indexes course content (titles, descriptions, tags)
- [ ] W2-2b: Verify search/ app indexes blog posts (title, body, tags)
- [ ] W2-2c: Add search filters for content type (course, blog, job)
- [ ] W2-2d: Add search analytics (track what users search for)
- [ ] W2-2e: Add "no results" suggestions (typo correction, related content)
```

---

## WS3 — Developer Platform

### Status

| Item | Description | Status |
|------|------------|--------|
| WS3-1 | API Key model (SHA-256 hashed) | 🟡 Partial — model exists in developer/models.py, but no custom DRF auth backend to validate API keys in request headers |
| WS3-2 | OAuth2 provider (django-oauth-toolkit) | 🟡 Partial — `oauth2_provider` is in INSTALLED_APPS, developer/models.py has OAuthApplication model, but no authorization_code flow implemented |
| WS3-3 | Webhook delivery system | 🔴 Missing — WebhookEndpoint + WebhookDelivery models exist, but no delivery mechanism (no Celery task to POST to endpoints) |
| WS3-4 | Developer dashboard frontend | 🔴 Missing — no frontend pages for developer portal |
| WS3-5 | API changelog with versioned entries | 🔴 Missing — APIChangelog model exists, but no views/serializers to serve it |
| WS3-6 | SDK generation (Python, JavaScript) | 🔴 Missing — no SDK scaffolding or auto-generation |

### W3-1: OAuth2 Authorization Code Flow

**Current state**: `oauth2_provider` is in INSTALLED_APPS. `developer/authentication.py` exists but needs verification.

**Tasks**:
```
- [ ] W3-1a: Verify oauth2_provider URL patterns are included in project urls.py
- [ ] W3-1b: Implement authorization_code grant flow (authorize → callback → token exchange)
- [ ] W3-1c: Create OAuth2 consent screen template
- [ ] W3-1d: Define OAuth scopes (read:profile, read:jobs, write:jobs, read:applications, etc.)
- [ ] W3-1e: Add PKCE support (required for public clients / SPAs)
- [ ] W3-1f: Add token introspection endpoint
- [ ] W3-1g: Add token revocation endpoint
- [ ] W3-1h: Write integration tests for full OAuth2 flow
```

### W3-2: API Key Authentication Backend

**Current state**: `developer/models.py` has APIKey model with SHA-256 hashing, but no DRF authentication backend that reads `X-API-Key` header and authenticates.

**Tasks**:
```
- [ ] W3-2a: Create developer/authentication.py — APIKeyAuthentication(BaseAuthentication)
- [ ] W3-2b: Validate X-API-Key header → SHA-256 hash → lookup in APIKey table
- [ ] W3-2c: Check key.is_active, key.expires_at, key.rate_limit
- [ ] W3-2d: Add to DEFAULT_AUTHENTICATION_CLASSES (last, after JWT and OAuth2)
- [ ] W3-2e: Track API key usage (last_used_at, request_count)
- [ ] W3-2f: Add per-API-key throttling based on key.rate_limit field
- [ ] W3-2g: Write tests: valid key, expired key, revoked key, rate-limited key
```

### W3-3: Webhook Delivery System

**Tasks**:
```
- [ ] W3-3a: Create developer/tasks.py — deliver_webhook Celery task
- [ ] W3-3b: POST to webhook URL with HMAC-SHA256 signature in header
- [ ] W3-3c: Implement retry with exponential backoff (3 attempts, then DLQ)
- [ ] W3-3d: Record delivery status in WebhookDelivery model (success, failed, retrying)
- [ ] W3-3e: Add webhook URL validation — denylist localhost, internal IPs, cloud metadata endpoints
- [ ] W3-3f: Add webhook event types (job.created, application.received, invoice.paid, etc.)
- [ ] W3-3g: Create webhook test endpoint — "Send test event" button in developer portal
- [ ] W3-3h: Add webhook delivery log viewer in developer dashboard
```

### W3-5: API Changelog

**Tasks**:
```
- [ ] W3-5a: Create developer/serializers.py — APIChangelogSerializer
- [ ] W3-5b: Create developer/views.py — APIChangelogListView (public, paginated)
- [ ] W3-5c: Create admin command to generate changelog from git diff of serializers/views
- [ ] W3-5d: Frontend: Developer changelog page with timeline view
```

### W3-6: SDK Generation

**Tasks**:
```
- [ ] W3-6a: Generate OpenAPI spec (P1-3 prerequisite)
- [ ] W3-6b: Use openapi-generator to create Python SDK from spec
- [ ] W3-6c: Use openapi-generator to create JavaScript/TypeScript SDK from spec
- [ ] W3-6d: Publish Python SDK to internal PyPI (or public if appropriate)
- [ ] W3-6e: Publish JS SDK to npm
- [ ] W3-6f: Auto-regenerate SDKs in CI on API schema change
```

---

## WS4 — Revenue & Growth

### Status

| Item | Description | Status |
|------|------------|--------|
| WS4-1 | Stripe integration — SubscriptionPlan, CustomerProfile, checkout session, portal | 🟡 Partial — 12 models in payments/models.py, views/serializers/URLs all exist, BUT zero migrations → no DB tables |
| WS4-2 | Invoice PDF generation | 🟡 Partial — Invoice model exists, but no PDF generation (no WeasyPrint/ReportLab) |
| WS4-3 | Coupon/Discount system | 🟡 Partial — Coupon + CouponRedemption models exist, but no redemption validation logic |
| WS4-4 | Referral program engine | 🟡 Partial — ReferralProgram, Referral, ReferralReward models exist, but reward distribution not implemented |
| WS4-5 | Sponsored job campaigns with daily budget | 🔴 Missing — SponsoredJobCampaign model exists, but no campaign runner (daily spend calculation, impression tracking) |
| WS4-6 | CRM talent pipeline with stages | 🔴 Missing — TalentPoolPipeline + TalentPoolCandidate models exist, but no stage transition logic, no WebSocket updates |
| WS4-7 | Revenue analytics dashboard backend | 🔴 Missing — views exist but return empty/mock data — no actual aggregation queries |

### W4-1: Run Payments Migrations (= P0-1)

See P0-1 above. This is the blocker for ALL of WS4.

### W4-2: Invoice PDF Generation

**Tasks**:
```
- [ ] W4-2a: Add weasyprint (or reportlab) to requirements.txt
- [ ] W4-2b: Create payments/invoice_generator.py — render Invoice model to PDF
- [ ] W4-2c: Include: company logo, line items, tax, total, payment status, due date
- [ ] W4-2d: Store generated PDF in S3 (Cloudflare R2)
- [ ] W4-2e: Add download endpoint: GET /api/payments/invoices/{id}/pdf/
- [ ] W4-2f: Auto-generate on invoice.paid webhook event (Celery task)
- [ ] W4-2g: Email PDF to customer via Resend
```

### W4-3: Coupon Redemption Validation

**Tasks**:
```
- [ ] W4-3a: Implement coupon validation logic: check expiry, usage_limit, min_purchase_amount
- [ ] W4-3b: Apply discount at checkout (percentage or fixed amount)
- [ ] W4-3c: Track redemption in CouponRedemption model
- [ ] W4-3d: Prevent double-redemption per user
- [ ] W4-3e: Stripe integration — apply coupon via Stripe Coupon API
```

### W4-4: Referral Reward Distribution

**Tasks**:
```
- [ ] W4-4a: Implement reward trigger: referee completes paid action → referrer gets reward
- [ ] W4-4b: Reward types: credit (apply to next invoice), cash (Stripe payout), or feature unlock
- [ ] W4-4c: Anti-fraud: block self-referrals, block same-IP referrals, require email verification
- [ ] W4-4d: Referral expiry: 30-day attribution window
- [ ] W4-4e: Celery task: process_referral_reward (queue: 'payments')
```

### W4-5: Sponsored Campaign Runner

**Tasks**:
```
- [ ] W4-5a: Celery periodic task: daily_campaign_runner (every midnight)
- [ ] W4-5b: Calculate daily spend from impressions × CPC or daily budget cap
- [ ] W4-5c: Pause campaigns that exceed budget or end date
- [ ] W4-5d: Track impressions and clicks on sponsored job listings
- [ ] W4-5e: Integration with jobs/ app — boost job in search results when campaign is active
- [ ] W4-5f: Revenue attribution — link campaign spend to revenue dashboard
```

### W4-6: CRM Pipeline Stage Transitions

**Tasks**:
```
- [ ] W4-6a: Define default pipeline stages (Sourced → Screened → Interviewing → Offered → Hired → Rejected)
- [ ] W4-6b: Implement stage transition API with validation (no skipping stages without ADMIN override)
- [ ] W4-6c: Add transition timestamp logging for stage-to-stage velocity metrics
- [ ] W4-6d: WebSocket broadcast on stage change (see INTEGRATION_BINDING.md Step 11)
- [ ] W4-6e: Add candidate notes/comments per stage
- [ ] W4-6f: Email notifications on stage change (to candidate and hiring manager)
```

### W4-7: Revenue Analytics Queries

**Tasks**:
```
- [ ] W4-7a: Implement MRR (Monthly Recurring Revenue) calculation from active subscriptions
- [ ] W4-7b: Implement churn rate calculation (cancelled / total active)
- [ ] W4-7c: Implement ARPU (Average Revenue Per User) from PaymentHistory
- [ ] W4-7d: Implement LTV estimation (ARPU × average lifespan)
- [ ] W4-7e: Cohort analysis — group users by signup month, track retention
- [ ] W4-7f: Revenue by source (subscriptions, sponsored posts, referral fees)
- [ ] W4-7g: Time-series trend data (monthly, aggregated with Django ORM annotations)
- [ ] W4-7h: Cache results (expensive queries) — see P3-1
```

---

## WS5 — AI/ML Platform

### Status

| Item | Description | Status |
|------|------------|--------|
| WS5-1 | AI-powered job description writer | 🟡 Partial — endpoint exists in intelligence/ai_views.py, but generation logic is scaffold/placeholder |
| WS5-2 | AI chatbot with context-aware responses | 🔴 Missing — no endpoint, no view, no chat history |
| WS5-3 | Interview scheduling with AI slot optimization | 🔴 Missing — endpoint may exist as scaffold, but no calendar integration, no optimization logic |
| WS5-4 | Compensation benchmarking with ML | 🔴 Missing — no endpoint, no model, no data pipeline |
| WS5-5 | PII detection in AI pipeline | 🔴 Missing — see P1-2 above |
| WS5-6 | Mobile app (React Native) | 🔴 Missing — no React Native project |

### W5-1: AI Job Description Writer (Complete the Scaffold)

**Current state**: `intelligence/ai_views.py` has a view but it either returns mock data or has minimal LLM integration.

**Tasks**:
```
- [ ] W5-1a: Verify current ai_views.py implementation — identify what's scaffold vs real
- [ ] W5-1b: Implement OpenAI call with structured prompt:
      System: "You are an expert HR writer. Generate a job description..."
      User: role_title + requirements + tone (formal↔casual scale)
- [ ] W5-1c: Add bias detection — scan generated JD for gendered language, age bias
- [ ] W5-1d: Add DOMPurify sanitization on generated HTML (server-side AND client-side)
- [ ] W5-1e: Add PII stripping on input (P1-2 prerequisite)
- [ ] W5-1f: Add rate limiting (10 generations/minute per user)
- [ ] W5-1g: Add generation caching — same input → cached output for 1 hour
- [ ] W5-1h: Use circuit breaker for OpenAI calls (existing circuit_breaker.py)
- [ ] W5-1i: Fallback when OpenAI is down: return "Service temporarily unavailable" with retry-after
- [ ] W5-1j: Log generation requests to AuditLog (input hash, not raw input)
```

### W5-2: AI Chatbot

**Tasks**:
```
- [ ] W5-2a: Create intelligence/ai_views.py — ChatWithAIView
- [ ] W5-2b: POST /api/intelligence/ai/chat/ — accepts message + context
- [ ] W5-2c: System prompt: "You are TalentOrbit assistant. Help with job searching, applications, hiring..."
- [ ] W5-2d: Context injection: include user role, active subscription, recent activity
- [ ] W5-2e: PII stripping before LLM call (P1-2 prerequisite)
- [ ] W5-2f: Content moderation on response — reject harmful/off-topic
- [ ] W5-2g: Prompt injection prevention:
      - Separate system prompt from user input clearly
      - Input length limit (2000 chars)
      - Reject inputs containing "ignore previous instructions" patterns
- [ ] W5-2h: Rate limit: 10 messages/minute
- [ ] W5-2i: No server-side chat persistence (privacy) — session-scoped only
- [ ] W5-2j: "Talk to Human" escalation — creates support ticket
- [ ] W5-2k: Circuit breaker for OpenAI calls
```

### W5-3: Interview Scheduling

**Tasks**:
```
- [ ] W5-3a: Determine calendar integration: Google Calendar API, Microsoft Graph, or Calendly
- [ ] W5-3b: Create intelligence/calendar_service.py — CalendarAdapter with provider abstraction
- [ ] W5-3c: OAuth2 flow for calendar access (Google/Microsoft consent)
- [ ] W5-3d: AI slot optimization: analyze interviewer availability + candidate timezone + meeting room
- [ ] W5-3e: Propose top 3 slots, let candidate pick
- [ ] W5-3f: Send calendar invites via iCal attachment or direct API
- [ ] W5-3g: Reminder notifications (24h before, 1h before) via Celery scheduled task
- [ ] W5-3h: Reschedule/cancel handling with notification propagation
```

### W5-4: Compensation Benchmarking

**Tasks**:
```
- [ ] W5-4a: Design data model — CompensationDataPoint (role, level, location, base, bonus, equity, source)
- [ ] W5-4b: Seed with public dataset (BLS, Glassdoor API if available, or user-contributed anonymized data)
- [ ] W5-4c: ML model: regression on (role, level, location, company_size) → predicted compensation range
- [ ] W5-4d: Create intelligence/views.py — CompensationBenchmarkView
- [ ] W5-4e: GET /api/intelligence/ai/compensation/?role=X&location=Y → { p25, p50, p75, p90 }
- [ ] W5-4f: Cache results (6h TTL) — same query returns cached
- [ ] W5-4g: Rate limit: 60 queries/minute (anti-scraping)
- [ ] W5-4h: Add to Celery periodic: weekly model retrain from new data
```

### W5-6: Mobile App (Deferred — Document Only)

**Tasks**:
```
- [ ] W5-6a: Create React Native project scaffold (Expo or bare workflow)
- [ ] W5-6b: Shared API service layer (same endpoints as web)
- [ ] W5-6c: Push notification integration (Firebase Cloud Messaging)
- [ ] W5-6d: Biometric auth (FaceID/TouchID)
- [ ] W5-6e: Offline mode with sync queue
```

**Priority**: P4 — deferred to post-launch. Web-first. Document requirements only for now.

---

## Testing Strategy

### Current Coverage

| App | Has Tests | Test Quality | Required Action |
|-----|-----------|-------------|-----------------|
| accounts | ✅ `tests.py` | Basic | Add edge cases, permission tests |
| jobs | ✅ `tests.py` | Basic | Add edge cases |
| payments | ✅ `tests.py` | Minimal | Rewrite — test Stripe webhook handling, idempotency, race conditions |
| compliance | ✅ `tests/` (10 files + factories) | Good | Maintain, extend for new audit coverage |
| developer | ✅ `tests/` (7 files) | Good | Add OAuth2 flow tests, API key auth tests |
| project-level | ✅ `tests/` (9 files) | Integration | Maintain |
| courses | 🔴 Zero | — | Write from scratch |
| intelligence | 🔴 Zero | — | Write from scratch (mock OpenAI) |
| blog | 🔴 Zero | — | Write from scratch |
| notifications | 🔴 Zero | — | Write from scratch |
| search | 🔴 Zero | — | Write from scratch |
| realtime | 🔴 Zero | — | Write from scratch (mock WebSocket) |
| assessments | 🔴 Zero | — | Write from scratch (mock Judge0) |
| reviews | 🔴 Zero | — | Write from scratch |
| admin_api | 🔴 Zero | — | Write from scratch |

### Test Pyramid Targets

| Layer | Count Target | Framework | What to Test |
|-------|-------------|-----------|-------------|
| Unit tests (models, utils) | ≥ 200 | pytest + pytest-django | Model validation, utility functions, serializer validation |
| Integration tests (views) | ≥ 150 | pytest + DRF test client | API endpoints, permissions, throttling, error responses |
| E2E tests (frontend) | ≥ 50 | Playwright or Cypress | Critical user flows (login → apply → pay → get results) |
| Load tests | ≥ 10 scenarios | Locust or k6 | SLO verification under load |

### Backend Test Tasks

```
- [ ] T1: Set up pytest-django + pytest-cov + factory-boy project-wide
- [ ] T2: Create base test factories for: User, CompanyProfile, TalentProfile, Job
- [ ] T3: Write tests for courses/ (CRUD, enrollment, progress, permissions)
- [ ] T4: Write tests for intelligence/ (mock OpenAI, test AI views, test recommendations)
- [ ] T5: Write tests for blog/ (CRUD, publishing workflow, permissions)
- [ ] T6: Write tests for notifications/ (creation, delivery, read status)
- [ ] T7: Write tests for search/ (indexing, querying, filtering, pagination)
- [ ] T8: Write tests for realtime/ (WebSocket connect, auth, message handling — mock channels)
- [ ] T9: Write tests for assessments/ (submission, code execution mock, scoring)
- [ ] T10: Write tests for reviews/ (creation, moderation, response)
- [ ] T11: Write tests for admin_api/ (admin-only access, CRUD operations)
- [ ] T12: Rewrite payments/tests.py — cover webhooks, idempotency, transaction atomicity
- [ ] T13: Add permission tests for ALL views — verify 403 for unauthorized roles
- [ ] T14: Add throttle tests — verify 429 when rate exceeded
- [ ] T15: Add N+1 query tests — assert max query count per endpoint
```

### Frontend Test Tasks

```
- [ ] FT1: Set up Vitest + @testing-library/react
- [ ] FT2: Write tests for all 14 new pages — test 4 states: loading, error, empty, data
- [ ] FT3: Write tests for Sidebar — verify nav items per role
- [ ] FT4: Write tests for ProtectedRoute — verify redirect for unauthorized
- [ ] FT5: Write tests for paymentStore — mock API, verify state transitions
- [ ] FT6: Write tests for aiStore — mock API, verify state transitions
- [ ] FT7: Write E2E test: login → navigate to billing → view invoices
- [ ] FT8: Write E2E test: company user → create sponsored campaign → view in dashboard
- [ ] FT9: Write E2E test: admin → toggle feature flag → verify flag state change
- [ ] FT10: Accessibility tests: run axe-core on all 14 pages
```

---

## Rollout Plan

### Phase 1 — Foundation (Weeks 1-2)

| Week | Tasks | Acceptance Gate |
|------|-------|----------------|
| 1 | P0-1 (migrations), P0-2 (transaction.atomic), P0-3 (idempotency), P0-4 (audit logging) | All DB tables exist. Financial writes are atomic. Audit trail covers all apps. |
| 2 | P1-1 (OWASP audit), P1-2 (PII detection), P1-4 (GDPR hardening) | Zero AllowAny views in production. PII stripped from AI pipeline. GDPR export covers all apps. |

### Phase 2 — Integration (Weeks 3-5)

| Week | Tasks | Acceptance Gate |
|------|-------|----------------|
| 3 | Wire all 14 pages (INTEGRATION_BINDING.md Steps 1-8) | All pages route-registered, use DashboardLayout, have loading/error/empty states. |
| 4 | P3-1 (caching), P3-2 (N+1 prevention), P3-3 (throttles) | Cache hit rate > 80% for read endpoints. No endpoint exceeds 10 queries. |
| 5 | WS4-1 through WS4-7 (revenue features) | Billing, plans, referrals, sponsored posts, CRM, revenue dashboard all functional with real data. |

### Phase 3 — AI/ML & Developer (Weeks 6-8)

| Week | Tasks | Acceptance Gate |
|------|-------|----------------|
| 6 | WS5-1 (AI job writer complete), WS5-2 (chatbot), WS5-5 (PII in pipeline) | AI features work with real OpenAI calls. PII is redacted. Circuit breaker tested. |
| 7 | WS3-1 (OAuth2), WS3-2 (API key auth), WS3-3 (webhooks) | Developer can authenticate via OAuth2 or API key. Webhooks deliver with HMAC signature. |
| 8 | WS5-3 (interviews), WS5-4 (compensation), P1-3 (OpenAPI docs) | Calendar integration works. Compensation benchmark returns real data. Full API docs at /api/docs/. |

### Phase 4 — Hardening (Weeks 9-10)

| Week | Tasks | Acceptance Gate |
|------|-------|----------------|
| 9 | P2-1 (structured logging), P2-2 (SLOs), P2-3 (circuit breaker verification), P2-4 (backup/DR) | Correlation IDs in all logs. SLO dashboards live. DR tested. |
| 10 | Testing (T1-T15, FT1-FT10), P4-1 (API versioning), P4-2 (dependency scanning) | ≥ 80% backend coverage. All 14 pages pass axe-core. Zero critical vulnerabilities. |

### Phase 5 — Scale & Polish (Weeks 11-12)

| Week | Tasks | Acceptance Gate |
|------|-------|----------------|
| 11 | WS1-7 (PgBouncer), WS1-8 (read replica), WS1-9 (edge caching), W2-1 (video transcoding) | Connection pooling active. Read replica routing works. Edge cache hit rate > 60%. |
| 12 | Load testing (k6/Locust against SLOs), security penetration test, final QA | All SLOs met under 10× expected load. Zero critical security findings. |

---

## Appendix: File Quick Reference

| Purpose | File(s) |
|---------|---------|
| Route registration | `src/App.jsx` |
| Sidebar nav | `src/components/Sidebar.jsx` |
| Layout wrapper | `src/layouts/DashboardLayout.jsx` |
| Auth guard | `src/components/ProtectedRoute.jsx` |
| Payment store | `src/store/paymentStore.js` |
| AI store (TO CREATE) | `src/store/aiStore.js` |
| API services | `src/services/api.js` |
| CSS tokens | `src/index.css` |
| Feature flags hook | `src/hooks/useFeatureFlags.js` |
| Backend settings | `backend/talentorbit/settings.py` |
| Celery config | `backend/talentorbit/celery.py` |
| Circuit breaker | `backend/talentorbit/circuit_breaker.py` |
| Audit middleware | `backend/compliance/middleware.py` |
| Payment models | `backend/payments/models.py` |
| AI views | `backend/intelligence/ai_views.py` |
| Health checks | `backend/talentorbit/health.py` or URL pattern |
