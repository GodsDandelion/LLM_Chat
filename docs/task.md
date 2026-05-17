## Task Breakdown

### 1. Project Setup & Configuration
- [ ] Initialize Git repository, create `.gitignore`, `README.md`.
- [ ] Set up Python virtual environment and install base packages (`fastapi`, `uvicorn`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `redis`, `python-jose`, `passlib[bcrypt]`, `httpx`, `llama-cpp-python`).
- [ ] Create project folder structure: `app/` (main, models, schemas, services, api, core), `alembic/`, `tests/`.
- [ ] Configure environment variables (`.env.example`): database URL, Redis URL, JWT secret, GitHub OAuth credentials, LLM model path.
- [ ] Create `core/config.py` for reading settings.
- [ ] Docker‑compose file for PostgreSQL + Redis (optional).

### 2. Database Models & Migrations
- [ ] Define SQLAlchemy `Base` and async engine.
- [ ] Create models: `User`, `Chat`, `Message` with relationships.
- [ ] Run `alembic init`, configure `env.py` for async.
- [ ] Generate initial migration and apply.

### 3. Authentication Services (Agents)
- [ ] `UserAgent`: get user by login, by ID, create user, link GitHub ID.
- [ ] `AuthAgent`:
  - Password hashing (bcrypt).
  - JWT access token creation and decoding (with expiry).
  - Refresh token generation (UUID), store in Redis with 30‑day TTL.
  - Token refresh logic (rotate, delete old).
  - GitHub OAuth: build authorization URL, exchange code, fetch user info, create/get user.
- [ ] Dependency `get_current_user` that validates access token and fetches user.

### 4. Auth Endpoints
- [ ] `POST /auth/register` – validate unique login, hash password, create user, return success.
- [ ] `POST /auth/login` – verify credentials, return `{access_token, refresh_token}`.
- [ ] `GET /auth/github` – redirect to GitHub OAuth.
- [ ] `GET /auth/github/callback` – handle callback, return token pair.
- [ ] `POST /auth/refresh` – accept refresh token, return new token pair.

### 5. Chat & Message Services
- [ ] `ChatAgent`: create, list (by user), delete (verify ownership).
- [ ] `MessageAgent`: save message, get history for chat (ordered), optional limit/offset.
- [ ] Write schemas (Pydantic) for request/response.

### 6. Chat Endpoints
- [ ] `GET /chats` – list user’s chats.
- [ ] `POST /chats` – create new chat (title optional).
- [ ] `DELETE /chats/{chat_id}` – delete chat (cascade messages).
- [ ] `GET /chats/{chat_id}/messages` – fetch message history.
- [ ] Add authorization checks (user must own the chat).

### 7. LLM Integration (LLMAgent)
- [ ] Place `model.gguf` in project root (or configured path).
- [ ] Implement LLMAgent as a singleton that loads the model once.
- [ ] Non‑streaming method: generate full response text.
- [ ] Build a simple prompt from recent messages (e.g., last 5 exchanges). Format: user/assistant.
- [ ] Connect to `POST /chats/{chat_id}/messages` – save user message, call LLM, save assistant message, return response.

### 8. Streaming & Bonus Features
- [ ] Extend LLMAgent with async streaming generator (using `stream=True`).
- [ ] Add `stream` query parameter to message endpoint; if true, return `StreamingResponse` with `text/event-stream`.
- [ ] Implement `CacheAgent`:
  - Redis caching for `/chats/{chat_id}/messages` with TTL.
  - Invalidate cache on new message insert.
- [ ] (Optional) Client‑side auto‑refresh by polling a status endpoint or using events.

### 9. Documentation & Final Touches
- [ ] Write detailed README: setup (dependencies, env vars, DB migration, run), GitHub OAuth app registration guide.
- [ ] Add a note on chosen architecture (SPA, MCS) and JWT/refresh token flow.
- [ ] Generate PDF report:
  - API structure (table of routes, or OpenAPI excerpt).
  - Code organisation section (modules, layers).
  - Screenshots of main screens (login, chat list, conversation, streaming).
  - Database ERD (tables, relationships).
- [ ] Code cleanup, linting (flake8/black).
- [ ] Final commit and push to GitHub.