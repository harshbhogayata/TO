#!/usr/bin/env bash
###############################################################################
# wait-for-service.sh — TCP readiness probe
#
# Waits for a TCP port to become reachable. Used by entrypoint scripts to
# ensure dependent services (Postgres, Redis) are ready before the app starts.
#
# Usage:
#   ./wait-for-service.sh <host> <port> [timeout_seconds]
#
# Examples:
#   ./wait-for-service.sh postgres 5432 30
#   ./wait-for-service.sh redis 6379 15
###############################################################################
set -euo pipefail

HOST="${1:?Usage: wait-for-service.sh <host> <port> [timeout]}"
PORT="${2:?Usage: wait-for-service.sh <host> <port> [timeout]}"
TIMEOUT="${3:-30}"

echo "[wait-for-service] Waiting for ${HOST}:${PORT} (timeout: ${TIMEOUT}s)..."

ELAPSED=0
INTERVAL=2

while ! bash -c "echo > /dev/tcp/${HOST}/${PORT}" 2>/dev/null; do
    if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
        echo "[wait-for-service] ERROR: ${HOST}:${PORT} not reachable after ${TIMEOUT}s"
        exit 1
    fi
    echo "[wait-for-service] ${HOST}:${PORT} not ready — retrying in ${INTERVAL}s (${ELAPSED}/${TIMEOUT}s)"
    sleep "$INTERVAL"
    ELAPSED=$((ELAPSED + INTERVAL))
done

echo "[wait-for-service] ${HOST}:${PORT} is reachable."
