#!/bin/sh
# Prepare the database and static files, then start uvicorn. Every step is idempotent,
# so restarting the container is always safe.
set -eu

# `docker compose run --rm web <command>` runs that command as is (no migrations, no server).
if [ "$#" -gt 0 ]; then
    exec "$@"
fi

python manage.py migrate --noinput
python manage.py collectstatic --noinput --verbosity 0
python manage.py ensure_superuser

# The verified document list (data/sources.csv, mounted read-only). Exits 0 even when
# rows are skipped; the summary and every skipped row are printed to the log.
if [ -n "${SOURCES_CSV:-}" ] && [ -f "$SOURCES_CSV" ]; then
    python manage.py load_sources
fi
if [ "${LOAD_SAMPLE_DOCUMENTS:-false}" = "true" ]; then
    python manage.py load_sample_documents
fi

# Load the Whisper model before serving, but never wait longer than WARM_TIMEOUT seconds
# (a missing network must not block start-up). On timeout the model loads on first use.
timeout "${WARM_TIMEOUT:-300}" python manage.py warm_models \
    || echo "warm_models: stopped after ${WARM_TIMEOUT:-300} s; the model loads on first use."

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
