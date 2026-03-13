# UnifyRoute — Usage & CLI Reference

Complete reference for all CLI commands, API endpoints, admin tasks, and operational procedures.

## CLI Quick Reference

```bash
# Setup & lifecycle
./unifyroute setup              # First-time interactive setup
./unifyroute setup refresh      # Re-sync deps, rebuild GUI, run migrations
./unifyroute setup uninstall    # Remove local files
./unifyroute wizard             # Interactive provider/routing wizard

./unifyroute start              # Start gateway (background)
./unifyroute stop               # Stop gateway
./unifyroute restart            # Restart gateway

# Token management
./unifyroute get token [all|admin|api]
./unifyroute create token [admin|api]
./unifyroute update token <id> <new-label>

# Credential operations
./unifyroute import-keys <file.json>

./unifyroute help               # Show all commands
```

> **Windows**: replace `./unifyroute` with `unifyroute.bat` or `python unifyroute`.

---


---

## Table of Contents

1. [unifyroute CLI](#unifyroute-cli)
2. [Script Reference](#script-reference)
3. [Database Migrations](#database-migrations)
4. [API Endpoints](#api-endpoints)
5. [Using with OpenAI SDKs](#using-with-openai-sdks)
6. [Admin Tasks via Dashboard](#admin-tasks-via-dashboard)
7. [Docker Commands](#docker-commands)
8. [Routing Configuration](#routing-configuration)
9. [Credential Management](#credential-management)
10. [Logs & Monitoring](#logs--monitoring)

---

## unifyroute CLI

The `unifyroute` launcher script is the main entrypoint. Run it from the project root.

```bash
./unifyroute <command>
```

| Command | Description |
|---------|-------------|
| `./unifyroute setup` | Full one-time setup (deps, DB migrations, admin key) |
| `./unifyroute start` | Start the gateway (sources `.env`, starts uvicorn) |

### `./unifyroute setup`

Runs `scripts/setup.sh`:
- Starts Docker containers (postgres + redis)
- Installs Python packages via `uv sync`
- Builds the GUI with `npm install && npm run build`
- Runs Alembic migrations (`alembic upgrade head`)
- Creates an initial admin `sk-...` key

```bash
./unifyroute setup
```

Expected output:
```
🚀 Starting OPENROUTER Setup...
🐳 Starting Docker containers...
📦 1. Setting up Backend Environment...
🌐 2. Building Frontend Application...
🔑 3. Generating Initial Admin Key...
✅ Gateway Key Created Successfully!
============================================================
RAW TOKEN:
sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
============================================================
⚠️ SAVE THIS TOKEN NOW
```

### `./unifyroute start`

Runs `scripts/start-gateway.sh` — sources `.env` and starts the unified launcher:

```bash
./unifyroute start
```

The gateway listens on `http://HOST:PORT` (default `http://0.0.0.0:<app_port>`).

---

## Script Reference

All scripts are in `scripts/`. Run from the project root using `uv run` or directly.

---

### `scripts/setup.sh`

Full project setup. Idempotent — safe to run again after updates.

```bash
bash scripts/setup.sh
```

---

### `scripts/start-gateway.sh`

Start the gateway in foreground mode. Sources `.env` automatically.

```bash
bash scripts/start-gateway.sh
# Override port/host:
PORT=9000 HOST=127.0.0.1 bash scripts/start-gateway.sh
```

---

### `scripts/create-key.py`

Create a new Gateway API key (for clients, integrations, or additional admins).

```bash
uv run --package shared python scripts/create-key.py "My Key Label" --scopes admin
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `label` | ✅ | Human-readable name for the key |
| `--scopes` | — | Space-separated list of scopes (e.g. `admin`) |

**Examples:**

```bash
# Admin-level key (full access)
uv run --package shared python scripts/create-key.py "Admin Key" --scopes admin

# Read-only client key (no scopes = inference only)
uv run --package shared python scripts/create-key.py "Client App Key"

# CI/CD key with specific scope
uv run --package shared python scripts/create-key.py "CI Pipeline" --scopes inference
```

> The `sk-...` token is shown only once. Copy it before closing the terminal.

---

### `scripts/list-keys.py`

List all gateway keys (labels, scopes, enabled status). Does NOT show plaintext tokens.

```bash
uv run --package shared python scripts/list-keys.py
```

Output:
```
Label                          | Scopes               | Enabled
-----------------------------------------------------------------
Admin Setup 1234567890         | admin                | True
Client App Key                 | None                 | True
```

---

### `scripts/cleanup.sh`

Stop all processes and remove all data. **Destructive — removes DB volumes.**

```bash
bash scripts/cleanup.sh
```

What it does:
1. Kills any running `launcher.main:app` processes
2. Stops and disables the systemd service (if installed)
3. Runs `docker compose down -v` to remove containers and volumes
4. Deletes `data/`, `.venv/`, `gui/node_modules/`, `gui/dist/`

---

## Database Migrations

Managed with Alembic. Run from the project root.

```bash
# Apply all pending migrations (run after git pull)
uv run --package shared alembic upgrade head

# Check current schema version
uv run --package shared alembic current

# Show migration history
uv run --package shared alembic history --verbose

# Create a new migration (after changing shared/src/shared/models.py)
uv run --package shared alembic revision --autogenerate -m "add column foo to providers"

# Upgrade to specific revision
uv run --package shared alembic upgrade <revision_id>

# Downgrade one step
uv run --package shared alembic downgrade -1

# Downgrade to base (empty schema)
uv run --package shared alembic downgrade base
```

---

## API Endpoints

All endpoints require the `Authorization: Bearer sk-...` header unless noted.

### OpenAI-Compatible Inference

#### `POST /api/v1/chat/completions`

Chat completion with automatic tier-based routing and failover.

```bash
curl http://localhost:<app_port>/api/v1/chat/completions \
  -H "Authorization: Bearer sk-your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "base",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Explain quantum entanglement simply."}
    ],
    "temperature": 0.7,
    "max_tokens": 512
  }'
```

**Streaming:**

```bash
curl http://localhost:<app_port>/api/v1/chat/completions \
  -H "Authorization: Bearer sk-your-key" \
  -H "Content-Type: application/json" \
  -d '{"model": "lite", "messages": [{"role": "user", "content": "Hi"}], "stream": true}'
```

**Available `model` values (tier aliases defined in `routing.yaml`):**

| Alias | Default Models | Strategy |
|-------|---------------|----------|
| `lite` | Groq, Gemini Flash, Claude Haiku | cheapest_available |
| `base` | GPT-4o, Claude Sonnet, Gemini Pro | cheapest_available |
| `thinking` | o1, Claude Opus, Gemini 2.5 Pro | highest_quota |

#### `POST /api/v1/completions`

Text completion (OpenAI legacy format). Delegates to the chat endpoint internally.

```bash
curl http://localhost:<app_port>/api/v1/completions \
  -H "Authorization: Bearer sk-your-key" \
  -H "Content-Type: application/json" \
  -d '{"model": "lite", "prompt": "The capital of France is", "max_tokens": 20}'
```

#### `GET /api/v1/models`

List all available model aliases from the database.

```bash
curl http://localhost:<app_port>/api/v1/models \
  -H "Authorization: Bearer sk-your-key"
```

---

### Admin — Providers

```bash
# List all providers
curl http://localhost:<app_port>/admin/providers -H "Authorization: Bearer sk-..."

# Create a provider
curl -X POST http://localhost:<app_port>/admin/providers \
  -H "Authorization: Bearer sk-..." \
  -H "Content-Type: application/json" \
  -d '{"name": "groq", "display_name": "Groq", "auth_type": "api_key", "enabled": true}'

# Seed the full provider catalog (~20 providers)
curl -X POST http://localhost:<app_port>/admin/providers/seed \
  -H "Authorization: Bearer sk-..."

# Update a provider
curl -X PUT http://localhost:<app_port>/admin/providers/<provider-uuid> \
  -H "Authorization: Bearer sk-..." \
  -d '{"enabled": false}'

# Delete a provider
curl -X DELETE http://localhost:<app_port>/admin/providers/<provider-uuid> \
  -H "Authorization: Bearer sk-..."
```

---

### Admin — Credentials

```bash
# List credentials (grouped by provider)
curl http://localhost:<app_port>/admin/credentials -H "Authorization: Bearer sk-..."

# Add an API key credential
curl -X POST http://localhost:<app_port>/admin/credentials \
  -H "Authorization: Bearer sk-..." \
  -H "Content-Type: application/json" \
  -d '{
    "provider_id": "<provider-uuid>",
    "label": "My OpenAI Key",
    "auth_type": "api_key",
    "secret": "sk-openai-actual-api-key"
  }'

# Verify a credential (test the key)
curl -X POST http://localhost:<app_port>/admin/credentials/<cred-uuid>/verify \
  -H "Authorization: Bearer sk-..."

# Check quota for a credential
curl http://localhost:<app_port>/admin/credentials/<cred-uuid>/quota \
  -H "Authorization: Bearer sk-..."

# Delete a credential
curl -X DELETE http://localhost:<app_port>/admin/credentials/<cred-uuid> \
  -H "Authorization: Bearer sk-..."
```

---

### Admin — Models

```bash
# List all models
curl http://localhost:<app_port>/admin/models -H "Authorization: Bearer sk-..."

# Sync models from provider API
curl -X POST http://localhost:<app_port>/admin/providers/<provider-uuid>/sync-models \
  -H "Authorization: Bearer sk-..."

# Update a model (e.g., set tier and pricing)
curl -X PUT http://localhost:<app_port>/admin/models/<model-uuid> \
  -H "Authorization: Bearer sk-..." \
  -H "Content-Type: application/json" \
  -d '{
    "tier": "base",
    "input_cost_per_1k": 0.003,
    "output_cost_per_1k": 0.015,
    "enabled": true
  }'

# Delete a model
curl -X DELETE http://localhost:<app_port>/admin/models/<model-uuid> \
  -H "Authorization: Bearer sk-..."
```

---

### Admin — Gateway Keys

```bash
# List keys (no plaintext tokens shown)
curl http://localhost:<app_port>/admin/keys -H "Authorization: Bearer sk-..."

# Create a new key
curl -X POST http://localhost:<app_port>/admin/keys \
  -H "Authorization: Bearer sk-..." \
  -H "Content-Type: application/json" \
  -d '{"label": "Production App", "scopes": ["inference"]}'

# Delete a key
curl -X DELETE http://localhost:<app_port>/admin/keys/<key-uuid> \
  -H "Authorization: Bearer sk-..."
```

---

### Admin — Logs & Usage

```bash
# Paginated request logs (filter by provider / status)
curl "http://localhost:<app_port>/admin/logs?page=1&limit=50" \
  -H "Authorization: Bearer sk-..."

curl "http://localhost:<app_port>/admin/logs?provider=openai&status=error" \
  -H "Authorization: Bearer sk-..."

# Stats summary (last 24h)
curl "http://localhost:<app_port>/admin/logs/stats?hours=24" \
  -H "Authorization: Bearer sk-..."

# Hourly token timeline (for dashboard chart)
curl "http://localhost:<app_port>/admin/logs/timeline?hours=24" \
  -H "Authorization: Bearer sk-..."

# Usage by provider (cost + tokens)
curl "http://localhost:<app_port>/admin/usage?days=30" \
  -H "Authorization: Bearer sk-..."
curl "http://localhost:<app_port>/admin/usage?days=7&provider=openai" \
  -H "Authorization: Bearer sk-..."
```

---

### Admin — Routing Config

```bash
# Get current routing.yaml content
curl http://localhost:<app_port>/admin/routing -H "Authorization: Bearer sk-..."

# Update routing config (full YAML replacement)
curl -X POST http://localhost:<app_port>/admin/routing \
  -H "Authorization: Bearer sk-..." \
  -H "Content-Type: application/json" \
  -d '{"yaml_content": "tiers:\n  lite:\n    strategy: cheapest_available\n    models:\n      - {provider: groq, model: llama3-8b-8192}\n"}'
```

---

### OAuth Flows

```bash
# Start Google Antigravity (gemini-cli) OAuth — returns a browser URL
curl http://localhost:<app_port>/oauth/google-antigravity/start \
  -H "Authorization: Bearer sk-..."
# Open the redirect_url in your browser, complete sign-in, token is stored automatically

# Start a generic OAuth2 provider flow
curl http://localhost:<app_port>/oauth/start/<provider-uuid> \
  -H "Authorization: Bearer sk-..."
```

---

## Using with OpenAI SDKs

### Python (openai SDK)

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:<app_port>/api/v1",
    api_key="sk-your-unifyroute-gateway-key"
)

response = client.chat.completions.create(
    model="base",   # uses the 'base' tier
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.choices[0].message.content)
```

### TypeScript / Node.js

```typescript
import OpenAI from 'openai';

const client = new OpenAI({
  baseURL: 'http://localhost:<app_port>/api/v1',
  apiKey: 'sk-your-unifyroute-gateway-key',
});

const response = await client.chat.completions.create({
  model: 'lite',
  messages: [{ role: 'user', content: 'What is 2+2?' }],
});
```

### curl (streaming)

```bash
curl http://localhost:<app_port>/api/v1/chat/completions \
  -H "Authorization: Bearer sk-your-key" \
  -H "Content-Type: application/json" \
  --no-buffer \
  -d '{"model": "thinking", "messages": [{"role": "user", "content": "Solve P vs NP"}], "stream": true}'
```

---

## Admin Tasks via Dashboard

Access the dashboard at `http://localhost:<app_port>` after starting the gateway.

| Dashboard Page | What you can do |
|---------------|----------------|
| **Dashboard** | View real-time token charts (6h/24h/48h), cost today, expiring token alerts |
| **Providers** | Add/edit/delete providers, seed full catalog with one click |
| **Credentials** | Add API keys, connect OAuth2 (Google Antigravity), verify/test keys |
| **Models** | View all synced models, assign tiers/pricing, enable/disable, delete |
| **Routing** | Edit `routing.yaml` live with instant save (hot-reloads in router) |
| **Usage & Quota** | Per-provider cost & token charts, OAuth credential health gauges (auto-refresh 30s) |
| **Request Logs** | Filter by provider/status/tier, export to CSV |
| **Settings** | Create/delete gateway keys |

---

## Docker Commands

```bash
# Start all services
docker compose up -d

# Start only data stores (for dev mode)
docker compose up -d postgres redis

# View logs for a specific service
docker compose logs -f api-gateway
docker compose logs -f credential-vault
docker compose logs -f quota-poller

# Restart a single service
docker compose restart api-gateway

# Stop everything (preserve data)
docker compose down

# Stop and delete all volumes (WIPES DATABASE)
docker compose down -v

# Rebuild images after code changes
docker compose build
docker compose up -d

# Run a one-off command in a service
docker compose exec api-gateway bash
docker compose exec postgres psql -U postgres -d unifyroute
```

---

## Routing Configuration

The routing config lives in `router/routing.yaml` and hot-reloads automatically when changed.

### Structure

```yaml
tiers:
  <alias>:
    strategy: cheapest_available | highest_quota
    min_quota_remaining: 100      # skip candidates with less than this quota
    models:
      - provider: openai
        model: gpt-4o-mini
      - provider: groq
        model: llama3-8b-8192
```

### Strategies

| Strategy | Sorts candidates by |
|----------|-------------------|
| `cheapest_available` | cost ↑, then quota ↓ |
| `highest_quota` | quota ↓, then cost ↑ |

### Edit from Dashboard

Go to **Routing Strategy** page, edit the YAML inline, and click **Save**. Changes take effect within 1-2 seconds (watchdog detects file change).

### Edit from CLI

```bash
# Edit directly
nano router/routing.yaml

# Apply via API
curl -X POST http://localhost:<app_port>/admin/routing \
  -H "Authorization: Bearer sk-..." \
  -H "Content-Type: application/json" \
  -d '{"yaml_content": "<your-yaml>"}'
```

---

## Credential Management

### Adding an API Key Provider

1. Dashboard → **Providers** → **Add Provider**
2. Name: `openai`, Auth Type: `API Key`
3. Dashboard → **Credentials** → **Add API Key**
4. Select provider, paste `sk-openai-...`, click **Verify**

### Adding OAuth2 (Google / Gemini)

1. Dashboard → **Credentials** → **Connect Google Antigravity**
2. Authorize in the popup window (uses Google's gemini-cli OAuth app)
3. Token is stored automatically, refresh runs every 10 minutes

### Credential Vault

The `credential-vault` service (port 8001) decrypts credentials on demand and refreshes OAuth tokens. It runs with its own scheduler — check logs if a refresh fails:

```bash
docker compose logs -f credential-vault
# or
uv run --package credential-vault uvicorn credential_vault.main:app --port 8001
```

---

## Logs & Monitoring

### API Stats

```bash
# Quick summary
curl "http://localhost:<app_port>/admin/logs/stats?hours=24" \
  -H "Authorization: Bearer sk-..." | python3 -m json.tool
```

### Export Logs to CSV

From the **Request Logs** page in the dashboard, apply filters then click **Export CSV**. The file is named `unifyroute-logs-YYYY-MM-DD.csv`.

### Check Provider Costs

```bash
curl "http://localhost:<app_port>/admin/usage?days=7" \
  -H "Authorization: Bearer sk-..." | python3 -m json.tool
```

### Monitor Docker Services

```bash
# Resource usage
docker stats

# Service health
docker compose ps
```

### systemd Service Logs

```bash
sudo journalctl -u unifyroute -f -n 100
```
