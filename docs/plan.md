## Implementation Plan

### Phase 1: Foundation & Auth (Days 1‑2)
- Set up project structure (FastAPI app, configuration, logging).
- Define SQLAlchemy models (`User`, `Chat`, `Message`) and create initial Alembic migration.
- Implement `AuthAgent` and `UserAgent`:
  - Register, login with password (bcrypt).
  - JWT access token generation and validation dependency.
  - Refresh token storage in Redis (with rotation).
  - GitHub OAuth flow (redirect + callback).
- Create auth endpoints (`/auth/*`).
- Docker‑compose for PostgreSQL + Redis (dev environment).
- Test authentication manually (using Swagger UI).

### Phase 2: Core Chat & LLM (Days 3‑5)
- Implement `ChatAgent` and `MessageAgent`.
- Create chat endpoints (`/chats`) with proper authorisation.
- Integrate `LLMAgent`:
  - Load model on startup (using `llama-cpp-python`).
  - Non‑streaming response for `POST /chats/{chat_id}/messages`.
- Persist messages (user + assistant) in DB.
- Expose message history endpoint.
- Add pagination or limit to history (optional).
- Manual testing of full flow: create chat → send message → receive answer → view history.

### Phase 3: Streaming & Bonus (Days 6‑7)
- Extend `LLMAgent` to support streaming.
- Implement streaming endpoint: `POST ...?stream=true` returns `text/event-stream`.
- Modify front‑end (just for visual check) to display streaming tokens.
- Implement `CacheAgent`:
  - Cache chat message list in Redis, invalidate on new message.
- Add auto‑refresh simulation (client‑side polling) if time permits.
- Polish and error handling.

### Phase 4: Documentation & Reporting (Day 8)
- Write README with all setup instructions.
- Prepare PDF report:
  - API structure (OpenAPI excerpt or table).
  - Code organisation (packages, layers).
  - Screenshots of main screens (chat list, chat view, login, streaming).
  - Database ERD (tables and relationships).
- Final code review, linting, cleanup.
- Push to Git repository.

**Dependencies**: PostgreSQL and Redis running locally or via Docker.  
**Risk**: GGUF model size may cause slow startup; mitigation: load once, keep in memory.