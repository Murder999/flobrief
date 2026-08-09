#!/bin/sh
# Production entrypoint: start uvicorn.
# Alembic migrations run as Railway preDeployCommand (before container swap).
# For local Docker use (no Railway preDeployCommand), set RUN_MIGRATIONS=true.
set -e

if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
  echo "[start] Running Alembic migrations (local mode)..."
  alembic upgrade head
  echo "[start] Migrations complete."
fi

WORKERS=${WORKERS:-1}
PORT=${PORT:-8000}

echo "[start] Starting uvicorn on port $PORT with $WORKERS worker(s)..."
# No --proxy-headers/--forwarded-allow-ips here: trusting those blindly (or
# with forwarded-allow-ips="*") lets any client spoof X-Forwarded-For and
# rewrite request.client to whatever they like. request.client is left as
# the raw TCP peer (Railway's edge); app.core.rate_limiter.get_client_ip()
# does its own bounded, trusted-hop-count parsing of X-Forwarded-For instead.
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "$PORT" \
  --workers "$WORKERS"
