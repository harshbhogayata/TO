# Codebase Map

This is the practical map of the repo for maintenance work. It favors file ownership and debugging value over exhaustive documentation.

## Top Level Shape

- `src/`: React/Vite frontend
- `backend/`: Django API, async tasks, websocket support, domain apps
- `docs/`: operating docs and workflow references
- `infra/`: nginx, Helm, Cloudflare, deployment assets
- `scripts/`: workspace-level release and validation scripts
- `dist/`: built frontend output

## Frontend Map

### Core Runtime Files

- `src/App.jsx`: all route registration and role-gated page wiring
- `src/services/api.js`: Axios client, token refresh queue, named services
- `src/store/authStore.js`: persisted auth/session state
- `src/components/ProtectedRoute.jsx`: auth and role gate
- `src/contexts/ToastContext.jsx`: toast/event UI plumbing

### High-Value Pages By Workflow

Auth and onboarding:

- `src/pages/AuthPage.jsx`
- `src/pages/UserRegistration.jsx`
- `src/pages/CompanyRegistration.jsx`
- `src/pages/PasswordRecovery.jsx`
- `src/pages/VerifyEmail.jsx`
- `src/pages/ResumeParser.jsx`

Talent marketplace:

- `src/pages/UserDashboard.jsx`
- `src/pages/JobBoard.jsx`
- `src/pages/JobDetail.jsx`
- `src/pages/MyApplications.jsx`
- `src/pages/SavedJobs.jsx`
- `src/pages/RecommendedJobs.jsx`

Company hiring:

- `src/pages/CompanyDashboard.jsx`
- `src/pages/PostJob.jsx`
- `src/pages/ApplicantReview.jsx`
- `src/pages/CompanyAnalytics.jsx`
- `src/pages/TalentSearch.jsx`
- `src/pages/InterviewScheduler.jsx`

Billing and growth:

- `src/pages/BillingCenter.jsx`
- `src/pages/SubscriptionPlans.jsx`
- `src/pages/ReferralProgram.jsx`
- `src/pages/SponsoredPosts.jsx`
- `src/pages/CRMPipeline.jsx`
- `src/pages/RevenueDashboard.jsx`

Messaging and settings:

- `src/pages/Inbox.jsx`
- `src/pages/Notifications.jsx`
- `src/pages/Settings.jsx`
- `src/pages/PrivacyCenter.jsx`

Admin and platform ops:

- `src/pages/AdminConsole.jsx`
- `src/pages/AdminAnalytics.jsx`
- `src/pages/AuditLog.jsx`
- `src/pages/FeatureFlagAdmin.jsx`
- `src/pages/PolicyManager.jsx`

Developer platform:

- `src/pages/DeveloperPortal.jsx`
- `src/pages/APIKeysManager.jsx`
- `src/pages/WebhookManager.jsx`
- `src/pages/OAuthAppManager.jsx`

### Frontend Observations

- Route sprawl is concentrated in `src/App.jsx`.
- `src/services/api.js` is the main cross-cutting file for auth, retries, and API naming consistency.
- Some files contain mojibake/corrupted comments or UI text. That is real technical debt but should be handled separately from functional repairs.

## Backend Map

### Root Platform Files

- `backend/talentorbit/urls.py`: API root routing and health/docs endpoints
- `backend/talentorbit/settings.py`: production/default settings
- `backend/talentorbit/test_settings.py`: SQLite/eager test config
- `backend/talentorbit/asgi.py`: ASGI app and websocket routing
- `backend/talentorbit/celery.py`: Celery bootstrap
- `backend/scripts/runtime_smoke.py`: import-level runtime validation

### Domain Apps

Accounts:

- Purpose: auth, registration, profile endpoints, password reset, email verification, 2FA
- Key files: `backend/accounts/views.py`, `backend/accounts/serializers.py`, `backend/accounts/models.py`, `backend/accounts/tasks.py`

Jobs:

- Purpose: job board, applications, saved jobs, company CRUD
- Key files: `backend/jobs/models.py`, `backend/jobs/views.py`, `backend/jobs/serializers.py`, `backend/jobs/tests.py`

Messaging:

- Purpose: threads, messages, unread counts, participant access control
- Key files: `backend/messaging/views.py`, `backend/messaging/models.py`

Realtime:

- Purpose: websocket/push routing and consumers
- Key files: `backend/realtime/consumers.py`, `backend/realtime/routing.py`, `backend/realtime/middleware.py`

Payments:

- Purpose: plans, checkout, customer portal, referrals, sponsored posts, CRM/pipeline, Stripe webhook handling
- Key files: `backend/payments/views.py`, `backend/payments/tasks.py`, `backend/tests/test_payments.py`

Search:

- Purpose: public search, talent/company search, analytics, caching, search vectors
- Key files: `backend/search/views.py`, `backend/search/cache.py`, `backend/search/signals.py`, `backend/tests/test_search.py`

Intelligence:

- Purpose: resume parsing, recommendations, AI-generated job descriptions, interview scheduling, compensation helpers, analytics helpers
- Key files: `backend/intelligence/views.py`, `backend/intelligence/views_ai_enhanced.py`, `backend/intelligence/nlp/*`

Compliance:

- Purpose: audit logs, policies, consent, GDPR, team invites, security.txt
- Key files: `backend/compliance/views.py`, `backend/compliance/tasks.py`, `backend/compliance/signals.py`

Assessments:

- Purpose: assessment catalog, attempts, grading, result calculations
- Key files: `backend/assessments/views.py`, `backend/assessments/tasks.py`

Developer:

- Purpose: API keys, webhooks, OAuth apps, delivery logs
- Key files: `backend/developer/views.py`, `backend/developer/models.py`, `backend/developer/tasks.py`

Admin API:

- Purpose: admin metrics, user actions, platform moderation endpoints
- Key files: `backend/admin_api/views.py`

Courses, Reviews, Blog, Notifications:

- Purpose: supporting product surfaces and content operations
- Key files live in their respective app folders

## Cross-Cutting Mechanics

Authentication and sessions:

- JWT auth via SimpleJWT
- frontend keeps access token in memory and refresh token persisted in Zustand
- session restore lives in `src/services/api.js`
- login endpoint lives at `backend/accounts/views.py:CustomTokenObtainPairView`

Async behavior:

- Celery is used for email, analytics, notifications, compliance, developer deliveries, and more
- local/test mode can degrade to eager execution if broker is absent or test settings force it

Realtime behavior:

- Channels + Redis in fuller environments
- in-memory channel layer for local/test fallback

Search behavior:

- cache invalidation and search-vector updates happen via signals
- PostgreSQL search-vector logic must be guarded when running on SQLite

## Where To Look First By Symptom

Login or session restore:

- `src/pages/AuthPage.jsx`
- `src/services/api.js`
- `src/store/authStore.js`
- `backend/accounts/views.py`
- `backend/accounts/serializers.py`

Wrong role redirect or inaccessible route:

- `src/components/ProtectedRoute.jsx`
- `src/App.jsx`
- corresponding backend permission class or view

Job board or apply flow:

- `backend/jobs/views.py`
- `backend/jobs/serializers.py`
- `backend/jobs/tests.py`
- `backend/tests/test_search.py`

Message thread or inbox issue:

- `backend/messaging/views.py`
- `backend/tests/test_messaging.py`
- `backend/tests/test_realtime.py`

Webhook, API key, or outbound integration issue:

- `backend/developer/views.py`
- `backend/developer/models.py`
- `backend/developer/tasks.py`
- `backend/developer/tests/test_webhooks.py`

## External Dependency Reality

The app can run in partially degraded local/test mode, but production intent assumes these integrations exist:

- Postgres
- Redis / Upstash Redis
- Stripe
- email delivery backend
- optional OpenAI
- Firebase
- Sentry
- PostHog

When debugging a bug that appears only in deployment, always ask whether the issue is code or environment mismatch.