# TalentOrbit — Full Platform Overview

Welcome to TalentOrbit! This is a comprehensive, top-level README for a modern, enterprise-grade HR-tech SaaS platform. TalentOrbit is designed for scale, reliability, and rapid innovation—making it suitable for startups and large organizations alike. This document explains everything: architecture, services, technologies, deployment, and how the platform works end-to-end.

---

## Table of Contents
1. [Project Vision](#project-vision)
## TalentOrbit — Consolidated Platform README

This single README consolidates the Frontend, Backend, and Infra operational guides into one central document. It is intended to be the primary entry point for developers, DevOps, product, and new contributors.

Table of contents
- Project vision
- Quick start (local)
- Frontend
- Backend
- Infrastructure & Helm
- Deployment runbook
- Runbooks & incident response
- CI / Developer workflows
- Contributing & code of conduct
- Contact

---

### Project Vision
TalentOrbit is an HR-tech SaaS platform focused on recruitment, talent management, and analytics. It is cloud-native, designed for scalability, resilience, and rapid product iteration.

---

### Quick start (local)
1. Clone the repo:

```bash
git clone <repo>
cd TO
```

2. Frontend (dev):

```bash
cd src
npm install
npm run dev
```

3. Backend (dev using venv):

```bash
cd backend
python -m venv venv
# Windows
venv\\Scripts\\activate
# Mac/Linux
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

4. Infra: For local development, use `docker-compose` (see `backend/Dockerfile.dev` and top-level `docker-compose.yml`). For production, see the Helm section below.

---

### Frontend
- Tech: React + Vite, Zustand, Zod, dompurify, @axe-core/react, Sentry, PostHog
- Key files: `src/pages`, `src/components`, `src/utils/schemas.js` (Zod schemas)
- Scripts: `dev`, `build`, `preview`, `lint`, `format`, `test`
- Env: `VITE_API_URL`, `VITE_SENTRY_DSN`, `VITE_POSTHOG_KEY`
- Deploy: Vercel, S3 + Cloudflare, or container + CDN

Notes:
- Keep Zod schemas in sync with backend validation.
- Use `@axe-core/react` during development for accessibility checks.

---

### Backend
- Tech: Django 6 (ASGI/Daphne), Django REST Framework, Celery, Celery Beat, PgBouncer
- Key apps: `accounts`, `jobs`, `messaging`, `compliance`, `assessments`, `intelligence`, etc.
- Auth: JWT (SimpleJWT), optional 2FA
- Database: Postgres (Neon in production), SQLite for local dev

Run locally:

```bash
cd backend
python -m venv venv
venv\\Scripts\\activate  # or source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Best practices:
- Avoid destructive DB migrations in a single release; use a 2-step migration process.
- Use `--max-tasks-per-child` for Celery workers to mitigate memory leaks.

---

### Infrastructure & Helm
- Kubernetes orchestrates API, worker, beat, and PgBouncer.
- Helm chart: `infra/helm/talentorbit` with `values-production.yaml` for production overrides.
- Key features: HPA, PodDisruptionBudget, NetworkPolicy, ServiceMonitor, Ingress (nginx) with cert-manager, PgBouncer, ExternalSecrets support.

Quick install (production):

```bash
helm upgrade --install talentorbit infra/helm/talentorbit \
	-f infra/helm/talentorbit/values-production.yaml \
	--namespace talentorbit --create-namespace \
	--set secrets.secretKey="$SECRET_KEY" \
	--set secrets.databaseUrl="$DATABASE_URL" \
	--set secrets.stripeSecretKey="$STRIPE_SECRET_KEY"
```

Recommendations:
- Use ExternalSecrets operator for production secrets.
- Tune PgBouncer pool sizes to match DB plan.

---

### Deployment runbook (summary)
- Pre-deploy: `helm lint`, verify `values-production.yaml`, ensure secrets available, notify on-call.
- Deploy: run Helm upgrade and monitor rollouts:

```bash
kubectl rollout status deployment/talentorbit-api -n talentorbit
kubectl rollout status deployment/talentorbit-worker -n talentorbit
```

- Smoke tests: `curl https://api.talentorbit.com/health` and a simple auth flow.
- Rollback: `helm history talentorbit -n talentorbit` then `helm rollback talentorbit <REVISION> -n talentorbit`.

---

### Runbooks & incident response (summary)
- API 5xx spike: check recent deploys, API logs, Sentry; consider rollback.
- Celery backlog: scale workers or restart worker deployment.
- PgBouncer exhaustion: increase pool sizes and inspect DB slow queries.

Emergency rollback checklist:
1. Pause external traffic if possible.
2. Helm rollback to previous release.
3. If DB schema incompatible, run recovery/migration steps before restoring traffic.

---

### CI / Developer workflows
- GitHub Actions CI at `.github/workflows/ci.yml` builds frontend and runs backend checks/tests.
- Branching: protect `main`, open PRs for all changes, small focused PRs preferred.
- Pre-commit: run linters and formatters before committing.

---

### Contributing & Code of Conduct
- See `CONTRIBUTING.md` for workflow and PR checklist.
- See `CODE_OF_CONDUCT.md` for community guidelines.

---

### Docs & additional resources
- `docs/DEPLOYMENT.md` — detailed deployment runbook and smoke tests
- `infra/helm/talentorbit/` — Helm templates and production values
- `backend/README.md`, `src/README.md`, `infra/helm/talentorbit/README.md` — legacy component READMEs have been consolidated into this file. Use this README as the single source of truth.

---

Contact
- infra@talentorbit.com — Infra & production issues
- Open an issue in the repo for feature requests or bugs

---

This consolidated README is intended to be the canonical entry point for the project. If you'd like, I can also generate visual diagrams (PlantUML) and place them under `docs/diagrams/`.
