# =============================================================================
# Backend Dockerfile — Autonomous AI Testing Platform
# =============================================================================
#
# Multi-stage build:
#   deps    – install Python dependencies into an isolated prefix (fast layer cache)
#   runtime – minimal production image (~250 MB) with non-root user
#
# Build args
#   PYTHON_VERSION   Python base image tag        (default: 3.11-slim-bookworm)
#
# Usage
#   # Production
#   docker build -t ai-test-backend .
#
#   # Development (bind-mount source; hot-reload via uvicorn --reload)
#   docker run --rm -v $(pwd):/app -p 8000:8000 ai-test-backend \
#       uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# =============================================================================

ARG PYTHON_VERSION=3.11-slim-bookworm

# ── Stage 1: dependency installer ────────────────────────────────────────────
FROM python:${PYTHON_VERSION} AS deps

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# System libraries needed at pip-install time only
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install requirements into /install prefix (layer-cached separately)
COPY requirements.txt .
RUN pip install --upgrade pip==24.* \
    && pip install --prefix=/install -r requirements.txt

# ── Stage 2: production runtime ──────────────────────────────────────────────
FROM python:${PYTHON_VERSION} AS runtime

LABEL org.opencontainers.image.title="Autonomous AI Testing Platform — Backend" \
      org.opencontainers.image.description="FastAPI + Celery service for autonomous test generation" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Prepend the /install prefix to the Python path so packages are found
    PYTHONPATH="/install/lib/python3.11/site-packages:${PYTHONPATH}" \
    PATH="/install/bin:${PATH}"

WORKDIR /app

# Runtime-only system dependencies (git for GitPython, curl for health check)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        git \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from deps stage
COPY --from=deps /install /install

# Copy application source
COPY . .

# Create non-root user and required directories
RUN useradd --create-home --shell /usr/sbin/nologin --uid 1001 appuser \
    && mkdir -p /app/repo /app/chroma_polyglot_storage /app/logs /app/auto_tests \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

# Production default: uvicorn with 2 workers (override for dev/celery)
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
