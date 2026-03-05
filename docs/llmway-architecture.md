**LLM Gateway**

Universal AI Provider Aggregator & Smart Routing System

*Architecture & Implementation Specification*

Version 1.0 \| AI Prompt Document

**1. Executive Summary**

LLM Gateway is a self-hosted universal proxy layer that aggregates
multiple AI provider API keys (including OpenAI, Anthropic, Google,
Cohere, Mistral, and others), intelligently routes requests based on
real-time token availability and cost, and exposes a single
OpenAI-compatible endpoint. Downstream tools such as OpenClaw consume
the gateway as a single provider and never experience token exhaustion
because the system dynamically selects the best available model from the
available pool.

The system is directly inspired by the open-source LiteLLM project
(github.com/BerriAI/litellm) but extends it with a full credential
vault, GUI management console, OAuth 2.0 flow support, per-tier model
selection (lite / base / thinking), and a live quota dashboard.

**2. Problem Statement & Goals**

**2.1 Problem**

-   OpenClaw and similar tools are bound to a single provider and
    exhaust rate limits quickly.

-   Managing API keys across dozens of providers is error-prone and
    insecure.

-   Some providers require OAuth flows rather than static API keys
    (e.g., Google Vertex AI).

-   Cost optimisation requires real-time visibility into token pricing
    across providers.

-   There is no unified interface to select the right model tier
    (fast/cheap vs. powerful/expensive).

**2.2 Goals**

1.  Accept OpenAI-compatible requests from any client (OpenClaw, Cursor,
    Continue, etc.).

2.  Maintain an encrypted vault of API keys and OAuth credentials for N
    providers.

3.  Poll provider APIs for available models, token quotas, and per-token
    pricing.

4.  Route each incoming request to the cheapest / most available model
    that satisfies the requested tier.

5.  Expose a management GUI for admins to configure providers, view
    usage, and set routing rules.

6.  Be self-hostable via Docker Compose with zero external dependencies
    (except provider APIs).

**3. Comparison with LiteLLM**

LiteLLM (BerriAI) is the closest open-source analog. Key points of
comparison:

  ------------------- --------------------------- ---------------------------
  **Capability**      **LiteLLM**                 **LLM Gateway**

  OpenAI-compatible   Yes                         Yes
  proxy                                           

  Multi-provider      Yes (100+ providers)        Yes (extensible)
  routing                                         

  Credential vault    Partial (env vars / DB)     Full --- AES-256 encrypted
  (encrypted)                                     DB

  OAuth 2.0 / OIDC    Limited                     First-class (Google Vertex,
  flows                                           Azure AD)

  Real-time quota     No                          Yes --- background poller
  polling                                         service

  Model tier          No                          Yes --- lite / base /
  abstraction                                     thinking aliases

  GUI management      Basic (LiteLLM UI,          Full open-source GUI
  console             enterprise)                 

  Cost-aware routing  Yes (basic)                 Yes + live cost dashboard

  Self-hosted, no     Yes                         Yes
  SaaS lock                                       
  ------------------- --------------------------- ---------------------------

*Decision: LLM Gateway adopts LiteLLM\'s proven provider SDK layer as an
optional backend while wrapping it with the credential vault, quota
engine, and tier routing described in this document.*

**4. System Architecture**

**4.1 High-Level Architecture**

The system consists of six primary services orchestrated via Docker
Compose:

┌──────────────────────────────────────────────────────────────┐

│ CLIENT LAYER │

│ OpenClaw │ Cursor │ Continue │ Any OpenAI SDK Client │

└────────────────────────┬─────────────────────────────────────┘

│ POST /v1/chat/completions (OpenAI API)

┌────────────────────────▼─────────────────────────────────────┐

│ API GATEWAY SERVICE │

│ FastAPI │ Auth Middleware │ Rate Limiter │ Audit Log │

└──────┬──────────────┬───────────────────────────────────────┘

│ │

┌──────▼──────┐ ┌──▼──────────────────────────────────────────┐

│ ROUTER │ │ CREDENTIAL VAULT SERVICE │

│ Tier Map │ │ AES-256 │ API Keys │ OAuth Tokens │ Refresh │

│ Cost Rank │ └────────────────────────────────────────────┘

│ Fallback │

└──────┬──────┘

│ dispatches to selected provider adapter

┌──────▼───────────────────────────────────────────────────────┐

│ PROVIDER ADAPTER LAYER │

│ OpenAI │ Anthropic │ Google │ Cohere │ Mistral │... │

└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐

│ QUOTA POLLER (background) │ GUI SERVICE (React + Vite) │

└──────────────────────────────────────────────────────────────┘

**4.2 Service Breakdown**

  --------------------- -------------------------------------------------
  **Service**           **Responsibility**

  api-gateway           Receives all incoming OpenAI-compatible requests,
                        validates JWT/API-key auth, passes to Router

  router                Maps requested model alias (lite/base/thinking)
                        to a real provider+model, ranks candidates by
                        cost & quota, handles fallback chains

  credential-vault      Stores and serves encrypted API keys and OAuth
                        tokens; runs OAuth refresh loops; never exposes
                        plaintext outside service boundary

  quota-poller          Background worker that polls each provider every
                        N minutes for available models, remaining quota,
                        and token pricing; writes to shared DB

  gui-service           React SPA served by a Node static server; talks
                        to api-gateway REST endpoints for configuration
                        and dashboards

  postgres + redis      PostgreSQL for persistent config/logs; Redis for
                        real-time quota cache and request deduplication
  --------------------- -------------------------------------------------

**5. Data Models**

**5.1 Provider & Credential**

\-- providers table CREATE TABLE providers ( id UUID PRIMARY KEY DEFAULT
gen_random_uuid(), name TEXT NOT NULL, \-- \"openai\", \"anthropic\",
\"google-vertex\" display_name TEXT NOT NULL, auth_type TEXT NOT NULL,
\-- \"api_key\" \| \"oauth2\" base_url TEXT, enabled BOOLEAN DEFAULT
TRUE, created_at TIMESTAMPTZ DEFAULT NOW() ); \-- credentials table (one
provider may have many keys) CREATE TABLE credentials ( id UUID PRIMARY
KEY DEFAULT gen_random_uuid(), provider_id UUID REFERENCES providers(id)
ON DELETE CASCADE, label TEXT, \-- \"production-key-1\" auth_type TEXT
NOT NULL, \-- \"api_key\" \| \"oauth2_token\" secret_enc BYTEA NOT NULL,
\-- AES-256-GCM encrypted iv BYTEA NOT NULL, oauth_meta JSONB, \-- {
client_id, client_secret_enc, token_url, scopes, refresh_token_enc }
expires_at TIMESTAMPTZ, enabled BOOLEAN DEFAULT TRUE, created_at
TIMESTAMPTZ DEFAULT NOW() );

**5.2 Models & Quota**

CREATE TABLE provider_models ( id UUID PRIMARY KEY DEFAULT
gen_random_uuid(), provider_id UUID REFERENCES providers(id), model_id
TEXT NOT NULL, \-- \"gpt-4o\", \"claude-3-5-sonnet-20241022\"
display_name TEXT, context_window INT, input_cost_per_1k NUMERIC(12,6),
\-- USD per 1k input tokens output_cost_per_1k NUMERIC(12,6), tier TEXT,
\-- \"lite\" \| \"base\" \| \"thinking\" \| null supports_streaming
BOOLEAN DEFAULT TRUE, supports_functions BOOLEAN DEFAULT TRUE, last_seen
TIMESTAMPTZ, enabled BOOLEAN DEFAULT TRUE ); CREATE TABLE
quota_snapshots ( id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
credential_id UUID REFERENCES credentials(id), model_id TEXT,
tokens_remaining BIGINT, requests_remaining INT, resets_at TIMESTAMPTZ,
polled_at TIMESTAMPTZ DEFAULT NOW() );

**5.3 Routing Tiers**

  ------------------- --------------------------- ---------------------------
  **Alias (sent by    **Target Tier**             **Example Models
  OpenClaw)**                                     (configurable)**

  lite-standard       lite                        gpt-4o-mini,
                                                  claude-haiku-3,
                                                  gemini-1.5-flash,
                                                  mistral-small

  base-standard       base                        gpt-4o, claude-3-5-sonnet,
                                                  gemini-1.5-pro,
                                                  mistral-large

  thinking-standard   thinking                    o1, claude-3-7-sonnet
                                                  (extended thinking),
                                                  gemini-2.0-flash-thinking
  ------------------- --------------------------- ---------------------------

**6. Core Services --- Detailed Design**

**6.1 Router Service**

The router is the heart of the system. When a request arrives with
model=\'lite-standard\':

7.  Query Redis for all credentials in tier=\'lite\' with
    quota_remaining \> threshold.

8.  Sort candidates by: (a) cost per token ascending, (b) quota
    remaining descending.

9.  Select top candidate; retrieve decrypted credential from vault via
    internal mTLS call.

10. Forward request to provider adapter; capture token usage in
    response.

11. If provider returns 429 or 503, remove from candidate list and retry
    next candidate (fallback chain).

12. Record usage event to PostgreSQL for billing/audit.

Routing config (YAML, hot-reloadable):

routing: tiers: lite: strategy: cheapest_available \# or: round_robin \|
highest_quota min_quota_remaining: 10000 fallback_on: \[429, 503,
timeout\] models: - provider: openai model: gpt-4o-mini - provider:
anthropic model: claude-haiku-3-5 - provider: google model:
gemini-1.5-flash base: strategy: cheapest_available models: - provider:
openai model: gpt-4o - provider: anthropic model:
claude-3-5-sonnet-20241022 thinking: strategy: highest_quota models: -
provider: openai model: o1 - provider: anthropic model:
claude-3-7-sonnet-20250219

**6.2 Credential Vault Service**

-   All secrets encrypted at rest using AES-256-GCM with a master key
    stored in environment variable or HashiCorp Vault.

-   Internal API (gRPC) accessible only within Docker network --- never
    exposed externally.

-   For OAuth2 providers: stores client_id, encrypted client_secret,
    refresh_token. Background goroutine checks expiry and refreshes
    tokens proactively (15 min before expiry).

-   Supports multiple credentials per provider --- the router can
    round-robin or use quota-based selection.

**6.3 Quota Poller Service**

-   Runs as a cron-style background worker (configurable interval,
    default 5 minutes).

-   For each enabled credential, calls the provider\'s usage/quota
    endpoint (or models endpoint).

-   Writes snapshot to quota_snapshots table and updates Redis cache
    with TTL = poll_interval.

-   Publishes quota_updated events via Redis pub/sub so the Router cache
    is instantly invalidated.

-   Providers without a native quota endpoint (e.g., Anthropic) fall
    back to token counting from response headers.

**6.4 API Gateway Service**

-   Built with FastAPI (Python) to maximise LiteLLM compatibility.

-   Exposes POST /v1/chat/completions, POST /v1/completions, GET
    /v1/models --- full OpenAI spec.

-   Auth: API keys (SHA-256 hashed in DB) or JWT (RS256) for GUI
    session.

-   Streaming: SSE pass-through --- gateway streams provider chunks
    directly to client.

-   Request/response logging to PostgreSQL for usage analytics (token
    counts, latency, cost).

**7. GUI Management Console**

**7.1 Tech Stack**

-   Frontend: React 18 + Vite + TailwindCSS + shadcn/ui + Recharts

-   State: TanStack Query (server state) + Zustand (UI state)

-   Auth: JWT via cookie; login page with MFA support

**7.2 GUI Pages & Features**

  --------------------- -------------------------------------------------
  **Page**              **Features**

  Dashboard             Live token usage graph (per provider, per tier),
                        total cost today/month, active requests, alert
                        banners for low quota

  Providers             Add/edit/delete providers; toggle enabled; view
                        connection status; test connectivity button

  Credentials           Add API key or start OAuth2 flow; view masked
                        key; set label; view expiry; delete; multiple
                        keys per provider

  Models                View all discovered models per provider; assign
                        to tier (lite/base/thinking); set enabled; view
                        cost/token and context window

  Routing Config        Visual editor for routing YAML; tier-to-model
                        mapping with drag-drop priority order; strategy
                        selector

  Quota Monitor         Real-time gauge per credential showing tokens
                        remaining, resets_at timestamp; historical usage
                        chart

  Usage Logs            Paginated request log with: timestamp, model
                        alias, actual model used, tokens in/out, cost,
                        latency, status

  Settings              Master key management, poll intervals, alert
                        thresholds, user management, API key generation
                        for clients

  OAuth Flows           Embedded OAuth2 authorization code flow for
                        Google Vertex AI and Azure OpenAI --- \'Connect\'
                        button launches popup
  --------------------- -------------------------------------------------

**8. OAuth 2.0 Integration**

Some enterprise providers use OAuth2 rather than static API keys:

13. Admin clicks \'Add OAuth Provider\' in GUI and selects provider
    (e.g., Google Vertex AI).

14. GUI opens popup to provider\'s authorization URL with scopes =
    \[\'https://www.googleapis.com/auth/cloud-platform\'\].

15. After user consent, provider redirects to gateway callback: GET
    /oauth/callback?code=\...&state=\...

16. Gateway exchanges code for access_token + refresh_token via POST to
    token_url.

17. Both tokens are encrypted and stored in credentials table with
    expires_at set.

18. Quota Poller refreshes access_token automatically before expiry
    using refresh_token.

19. Provider adapter uses current access_token for all API calls (Bearer
    header).

**9. OpenClaw Integration**

**9.1 Configuration in OpenClaw**

Configure OpenClaw (or any OpenAI-compatible client) as follows:

\# OpenClaw / any OpenAI SDK config
OPENAI_API_BASE=http://unifyroute:8000/v1
OPENROUTER_API_KEY=gw-your-gateway-api-key \# Model names to use: \#
lite-standard → cheapest available lite model \# base-standard →
balanced model \# thinking-standard → most capable reasoning model

**9.2 Benefits**

-   OpenClaw never touches individual provider keys --- all secrets stay
    inside the gateway.

-   If the primary model\'s quota is exhausted, the gateway
    transparently retries the next provider --- OpenClaw sees no error.

-   Cost tracking is centralised: all spend flows through the gateway\'s
    usage log.

-   Adding a new provider or rotating keys requires zero changes in
    OpenClaw.

**10. Deployment Architecture**

**10.1 Docker Compose (Development / Small Teams)**

version: \"3.9\" services: api-gateway: build: ./services/api-gateway
ports: \[\"8000:8000\"\] environment: -
DATABASE_URL=postgresql://postgres:pass@postgres:5432/unifyroute -
REDIS_URL=redis://redis:6379 - VAULT_MASTER_KEY=\${VAULT_MASTER_KEY}
depends_on: \[postgres, redis, credential-vault\] credential-vault:
build: ./services/credential-vault environment: -
DATABASE_URL=postgresql://postgres:pass@postgres:5432/unifyroute -
MASTER_KEY=\${VAULT_MASTER_KEY} expose: \[\"50051\"\] \# internal gRPC
only router: build: ./services/router environment: -
REDIS_URL=redis://redis:6379 - VAULT_GRPC=credential-vault:50051
quota-poller: build: ./services/quota-poller environment: -
DATABASE_URL=postgresql://postgres:pass@postgres:5432/unifyroute -
REDIS_URL=redis://redis:6379 - VAULT_GRPC=credential-vault:50051 gui:
build: ./services/gui ports: \[\"3000:3000\"\] postgres: image:
postgres:16-alpine volumes: \[\"pgdata:/var/lib/postgresql/data\"\]
redis: image: redis:7-alpine

**10.2 Production (Kubernetes)**

-   Each service becomes a Kubernetes Deployment with HPA (auto-scale
    api-gateway on CPU/RPS).

-   credential-vault runs as a StatefulSet with PodDisruptionBudget.

-   Secrets (VAULT_MASTER_KEY) stored in Kubernetes Secrets or external
    secrets operator pulling from AWS Secrets Manager / GCP Secret
    Manager.

-   PostgreSQL replaced by managed DB (RDS / Cloud SQL). Redis replaced
    by ElastiCache / Memorystore.

-   Ingress (nginx / Traefik) terminates TLS; internal services
    communicate over mTLS via cert-manager.

**11. Security Model**

  --------------------- -------------------------------------------------
  **Threat**            **Mitigation**

  API key theft from DB AES-256-GCM encryption; master key never in DB;
                        key only decrypted in-memory inside vault service

  Unauthorized API      All gateway requests require API key or JWT; keys
  access                stored as SHA-256 hash

  OAuth token leakage   Refresh tokens encrypted same as API keys; access
                        tokens held only in Redis with TTL

  Internal service      credential-vault only accessible via internal
  compromise            network on port 50051; mTLS in production

  Audit & compliance    All requests logged with user, model, tokens,
                        cost, timestamp; logs immutable (append-only
                        table)

  Rate abuse            Per-client rate limits enforced at gateway;
                        configurable per API key
  --------------------- -------------------------------------------------

**12. AI Prompt --- Implementation Specification**

Use the following prompt with an AI coding assistant to implement the
full system:

> **SYSTEM PROMPT FOR AI CODING ASSISTANT**

You are an expert software architect and senior full-stack engineer.
Build a production-ready system called \"LLM Gateway\" according to the
following specification. Use Python (FastAPI) for backend services,
TypeScript (React 18 + Vite + TailwindCSS) for the GUI, PostgreSQL for
persistence, and Redis for caching. PROJECT: LLM Gateway --- Universal
AI Provider Aggregator ARCHITECTURE: Build six services in a monorepo
(pnpm workspaces or Python Poetry workspaces): 1. api-gateway (FastAPI)
--- OpenAI-compatible API proxy on port 8000 2. credential-vault
(FastAPI + gRPC) --- encrypted secret storage, internal only 3. router
(Python library imported by api-gateway) --- tier-based model routing 4.
quota-poller (Python APScheduler worker) --- background quota polling 5.
gui (React + Vite) --- admin console on port 3000 6. shared (Python
package) --- DB models, schemas, utils DATABASE SCHEMA (PostgreSQL, use
Alembic migrations): - providers(id UUID PK, name TEXT, display_name
TEXT, auth_type TEXT CHECK IN (\'api_key\',\'oauth2\'), base_url TEXT,
enabled BOOL, created_at TIMESTAMPTZ) - credentials(id UUID PK,
provider_id UUID FK, label TEXT, auth_type TEXT, secret_enc BYTEA, iv
BYTEA, oauth_meta JSONB, expires_at TIMESTAMPTZ, enabled BOOL) -
provider_models(id UUID PK, provider_id UUID FK, model_id TEXT,
display_name TEXT, context_window INT, input_cost_per_1k NUMERIC,
output_cost_per_1k NUMERIC, tier TEXT CHECK IN
(\'lite\',\'base\',\'thinking\'), supports_streaming BOOL, enabled
BOOL) - quota_snapshots(id UUID PK, credential_id UUID FK, model_id
TEXT, tokens_remaining BIGINT, requests_remaining INT, resets_at
TIMESTAMPTZ, polled_at TIMESTAMPTZ) - request_logs(id UUID PK,
client_key_id UUID, model_alias TEXT, actual_model TEXT, provider TEXT,
prompt_tokens INT, completion_tokens INT, cost_usd NUMERIC, latency_ms
INT, status TEXT, created_at TIMESTAMPTZ) - gateway_keys(id UUID PK,
label TEXT, key_hash TEXT UNIQUE, scopes TEXT\[\], enabled BOOL)
CREDENTIAL VAULT SERVICE: - Use cryptography.fernet (AES-128-CBC) or
cryptography AES-256-GCM - Master key from env VAULT_MASTER_KEY
(base64-encoded 32 bytes) - Expose internal REST API (not gRPC for
simplicity): POST /internal/decrypt {credential_id} -\>
{plaintext_secret} - OAuth2 refresh loop: APScheduler job every 10
minutes checks credentials with auth_type=\'oauth2_token\', if
expires_at \< now+15min, refresh using stored refresh_token and update
DB API GATEWAY SERVICE: - Implement POST /v1/chat/completions fully
compatible with OpenAI spec - Implement GET /v1/models returning all
enabled provider_models with their tier - Auth middleware: extract
Bearer token, hash it, look up gateway_keys table - Streaming: if
stream=true in request, proxy SSE chunks from provider to client - After
completion, record to request_logs table ROUTER: - Function:
select_model(alias: str, request: ChatRequest) -\> (credential_id,
provider, model_id) - Load tier config from routing.yaml (hot-reload on
file change using watchdog) - Read quota data from Redis key
quota:{credential_id}:{model_id} (set by poller) - Sort candidates: cost
ascending, quota descending - On provider error (429/503/timeout), mark
credential+model as failed in Redis for 60s, try next QUOTA POLLER: -
Use APScheduler AsyncIOScheduler - For each enabled credential: call
provider\'s native API to get quota/usage - OpenAI: GET
https://api.openai.com/v1/usage with date param - Anthropic: parse
x-ratelimit-remaining-tokens from last response header (store in
Redis) - Google Vertex: GET
projects/{project}/locations/{location}/quotas via Google Cloud Quotas
API - Fallback: estimate from request_logs sum in last window - Write to
quota_snapshots and update Redis with 10min TTL PROVIDER ADAPTERS:
Create adapters for: openai, anthropic, google-gemini, cohere, mistral,
groq Each adapter: - adapter.chat(messages, model, stream, \*\*kwargs)
-\> AsyncGenerator \| ChatResponse - adapter.list_models() -\>
list\[ModelInfo\] - adapter.get_quota(credential) -\> QuotaInfo Use
litellm as the underlying call library: import litellm;
litellm.acompletion(\...) GUI (React + TypeScript + TailwindCSS +
shadcn/ui): Pages (React Router v6): - /dashboard: summary cards (total
cost today, requests/min, active providers), line chart of token usage
last 24h (Recharts), quota gauges per provider - /providers: DataTable
with add/edit/delete; ProviderForm modal with fields: name, auth_type,
base_url, enabled - /credentials: grouped by provider; AddKeyModal for
api_key type; OAuthConnectModal that opens popup to
/oauth/start/{provider_id} - /models: DataTable with columns: provider,
model_id, tier (editable dropdown), cost/1k tokens, enabled toggle -
/routing: YAML editor (Monaco editor) with live validation + visual tier
editor showing models per tier with drag-drop reorder - /quota:
real-time gauge charts (Recharts RadialBarChart) per credential, refresh
every 30s - /logs: TanStack Table with server-side pagination, filters
by provider/tier/status, CSV export - /settings: gateway API key
management, poll interval config, alert thresholds OAUTH2 FLOW: - GET
/oauth/start/{provider_id} -\> redirect to provider authorization URL -
GET /oauth/callback?code=&state= -\> exchange code, encrypt tokens,
store in credentials, redirect to GUI /credentials with success toast
DOCKER COMPOSE: Create docker-compose.yml with services: api-gateway,
credential-vault, quota-poller, gui, postgres:16-alpine, redis:7-alpine
Add docker-compose.override.yml for development with hot-reload volumes
ROUTING CONFIG FILE (routing.yaml): tiers: lite: strategy:
cheapest_available min_quota_remaining: 5000 fallback_on: \[429, 503,
timeout\] models: - {provider: openai, model: gpt-4o-mini} - {provider:
anthropic, model: claude-haiku-3-5-20241022} - {provider: google, model:
gemini-1.5-flash} - {provider: groq, model: llama-3.1-8b-instant} base:
strategy: cheapest_available models: - {provider: openai, model:
gpt-4o} - {provider: anthropic, model: claude-3-5-sonnet-20241022} -
{provider: google, model: gemini-1.5-pro} thinking: strategy:
highest_quota models: - {provider: openai, model: o1} - {provider:
anthropic, model: claude-3-7-sonnet-20250219} IMPLEMENTATION ORDER: 1.
shared package: DB models (SQLAlchemy 2.0 async), Pydantic schemas,
encryption utils 2. Database migrations (Alembic) 3. credential-vault
service with encryption and OAuth refresh 4. api-gateway skeleton with
auth middleware and /v1/models endpoint 5. Router with routing.yaml
loader and Redis quota reads 6. Provider adapters (start with openai +
anthropic) 7. Full /v1/chat/completions with streaming and logging 8.
quota-poller with OpenAI and Anthropic adapters 9. GUI: Dashboard,
Providers, Credentials pages 10. GUI: Models, Routing, Quota, Logs pages
11. OAuth2 flow end-to-end 12. Docker Compose + README CODE QUALITY
REQUIREMENTS: - Type hints everywhere (Python: strict mypy, TypeScript:
strict mode) - Async throughout (asyncpg, aioredis, httpx) - Unit tests
for router logic and encryption utils (pytest) - API integration tests
against testcontainers (Postgres + Redis) - Error handling: never expose
provider API keys in error messages or logs - README with: quickstart,
environment variables reference, routing config reference, adding a new
provider guide Start by creating the project structure and the shared
package.

**13. Project File Structure**

unifyroute/ ├── docker-compose.yml ├── docker-compose.override.yml ├──
routing.yaml ├── README.md ├── services/ │ ├── api-gateway/ │ │ ├──
Dockerfile │ │ ├── pyproject.toml │ │ └── src/ │ │ ├── main.py \#
FastAPI app, lifespan │ │ ├── auth.py \# API key / JWT middleware │ │
├── routes/ │ │ │ ├── completions.py \# POST /v1/chat/completions │ │ │
└── models.py \# GET /v1/models │ │ ├── router/ │ │ │ ├── engine.py \#
select_model() core logic │ │ │ ├── config.py \# routing.yaml loader │ │
│ └── fallback.py \# retry / circuit breaker │ │ └── adapters/ │ │ ├──
base.py │ │ ├── openai.py │ │ ├── anthropic.py │ │ ├── google.py │ │ ├──
cohere.py │ │ ├── mistral.py │ │ └── groq.py │ ├── credential-vault/ │ │
├── Dockerfile │ │ └── src/ │ │ ├── main.py │ │ ├── crypto.py \#
AES-256-GCM encrypt/decrypt │ │ ├── oauth.py \# OAuth2 flows + refresh
loop │ │ └── routes/internal.py \# /internal/decrypt │ ├── quota-poller/
│ │ ├── Dockerfile │ │ └── src/ │ │ ├── main.py \# APScheduler setup │ │
└── pollers/ │ │ ├── openai.py │ │ ├── anthropic.py │ │ └── google.py │
├── gui/ │ │ ├── Dockerfile │ │ ├── package.json │ │ └── src/ │ │ ├──
App.tsx │ │ ├── pages/ │ │ │ ├── Dashboard.tsx │ │ │ ├── Providers.tsx │
│ │ ├── Credentials.tsx │ │ │ ├── Models.tsx │ │ │ ├── Routing.tsx │ │ │
├── QuotaMonitor.tsx │ │ │ ├── Logs.tsx │ │ │ └── Settings.tsx │ │ ├──
components/ │ │ └── lib/api.ts │ └── shared/ │ ├── pyproject.toml │ └──
src/ │ ├── models.py \# SQLAlchemy models │ ├── schemas.py \# Pydantic
v2 schemas │ ├── crypto.py \# encryption utils │ └── db.py \# async
engine + session └── migrations/ └── alembic/

**14. Key Environment Variables**

  ----------------------------- -------------------------------------------------
  **Variable**                  **Description**

  VAULT_MASTER_KEY              Base64-encoded 32-byte key for AES-256-GCM
                                encryption of all secrets

  DATABASE_URL                  PostgreSQL connection string (asyncpg format)

  REDIS_URL                     Redis connection URL

  VAULT_INTERNAL_URL            Internal URL of credential-vault service (e.g.,
                                http://credential-vault:8001)

  ROUTING_CONFIG_PATH           Path to routing.yaml (default:
                                /etc/unifyroute/routing.yaml)

  QUOTA_POLL_INTERVAL_SECONDS   How often to poll provider quotas (default: 300)

  JWT_SECRET                    Secret for signing GUI session JWTs

  ALLOWED_ORIGINS               CORS allowed origins for GUI (comma-separated)

  LOG_LEVEL                     Logging level: DEBUG / INFO / WARNING
  ----------------------------- -------------------------------------------------

*LLM Gateway Architecture Specification v1.0 --- Generated for
AI-assisted implementation*
