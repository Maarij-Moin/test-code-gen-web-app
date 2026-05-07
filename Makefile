SHELL := /bin/sh

COMPOSE      := docker compose
COMPOSE_PROD := docker compose --file docker-compose.yml --file /dev/null
PROJECT      := autonomous-ai-testing
ENV_FILE     := .env

# ── Detect OS for open-browser command ────────────────────────────────────────
UNAME := $(shell uname -s 2>/dev/null || echo Windows)

.PHONY: help env build up up-prod down restart logs ps health \
        migrate backend-shell worker-shell flower-shell \
        clean clean-all pull push ecr-login \
        dev dev-backend dev-frontend lint test

# ── Help ──────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  Autonomous AI Testing Platform — Makefile"
	@echo ""
	@echo "  Development:"
	@echo "    make env             Create .env from .env.example if missing"
	@echo "    make up              Start full stack with hot-reload (dev override)"
	@echo "    make dev-backend     Run FastAPI with --reload on host (no Docker)"
	@echo "    make dev-frontend    Run Vite dev server on host (no Docker)"
	@echo ""
	@echo "  Production:"
	@echo "    make up-prod         Start production stack (no override file)"
	@echo "    make build           Build backend + frontend images"
	@echo "    make down            Stop all containers"
	@echo "    make restart         down + up"
	@echo ""
	@echo "  Operations:"
	@echo "    make logs            Follow all service logs"
	@echo "    make ps              Show container status"
	@echo "    make health          Docker health summary"
	@echo "    make migrate         Run Alembic migrations (inside backend container)"
	@echo "    make backend-shell   Open shell in backend container"
	@echo "    make worker-shell    Open shell in celery_worker container"
	@echo "    make flower-shell    Open shell in flower container"
	@echo "    make lint            Ruff + tsc type-check"
	@echo "    make test            pytest in backend container"
	@echo ""
	@echo "  Cleanup:"
	@echo "    make clean           Stop and remove containers"
	@echo "    make clean-all       Stop + remove containers + volumes (DESTRUCTIVE)"
	@echo ""
	@echo "  AWS ECR:"
	@echo "    make ecr-login       Authenticate Docker to ECR"
	@echo "    make push            Build and push images to ECR"
	@echo ""

# ── Environment setup ─────────────────────────────────────────────────────────
env:
	@test -f $(ENV_FILE) || (cp .env.example $(ENV_FILE) && echo "Created $(ENV_FILE) from .env.example — fill in secrets before deploying.")
	@test -f $(ENV_FILE) && echo "Using $(ENV_FILE)."

# ── Build ─────────────────────────────────────────────────────────────────────
build: env
	$(COMPOSE) --env-file $(ENV_FILE) build --parallel

# ── Development (auto-loads docker-compose.override.yml) ──────────────────────
up: env
	$(COMPOSE) --env-file $(ENV_FILE) up -d --build
	@echo ""
	@echo "  Stack is up."
	@echo "  Frontend  → http://localhost:$${FRONTEND_PORT:-8080}"
	@echo "  Backend   → http://localhost:$${BACKEND_PORT:-8000}/docs"
	@echo "  Flower    → http://localhost:$${FLOWER_PORT:-5555}/flower"
	@echo "  ChromaDB  → http://localhost:$${CHROMADB_PORT:-8001}"
	@echo ""

# ── Production (skips override file) ──────────────────────────────────────────
up-prod: env
	$(COMPOSE) --env-file $(ENV_FILE) \
	    --file docker-compose.yml \
	    up -d --build
	@echo "Production stack started."

# ── Stop ──────────────────────────────────────────────────────────────────────
down:
	$(COMPOSE) --env-file $(ENV_FILE) down

restart: down up

# ── Logs ──────────────────────────────────────────────────────────────────────
logs:
	$(COMPOSE) --env-file $(ENV_FILE) logs -f --tail=200

logs-backend:
	$(COMPOSE) --env-file $(ENV_FILE) logs -f --tail=200 backend

logs-worker:
	$(COMPOSE) --env-file $(ENV_FILE) logs -f --tail=200 celery_worker

# ── Status ────────────────────────────────────────────────────────────────────
ps:
	$(COMPOSE) --env-file $(ENV_FILE) ps

health:
	@docker ps --filter "name=ai-test-" \
	    --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# ── Database migrations ───────────────────────────────────────────────────────
migrate:
	$(COMPOSE) --env-file $(ENV_FILE) exec backend alembic upgrade head

migrate-down:
	$(COMPOSE) --env-file $(ENV_FILE) exec backend alembic downgrade -1

migrate-history:
	$(COMPOSE) --env-file $(ENV_FILE) exec backend alembic history

# ── Shells ────────────────────────────────────────────────────────────────────
backend-shell:
	$(COMPOSE) --env-file $(ENV_FILE) exec backend sh

worker-shell:
	$(COMPOSE) --env-file $(ENV_FILE) exec celery_worker sh

flower-shell:
	$(COMPOSE) --env-file $(ENV_FILE) exec flower sh

# ── Quality ───────────────────────────────────────────────────────────────────
lint:
	$(COMPOSE) --env-file $(ENV_FILE) exec backend ruff check app
	cd frontend && node node_modules/typescript/bin/tsc --noEmit

test:
	$(COMPOSE) --env-file $(ENV_FILE) exec backend pytest tests/ -q --tb=short

# ── Host-only dev (no Docker for app code) ───────────────────────────────────
dev-backend:
	cd backend && uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd frontend && pnpm dev

# ── Cleanup ───────────────────────────────────────────────────────────────────
clean:
	$(COMPOSE) --env-file $(ENV_FILE) down --remove-orphans

clean-all:
	@echo "WARNING: This will delete ALL volumes (database, repos, embeddings)."
	@read -r -p "Type 'yes' to confirm: " confirm; \
	    [ "$$confirm" = "yes" ] && \
	    $(COMPOSE) --env-file $(ENV_FILE) down -v --remove-orphans || \
	    echo "Aborted."

# ── AWS ECR ───────────────────────────────────────────────────────────────────
ecr-login:
	aws ecr get-login-password --region "$${AWS_REGION}" \
	    | docker login --username AWS --password-stdin \
	      "$${AWS_ACCOUNT_ID}.dkr.ecr.$${AWS_REGION}.amazonaws.com"

pull:
	$(COMPOSE) --env-file $(ENV_FILE) pull

push: ecr-login build
	docker tag autonomous-ai-testing/backend:$${IMAGE_TAG:-latest} \
	    "$${AWS_ACCOUNT_ID}.dkr.ecr.$${AWS_REGION}.amazonaws.com/$${ECR_BACKEND_REPOSITORY}:$${IMAGE_TAG:-latest}"
	docker tag autonomous-ai-testing/frontend:$${IMAGE_TAG:-latest} \
	    "$${AWS_ACCOUNT_ID}.dkr.ecr.$${AWS_REGION}.amazonaws.com/$${ECR_FRONTEND_REPOSITORY}:$${IMAGE_TAG:-latest}"
	docker push "$${AWS_ACCOUNT_ID}.dkr.ecr.$${AWS_REGION}.amazonaws.com/$${ECR_BACKEND_REPOSITORY}:$${IMAGE_TAG:-latest}"
	docker push "$${AWS_ACCOUNT_ID}.dkr.ecr.$${AWS_REGION}.amazonaws.com/$${ECR_FRONTEND_REPOSITORY}:$${IMAGE_TAG:-latest}"
