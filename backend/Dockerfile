# =============================================================================
# Backend Dockerfile — Autonomous AI Testing Platform
# =============================================================================
# Single-stage production build. Simple and reliable.
# =============================================================================

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System dependencies (git for GitPython, curl for healthcheck, libpq for asyncpg)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# Copy application source
COPY . .

# Create non-root user and directories
RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /app/repo /app/chroma_polyglot_storage /app/logs /app/auto_tests \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
