# Installation Guide

This guide walks you through setting up **OPENROUTER** from scratch on a Linux or macOS machine for both local development and production deployment.

---

## Prerequisites

| Tool | Minimum Version | Install |
|------|----------------|---------|
| Python | 3.11+ | [python.org](https://python.org) |
| `uv` | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node.js | 18+ | [nodejs.org](https://nodejs.org) |
| npm | 9+ | Bundled with Node.js |
| Docker | 20+ | [docs.docker.com](https://docs.docker.com) |
| Docker Compose | v2 plugin | Bundled with Docker Desktop |
| PostgreSQL | 14+ | Via Docker (recommended) or native |
| Redis | 6+ | Via Docker (recommended) or native |

> **Note:** PostgreSQL and Redis can be started via the included `docker-compose.yml` — no separate installation needed if you have Docker.

---

## Step 1 — Clone the Repository

```bash
git clone <repo-url> unifyroute
cd unifyroute
```

---

## Step 2 — Configure Environment Variables

```bash
cp sample.env .env
```

Edit `.env` with your values:

```ini
# Required
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/unifyroute
VAULT_MASTER_KEY=<generate below>
REDIS_URL=redis://localhost:6379/0

# Optional
PORT=<app_port>
HOST=0.0.0.0
API_BASE_URL=http://localhost:<app_port>
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
```

### Generating a VAULT_MASTER_KEY

The master key encrypts all provider credentials at rest. Generate one with:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copy the output and set it as `VAULT_MASTER_KEY` in your `.env`.

> ⚠️ **Keep this key secret and back it up.** If you lose it, all stored credentials become unrecoverable.

---

## Step 3 — Start the Database and Redis

Using Docker (recommended):

```bash
docker compose up -d postgres redis
```

Or if you have PostgreSQL and Redis installed natively, make sure they're running and update `DATABASE_URL` / `REDIS_URL` in `.env` accordingly.

---

## Step 4 — Run Setup

The setup script installs all Python and Node.js dependencies, runs database migrations, and creates your first admin API key.

```bash
./unifyroute setup
```

This does:
1. **`docker compose up -d`** — starts Postgres + Redis if `docker-compose.yml` is present
2. **`uv sync`** — installs all Python packages into a virtual environment
3. **`npm install && npm run build`** (in `gui/`) — builds the React dashboard
4. **`alembic upgrade head`** — applies all database migrations
5. **Generates an admin `sk-...` key** — printed to terminal once

> ⚠️ **Copy the `sk-...` token immediately.** It is shown only once and cannot be recovered.

---

## Step 5 — Start the Gateway

```bash
./unifyroute start
```

Open **http://localhost:<app_port>** in your browser, enter the `sk-...` token from setup.

---

## Step 6 — Add Your First Provider

1. Go to **Providers** → click **Add Provider**
2. Select a provider (e.g. `openai`), set display name
3. Go to **Credentials** → click **Add API Key**
4. Paste your provider API key and click **Verify**
5. Go to **Models** → click **Sync Models** for the provider
6. Done — make your first request:

```bash
curl http://localhost:<app_port>/api/v1/chat/completions \
  -H "Authorization: Bearer sk-your-gateway-key" \
  -d '{"model": "base", "messages": [{"role": "user", "content": "Hi!"}]}'
```

---

## Production Deployment

### Option A — Docker Compose (Recommended)

Runs all services containerized:

```bash
# Set your real environment variables first
export VAULT_MASTER_KEY="..."
export JWT_SECRET="$(openssl rand -hex 32)"

docker compose up -d
```

Services and ports:

| Service | Port | Description |
|---------|------|-------------|
| `api-gateway` | 8000 | Main API + dashboard |
| `credential-vault` | 8001 | Internal credential service |
| `quota-poller` | — | Background jobs |
| `gui` | 3000 | Nginx-served dashboard |
| `postgres` | 5433 | Database |
| `redis` | 6379 | Cache + routing state |

Check logs:
```bash
docker compose logs -f api-gateway
docker compose logs -f credential-vault
```

### Option B — systemd Service

For running OPENROUTER on bare metal that starts on boot:

1. Edit `scripts/unifyroute.service`:
   - Update `User`, `Group`, and `WorkingDirectory` to match your system
   - Update `ExecStart` to the absolute path of `uv`

2. Install and enable:

```bash
sudo cp scripts/unifyroute.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable unifyroute.service
sudo systemctl start unifyroute.service
```

3. Check status and logs:

```bash
sudo systemctl status unifyroute.service
sudo journalctl -u unifyroute -f
```

---

## Development Mode (Hot-Reload)

For active development, start background services in Docker and run the application code natively:

```bash
# Terminal 1 — data stores
docker compose up -d postgres redis

# Terminal 2 — API Gateway (hot-reload)
uv run --package api-gateway uvicorn api_gateway.main:app --reload --port <app_port>

# Terminal 3 — GUI dev server
cd gui && npm run dev

# Terminal 4 — Credential Vault (optional)
uv run --package credential-vault uvicorn credential_vault.main:app --port 8001

# Terminal 5 — Quota Poller (optional)
uv run --package quota-poller python -m quota_poller.main
```

Or use the Docker dev override for everything containerized with hot-reload:

```bash
docker compose up  # loads docker-compose.override.yml automatically
```

---

## Database Migrations

Migrations are managed with Alembic:

```bash
# Apply all pending migrations
uv run --package shared alembic upgrade head

# Check current migration version
uv run --package shared alembic current

# Create a new migration after changing models
uv run --package shared alembic revision --autogenerate -m "describe your change"

# Roll back one migration
uv run --package shared alembic downgrade -1
```

---

## Cleanup and Uninstall

```bash
# Stop everything and remove all data
./scripts/cleanup.sh
```

Or manually:

```bash
# Stop Docker services
docker compose down -v

# Stop standalone processes
pkill -f "launcher.main:app"

# Remove build artifacts and data
rm -rf gui/dist gui/node_modules .venv data/

# Remove the directory
cd .. && rm -rf unifyroute/
```

---

## Troubleshooting

| Problem | Solution |
|---------|---------|
| `ConnectionRefusedError: port 5433` | Run `docker compose up -d postgres` |
| `VAULT_MASTER_KEY not set` | Set it in `.env` and re-run `./unifyroute setup` |
| `No valid routing candidates found` | Add a provider + credential, then sync models |
| OAuth callback fails | Set `API_BASE_URL` to your externally accessible URL |
| GUI shows "Unauthorized" | Check the `sk-...` token in dashboard settings |
| `alembic not found` | Run `uv sync` first to install all deps |
