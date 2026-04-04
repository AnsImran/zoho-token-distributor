FROM python:3.12-slim

WORKDIR /app

# Install dependencies (no cache to keep image small).
RUN pip install --no-cache-dir \
    fastapi \
    "uvicorn[standard]" \
    httpx \
    "pydantic>=2,<3" \
    python-dotenv \
    certifi

COPY app/ ./app/

EXPOSE 8000

# --workers 1 is INTENTIONAL:
# Multiple workers would each have their own _TOKEN_CACHE, causing
# N parallel Zoho refresh calls instead of one.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
