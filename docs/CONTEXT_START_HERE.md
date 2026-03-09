# Context Start Here

This file is the repo context bootstrap for future work.

If a future session has limited context or has to reconstruct the project from a summary, read these files in this order:

1. `docs/CONTEXT_START_HERE.md`
2. `docs/CODEBASE_MAP.md`
3. `docs/ROUTE_POLICY_MATRIX.md`
4. `docs/TESTING_OPERATING_MODEL.md`
5. `docs/USE_CASE_REPAIR_PLAN.md`
6. `README.md`

## Current Working Model

TalentOrbit is not a small MVP anymore. It behaves like a multi-surface SaaS with these major product areas:

- Public discovery and marketing
- Talent onboarding and account security
- Job marketplace flows
- Company hiring workflows
- Billing and growth surfaces
- Messaging and notifications
- Admin and compliance tools
- Developer platform and outbound integrations
- AI-assisted workflows

The repo should be worked on by workflow, not by broad audit sweeps.

## Non-Negotiable Rules For Future Sessions

- Do not propose reducing the product to a simpler MVP unless the user explicitly asks for that.
- Treat one workflow as the unit of repair.
- Add or extend the narrowest failing automated test before broad refactors.
- Prefer focused verification via `python scripts/release_checks.py --focus ...` instead of rerunning the entire platform every time.
- Preserve existing role boundaries: `TALENT`, `COMPANY`, `ADMIN`.
- When local tests run on SQLite, guard PostgreSQL-specific behavior instead of assuming Postgres features are always available.

## Stable Entry Points

Frontend:

- Route registry: `src/App.jsx`
- Auth route guard: `src/components/ProtectedRoute.jsx`
- API client and session restore: `src/services/api.js`
- Auth state: `src/store/authStore.js`
- Login UI: `src/pages/AuthPage.jsx`

Backend:

- Root URL routing: `backend/talentorbit/urls.py`
- Settings and env behavior: `backend/talentorbit/settings.py`
- Test settings: `backend/talentorbit/test_settings.py`
- Auth endpoints: `backend/accounts/urls.py`, `backend/accounts/views.py`
- Search signal behavior: `backend/search/signals.py`
- Runtime smoke checks: `backend/scripts/runtime_smoke.py`

## Verified Baseline As Of 2026-03-09

These workflow checks currently pass end to end:

```bash
python scripts/release_checks.py --focus onboarding
python scripts/release_checks.py --focus jobs
python scripts/release_checks.py --focus billing
python scripts/release_checks.py --focus growth
python scripts/release_checks.py --focus messaging
python scripts/release_checks.py --focus admin
python scripts/release_checks.py --focus developer
python scripts/release_checks.py --focus ai
python scripts/release_checks.py --focus learning
```

That means the current verified baseline includes:

- frontend auth/session tests
- frontend billing store and checkout-page tests
- frontend growth workflow tests for `/company/sponsored`, `/company/crm`, and `/company/analytics`
- backend runtime smoke
- backend Django config check
- onboarding/auth/resume parsing tests
- jobs and search tests
- billing and Stripe lifecycle tests
- growth permissions and API contract tests
- messaging REST and realtime tests
- admin and compliance tests
- developer API key, webhook, OAuth app, and delivery-log tests
- AI resume parsing contracts and intelligence permission-boundary tests
- frontend learning tests for continue-learning resume, assessment player/result routes, and assessment history links
- backend learning course progression, result-contract, and assessment invitation workflow tests

Recent jobs workflow fixes included:

- search metadata no longer reflects raw HTML payloads back into JSON responses
- trending search results now invalidate correctly when analytics rows change
- trending search responses no longer trust stale cache when the qualifying dataset is empty

Recent billing workflow fixes included:

- `/plans` now starts real checkout instead of stopping at a TODO
- the plans page now filters and normalizes plan catalog data by audience and billing interval
- the billing store now normalizes backend billing overview data into the page contract used by `/billing`
- the billing focus group now includes frontend billing tests so this path stays protected

Recent growth workflow fixes included:

- `python scripts/release_checks.py --focus growth` now protects sponsored posts, CRM pipeline, and company analytics surfaces as one repeatable company workflow
- the growth store now normalizes sponsored campaign spend, CRM stage labels, and candidate display-name payloads into the page contract used by the frontend
- growth page loads now rethrow request failures so `/company/sponsored` and `/company/crm` can show real error states instead of silently falling back to empty UI
- sponsored campaign and CRM API endpoints now require company accounts instead of allowing any authenticated user to create or mutate growth objects
- company analytics now tolerates benchmark payloads delivered as a `results` envelope as well as raw arrays

Recent messaging workflow fixes included:

- websocket two-participant tests now drain queued presence frames without hanging or cancelling the communicator
- the messaging focus group now completes cleanly across inbox, notification, and realtime coverage

Recent admin workflow fixes included:

- test settings now force local filesystem media storage even when R2 env vars exist
- GDPR export requests now stay local and complete under eager Celery test runs instead of failing against remote object storage

Recent developer workflow fixes included:

- developer list endpoints now return raw arrays instead of inheriting global pagination envelopes
- webhook URL validation now correctly blocks private-network and metadata IP targets on create, update, and test-ping paths

Recent AI workflow fixes included:

- `python scripts/release_checks.py --focus ai` now groups resume parsing contracts with AI and analytics boundary tests
- company-only AI job writer and interview scheduler endpoints now reject talent accounts at the permission layer instead of reaching feature-config checks

Recent learning workflow fixes included:

- `python scripts/release_checks.py --focus learning` now runs dedicated frontend tests for continue-learning state, assessment attempt loading, result rendering, and assessment history links before the backend workflow suite
- course progress responses now expose `overall_progress`, `completed_lessons`, `total_lessons`, `lesson_statuses`, and `next_lesson` so the frontend can restore learner state from real API data
- learner assessment pages now load attempts and results by attempt id, handle pending grading cleanly, and build result-detail links from `attempt_id` instead of the result primary key
- assessment invitations now enforce company-only access, require company ownership of the assessment, and correctly resolve existing users through `accounts.models.User`
- course catalog/detail querysets now annotate `_module_count`, `_lesson_count`, and `_total_duration` to match the LMS model property cache contract instead of crashing course detail reads with property name collisions
- assessment result detail now accepts both legacy dict-style and list-of-dicts `skill_scores` payloads, so seeded/manual badge result pages render without `500`s

This still does not mean the full platform is green. It means nine critical workflows now have a repeatable repair and verification path.

Broader verification note:

- `python scripts/release_checks.py --focus full` still trips pre-existing frontend lint errors outside the repaired workflows, including hook-rule failures in `src/pages/ReferralProgram.jsx`.

## Local Manual QA Stack

When the deployed frontend is stale or unpushed, use the local QA stack instead of guessing from production drift:

```bash
cd backend
python manage.py migrate --run-syncdb --noinput --settings=talentorbit.local_qa_settings
python manage.py seed_local_qa --settings=talentorbit.local_qa_settings
python manage.py runserver localhost:8000 --settings=talentorbit.local_qa_settings --noreload
```

In a second terminal:

```bash
npm run dev -- --host localhost
```

Seeded manual-QA credentials:

- `alex.rivera@example.com / password123`
- `techflow@example.com / password123`
- `admin@talentorbit.io / admin123`

Local manual QA verified on 2026-03-09:

- login and session restore for talent on `/auth` -> `/user`
- continue-learning navigation from `/my-learning` into `/courses/workflow-state-restoration/lessons/keep-partial-assessment-state`
- learner result detail from `/my-assessments` into `/assessments/1/results/<attempt_id>`
- company growth surfaces on `/company/sponsored`, `/company/crm`, and `/company/analytics`

## Next Recommended Workflow Order

Use this order unless a more urgent production issue overrides it:

1. Push the current repair batch and rerun the same login, learning, and growth manual checks on the deployed environment
2. Long-tail AI output correctness and compensation behavior

Already verified in focused checks:

- `onboarding`
- `jobs`
- `billing`
- `growth`
- `messaging`
- `admin`
- `developer`
- `ai`
- `learning`

## Known Structural Risks

- `src/App.jsx` is the live route registry and is very large, so route drift is easy.
- Several frontend files contain mojibake or corrupted comments/text. Treat those as cleanup candidates, but do not mix them into unrelated bug fixes.
- Production behavior assumes external services such as Stripe, Redis, email delivery, optional OpenAI, and Firebase. Tests often run with local or eager fallbacks.
- Search and analytics code contains PostgreSQL-oriented paths. Test and local fallback paths must remain SQLite-safe.
- Real user issues may appear only in manual flow testing, especially around login/session restore, role redirects, and long-tail pages.

## When A Session Starts With "Login Is Broken"

Check these first:

1. `src/pages/AuthPage.jsx`
2. `src/services/api.js`
3. `src/store/authStore.js`
4. `src/components/ProtectedRoute.jsx`
5. `backend/accounts/views.py`
6. `backend/accounts/serializers.py`
7. `backend/accounts/urls.py`

Then run:

```bash
python scripts/release_checks.py --focus onboarding
```

If that passes but manual login still fails, the likely gap is one of:

- env/config mismatch between frontend and deployed backend
- token refresh/session restore behavior
- role redirect logic
- manual-only UI state regression not covered by the current tests

## Session Handoff Format

When ending a workflow repair session, leave these facts easy to recover:

- workflow repaired
- actor affected
- exact routes and API endpoints touched
- failing tests added or updated
- focused check command used
- manual retest result
- next likely workflow or blocker


