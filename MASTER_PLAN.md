# UnifyRoute Master End-to-End Plan

This document serves as the definitive reference for the project's current state, recent progress, and the specific path to completion. It is designed to be updated at the end of each round of work to maintain clear focus, momentum, and accountability.

## 1. Current State & Recent Progress
Based on the original architecture spec and recent optimization iterations, the core components of UnifyRoute are highly functional:
- **Core Architecture & Setup:** The database tier uses SQLite as the primary backend with shared async SQLAlchemy models and Alembic migrations. The developer experience has been dramatically refined via the consolidated `unifyroute` CLI tool (setup, start, refresh, uninstall) and streamlined DB configuration.
    - **Status:** 🔴 **COMPLETED**
    - **Details:** Found that the fallback to the fallback router was disabled, but the `auto` tier fallback suppressed errors, and unconfigured aliases were inadvertently matching database names directly. Modified `core.py` and `main.py` so a true configuration error (`RuntimeError`) drops straight out into an HTTP `503 Service Unavailable`, correctly bypassing the brain layer when candidates intentionally do not exist.
- **Gateway & Routing Resilience:** The `POST /v1/chat/completions` proxy performs complex tier-based routing. Crucial failover logic (handling 429/503s), streaming preflight checks, and a "last-resort" fallback to local brain models have been successfully integrated and debugged.
- **Provider Stabilization:** Integrations for a wide variety of adapters—OpenAI, Anthropic, Google/Gemini, Groq, Ollama Cloud, OpenClaw, and Z.AI—have been fixed to properly handle rate limits, authentication constraints, and edge-case exceptions.
- **Authentication & Persistence:** API Key validation is working smoothly alongside chat persistence implementations.

## 2. Immediate Blocking Tasks (High Priority - Core Pipeline)
To reach a stable, production-ready "V1" release, the following backend and metric tracking gaps must be resolved immediately:

- [ ] **Track Prompt/Completion Tokens During Streaming:** Streaming responses (`stream=True`) currently log token usage as `0`. We must accumulate chunks or utilize `litellm` usage hooks to accurately record tokens.
- [ ] **Calculate and Log Actual Cost:** Update the request logger to compute `cost_usd` based on the provider's pricing (`input_cost_per_1k` / `output_cost_per_1k`) combined with correct token counts.
- [x] **Implement Real OAuth2 Token Refresh:** The `credential-vault` background task currently uses a mock implementation. We must implement actual HTTP POST requests to provider `token_url`s to obtain new `access_token`s. *(Completed previously in `credential-vault` main.py)*
- [ ] **Upgrade Encryption Standard:** Migrate from Fernet (AES-128-CBC) to AES-256-GCM symmetric encryption for credential storage, actively utilizing the existing `iv` database column.
- [ ] **Expand Provider-Specific Quota Polling:** Build real quota pollers for remaining providers (Google Vertex/Gemini, Groq, Mistral, Cohere) beyond the basic OpenAI/Anthropic implementations.

## 3. GUI & User Experience (Medium Priority)
Once the backend metrics are fully reliable, the React/Vite dashboard needs crucial data visualization upgrades:

- [x] **Setup Wizard (GUI + CLI):** A guided multi-step wizard for provider onboarding, credential addition, model selection, routing strategy configuration, and brain setup. Available at `/wizard` in the dashboard and `./unifyroute wizard` in the CLI. *(Completed in setup wizard module)*
- [ ] **Live Usage & Quota Visualizations:** Integrate Recharts to provide line charts for daily token usage and radial gauges for real-time quota tracking per credential.
- [ ] **Cost Dashboards & Banners:** Build UI elements conveying daily/monthly cost aggregates, along with actionable alert banners for credentials running low on quota.
- [ ] **Routing Strategy Editor:** Replace the basic textarea for `routing.yaml` with an active Monaco editor featuring YAML syntax validation.
- [ ] **Logging Polish:** Add CSV export capabilities to the "Sessions & Logs" screen and establish a Tier-based filtering system.

## 4. Security, Completeness & Deployment (Medium Priority)
- [ ] **GUI Session Authentication:** Switch the GUI away from API-key auth to a more secure RS256 JWT cookie-based session approach.
- [ ] **Gateway Rate Limiting:** Introduce per-client/API-key rate-limiting middleware to prevent abuse and overspending upstream.
- [ ] **`/v1/completions` Endpoint:** Add the standard text completion endpoint, extending compatibility with older tools that don't use the chat format.
- [ ] **Full-Stack Containerization:** Write Dockerfiles for internal Python services (`api-gateway`, `credential-vault`, `quota-poller`) and the `gui` to ensure the entire stack launches efficiently via `docker-compose`.

## 5. Comprehensive Test Suite ✅ (Completed)

A run-after-every-change regression suite. Run with `./run-tests.sh`.

### Test Philosophy
- **Unit tests** (`--unit`): Fast, mocked, no live server. Cover business logic in isolation.
- **Integration tests** (`--integration`): Hit the live gateway on `localhost:6565`. Cover full request/response cycles with the real database.

### How to Run
```bash
./run-tests.sh            # All tests (unit + integration)
./run-tests.sh --unit     # Unit tests only (no server needed)
./run-tests.sh --integration  # Integration tests only
```
Or use the agent workflow: `/run-tests`

### Unit Test Files (no server required)
| File | Coverage |
|---|---|
| `test_brain_health.py` | brain.health endpoint checks, provider health detection |
| `test_brain_importer.py` | brain.importer YAML/JSON import parsing |
| `test_brain_ranker.py` | brain.ranker scoring, priority/health ordering |
| `test_brain_selector.py` | brain.selector BrainSelection, empty/unhealthy/success paths |
| `test_brain_tester.py` | brain.tester credential testing, Redis health cache |
| `test_router_core.py` | router.core Candidate class, task-type detection, auto-tier selection |
| `test_shared_security.py` | shared.security encrypt/decrypt roundtrip, IV uniqueness, corruption |
| `test_stream_cost_unit.py` | Streaming token accumulation cost calculation |

### Integration Test Files (requires live gateway)
| File | Coverage |
|---|---|
| `test_auth.py` | Token validation, admin/API scope enforcement |
| `test_providers.py` | Provider CRUD (create/update/delete/seed) |
| `test_credentials.py` | Credential CRUD, secret masking, verify/quota |
| `test_keys.py` | API key lifecycle (create/delete/expiry) |
| `test_key_reveal.py` | Key reveal endpoint |
| `test_key_update.py` | Key update endpoint |
| `test_admin_models.py` | Model CRUD with tier/cost fields |
| `test_models_endpoint.py` | Public /v1/models listing |
| `test_chat_completions.py` | Chat completion routing, virtual model aliases |
| `test_routing_config.py` | Routing YAML get/update |
| `test_routing_tiers.py` | Tier routing isolation (lite/base/thinking) |
| `test_brain_api.py` | Brain API endpoints (status/assign/test/rank) |
| `test_wizard_api.py` | Setup wizard endpoints |
| `test_oauth_routes.py` | OAuth start/callback routes |
| `test_gateway_health.py` | Gateway smoke tests (all major endpoints exist) |
| `test_connection_security.py` | Token lifecycle, CORS |
| `test_quota_pollers.py` | Provider quota polling |
| `test_sync_models.py` | Provider model sync |
| `test_fireworks.py` | Fireworks adapter integration |

---

## 6. Setup Wizard Module (Completed ✅)

A new guided onboarding wizard added as a dedicated module. Components:

- **`api-gateway/src/api_gateway/routes/wizard.py`** — 3 new REST endpoints (`GET /admin/wizard/providers/available`, `GET /admin/wizard/models/{name}`, `POST /admin/wizard/onboard`).
- **`api-gateway/src/api_gateway/routes/model_catalog.py`** — Static catalog of popular models for 12 providers (OpenAI, Anthropic, Google, Groq, UnifyRouter, Mistral, DeepSeek, xAI, Together, Fireworks, Cerebras, Perplexity).
- **`scripts/wizard.py`** — Interactive terminal wizard (color ANSI UI, HTTP calls to gateway).
- **`unifyroute wizard`** — New CLI command delegating to `scripts/wizard.py`.
- **`gui/src/pages/SetupWizard.tsx`** — 6-step wizard GUI page (Provider → Credentials → Models → Routing → Brain → Summary).
- **`gui/src/lib/wizard.ts`** — TypeScript API helpers for wizard endpoints.
- **`tests/test_wizard_api.py`** — Integration tests for all 3 wizard endpoints.

---

## Action Plan for the Immediate Next Round
1. Confirm alignment on this master plan.
2. We will immediately begin by tackling **Section 2** (Cost tracking and Streaming token tracking) since accurate metrics are a prerequisite for the Dashboard enhancements in Section 3.
