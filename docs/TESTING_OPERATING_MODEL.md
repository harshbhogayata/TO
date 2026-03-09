# Testing Operating Model

This file defines how the codebase should be tested so repair quality stays consistent across sessions.

## Principle

Do not test the whole platform blindly every time. Test the workflow you are actively repairing, then escalate only if the change crosses workflow boundaries.

## Primary Command Surface

Focused checks live in:

```bash
python scripts/release_checks.py --list
```

Available workflow groups currently include:

- `onboarding`
- `jobs`
- `billing`
- `growth`
- `messaging`
- `admin`
- `developer`
- `ai`
- `learning`
- `full`

## Expected Testing Order Per Bug

1. Reproduce the bug manually.
2. Identify the workflow and actor.
3. Add or update the smallest failing automated test.
4. Run the matching focused check group.
5. Fix the bug.
6. Re-run the same focused check group.
7. Manually verify the same path again.
8. Only then consider wider regression checks.

## What Each Layer Proves

Frontend targeted tests:

- route guards and redirect logic
- auth store/session behavior
- API error normalization
- small component and hook contracts

Backend runtime smoke:

- import-time health of the live Django app wiring
- URL registration and critical dependency imports
- catches bad bootstrap assumptions before deeper tests run

Backend Django check:

- settings, model, and framework consistency

Focused backend tests:

- real workflow rules, permissions, serializers, side effects, and contracts

Manual retest:

- catches real navigation, session, and state issues that static audits often miss

## Local Manual QA Fallback

If the deployed app is stale or the current branch has not been pushed yet, run manual QA against the local stack instead of comparing against old production code.

Backend:

```bash
cd backend
python manage.py migrate --run-syncdb --noinput --settings=talentorbit.local_qa_settings
python manage.py seed_local_qa --settings=talentorbit.local_qa_settings
python manage.py runserver localhost:8000 --settings=talentorbit.local_qa_settings --noreload
```

Frontend:

```bash
npm run dev -- --host localhost
```

Use the seeded QA accounts from `backend/jobs/management/commands/seed_local_qa.py` for repeatable login, learning, result, and growth checks.

## Workflow-to-Command Mapping

Onboarding:

```bash
python scripts/release_checks.py --focus onboarding
```

Use for:

- login
- registration
- verify email
- password reset
- 2FA
- resume parsing entry flows

Jobs and hiring:

```bash
python scripts/release_checks.py --focus jobs
```

Use for:

- jobs list/detail
- apply/withdraw/save
- company job CRUD
- talent search and search filters

Billing:

```bash
python scripts/release_checks.py --focus billing
```

Use for:

- plans
- checkout
- customer portal
- Stripe webhook state changes

Current focused coverage:

- `src/store/paymentStore.test.js`
- `src/pages/SubscriptionPlans.test.jsx`
- `backend/tests/test_payments.py`

Growth:

```bash
python scripts/release_checks.py --focus growth
```

Use for:

- `/company/sponsored`
- `/company/crm`
- `/company/analytics`
- sponsored campaign totals and load failures
- CRM stage and candidate rendering contracts
- company-only growth endpoint boundaries

Current focused coverage:

- `src/store/paymentStore.growth.test.js`
- `src/pages/SponsoredPosts.test.jsx`
- `src/pages/CRMPipeline.test.jsx`
- `src/pages/CompanyAnalytics.test.jsx`
- `backend/tests/test_growth_workflow.py`

Messaging:

```bash
python scripts/release_checks.py --focus messaging
```

Use for:

- thread creation
- inbox
- unread counts
- websocket/realtime delivery

Admin:

```bash
python scripts/release_checks.py --focus admin
```

Use for:

- admin stats
- user moderation
- audit/compliance actions
- GDPR/team/policy flows

Developer:

```bash
python scripts/release_checks.py --focus developer
```

Use for:

- API keys
- webhooks
- OAuth apps
- delivery logs and limits

AI and intelligence:

```bash
python scripts/release_checks.py --focus ai
```

Use for:

- public and authenticated resume parsing contracts
- company-only AI job writer and interview scheduler routes
- company analytics overview permission boundaries
- admin platform analytics permission boundaries

Current focused coverage:

- `backend/tests/test_resume_parsing_contract.py`
- `backend/tests/test_ai_workflow.py`

Learning and assessments:

```bash
python scripts/release_checks.py --focus learning
```

Use for:

- course enrollment and lesson progression
- course progress overview and continue-learning state
- `?tab=certificates` restoration and continue-learning routes
- assessment attempt loading and answer submission by attempt id
- learner result detail and assessment history links
- company assessment invitation workflows

Current focused coverage:

- `src/pages/MyLearning.test.jsx`
- `src/pages/AssessmentPlayer.test.jsx`
- `src/pages/AssessmentResults.test.jsx`
- `src/pages/MyAssessments.test.jsx`
- `backend/tests/test_learning_workflow.py`

## Manual QA Template

When a bug is reported, capture it in this shape before touching code:

- Workflow:
- Actor:
- Frontend route:
- Backend endpoint:
- Expected result:
- Actual result:
- Repro steps:
- Existing automated coverage:
- Focus command:

Example:

- Workflow: onboarding
- Actor: anonymous talent
- Frontend route: `/auth`
- Backend endpoint: `/api/v1/auth/login/`
- Expected result: user receives tokens and is redirected to `/user`
- Actual result: login spinner ends but redirect fails or token refresh later breaks
- Repro steps: enter credentials, submit, refresh page, observe logout
- Existing automated coverage: `src/store/authStore.test.js`, `src/components/ProtectedRoute.test.jsx`, `backend/tests/test_auth_security.py`
- Focus command: `python scripts/release_checks.py --focus onboarding`

## Done Criteria

A fix is not done until all of these are true:

- The original bug is reproducible before the change.
- A narrow automated test protects the path.
- The matching focused check group passes.
- Manual retest confirms the user-visible behavior.
- The change does not quietly widen scope into unrelated cleanup.

## Escalation Rules

Run `--focus full` only when:

- the change touched shared auth/session plumbing
- the change touched `src/services/api.js`
- the change touched root settings/bootstrap files
- the change touched common middleware or signals
- multiple workflows were intentionally affected

## Known Testing Gotchas

- SQLite test runs do not support PostgreSQL search-vector SQL directly.
- Celery is often eager in tests, so some timing issues may still need manual verification.
- Realtime behavior is partially simulated in tests; production websocket regressions may still require manual flow checks.
- Some frontend files still have encoding corruption in comments or labels. Do not mistake that for test failure output.

## Documentation Rule

If a workflow gets a new focused test cluster or a new check group, update this file and `docs/USE_CASE_REPAIR_PLAN.md` in the same change so future sessions inherit the same testing model.





