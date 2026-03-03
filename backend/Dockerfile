###############################################################################
# TalentOrbit Backend — Multi-Stage Production Dockerfile
#
# Stages:
#   1. base     — Python runtime + system dependencies
#   2. builder  — Install Python packages into a virtualenv
#   3. prod     — Lean production image with only runtime artifacts
#
# Usage:
#   docker build -t talentorbit-api .
#   docker run -p 8000:8000 --env-file .env talentorbit-api
#
# This image supports multiple entrypoints via the CMD override:
#   API server:   (default) daphne
#   Celery worker: celery -A talentorbit worker ...
#   Celery beat:   celery -A talentorbit beat ...
###############################################################################

# ── Stage 1: Base ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS base

# Prevent Python from writing .pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Ensure pip doesn't cache packages (smaller image)
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System dependencies required at runtime:
#   - libpq5: PostgreSQL client library (psycopg)
#   - libmagic1: MIME type detection for file uploads
#   - curl: Health check probes
#   - tini: PID 1 init process (proper signal handling)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        libmagic1 \
        curl \
        tini \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd --gid 1000 talentorbit \
    && useradd --uid 1000 --gid talentorbit --shell /bin/bash --create-home talentorbit

WORKDIR /app


# ── Stage 2: Builder ──────────────────────────────────────────────────────────
FROM base AS builder

# Build dependencies (not needed at runtime)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtualenv so we can copy it cleanly to the prod stage
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies (cached layer — only rebuilt when requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install gunicorn for HTTP (daphne handles ASGI/WebSocket)
RUN pip install --no-cache-dir gunicorn[gthread]==22.0.0


# ── Stage 3: Production ──────────────────────────────────────────────────────
FROM base AS prod

# Copy the virtualenv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application source
COPY --chown=talentorbit:talentorbit . /app/

# Copy entrypoint scripts and ensure they're executable
COPY --chown=talentorbit:talentorbit scripts/ /app/scripts/
RUN chmod +x /app/scripts/*.sh

# Collect static files (WhiteNoise serves them in production)
RUN SECRET_KEY=build-placeholder \
    DEBUG=False \
    DATABASE_URL=sqlite:///tmp/build.db \
    python manage.py collectstatic --noinput 2>/dev/null || true

# Create directories that the app may need at runtime
RUN mkdir -p /app/media /app/staticfiles /app/logs \
    && chown -R talentorbit:talentorbit /app/media /app/staticfiles /app/logs

# Switch to non-root user
USER talentorbit

# Expose the application port
EXPOSE 8000

# Use tini as PID 1 (handles zombie processes + signal forwarding)
ENTRYPOINT ["tini", "--"]

# Default: run the ASGI server (Daphne) for HTTP + WebSocket
# Override CMD in docker-compose for Celery workers/beat
CMD ["/app/scripts/entrypoint.sh"]

# Health check — K8s/Render/Docker Compose can use this
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1
