## Agents / Services Overview (MCS Architecture)

This project follows the **Model–Controller–Service (MCS)** pattern for a Single‑Page Application.  
All business logic is encapsulated in **services** (referred to as *agents*) that are called by thin FastAPI route handlers.

### 1. AuthAgent
- **Responsibilities**: registration, login (password + GitHub OAuth), token generation and validation.
- **Password**: hashes with `bcrypt` before storing in `users` table.
- **GitHub OAuth**: exchanges authorization code for GitHub token, fetches user profile, creates or links user.
- **Tokens**:
  - Generates short‑lived JWT **access tokens** (e.g., 15 min).
  - Generates unique **refresh tokens** (UUID) stored in Redis with a TTL of 30 days.
  - On refresh: validates refresh token in Redis, issues new access + refresh token pair (rotation).
- **External dependencies**: Redis, GitHub API.

### 2. ChatAgent
- **Responsibilities**: create, list, and delete chat threads.
- **Persistence**: `chats` table (user‑id, title, timestamps).
- **Authorization**: only the chat owner can access / modify.
- **Interaction**: used by `ChatController` endpoints.

### 3. MessageAgent
- **Responsibilities**: save user messages and model responses, fetch history for a chat.
- **Persistence**: `messages` table with foreign key to `chats`.
- **Ordering**: returns messages sorted by creation time.
- **Note**: does **not** store full prompt context in memory; the LLMAgent may choose to use recent messages as context (optional).

### 4. LLMAgent
- **Responsibilities**: communicate with the local LLM (`llama-cpp-python`).
- **Modes**:
  - **Non‑streaming**: returns complete answer text.
  - **Streaming**: yields chunks that are consumed by the controller and forwarded to the client via `StreamingResponse` or similar (bonus).
- **Prompt construction**: optionally includes the last N messages to provide minimal conversation context (stateless per request).
- **Configuration**: model path, max tokens, temperature loaded from environment variables.
- **Internal**: wraps `llama_cpp.Llama` instance (singleton) to keep model loaded.

### 5. CacheAgent
- **Responsibilities**: manage Redis caching to reduce database load.
- **Use cases**:
  - Store refresh tokens (mandatory).
  - Cache list of chats or recent chat history (bonus). Invalidation on new messages.
- **TTL rules**: refresh tokens 30 days; cached data short TTL (e.g., 5 minutes) or explicit invalidation.

### 6. (Auxiliary) UserAgent
- **Responsibilities**: fetch user profile, handle DB lookups for authentication.
- **Persistence**: `users` table (email/login, hashed password, GitHub ID, etc.).
- **Used by**: AuthAgent, token validation dependency.

**Interaction flow**:  
HTTP request → FastAPI route (Controller) → calls appropriate Service (Agent) → Service uses Models (SQLAlchemy) or external systems (Redis, LLM) → returns result.