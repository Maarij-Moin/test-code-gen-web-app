# Autonomous AI Testing Platform — Deployment Guide

## Architecture overview

```
Browser
  │
  ▼
┌──────────────────────────────────────────┐
│  nginx (frontend:80 / host:8080)         │
│  • Serves React SPA (static assets)      │
│  • Proxy /api/* → backend:8000/          │
│  • Proxy /webhooks/* → backend:8000/…    │
│  • WebSocket /ws → backend:8000/ws       │
└──────────────────────────────────────────┘
  │                    │
  ▼                    ▼
FastAPI (backend:8000)     Celery Workers
  │  ─────────────── ──────── ─────────────
  ├─ PostgreSQL (postgres:5432)
  ├─ Redis       (redis:6379)
  └─ ChromaDB    (chromadb:8000 / host:8001)

Celery Beat  → periodic maintenance tasks
Flower       → Celery monitoring UI (host:5555/flower)
```

## Quick start (development)

```bash
# 1. Create environment file
cp .env.example .env
# Edit .env — at minimum set JWT_SECRET_KEY and API_KEY

# 2. Start the stack (auto-merges docker-compose.override.yml)
make up

# 3. Run database migrations
make migrate

# Open in browser
#   Frontend  → http://localhost:8080
#   API docs  → http://localhost:8000/docs
#   Flower    → http://localhost:5555/flower
```

## Production deployment

```bash
# Skip the dev override file
make up-prod

# Or manually:
docker compose --file docker-compose.yml up -d --build
```

## Services

| Service | Image | Host port | Purpose |
|---|---|---|---|
| `frontend` | `nginx:1.27-alpine` | 8080 | React SPA + API proxy |
| `backend` | custom (Python 3.11) | 8000 | FastAPI + REST + WS |
| `celery_worker` | same as backend | — | Async job queue |
| `celery_beat` | same as backend | — | Periodic scheduler |
| `flower` | same as backend | 5555 | Celery monitoring |
| `postgres` | `postgres:16-alpine` | 5432 | Relational DB |
| `redis` | `redis:7-alpine` | 6379 | Broker + cache |
| `chromadb` | `ghcr.io/chroma-core/chroma:0.5.23` | 8001 | Vector DB |

## Environment variables

See `.env.example` for a fully annotated list. Critical ones:

| Variable | Description |
|---|---|
| `JWT_SECRET_KEY` | `openssl rand -hex 32` |
| `API_KEY` | `openssl rand -hex 32` |
| `GITHUB_WEBHOOK_SECRET` | Must match GitHub webhook config |
| `LLM_PROVIDER` | `mock` / `openai` / `azure` / `ollama` |
| `OPENAI_API_KEY` | Required when `LLM_PROVIDER=openai` or `azure` |

## LLM configuration

### OpenAI
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

### Azure OpenAI
```env
LLM_PROVIDER=azure
OPENAI_API_KEY=<your-azure-key>
OPENAI_BASE_URL=https://<resource>.openai.azure.com
AZURE_API_VERSION=2024-05-01-preview
OPENAI_MODEL=gpt-4o
```

### Local Ollama
```env
LLM_PROVIDER=ollama
OPENAI_BASE_URL=http://host.docker.internal:11434/v1
OPENAI_MODEL=llama3
```

### Mock (CI / no API key)
```env
LLM_PROVIDER=mock
```

## GitHub Webhook setup

1. Go to your repository → **Settings → Webhooks → Add webhook**
2. Payload URL: `https://<your-domain>/webhooks/github`
3. Content type: `application/json`
4. Secret: same value as `GITHUB_WEBHOOK_SECRET` in `.env`
5. Events: ☑ Pushes, ☑ Pull requests
6. Verify health: `GET /webhooks/health`

## Volume management

| Volume | Stores |
|---|---|
| `ai-test-postgres-data` | All relational data (jobs, users, events) |
| `ai-test-redis-data` | Celery task queue + AOF log |
| `ai-test-chroma-server-data` | ChromaDB vector store (server mode) |
| `ai-test-chroma-embed-data` | ChromaDB embedded mode cache |
| `ai-test-repo-data` | Cloned Git repositories |
| `ai-test-auto-tests` | LLM-generated test files |
| `ai-test-backend-logs` | Application logs |

## Makefile targets

```
make env           Create .env from .env.example
make up            Start dev stack (hot-reload)
make up-prod       Start production stack
make down          Stop all containers
make restart       down + up
make logs          Follow all logs
make logs-backend  Follow backend logs only
make migrate       Run Alembic migrations
make test          pytest in backend container
make lint          ruff + tsc
make health        Container health table
make clean         Remove containers
make clean-all     Remove containers + volumes (DESTRUCTIVE)
make push          Build + push images to AWS ECR
```

## Health checks

All containers expose health checks to Docker:

| Container | Endpoint / command |
|---|---|
| backend | `GET /health` |
| frontend | `GET /health` (nginx stub) |
| celery_worker | `celery inspect ping` |
| postgres | `pg_isready` |
| redis | `redis-cli ping` |
| chromadb | `/api/v2/heartbeat` |

## Security notes

- JWT tokens expire after `JWT_EXPIRE_MINUTES` (default 60 min)
- GitHub webhooks use HMAC-SHA256 constant-time signature verification
- Replay protection via `X-GitHub-Delivery` uniqueness constraint
- nginx forwards `X-API-Key` header on all `/api/*` requests
- All containers run as non-root users
- The internal `app_network` bridge (172.20.0.0/16) isolates services
- No service other than `backend` is reachable from `celery_worker` or `celery_beat`

## Scaling workers

```bash
# Run 4 Celery worker replicas
docker compose --env-file .env up -d --scale celery_worker=4
```

## AWS ECR push

```bash
# Fill AWS_ACCOUNT_ID, AWS_REGION, ECR_*_REPOSITORY in .env
make push
```
