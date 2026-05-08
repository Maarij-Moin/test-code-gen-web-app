# =============================================================================
# Frontend Dockerfile — Autonomous AI Testing Platform
# =============================================================================

FROM node:22-alpine AS build

WORKDIR /app

RUN npm install -g pnpm@9.12.3

COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .

ARG VITE_API_BASE_URL=/api
ARG VITE_API_KEY=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_API_KEY=$VITE_API_KEY

RUN pnpm run build

FROM nginx:1.27-alpine AS runtime

RUN apk add --no-cache curl

COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
