# Production image for the Zoho Token Service.
#
# Uses `uv sync --frozen` to install from pyproject.toml + uv.lock so dep
# drift is impossible (the previous hardcoded pip list got out of date
# every time a new dep was added to pyproject). CMD is wrapped with
# `opentelemetry-instrument`; when OTEL_* env vars are set by
# docker-compose, traces ship via OTLP to the observability collector.

FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv

ENV UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# ── Dependency layer — cached unless pyproject.toml / uv.lock change ──────
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# ── curl for healthchecks + non-root user ────────────────────────────────
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

# ── Application code ─────────────────────────────────────────────────────
COPY app/ ./app/

ARG BUILD_DATE
ARG VERSION=0.1.0
LABEL org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.title="zoho-token-service" \
      org.opencontainers.image.description="Internal Zoho OAuth token cache with proactive refresh"

USER appuser
EXPOSE 8000

# --workers 1 is INTENTIONAL:
# Multiple workers would each have their own _TOKEN_CACHE, causing
# N parallel Zoho refresh calls instead of one.
# opentelemetry-instrument wraps uvicorn; inert when OTEL env vars absent.
CMD ["opentelemetry-instrument", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
