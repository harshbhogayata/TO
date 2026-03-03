#!/usr/bin/env bash
###############################################################################
# TalentOrbit — Celery Worker Entrypoint
#
# Starts a Celery worker that consumes from the configured queues.
# Designed to run as a separate container/service alongside the API server.
#
# Environment variables:
#   CELERY_QUEUES     — Comma-separated queue names (default: all queues)
#   CELERY_CONCURRENCY — Worker concurrency (default: 2)
#   CELERY_LOG_LEVEL   — Log verbosity (default: info)
###############################################################################
set -euo pipefail

echo "╔═══════════════════════════════════════════════════════════════════╗"
echo "║  TalentOrbit Celery Worker — Starting                           ║"
echo "╚═══════════════════════════════════════════════════════════════════╝"

# ── Wait for Redis (broker) ───────────────────────────────────────────────────
if [ -n "${REDIS_HOST:-}" ]; then
    echo "[celery-worker] Waiting for Redis broker..."
    /app/scripts/wait-for-service.sh "${REDIS_HOST:-redis}" "${REDIS_PORT:-6379}" 30
fi

# ── Wait for Postgres (result backend uses Django ORM) ────────────────────────
if [ -n "${DATABASE_URL:-}" ] || [ -n "${DB_HOST:-}" ]; then
    echo "[celery-worker] Waiting for PostgreSQL..."
    /app/scripts/wait-for-service.sh "${DB_HOST:-postgres}" "${DB_PORT:-5432}" 30
fi

# ── Configuration ─────────────────────────────────────────────────────────────
QUEUES="${CELERY_QUEUES:-default,emails,notifications,intelligence,analytics,compliance,dlq}"
CONCURRENCY="${CELERY_CONCURRENCY:-2}"
LOG_LEVEL="${CELERY_LOG_LEVEL:-info}"
MAX_TASKS_PER_CHILD="${CELERY_MAX_TASKS_PER_CHILD:-100}"

echo "[celery-worker] Queues: ${QUEUES}"
echo "[celery-worker] Concurrency: ${CONCURRENCY}"
echo "[celery-worker] Max tasks per child: ${MAX_TASKS_PER_CHILD}"
echo "──────────────────────────────────────────────────────────────────────"

# exec replaces shell process — signals propagate correctly via tini
exec celery -A talentorbit worker \
    --loglevel="${LOG_LEVEL}" \
    --queues="${QUEUES}" \
    --concurrency="${CONCURRENCY}" \
    --max-tasks-per-child="${MAX_TASKS_PER_CHILD}" \
    --without-heartbeat \
    --without-mingle \
    --without-gossip \
    --optimization=fair
