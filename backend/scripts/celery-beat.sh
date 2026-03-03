#!/usr/bin/env bash
###############################################################################
# TalentOrbit — Celery Beat Entrypoint
#
# Runs the Celery Beat scheduler using the DatabaseScheduler.
# Periodic tasks are defined in settings.CELERY_BEAT_SCHEDULE and can also
# be managed via Django Admin → Periodic Tasks.
#
# IMPORTANT: Only ONE Beat instance should run at a time.
# Docker Compose enforces this via deploy.replicas: 1
###############################################################################
set -euo pipefail

echo "╔═══════════════════════════════════════════════════════════════════╗"
echo "║  TalentOrbit Celery Beat — Starting                             ║"
echo "╚═══════════════════════════════════════════════════════════════════╝"

# ── Wait for Redis ────────────────────────────────────────────────────────────
if [ -n "${REDIS_HOST:-}" ]; then
    echo "[celery-beat] Waiting for Redis broker..."
    /app/scripts/wait-for-service.sh "${REDIS_HOST:-redis}" "${REDIS_PORT:-6379}" 30
fi

# ── Wait for Postgres ─────────────────────────────────────────────────────────
if [ -n "${DATABASE_URL:-}" ] || [ -n "${DB_HOST:-}" ]; then
    echo "[celery-beat] Waiting for PostgreSQL..."
    /app/scripts/wait-for-service.sh "${DB_HOST:-postgres}" "${DB_PORT:-5432}" 30
fi

LOG_LEVEL="${CELERY_LOG_LEVEL:-info}"

echo "[celery-beat] Scheduler: DatabaseScheduler"
echo "──────────────────────────────────────────────────────────────────────"

# Remove stale pidfile (prevents "beat already running" errors after crash)
rm -f /tmp/celerybeat.pid

exec celery -A talentorbit beat \
    --loglevel="${LOG_LEVEL}" \
    --scheduler django_celery_beat.schedulers:DatabaseScheduler \
    --pidfile=/tmp/celerybeat.pid
