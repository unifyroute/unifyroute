# UnifyRoute Migration Guide

Welcome to **UnifyRoute** — a rebranded and simplified version of the LLM Gateway project optimized for single-database deployments and maximum cross-platform compatibility.

## What Changed

This rebranded version includes several key modifications from the original LLMWay project:

### 1. Database: SQLite Only
- **Removed PostgreSQL Support**: All PostgreSQL dependencies have been stripped out
- **Database Backend**: UnifyRoute now uses SQLite exclusively via `aiosqlite`
- **Removed Dependencies**: `asyncpg`, `psycopg2-binary`, `libpq-dev` are no longer included
- **Benefit**: Zero external database service required; perfect for local development and small-scale deployments

### 2. Cross-Platform Support
- **Windows, Linux, macOS**: The launcher script now handles all three platforms natively
- **Path Handling**: Cross-platform-compatible path handling throughout
- **Process Management**:
  - Windows: Uses `taskkill` for process termination
  - Linux/macOS: Uses `pkill` for process termination
  - Systemd services: Linux only (gracefully skipped on Windows/macOS)
- **No Bash Dependency**: The startup process no longer relies on bash scripts on non-Unix systems

### 3. Rebranding
- **Project Name**: Changed from "OPENROUTER" to "UnifyRoute"
- **CLI Tool**: Now use `./unifyroute` instead of `./unifyroute`
- **Docker Containers**: Container names updated (e.g., `unifyroute_api_gateway` instead of `unifyroute_api_gateway`)
- **Configuration**: Environment variables and file paths updated throughout

## Quick Start

### 1. Clone and Setup
```bash
cd UnifyRoute
cp sample.env .env
# Edit .env if needed (defaults work for local development)
./unifyroute setup
```

### 2. Run the Application
```bash
./unifyroute start
```

The application will start on `http://localhost:6565` by default.

### 3. Access the Dashboard
- **URL**: `http://localhost:6565`
- **Login**: Use the master password you set during setup

## Configuration

### Environment Variables
Key variables for UnifyRoute:

| Variable | Default | Description |
|----------|---------|-------------|
| `SQLITE_PATH` | `data/unifyroute.db` | SQLite database file location |
| `PORT` | `6565` | Application port |
| `HOST` | `localhost` | Bind address |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `VAULT_MASTER_KEY` | (generated) | Encryption key for credentials |
| `MASTER_PASSWORD` | (set by user) | Master password for authentication |

### Database Path
By default, UnifyRoute stores its SQLite database in `data/unifyroute.db`. This can be customized via the `SQLITE_PATH` environment variable.

## Available Commands

```bash
# Interactive setup
./unifyroute setup

# Setup wizard for providers and routing
./unifyroute wizard

# Start the application
./unifyroute start

# Stop the application
./unifyroute stop

# Restart the application
./unifyroute restart

# List API tokens
./unifyroute get token

# Create a new API token
./unifyroute create token [admin|api]

# Update a token label
./unifyroute update token <id> <new_label>

# Bulk import provider API keys
./unifyroute import-keys <file.json>

# Show help
./unifyroute help
```

## Platform-Specific Notes

### Windows
- The launcher handles file paths correctly with backslashes
- Process management uses Windows Task Manager (`taskkill`)
- Systemd services are not available (only applicable on Linux)
- All paths in `.env` should use forward slashes

### Linux/macOS
- Full systemd service support for production deployments (Linux only)
- Process management via `pkill` command
- Standard Unix file paths with forward slashes

## Docker Deployment

UnifyRoute includes Docker support for containerized deployment:

```bash
# Build and start all services
docker-compose up --build

# Stop all services
docker-compose down

# Remove volumes (and reset database)
docker-compose down -v
```

The Docker setup includes:
- API Gateway service
- Credential Vault service
- Quota Poller service
- Redis service
- GUI service (React frontend)

## Testing

Run the test suite with:

```bash
./run-tests.sh              # All tests
./run-tests.sh --unit       # Unit tests only
./run-tests.sh --integration # Integration tests only
```

## Troubleshooting

### Database Issues
If you encounter database-related errors:
1. Check that `data/` directory is writable
2. Verify the `SQLITE_PATH` setting points to a valid location
3. Review logs in `logs/api.log`

### Process Termination
If the application doesn't stop cleanly:
- Linux: `pkill -f launcher.main:app`
- Windows: `taskkill /IM python.exe /F`
- macOS: `pkill -f launcher.main:app`

### Permissions
On Linux/macOS, ensure the UnifyRoute directory is accessible:
```bash
chmod -R 755 UnifyRoute
```

## Architecture

```
Client (OpenAI-compatible SDK)
         │
         ▼ POST /api/v1/chat/completions
┌────────────────────────────────┐
│        API Gateway :8000       │  ← Auth, routing, logging
│   FastAPI + litellm + Redis    │
└────────────────────────────────┘
         │
    ┌────┴────┐
    │ Router  │  ← Tier config (routing.yaml), candidate ranking
    └────┬────┘
         │
   ┌─────▼──────┐   ┌───────────────┐   ┌──────────────┐
   │  Provider 1│   │  Provider 2   │   │  Provider N  │
   │  (OpenAI)  │   │  (Anthropic)  │   │  (Groq…)     │
   └────────────┘   └───────────────┘   └──────────────┘

Local Services
  credential-vault :8001  → Token encryption/decryption
  redis                   → Failure tracking and caching
  (SQLite)                → Config, credentials, logs
```

## Migration from LLMWay

If you're migrating from the original LLMWay project:

1. **Database**: Back up your PostgreSQL database if you have production data
2. **Configuration**: Update your `.env` file to use `SQLITE_PATH` instead of `DATABASE_URL`
3. **CLI Commands**: Replace `./unifyroute` with `./unifyroute` in all scripts
4. **Docker Services**: Update docker-compose references from `unifyroute_*` to `unifyroute_*`
5. **Documentation**: Review updated docs in the `docs/` folder

## Support & Documentation

- **Installation Guide**: See `docs/installation.md`
- **Usage Guide**: See `docs/usage.md`
- **Architecture**: See `docs/llm-gateway-architecture.md`

## License

MIT License © UnifyRoute Contributors
