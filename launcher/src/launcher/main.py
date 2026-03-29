import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os

# ── Centralized logging — MUST be first, before any getLogger() calls ─────
from shared.logging_config import setup_logging
setup_logging()

# Pre-load anyio's asyncio backend to work around a Python 3.14 import-system
# regression: anyio's _backends subpackage fails to import when first accessed
# from a worker thread (e.g. Starlette StaticFiles.check_config via run_sync).
# Importing it here ensures loaded_backends['asyncio'] is populated at startup.
import anyio._backends._asyncio as _anyio_asyncio_backend  # noqa: F401
import anyio._core._eventloop as _anyio_eventloop  # noqa: F401
_anyio_eventloop.loaded_backends.setdefault("asyncio", _anyio_asyncio_backend.backend_class)

from launcher.scheduler import start_scheduler, shutdown_scheduler
from api_gateway.main import app as gateway_app
from credential_vault.main import app as vault_app

logger = logging.getLogger("launcher")


@asynccontextmanager
async def lifespan(app: FastAPI):
    port = os.environ.get("PORT", "6565")
    host = os.environ.get("HOST", "0.0.0.0")
    logger.info("UnifyRoute starting on %s:%s", host, port)
    logger.info("Components mounted: API Gateway → /api, Credential Vault → /internal, GUI → /")

    # Start the unified scheduler
    scheduler = start_scheduler()

    # Locate and load routing.yaml
    import router.config
    config_path = os.environ.get("ROUTING_CONFIG")
    if not config_path:
        _here = os.path.dirname(os.path.abspath(__file__))
        for _parent in [_here] + [os.path.join(_here, *['..'] * i) for i in range(1, 6)]:
            _candidate = os.path.normpath(os.path.join(_parent, 'router/routing.yaml'))
            if os.path.exists(_candidate):
                config_path = _candidate
                break
            _candidate2 = os.path.normpath(os.path.join(_parent, 'routing.yaml'))
            if os.path.exists(_candidate2):
                config_path = _candidate2
                break
    if config_path:
        router.config.start_watchdog(config_path)
        logger.info("Routing config loaded from %s", config_path)
    else:
        logger.warning("Could not locate routing.yaml — routing may not work correctly")

    logger.info("UnifyRoute startup complete.")

    # Self-healing: run initial health probe on startup
    try:
        from selfheal.health_prober import probe_all_providers
        logger.info("Running initial provider health probe...")
        probe_result = await probe_all_providers()
        logger.info(
            "Initial health probe: %d healthy, %d unhealthy out of %d providers",
            probe_result.get("healthy", 0),
            probe_result.get("unhealthy", 0),
            probe_result.get("total", 0),
        )
    except Exception as e:
        logger.warning("Initial health probe skipped: %s", e)

    # Self-healing: verify Redis connectivity
    try:
        from router.quota import get_redis
        r = get_redis()
        await r.ping()
        logger.info("Redis connectivity verified.")
    except Exception as e:
        logger.warning("Redis not reachable — self-healing features may be limited: %s", e)

    yield
    # Shutdown the unified scheduler
    shutdown_scheduler(scheduler)
    logger.info("UnifyRoute shutdown complete.")

app = FastAPI(title="LLM Gateway Launcher", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost",
        "http://127.0.0.1",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request

_OPENAI_COMPAT_PREFIXES = ("/v1/", "/chat/", "/completions", "/models")

class V1RewriteMiddleware(BaseHTTPMiddleware):
    """
    OpenClaw and other OpenAI-compatible clients use paths like /v1/chat/completions
    or even /chat/completions directly. Since the Gateway is mounted at /api, we
    transparently rewrite these paths to /api/v1/* to avoid 405 errors from the
    SPA static file handler catching everything that doesn't match a known prefix.
    """
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # Already correctly prefixed or is an internal/GUI path
        if path.startswith("/api/") or path.startswith("/internal/"):
            return await call_next(request)

        # /v1/... → /api/v1/...
        if path.startswith("/v1/"):
            request.scope["path"] = "/api" + path
        # /chat/completions → /api/v1/chat/completions
        elif path.startswith("/chat/"):
            request.scope["path"] = "/api/v1" + path
        # /completions → /api/v1/completions
        elif path == "/completions" or path.startswith("/completions"):
            request.scope["path"] = "/api/v1" + path
        # /models → /api/v1/models
        elif path == "/models" or path.startswith("/models"):
            request.scope["path"] = "/api/v1" + path

        return await call_next(request)

app.add_middleware(V1RewriteMiddleware)


# Mount the sub-applications
# 1. Credential Vault
app.mount("/internal", vault_app)

# 2. Main API Gateway (mount handles /v1, /admin, etc.)
# We mount this at root because its internal routes exactly match the GUI expectations 
# (e.g. /admin/providers). However, FastAPI doesn't easily let two apps share `/`. 
# The easiest fix given our constraints is mounting the API Gateway *after* explicit API paths, 
# or just mounting it at /api and configuring the GUI API_BASE to point to it. 
# Let's fix the frontend instead to point to `/api`.

# Mounting Gateway at /api
app.mount("/api", gateway_app)

# 3. GUI (Static Files)
# Use absolute path relative to this file to handle uvicorn working directories correctly
current_file = os.path.abspath(__file__)
gui_dist_path = os.path.normpath(os.path.join(os.path.dirname(current_file), "../../../gui/dist"))
if os.path.exists(gui_dist_path):
    app.mount("/", StaticFiles(directory=gui_dist_path, html=True), name="gui")
else:
    logger.warning(f"GUI build not found at {gui_dist_path}. Run `npm run build` in gui/.")

from fastapi import Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

@app.exception_handler(404)
async def spa_fallback_handler(request: Request, exc: StarletteHTTPException):
    path = request.url.path
    if not path.startswith("/api/") and not path.startswith("/internal/"):
        index_file = os.path.join(gui_dist_path, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
    return JSONResponse({"detail": "Not Found"}, status_code=404)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "127.0.0.1")
    uvicorn.run("launcher.main:app", host=host, port=port, reload=True)
