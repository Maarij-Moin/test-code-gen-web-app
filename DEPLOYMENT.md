# Autonomous AI Testing Platform Deployment

This repository includes a production-oriented Docker setup for:

- `backend`: FastAPI API on port `8000`
- `frontend`: React static app served by nginx on port `80`
- `postgres`: PostgreSQL 16 with persistent data
- `redis`: Redis 7 for Celery broker/results
- `chromadb`: Chroma server with persistent data
- `celery_worker`: Celery worker using the backend image

## Docker Compose

1. Create your environment file:

   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and replace at minimum:

   ```bash
   JWT_SECRET_KEY=...
   API_KEY=...
   POSTGRES_PASSWORD=...
   ```

3. Build and start:

   ```bash
   docker compose --env-file .env up -d --build
   ```

4. Open the app:

   ```text
   http://localhost:8080
   ```

5. Useful commands:

   ```bash
   make ps
   make logs
   make health
   make down
   ```

The frontend calls `/api/*` on nginx. Nginx forwards those requests to `backend:8000` and injects `X-API-Key` for protected test-generation endpoints.

## Health Checks

The compose stack waits for dependency health before starting dependent services:

- Backend: `GET /health`
- Frontend: `GET /health`
- PostgreSQL: `pg_isready`
- Redis: `redis-cli ping`
- ChromaDB: `/api/v2/heartbeat`
- Celery: `celery inspect ping`

## Persistent Volumes

Named volumes are used for durable state:

- `postgres_data`: PostgreSQL data
- `redis_data`: Redis append-only data
- `repo_data`: cloned repositories
- `chroma_data`: embedded Chroma vectorstore data used by the backend
- `chroma_server_data`: Chroma server persistence
- `backend_logs`: backend logs

## AWS EC2 Deployment

1. Launch an Ubuntu 22.04 or 24.04 EC2 instance.

2. Security group:

   - Allow inbound `22` from your IP
   - Allow inbound `80` or `8080` from trusted users
   - Do not expose PostgreSQL, Redis, or ChromaDB publicly unless you have a strict reason

3. Install Docker:

   ```bash
   sudo apt-get update
   sudo apt-get install -y ca-certificates curl git make
   sudo install -m 0755 -d /etc/apt/keyrings
   curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
   echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list
   sudo apt-get update
   sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
   sudo usermod -aG docker ubuntu
   ```

4. Reconnect SSH, then deploy:

   ```bash
   git clone <your-repo-url>
   cd automated-web-app
   cp .env.example .env
   nano .env
   make up
   ```

5. Optional production edge:

   - Put an AWS Application Load Balancer or Caddy/Traefik in front for TLS.
   - Set `FRONTEND_PORT=80` in `.env` if nginx should bind directly to port 80.
   - Set `ALLOWED_ORIGINS` to your real domain.

## AWS ECS Deployment

Recommended ECS shape:

- Push `backend` and `frontend` images to Amazon ECR.
- Use Amazon RDS PostgreSQL instead of the compose PostgreSQL container.
- Use Amazon ElastiCache Redis instead of the compose Redis container.
- Use EFS volumes for `/app/repo` and `/app/chroma_polyglot_storage` if running multiple backend/worker tasks.
- Put the frontend service behind an Application Load Balancer.
- Keep backend and worker services private in the VPC.

High-level steps:

1. Create ECR repositories:

   ```bash
   aws ecr create-repository --repository-name autonomous-ai-testing-backend
   aws ecr create-repository --repository-name autonomous-ai-testing-frontend
   ```

2. Configure `.env`:

   ```bash
   AWS_ACCOUNT_ID=<account-id>
   AWS_REGION=us-east-1
   IMAGE_TAG=prod
   ECR_BACKEND_REPOSITORY=autonomous-ai-testing-backend
   ECR_FRONTEND_REPOSITORY=autonomous-ai-testing-frontend
   ```

3. Build and push:

   ```bash
   make push
   ```

4. Create ECS services:

   - Frontend task: image `frontend`, port `80`, ALB target group health path `/health`.
   - Backend task: image `backend`, port `8000`, health path `/health`.
   - Worker task: image `backend`, command:

     ```text
     celery -A app.workers.celery_app.celery_app worker --loglevel=info --concurrency=2
     ```

5. Set ECS environment variables:

   ```text
   DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@RDS_ENDPOINT:5432/ai_test_db
   REDIS_URL=redis://ELASTICACHE_ENDPOINT:6379/0
   CELERY_BROKER_URL=redis://ELASTICACHE_ENDPOINT:6379/0
   CELERY_RESULT_BACKEND=redis://ELASTICACHE_ENDPOINT:6379/0
   CHROMA_DIR=/app/chroma_polyglot_storage
   REPO_BASE_DIR=/app/repo
   JWT_SECRET_KEY=<secret>
   API_KEY=<secret>
   ALLOWED_ORIGINS=["https://your-domain.com"]
   ```

6. Store secrets in AWS Secrets Manager or SSM Parameter Store, then reference them from ECS task definitions.

## Startup Commands

FastAPI:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers
```

Celery:

```bash
celery -A app.workers.celery_app.celery_app worker --loglevel=info --concurrency=2
```

React frontend:

```bash
pnpm run build
nginx -g "daemon off;"
```

Local development frontend:

```bash
cd frontend
pnpm install
pnpm run dev
```

## Notes

- The backend currently uses embedded Chroma persistence through `CHROMA_DIR`. The `chromadb` service is included for future HTTP-client usage and operational parity, while the backend volume remains the active vectorstore persistence path.
- Do not expose Redis, PostgreSQL, or ChromaDB directly to the public internet in production.
- Rotate `JWT_SECRET_KEY`, `API_KEY`, and database credentials before any real deployment.
