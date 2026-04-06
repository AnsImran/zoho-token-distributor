# Zoho Token Service

Internal microservice that caches Zoho OAuth access tokens and proactively refreshes them before expiry. Other services call a single endpoint to get a valid token — no need to manage refresh logic themselves.

## How It Works

1. On startup, the service fetches an access token from Zoho using the OAuth2 `refresh_token` grat.
2. The token is held in an in-memory cache and served instantly via `GET /token`.
3. A background loop monitors expiry and refreshes the token **2 minutes before it expires** (tokens last 1 hour).
4. If a refresh fails, the service retries every 15 seconds until it succeeds.

## API

| Endpoint | Method | Description |
|---|---|---|
| `/token` | GET | Returns the cached access token. **503** if the token isn't available yet. |
| `/health` | GET | Health probe for Docker / load balancers. Always **200**. |

### `GET /token` Response

```json
{
  "access_token": "1000.xxxx...",
  "created_at": "2026-04-04T12:00:00+00:00",
  "expires_at": "2026-04-04T13:00:00+00:00",
  "token_type": "Zoho-oauthtoken"
}
```

### `GET /health` Response

```json
{
  "status": "ok",
  "token_cached": true,
  "expires_at": "2026-04-04T13:00:00+00:00"
}
```

## Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager

### Environment Variables

Create a `.env` file in the project root:

```env
ZOHO_REFRESH_TOKEN=your_refresh_token
ZOHO_CLIENT_ID=your_client_id
ZOHO_CLIENT_SECRET=your_client_secret
# Optional — defaults to https://accounts.zoho.com/oauth/v2/token
# ZOHO_ACCOUNTS_TOKEN_URL=https://accounts.zoho.com/oauth/v2/token
```

### Local Development

```bash
uv sync --frozen
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

### Running Tests

```bash
uv sync --frozen
uv run pytest tests/ -q
```

## Docker

### Build and Run

```bash
docker compose up --build -d
```

The service binds to `127.0.0.1:8000` (host-only, not exposed to the internet). A health check pings `/health` every 30 seconds.

### Why `--workers 1`?

The token cache is an in-memory Python dict. Multiple Uvicorn workers would each maintain their own independent cache, causing N parallel refresh calls to Zoho instead of one. A single worker is intentional.

## Project Structure

```
zoho_token_service/
  app/
    __init__.py
    main.py             # FastAPI app, endpoints, lifespan
    schemas.py          # Pydantic response models
    token_manager.py    # Token cache, background refresh loop
  tests/
    test_token_manager.py
  Dockerfile
  docker-compose.yml
  pyproject.toml
  .github/
    workflows/
      ci.yml            # Test on push/PR, deploy on merge to main
```

## CI/CD

The GitHub Actions workflow (`.github/workflows/ci.yml`) runs on every push and pull request:

1. **Test** — installs dependencies, compiles, and runs pytest.
2. **Deploy** (only on push to `main`) — SSHes into the production server, pulls the latest code, and runs `docker compose up --build -d`. Waits for the health check to pass before confirming success.
