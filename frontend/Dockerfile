# =============================================================================
# Frontend Dockerfile — Autonomous AI Testing Platform
# =============================================================================
#
# Multi-stage build:
#   build   – pnpm install + vite build (Node 22 Alpine)
#   runtime – nginx:alpine serving static assets (< 30 MB)
#
# Build args (injected by docker compose; baked into the Vite bundle)
#   VITE_API_BASE_URL    Backend URL seen by the browser  (default: /api)
#   VITE_API_KEY         Optional static API key           (default: empty)
#
# The nginx config uses envsubst at container start (via docker-entrypoint)
# so the API_KEY env var is substituted into nginx.conf at runtime.
# =============================================================================

# ── Stage 1: build ───────────────────────────────────────────────────────────
FROM node:22-alpine AS build

WORKDIR /app

# Install pnpm once (cached layer)
RUN npm install -g pnpm@9.12.3

# Install dependencies (cached unless lock file changes)
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# Copy source and compile
COPY . .

# Build-time Vite env vars (baked into the JS bundle at build time)
ARG VITE_API_BASE_URL=/api
ARG VITE_API_KEY=
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_API_KEY=${VITE_API_KEY}

RUN pnpm run build

# ── Stage 2: nginx runtime ───────────────────────────────────────────────────
FROM nginx:1.27-alpine AS runtime

LABEL org.opencontainers.image.title="Autonomous AI Testing Platform — Frontend" \
      org.opencontainers.image.description="React + Vite SPA served via nginx with API proxy"

# curl for healthcheck
RUN apk add --no-cache curl

# nginx config is a template so envsubst can inject $API_KEY at runtime
COPY nginx.conf /etc/nginx/templates/default.conf.template

# Static assets from build stage
COPY --from=build /app/dist /usr/share/nginx/html

# nginx runs as non-root (nginx user, uid 101, created by the base image)
RUN chown -R nginx:nginx /usr/share/nginx/html \
    && chown -R nginx:nginx /var/cache/nginx \
    && touch /var/run/nginx.pid \
    && chown nginx:nginx /var/run/nginx.pid

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://127.0.0.1/health || exit 1

# docker-entrypoint.sh from the base image runs envsubst on templates/ then starts nginx
CMD ["/docker-entrypoint.sh", "nginx", "-g", "daemon off;"]
