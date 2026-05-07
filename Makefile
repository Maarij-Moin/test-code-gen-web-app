SHELL := /bin/sh

COMPOSE := docker compose
PROJECT := autonomous-ai-testing
ENV_FILE := .env

.PHONY: help env build up down restart logs ps health backend-shell worker-shell migrate clean pull push ecr-login

help:
	@echo "Autonomous AI Testing Platform"
	@echo "Targets:"
	@echo "  make env             Create .env from .env.example if missing"
	@echo "  make build           Build backend and frontend images"
	@echo "  make up              Start the full stack"
	@echo "  make down            Stop containers"
	@echo "  make restart         Restart the stack"
	@echo "  make logs            Follow service logs"
	@echo "  make ps              Show service status"
	@echo "  make health          Run container health summary"
	@echo "  make migrate         Run Alembic migrations in backend"
	@echo "  make backend-shell   Open backend shell"
	@echo "  make worker-shell    Open celery worker shell"
	@echo "  make clean           Stop stack and remove volumes"
	@echo "  make ecr-login       Login Docker to AWS ECR"
	@echo "  make push            Build and push images to configured ECR repos"

env:
	@test -f $(ENV_FILE) || cp .env.example $(ENV_FILE)
	@echo "Using $(ENV_FILE). Edit secrets before deploying."

build: env
	$(COMPOSE) --env-file $(ENV_FILE) build

up: env
	$(COMPOSE) --env-file $(ENV_FILE) up -d --build

down:
	$(COMPOSE) --env-file $(ENV_FILE) down

restart: down up

logs:
	$(COMPOSE) --env-file $(ENV_FILE) logs -f --tail=200

ps:
	$(COMPOSE) --env-file $(ENV_FILE) ps

health:
	@docker ps --filter "name=ai-test-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

migrate:
	$(COMPOSE) --env-file $(ENV_FILE) exec backend alembic upgrade head

backend-shell:
	$(COMPOSE) --env-file $(ENV_FILE) exec backend sh

worker-shell:
	$(COMPOSE) --env-file $(ENV_FILE) exec celery_worker sh

clean:
	$(COMPOSE) --env-file $(ENV_FILE) down -v --remove-orphans

ecr-login:
	aws ecr get-login-password --region "$${AWS_REGION}" | docker login --username AWS --password-stdin "$${AWS_ACCOUNT_ID}.dkr.ecr.$${AWS_REGION}.amazonaws.com"

push: ecr-login build
	docker tag autonomous-ai-testing/backend:$${IMAGE_TAG:-latest} "$${AWS_ACCOUNT_ID}.dkr.ecr.$${AWS_REGION}.amazonaws.com/$${ECR_BACKEND_REPOSITORY}:$${IMAGE_TAG:-latest}"
	docker tag autonomous-ai-testing/frontend:$${IMAGE_TAG:-latest} "$${AWS_ACCOUNT_ID}.dkr.ecr.$${AWS_REGION}.amazonaws.com/$${ECR_FRONTEND_REPOSITORY}:$${IMAGE_TAG:-latest}"
	docker push "$${AWS_ACCOUNT_ID}.dkr.ecr.$${AWS_REGION}.amazonaws.com/$${ECR_BACKEND_REPOSITORY}:$${IMAGE_TAG:-latest}"
	docker push "$${AWS_ACCOUNT_ID}.dkr.ecr.$${AWS_REGION}.amazonaws.com/$${ECR_FRONTEND_REPOSITORY}:$${IMAGE_TAG:-latest}"
