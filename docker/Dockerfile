# syntax=docker/dockerfile:1
# Shared base image for API and worker services.
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependencies (cached layer — invalidated only when deps change)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy application code
COPY app/ app/
COPY ml/ ml/
COPY alembic/ alembic/
COPY alembic.ini ./

# ---------------------------------------------------------------------------
# API target
# ---------------------------------------------------------------------------
FROM base AS api
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ---------------------------------------------------------------------------
# Worker target
# ---------------------------------------------------------------------------
FROM base AS worker
CMD ["uv", "run", "python", "-m", "app.workers"]
