# Deployment Runbook — TalentOrbit

This runbook lists repeatable steps and commands for deploying, verifying, and rolling back TalentOrbit in production. It assumes a Kubernetes cluster, `kubectl` access, and `helm` CLI configured for the target cluster.

## Quick deploy (production)

```bash
# set values file and secrets in environment
helm upgrade --install talentorbit infra/helm/talentorbit \
  -f infra/helm/talentorbit/values-production.yaml \
  --namespace talentorbit --create-namespace \
  --set secrets.secretKey="$SECRET_KEY" \
  --set secrets.databaseUrl="$DATABASE_URL" \
  --set secrets.stripeSecretKey="$STRIPE_SECRET_KEY"
```

## Pre-deploy checklist
- Run `helm lint infra/helm/talentorbit`
- Ensure `values-production.yaml` is correct for the target cluster
- Validate secrets exist in the external secret store or provided via `--set`
- Confirm maintenance windows or inform on-call

## Rolling upgrade
1. Run the `helm upgrade` command above.
2. Monitor rollout:

```bash
kubectl rollout status deployment/talentorbit-api -n talentorbit
kubectl rollout status deployment/talentorbit-worker -n talentorbit
```

3. Watch logs and metrics for 10–15 minutes.

## Smoke tests (post-deploy)
- API health:

```bash
curl -fS https://api.talentorbit.com/health || echo "API unhealthy"
```

- Perform a small login + simple API call using a staging test account (via CI or manual curl).

## Rollback
To rollback to the previous Helm revision:

```bash
helm history talentorbit -n talentorbit
helm rollback talentorbit <REVISION> -n talentorbit
```

If migration incompatibilities exist, follow the DB rollback plan documented in `backend/README.md` and consult the database admin.

## Database migrations policy
- Use backward-compatible migrations when possible
- For destructive migrations, use a 2-step deploy:
  1. Deploy schema changes that are additive
  2. Backfill or migrate data
  3. Deploy code that relies on the new schema
  4. Remove legacy schema elements in a later release

## Verifications
- Prometheus: check API latency and error rate graphs
- PgBouncer: ensure pool utilization is within limits
- Celery: ensure worker count and queue depth are healthy
- Sentry: confirm no new fatal errors

## Emergency procedures
- If API is dead: scale down problematic pods or rollback via Helm
- If DB is unreachable: cut traffic via Ingress rules and restore DB access
- If Celery backlog grows: scale workers, restart workers, and investigate long-running tasks

## Post-deploy
- Record release revision and notes in changelog
- Run smoke tests and functional checks
- Observe monitoring/alerts for 1–2 hours


For any complex rollbacks or data recovery, contact `infra@talentorbit.com` and follow the incident response plan.
