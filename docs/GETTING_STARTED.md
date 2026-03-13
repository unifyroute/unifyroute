# Getting Started with UnifyRoute

This guide covers first-time configuration and day-to-day usage after a successful `setup`.  
For installation instructions, see [INSTALLATION.md](INSTALLATION.md).

---

## 1. Clone & Configure

```bash
git clone https://github.com/unifyroute/UnifyRoute.git
cd UnifyRoute
cp sample.env .env   # Windows: copy sample.env .env
```

Review `.env` — defaults work for local development. The key variables:

| Variable | Default | Description |
|---|---|---|
| `SQLITE_PATH` | `data/unifyroute.db` | SQLite database location |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `PORT` | `6565` | Gateway listen port |
| `HOST` | `localhost` | Gateway bind address |
| `API_BASE_URL` | `http://localhost:6565` | Public base URL (used in OAuth callbacks) |
| `MASTER_PASSWORD` | (set during setup) | Admin password for GUI and CLI |
| `VAULT_MASTER_KEY` | (auto-generated) | AES encryption key for credentials |
| `JWT_SECRET` | (auto-generated) | Signing key for auth tokens |
| `GOOGLE_OAUTH_CLIENT_ID` | — | Google OAuth client ID |
| `GOOGLE_OAUTH_CLIENT_SECRET` | — | Google OAuth client secret |

---

## 2. Run Setup

```bash
./unifyroute setup          # Linux / macOS
unifyroute.bat setup        # Windows
```

The wizard takes ~2 minutes and sets up the venv, installs deps, builds the GUI, and runs the database migration.

---

## 3. Start

```bash
./unifyroute start
unifyroute.bat start        # Windows
```

Default access points:
- **Dashboard / GUI** → `http://localhost:6565`
- **OpenAI-compatible API** → `http://localhost:6565/api/v1`

---

## 4. Interactive Wizard (Recommended First Run)

```bash
./unifyroute wizard
```

The wizard guides you through:
1. Adding your first AI provider (OpenAI, Anthropic, Google, etc.)
2. Storing credentials securely in the vault
3. Configuring routing tiers (`lite`, `base`, `thinking`)

---

## 5. Verify the API

```bash
curl http://localhost:6565/api/v1/models
```

You should receive a JSON list of enabled provider models.

---

## 6. Connect an OpenAI-Compatible Client

Point any OpenAI SDK client to UnifyRoute:

```bash
OPENAI_API_BASE=http://localhost:6565/api/v1
OPENAI_API_KEY=<your-gateway-api-key>
```

Model aliases:
| Alias | Routes to | Example models |
|---|---|---|
| `lite` | Cheapest available | gpt-4o-mini, claude-haiku, gemini-flash |
| `base` | Balanced | gpt-4o, claude-3-5-sonnet, gemini-pro |
| `thinking` | Highest-capability | o1, claude-3-7-sonnet, gemini-thinking |

---

## 7. Routing Configuration

Routing is defined in `router/routing.yaml`. You can edit it via the GUI (*Routing Strategy* page) or directly. Example:

```yaml
tiers:
  lite:
    strategy: cheapest_available
    min_quota_remaining: 5000
    fallback_on: [429, 503, timeout]
    models:
      - {provider: openai, model: gpt-4o-mini}
      - {provider: anthropic, model: claude-haiku-3-5-20241022}
  base:
    strategy: cheapest_available
    models:
      - {provider: openai, model: gpt-4o}
      - {provider: anthropic, model: claude-3-5-sonnet-20241022}
  thinking:
    strategy: highest_quota
    models:
      - {provider: openai, model: o1}
      - {provider: anthropic, model: claude-3-7-sonnet-20250219}
```

---

## 8. Token Management

```bash
# List all tokens
./unifyroute get token

# Create a standard API token
./unifyroute create token api

# Create an admin token
./unifyroute create token admin
```

---

*See also: [USAGE.md](USAGE.md) for the full CLI reference · [ARCHITECTURE.md](ARCHITECTURE.md) for internals*
