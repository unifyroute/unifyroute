# LLM Gateway — Progress Report & Remaining Work

**Last Updated:** 2026-02-23

> Gap analysis comparing the current implementation against the
> [Architecture Specification](./llm-gateway-architecture.md) (v1.0).

---

## 1. Work Completed ✅

### 1.1 Shared Package (`shared/`)
- [x] SQLAlchemy 2.0 async models for all 6 tables: `providers`, `credentials`, `provider_models`, `quota_snapshots`, `request_logs`, `gateway_keys`
- [x] Pydantic v2 schemas (`ChatRequest`, `ChatMessage`, provider/credential/model/key CRUD schemas)
- [x] Async database engine with `asyncpg` (PostgreSQL) and `aiosqlite` (SQLite) support
- [x] Encryption utilities (Fernet-based encrypt/decrypt with `VAULT_MASTER_KEY`)
- [x] Alembic migrations (3 versions: initial schema, empty-tier-check, oauth_meta on providers)

### 1.2 API Gateway (`api-gateway/`)
- [x] FastAPI app on port 8000 with CORS middleware
- [x] **Auth middleware** — Bearer token → SHA-256 hash → `gateway_keys` table lookup
- [x] **`GET /v1/models`** — OpenAI-compatible models list from `provider_models`
- [x] **`POST /v1/chat/completions`** — Full proxy with tier-based routing, litellm dispatch, streaming (SSE), and non-streaming support
- [x] **Request logging** — Background task writes to `request_logs` (tokens, latency, cost, status)
- [x] Admin CRUD endpoints:
  - Providers: list / create / update / delete / seed catalog (~20 providers)
  - Credentials: list / create / delete / verify / check-quota
  - Models: list / create / update / delete / sync-from-provider API
  - Gateway keys: list / create / delete
  - Logs: paginated list with filters, stats aggregation, usage stats
  - Routing config: read & write `routing.yaml`
- [x] **OAuth2 flows**:
  - Generic OAuth: `GET /oauth/start/{provider_id}` + `GET /oauth/callback`
  - Google Antigravity (gemini-cli): dedicated PKCE flow with hardcoded client credentials
  - Callback stores encrypted tokens & posts `oauth_success` to opener window
- [x] **Model sync** — Provider-specific logic for OpenAI, Anthropic, Google, Groq, UnifyRouter, Together, HuggingFace + generic fallback

### 1.3 Router (`router/`)
- [x] `select_model()` — Tier-based routing from `routing.yaml` config
- [x] `routing.yaml` — Pre-configured with lite / base / thinking tiers
- [x] Hot-reload via `watchdog` (ConfigReloader + file observer)
- [x] Candidate sorting: `cheapest_available` (cost ↑, quota ↓) and `highest_quota` (quota ↓, cost ↑)
- [x] Redis-backed quota reads (`quota:{credential_id}:{model_id}`)
- [x] Failed-provider marking in Redis with 60s cooldown (`failed:{cred_id}:{model_id}`)
- [x] Provider adapters via `litellm.acompletion()` — OpenAI, Anthropic, Google/Gemini, Groq + generic fallback

### 1.4 Credential Vault (`credential-vault/`)
- [x] FastAPI internal service on port 8001
- [x] `POST /internal/decrypt/{credential_id}` — Returns decrypted plaintext secret
- [x] OAuth2 token refresh background task (mock implementation — extends deadline)

### 1.5 Quota Poller (`quota-poller/`)
- [x] APScheduler AsyncIOScheduler with 3 jobs:
  - `poll_quotas` — every 5 min (OpenAI + Anthropic specific, generic fallback)
  - `sync_models_job` — every 6 hours (placeholder/stub)
  - `collect_usage_job` — every 1 hour (placeholder/stub)
- [x] Writes `QuotaSnapshot` to DB and updates Redis cache (600s TTL)
- [x] Runs once on startup

### 1.6 GUI (`gui/`)
- [x] React 18 + Vite + TailwindCSS + shadcn/ui
- [x] SWR for server-state management
- [x] Dark/light theme toggle
- [x] All 8 pages present:
  - **Dashboard** — Summary cards (basic)
  - **Providers** — DataTable with add/edit/delete, seed catalog button
  - **Credentials** — Grouped by provider, add API key, OAuth connect buttons, verify/quota check
  - **Models** — DataTable with tier assignment, enable/disable, sync from provider, delete
  - **Routing Strategy** — YAML editor (textarea) with save
  - **Usage & Quota** — Basic view
  - **Sessions & Logs** — Paginated table with provider/status filters
  - **Settings (Config)** — Gateway key management (create/delete)

### 1.7 Infrastructure
- [x] Docker Compose — PostgreSQL 16 + Redis 7 (data stores only)
- [x] `unifyroute` launcher script (CLI entrypoint)
- [x] Setup script (`scripts/setup.sh`)
- [x] Admin key creation script (`scripts/create-key.py`)
- [x] Cleanup script (`scripts/cleanup.sh`)
- [x] systemd service file (`scripts/llm-gateway.service`)
- [x] `.env` / `sample.env` configuration
- [x] `README.md`

---

## 2. Remaining Work 🔧

### 2.1 High Priority — Core Functionality Gaps

| # | Area | Task | Spec Reference |
|---|------|------|----------------|
| 1 | **Router** | **Fallback chain on 429/503/timeout** — Currently the router selects the top candidate but does NOT retry the next candidate on provider errors. Need to implement the retry loop described in §6.1 steps 5. | §6.1 |
| 2 | **Router** | **Cost calculation in request logging** — `cost_usd` is always logged as `0`. Need to calculate actual cost from `input_cost_per_1k` / `output_cost_per_1k` × token count. | §6.4, §7.2 |
| 3 | **Credential Vault** | **Real OAuth2 token refresh** — Currently mocked. Need actual HTTP POST to provider's `token_url` using `refresh_token` to get new `access_token`. | §6.2, §8 |
| 4 | **Encryption** | **Upgrade to AES-256-GCM** — Currently using Fernet (AES-128-CBC). Spec requires AES-256-GCM with separate IV storage. The `iv` column exists in DB but is unused. | §5.1, §6.2 |
| 5 | **Quota Poller** | **Provider-specific quota polling** — Only OpenAI and Anthropic have basic implementations. Need Google Vertex, Cohere, Mistral, Groq pollers. `sync_models_job` and `collect_usage_job` are stubs. | §6.3 |
| 6 | **Streaming** | **Token counting during streaming** — Streaming responses log `0` for prompt/completion tokens. Need to accumulate from SSE chunks or use litellm's usage tracking. | §6.4 |

### 2.2 Medium Priority — GUI Enhancements

| # | Area | Task | Spec Reference |
|---|------|------|----------------|
| 7 | **Dashboard** | **Live token usage graph** — Need line chart (Recharts) for token usage over last 24h, per-provider and per-tier breakdown. Currently shows basic cards only. | §7.2 |
| 8 | **Dashboard** | **Alert banners for low quota** — No alert/notification system for low quota thresholds. | §7.2 |
| 9 | **Dashboard** | **Cost today/month summary** — Needs real cost data (blocked by #2 above). | §7.2 |
| 10 | **Routing Config** | **Monaco editor** — Currently a basic textarea. Spec calls for Monaco editor with live YAML validation. | §7.2 |
| 11 | **Routing Config** | **Visual tier editor** — Drag-drop model priority ordering per tier. Not implemented. | §7.2 |
| 12 | **Quota Monitor** | **Real-time gauge charts** — Spec calls for Recharts RadialBarChart per credential, auto-refresh every 30s. Current implementation is basic. | §7.2 |
| 13 | **Quota Monitor** | **Historical usage chart** — Per-credential usage over time. Not yet built. | §7.2 |
| 14 | **Logs** | **CSV export** — Not implemented. | §7.2 |
| 15 | **Logs** | **Tier filter** — Can filter by provider/status but not by tier alias. | §7.2 |
| 16 | **Settings** | **Poll interval config** — Cannot change `QUOTA_POLL_INTERVAL_SECONDS` from GUI. | §7.2 |
| 17 | **Settings** | **Alert thresholds config** — No UI for configuring low-quota alert thresholds. | §7.2 |
| 18 | **Settings** | **User management** — No user/role system in GUI. | §7.2 |
| 19 | **GUI** | **TanStack Query migration** — Spec calls for TanStack Query; currently uses SWR. (Functional equivalent, low priority.) | §7.1 |

### 2.3 Medium Priority — Backend & Security

| # | Area | Task | Spec Reference |
|---|------|------|----------------|
| 20 | **API Gateway** | **`POST /v1/completions`** — Only `/v1/chat/completions` is implemented. Completions endpoint missing. | §6.4 |
| 21 | **API Gateway** | **JWT auth for GUI sessions** — Currently GUI uses API key auth same as clients. Spec calls for RS256 JWT + cookie-based session with MFA. | §6.4, §7.1 |
| 22 | **API Gateway** | **Per-client rate limiting** — No rate limiter middleware. Spec lists per-API-key rate limits. | §4.1, §11 |
| 23 | **Provider Adapters** | **Separate adapter files** — All adapters are in a single generic `ProviderAdapter` class using litellm. Spec calls for separate adapter files per provider (`openai.py`, `anthropic.py`, `google.py`, `cohere.py`, `mistral.py`, `groq.py`) with `list_models()` and `get_quota()` methods. | §12, §13 |
| 24 | **Security** | **Audit log immutability** — `request_logs` is a regular table. Spec calls for append-only table. | §11 |
| 25 | **Security** | **Internal-only credential-vault** — Currently exposed; spec says it should be internal-only (no external port). gRPC was originally planned but REST was used for simplicity. | §6.2, §11 |

### 2.4 Low Priority — Deployment & Quality

| # | Area | Task | Spec Reference |
|---|------|------|----------------|
| 26 | **Docker** | **Application services in Docker Compose** — Only Postgres + Redis are containerized. Need Dockerfiles and compose entries for `api-gateway`, `credential-vault`, `quota-poller`, and `gui`. | §10.1 |
| 27 | **Docker** | **`docker-compose.override.yml`** — Dev override with hot-reload volumes not created. | §10.1 |
| 28 | **Testing** | **Unit tests** — No tests exist. Spec requires pytest for router logic and encryption utils. | §12 |
| 29 | **Testing** | **Integration tests** — No testcontainers-based API integration tests. | §12 |
| 30 | **Code Quality** | **Type hints** — Partial coverage. Spec requires strict mypy / strict TypeScript mode. | §12 |
| 31 | **API Gateway** | **Refactor `main.py`** — Currently a 1270-line monolith. Spec calls for modular structure: `auth.py`, `routes/completions.py`, `routes/models.py`. | §13 |
| 32 | **Kubernetes** | **K8s manifests** — Production Kubernetes deployment config not created (lower priority for self-hosted). | §10.2 |

---

## 3. Implementation Priority Order (Recommended)

### Phase 1 — Core Reliability
1. **Fallback chain** (#1) — Critical for production reliability
2. **Cost calculation** (#2) — Needed for Dashboard and usage analytics
3. **Real OAuth refresh** (#3) — Required for Google Vertex/Antigravity tokens to stay valid
4. **Streaming token counting** (#6) — Accurate usage tracking

### Phase 2 — Dashboard & Monitoring
5. **Dashboard charts** (#7, #8, #9) — Live usage visibility
6. **Quota gauge charts** (#12, #13) — Real-time quota monitoring
7. **Provider-specific pollers** (#5) — Accurate quota data

### Phase 3 — Security & Polish
8. **AES-256-GCM encryption** (#4) — Spec compliance
9. **JWT GUI auth** (#21) — Proper session management
10. **Rate limiting** (#22) — Abuse prevention
11. **CSV export** (#14) — Log export feature

### Phase 4 — Deployment & Quality
12. **Docker Compose full stack** (#26, #27) — Containerized deployment
13. **Unit & integration tests** (#28, #29) — Code quality
14. **Code refactoring** (#31, #23) — Maintainability
15. **Remaining GUI enhancements** (#10, #11, #15–#19)

---

## 4. Summary Statistics

| Category | Done | Remaining | % Complete |
|----------|------|-----------|------------|
| Database schema | 6/6 tables | — | **100%** |
| API endpoints | ~30 routes | 3+ | **~90%** |
| Router logic | Core routing | Fallback chain | **~80%** |
| Credential Vault | Decrypt API | Real OAuth refresh, AES-256-GCM | **~60%** |
| Quota Poller | 2 providers | 4+ providers, real sync/usage jobs | **~40%** |
| GUI pages | 8/8 pages | Chart enhancements, editor upgrades | **~65%** |
| Docker | Data stores | App service containers | **~30%** |
| Testing | — | Unit + integration tests | **0%** |
| **Overall** | | | **~60%** |
