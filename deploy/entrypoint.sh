#!/bin/sh
set -eu

echo "Applying database migrations..."
alembic upgrade head

echo "Seeding the canonical company universe..."
python scripts/seed_companies.py

echo "Starting Enigma API..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "${APP_WORKERS:-2}" \
    --proxy-headers \
    --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-127.0.0.1}"
