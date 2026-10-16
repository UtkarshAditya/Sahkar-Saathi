# The public entry point: Caddy serving the React build and proxying /api and /admin to
# Django. Stage 1 builds the front end against the real API (no mocks).
FROM node:20-alpine AS frontend
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
ARG VITE_USE_MOCKS=false
ARG VITE_REGIONAL_LANGUAGE_CODE=ta
ARG VITE_REGIONAL_LANGUAGE_LABEL=தமிழ்
ENV VITE_USE_MOCKS=$VITE_USE_MOCKS \
    VITE_REGIONAL_LANGUAGE_CODE=$VITE_REGIONAL_LANGUAGE_CODE \
    VITE_REGIONAL_LANGUAGE_LABEL=$VITE_REGIONAL_LANGUAGE_LABEL
# Type-checks the app against the frozen contract (contract-check.ts), then builds.
RUN npm run build

FROM caddy:2.8.4-alpine
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=frontend /app/dist /srv/frontend
# Caddy's admin API on 127.0.0.1:2019 (inside the container only) doubles as a health check.
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
    CMD wget -q --spider http://127.0.0.1:2019/config/ || exit 1
