# ---------- builder stage ----------
FROM python:3.12-slim AS builder

WORKDIR /build
COPY pyproject.toml ./

RUN pip install --no-cache-dir \
    fastapi \
    "uvicorn[standard]" \
    httpx \
    "pydantic>=2,<3" \
    pydantic-settings \
    certifi

# ---------- runtime stage ----------
FROM python:3.12-slim

ARG BUILD_DATE
ARG VERSION=0.1.0

LABEL org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.title="zoho-token-service" \
      org.opencontainers.image.description="Internal Zoho OAuth token cache with proactive refresh"

# Install curl for health checks, create non-root user.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

# Copy installed packages from builder.
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY app/ ./app/

USER appuser
EXPOSE 8000

# --workers 1 is INTENTIONAL:
# Multiple workers would each have their own _TOKEN_CACHE, causing
# N parallel Zoho refresh calls instead of one.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
