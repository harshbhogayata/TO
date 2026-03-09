# Use-Case Repair Plan

This project should be repaired by workflow, not by broad "audit count" goals.

The route surface is already large enough that generic audits will miss real breakage. The practical unit of work is one user journey at a time:

1. Reproduce the issue in the deployed app or local environment.
2. Pin the exact actor, route, API call, and broken expectation.
3. Add or extend the narrowest failing test for that journey.
4. Fix the backend or frontend code without changing adjacent product areas.
5. Run the matching focused checks from `scripts/release_checks.py`.
6. Re-test the same journey manually after deploy, or on the local QA stack when the deploy is stale.

## Priority Order

Start with flows that block trust, conversion, or daily use.

| Priority | Workflow | Why first | Focus command |
| --- | --- | --- | --- |
| P0 | Talent onboarding | If auth, verification, password reset, or resume parsing breaks, new users churn immediately. | `python scripts/release_checks.py --focus onboarding` |
| P0 | Jobs and company hiring | This is the core marketplace loop: discovery, apply, save, post, review applicants. | `python scripts/release_checks.py --focus jobs` |
| P1 | Billing and subscriptions | Broken billing creates support load and bad state mutations. | `python scripts/release_checks.py --focus billing` |
| P1 | Messaging and notifications | Daily-use workflow with hidden realtime and permission bugs. | `python scripts/release_checks.py --focus messaging` |
| P1 | Admin and compliance | High-risk surface for leakage, permissions, exports, and team access. | `python scripts/release_checks.py --focus admin` |
| P1 | Developer integrations | External-facing surface where webhook or secret handling errors become expensive fast. | `python scripts/release_checks.py --focus developer` |
| P2 | Company growth surfaces | Sponsored campaigns, CRM pipeline, and analytics pages are conversion-critical but easy to miss in audits because the frontend contract drift is subtle. | `python scripts/release_checks.py --focus growth` |
| P2 | Learning and assessments | Course progression and candidate evaluation span many stateful endpoints that fail quietly without targeted coverage. | `python scripts/release_checks.py --focus learning` |
| P2 | AI and analytics flows | Valuable, but many of these are support features rather than the marketplace core. | `python scripts/release_checks.py --focus ai` |

## What Exists Already

The repo already contains meaningful workflow coverage. Use it as the base layer instead of starting over.

| Workflow | Existing automated coverage |
| --- | --- |
| Onboarding | `backend/tests/test_auth_security.py`, `backend/tests/test_resume_parsing_contract.py`, `src/services/api.test.js`, `src/store/authStore.test.js`, `src/components/ProtectedRoute.test.jsx` |
| Jobs and hiring | `backend/jobs/tests.py`, `backend/tests/test_search.py` |
| Billing | `src/store/paymentStore.test.js`, `src/pages/SubscriptionPlans.test.jsx`, `backend/tests/test_payments.py` |
| Growth | `src/store/paymentStore.growth.test.js`, `src/pages/SponsoredPosts.test.jsx`, `src/pages/CRMPipeline.test.jsx`, `src/pages/CompanyAnalytics.test.jsx`, `backend/tests/test_growth_workflow.py` |
| Messaging | `backend/tests/test_messaging.py`, `backend/tests/test_realtime.py` |
| Admin and compliance | `backend/tests/test_admin_api.py`, `backend/compliance/tests/test_*.py` |
| Developer integrations | `backend/developer/tests/test_api_keys.py`, `backend/developer/tests/test_oauth_apps.py`, `backend/developer/tests/test_tasks.py`, `backend/developer/tests/test_webhooks.py` |
| Learning and assessments | `src/pages/MyLearning.test.jsx`, `src/pages/AssessmentPlayer.test.jsx`, `src/pages/AssessmentResults.test.jsx`, `src/pages/MyAssessments.test.jsx`, `backend/tests/test_learning_workflow.py` |
| AI and analytics flows | `backend/tests/test_resume_parsing_contract.py`, `backend/tests/test_ai_workflow.py` |

## Coverage Gaps You Should Expect

These areas still need deeper journey coverage even after the current focused groups:

- richer AI output correctness and compensation behavior
- some long-tail frontend pagination and state-restoration paths
- manual-only role redirect and deployed session restore bugs

For these areas, do not start by "cleaning code." Start by writing the smallest failing scenario that matches the bug you just reproduced.

## Session Rules

Keep each repair session narrow.

- One workflow only.
- One actor only, unless the bug is cross-role.
- One reproduction note.
- One failing test before broad refactors.
- One focused check command after the fix.

Good session example:

- Workflow: growth
- Actor: verified company
- Bug: `/company/crm` shows blank stage headers and `Unknown` candidates
- Fix: growth store normalization plus company-only endpoint enforcement
- Validation: `python scripts/release_checks.py --focus growth`

Bad session example:

- "Fix auth, jobs, profile, notifications, and random UI issues"

That will produce noise, not progress.

## Local QA Fallback

If the deployed app is stale, not yet pushed, or clearly out of sync with the branch under repair, run the manual journey against the local QA stack instead:

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

That keeps manual QA attached to the code you just changed instead of a stale deploy.

## Definition Of Done

A use case is only considered repaired when all of the following are true:

- The bug has a reproducible before/after note.
- At least one automated test now protects the path.
- The focused workflow checks pass.
- The same path is manually verified in the deployed environment, or on the local QA stack when the deploy is stale.
- Any follow-on bugs discovered during retest are logged separately, not folded into the same fix blindly.

## Deployment Note

Do not collapse the product into a smaller MVP if that is not your goal. Keep the current split deployment, but ship fixes in smaller workflow batches with focused verification. That reduces risk without throwing away the effort already invested in the full platform.





