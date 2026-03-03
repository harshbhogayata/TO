#!/usr/bin/env bash
###############################################################################
# TalentOrbit — API Server Entrypoint
#
# Responsibilities:
#   1. Wait for dependent services (Postgres, Redis) to be reachable
#   2. Run database migrations (idempotent — safe to run on every start)
#   3. Launch Daphne (ASGI) for HTTP + WebSocket on port 8000
#
# In production, this runs as PID 2 under tini (PID 1).
# Signals (SIGTERM from Docker/K8s) are forwarded cleanly by tini.
###############################################################################
set -euo pipefail

echo "╔═══════════════════════════════════════════════════════════════════╗"
echo "║  TalentOrbit API Server — Starting                              ║"
echo "╚═══════════════════════════════════════════════════════════════════╝"

# ── Wait for Postgres ─────────────────────────────────────────────────────────
if [ -n "${DATABASE_URL:-}" ] || [ -n "${DB_HOST:-}" ]; then
    echo "[entrypoint] Waiting for PostgreSQL..."
    /app/scripts/wait-for-service.sh "${DB_HOST:-postgres}" "${DB_PORT:-5432}" 30
fi

# ── Wait for Redis ────────────────────────────────────────────────────────────
if [ -n "${UPSTASH_REDIS_URL:-}" ] || [ -n "${REDIS_HOST:-}" ]; then
    REDIS_HOST_PARSED="${REDIS_HOST:-localhost}"
    REDIS_PORT_PARSED="${REDIS_PORT:-6379}"
    # Extract host:port from URL if REDIS_HOST not explicitly set
    if [ -z "${REDIS_HOST:-}" ] && [ -n "${UPSTASH_REDIS_URL:-}" ]; then
        echo "[entrypoint] Redis URL configured — skipping TCP wait (Upstash uses TLS)"
    else
        echo "[entrypoint] Waiting for Redis..."
        /app/scripts/wait-for-service.sh "$REDIS_HOST_PARSED" "$REDIS_PORT_PARSED" 15
    fi
fi

# ── Run migrations ────────────────────────────────────────────────────────────
echo "[entrypoint] Applying database migrations..."
python manage.py migrate --noinput

echo "[entrypoint] Migrations complete."

# ── Determine server configuration ───────────────────────────────────────────
WORKERS="${GUNICORN_WORKERS:-1}"
PORT="${PORT:-8000}"
BIND="0.0.0.0:${PORT}"

echo "[entrypoint] Starting Daphne on ${BIND} ..."
echo "──────────────────────────────────────────────────────────────────────"

# Daphne handles both HTTP and WebSocket (ASGI)
# --ping-interval / --ping-timeout: WebSocket keepalive
# --proxy-headers: Trust X-Forwarded-For from Render/Nginx/Cloudflare
# --application-close-timeout: Grace period for in-flight requests on shutdown
exec daphne \
    --bind 0.0.0.0 \
    --port "${PORT}" \
    --proxy-headers \
    --ping-interval 25 \
    --ping-timeout 30 \
    --application-close-timeout 10 \
    --verbosity 1 \
    talentorbit.asgi:application
