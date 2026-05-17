## Project Specification: LLM Chat

### 1. Overview
A ChatGPT‑like web application enabling users to create chat threads, send messages to a local LLM, and receive answers.  
Authentication supports email/password and GitHub OAuth. Security is provided by JWT access/refresh tokens with a 30‑day session stored in Redis.

### 2. Tech Stack
- **Backend**: Python 3.11+, FastAPI, SQLAlchemy (async), Alembic, Pydantic.
- **Database**: PostgreSQL (primary). Migrations via Alembic.
- **Cache / Session store**: Redis.
- **Auth**: PyJWT, passlib[bcrypt], httpx (for GitHub OAuth).
- **LLM**: llama‑cpp‑python with a GGUF model (CPU inference).
- **Frontend**: SPA (out of review scope, only visual assessment).

### 3. Architecture
- **UI Strategy**: Single‑Page Application → backend follows **MCS (Model–Controller–Service)**.
- **Layers**:
  - *Models*: SQLAlchemy ORM models (`User`, `Chat`, `Message`).
  - *Controllers*: FastAPI route handlers (thin, delegating to services).
  - *Services*: Business logic agents (see `agents.md`).
- **JWT + Refresh Flow**: Access token in `Authorization: Bearer`. Refresh endpoint swaps refresh token from Redis for new token pair.

### 4. Core Features
- **User registration** with unique login and password (hashed).
- **Login** returning access + refresh tokens.
- **GitHub OAuth** login: redirects to GitHub, handles callback, issues tokens.
- **Chat management**:
  - Create a new chat (auto‑generated title or user‑supplied).
  - List user’s chats (ordered by last activity).
  - Delete a chat.
- **Messaging**:
  - Send a user message to a chat → triggers LLM response.
  - Retrieve message history for a chat (paginated or full).
- **LLM interaction**: stateless per request; optionally include a window of recent messages.
- **Token refresh**: `/auth/refresh` endpoint to rotate tokens.

### 5. Authentication & Security
- Password hashing: `bcrypt` via passlib.
- GitHub OAuth: standard authorization code flow.
- Access token: short‑lived (15 min), signed JWT containing user ID.
- Refresh token: random UUID, stored in Redis with key `refresh:<token>` → `user_id`, TTL 30 days. On refresh, old token is deleted and new one created (rotation).
- All protected routes require valid access token (dependency).

### 6. API Design (FastAPI)
**Public**:
- `POST /auth/register` – create user.
- `POST /auth/login` – return token pair.
- `GET /auth/github` – redirect to GitHub.
- `GET /auth/github/callback` – exchange code, return tokens.
- `POST /auth/refresh` – accept refresh token, return new pair.

**Protected** (require `Authorization: Bearer <access_token>`):
- `GET /chats` – list user chats.
- `POST /chats` – create chat.
- `DELETE /chats/{chat_id}` – delete chat.
- `GET /chats/{chat_id}/messages` – get message history.
- `POST /chats/{chat_id}/messages` – send message, returns (streaming or full) LLM response.
  - Support `stream=true` query parameter for streaming (bonus).

**Bonus streaming**: response sent as `text/event-stream` (Server‑Sent Events) with chunks.

### 7. Local LLM Integration
- Model file: `model.gguf` placed in project root.
- Loaded once on startup using `llama_cpp.Llama`.
- Non‑streaming: `stream=False`, extract `result["choices"][0]["text"]`.
- Streaming: `stream=True`, iterate chunks, yield text.
- Environment variables: `LLM_MODEL_PATH`, `LLM_MAX_TOKENS`, `LLM_TEMPERATURE`.

### 8. Database Schema (PostgreSQL)
**Tables**:
- `users`: id (PK), login (unique), password_hash, github_id (nullable, unique), created_at.
- `chats`: id (PK), user_id (FK→users), title, created_at, updated_at.
- `messages`: id (PK), chat_id (FK→chats), role (enum: user/assistant), content (text), created_at.

**Redis keys**:
- `refresh:<token>` → `user_id`, TTL 2 592 000 seconds (30 days).
- (Bonus) `chat:<chat_id>:messages` → cached JSON list, TTL 300 seconds.

### 9. Bonus Requirements (Optional)
- Streaming LLM output to UI (Server‑Sent Events).
- Auto‑refresh of answer visualization (client polling or SSE).
- Redis caching of chat history with invalidation on new messages.

### 10. Deliverables
- Git repository with source code.
- README with setup instructions (env vars, dependencies, DB migrations, GitHub OAuth app creation).
- Note on chosen UI strategy (SPA) and MCS architecture.
- PDF report including: API structure overview, code organization, screenshots, database schema/ERD.