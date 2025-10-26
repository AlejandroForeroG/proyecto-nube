#!/usr/bin/env sh
set -eu


: "${WORKERS:=$((2 * $(getconf _NPROCESSORS_ONLN) + 1))}"
: "${TIMEOUT:=60}"
: "${KEEPALIVE:=15}"
: "${GRACEFUL_TIMEOUT:=30}"
: "${FORWARDED_ALLOW_IPS:=*}"

export FORWARDED_ALLOW_IPS

exec gunicorn \
  -k uvicorn.workers.UvicornWorker \
  --workers "$WORKERS" \
  --bind "0.0.0.0:8000" \
  --timeout "$TIMEOUT" \
  --graceful-timeout "$GRACEFUL_TIMEOUT" \
  --keep-alive "$KEEPALIVE" \
  --worker-tmp-dir "/dev/shm" \
  --access-logfile "-" \
  --log-level "info" \
  app.main:app
