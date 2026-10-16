#!/bin/sh
# Prepare the database and static files, then start uvicorn. Every step is idempotent,
# so restarting the container is always safe.
set -eu

python manage.py migrate --noinput
python manage.py collectstatic --noinput --verbosity 0
python manage.py ensure_superuser
if [ "${LOAD_SAMPLE_DOCUMENTS:-false}" = "true" ]; then
    python manage.py load_sample_documents
fi

# Only Caddy can reach this port. --proxy-headers makes the client address and scheme
# come from Caddy's X-Forwarded-* headers.
exec uvicorn config.asgi:application \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "${WEB_CONCURRENCY:-2}" \
    --proxy-headers \
    --forwarded-allow-ips '*' \
    --no-server-header \
    --timeout-graceful-shutdown 20
