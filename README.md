# LLM Chat API

Backend for a ChatGPT-style app: **FastAPI**, **PostgreSQL** (async SQLAlchemy + Alembic), **Redis** (refresh tokens and optional message cache), **JWT** access + refresh flow, **GitHub OAuth**, and a local **GGUF** model via **llama-cpp-python**. Architecture follows **MCS** (models, thin controllers/routes, service “agents”) for a SPA client.

See `docs/spec.md`, `docs/plan.md`, `docs/agents.md`, and `docs/task.md` for the full brief.

## Requirements

- **Python 3.11+** recommended (matches the course spec; 3.9+ may work with current typing).
- **PostgreSQL** and **Redis** (Docker Compose provided).
- A **GGUF** model file (e.g. `model.gguf` in the project root, or set `LLM_MODEL_PATH`).

`llama-cpp-python` may require a compiler or a [prebuilt wheel](https://github.com/abetlen/llama-cpp-python#supported-backends) for your platform.

## Quick start

1. **Clone / enter the project** and create a virtualenv:

   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Start PostgreSQL and Redis** (must be running **before** `alembic` or the app):

   ```bash
   docker compose up -d
   ```

   Wait a few seconds for Postgres to accept connections. If you do not use Docker, run a local Postgres on port **5432** with database/user/password matching `DATABASE_URL` in `.env`.

3. **Configure environment** — copy `.env.example` to `.env` and adjust secrets and OAuth values.

4. **Run migrations**:

   ```bash
   alembic upgrade head
   ```

5. **Run the API**:

   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

6. Open the **web UI**: `http://localhost:8000/` (redirects to `/ui/`) — register, log in, create chats, and message the model. **Swagger**: `http://localhost:8000/docs`. Machine-readable discovery: `GET /api-info`.

## Troubleshooting

### `alembic upgrade head` — connection refused / `Errno 61` on port 5432

Nothing is listening on **localhost:5432** (PostgreSQL is not running or uses another port).

- **Docker**: Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine), then from the project directory run `docker compose up -d`. Confirm with `docker compose ps` that `postgres` is healthy, then run `alembic upgrade head` again.
- **No Docker**: Install PostgreSQL locally, create role/database matching `.env` (default user/password/db: `llmchat` / `llmchat` / `llmchat`), or change `DATABASE_URL` to match your setup.
- **Remote DB**: Set `DATABASE_URL` in `.env` to your provider’s connection string (must use driver `postgresql+asyncpg://…`).

## Environment variables

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Async SQLAlchemy URL, e.g. `postgresql+asyncpg://llmchat:llmchat@localhost:5432/llmchat` |
| `REDIS_URL` | e.g. `redis://localhost:6379/0` |
| `JWT_SECRET` | Signing key for access JWTs |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Default `15` |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` / `GITHUB_REDIRECT_URI` | GitHub OAuth app ([Creating an OAuth App](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app)) |
| `LLM_MODEL_PATH` | Path to `.gguf` model |
| `LLM_MAX_TOKENS`, `LLM_TEMPERATURE`, `LLM_CONTEXT_MESSAGES` | Generation settings |
| `CORS_ORIGINS` | Comma-separated origins for the SPA |

## Auth flow (summary)

- **Register** `POST /auth/register` → then **login** `POST /auth/login` with JSON `{ "login", "password" }` → `{ access_token, refresh_token, token_type }`.
- **GitHub**: `GET /auth/github` redirects to GitHub; `GET /auth/github/callback?code=...` exchanges the code and returns the same token JSON.
- **Refresh**: `POST /auth/refresh` with `{ "refresh_token" }`; the old refresh token is removed from Redis and a new pair is issued (rotation).
- Protected routes: `Authorization: Bearer <access_token>`.

## Main API

| Method | Path | Auth |
|--------|------|------|
| GET | `/health` | No |
| POST | `/auth/register` | No |
| POST | `/auth/login` | No |
| GET | `/auth/github` | No |
| GET | `/auth/github/callback` | No |
| POST | `/auth/refresh` | No |
| GET | `/chats` | Yes |
| POST | `/chats` | Yes |
| DELETE | `/chats/{chat_id}` | Yes |
| GET | `/chats/{chat_id}/messages` | Yes (optional `limit`, `offset`) |
| POST | `/chats/{chat_id}/messages` | Yes; query `stream=true` for SSE (`text/event-stream`) |

## Tests

```bash
pytest tests/
```

## Project layout

- `app/main.py` — FastAPI app, CORS, Redis lifespan
- `app/core/` — settings, DB session, dependencies
- `app/models/` — SQLAlchemy models
- `app/schemas/` — Pydantic request/response models
- `app/services/` — agents (`AuthAgent`, `UserAgent`, `ChatAgent`, `MessageAgent`, `LLMAgent`, `CacheAgent`)
- `app/api/routes/` — route handlers
- `alembic/` — migrations

## PDF report (per spec)

The task list mentions a PDF with OpenAPI excerpt, module layout, screenshots, and ERD. Generate that locally (export from `/docs` OpenAPI, diagram DB from models, add UI screenshots) when you submit the assignment.
