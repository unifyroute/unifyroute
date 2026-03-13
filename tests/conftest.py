"""
Pytest configuration and shared fixtures for the UnifyRouter test suite.

The tests hit the live API gateway that must be running on localhost:6565.
They require two environment variables (or .env):
  ADMIN_TOKEN – a gateway key with ["admin"] scope
  API_TOKEN   – a gateway key with ["api"] scope (no admin)

You can create them with:
  ./unifyroute key          # creates API token
  ./unifyroute key --admin  # creates admin token

The tokens are also read from .admin_token and .api_token files at the project root.
"""
import os
import pathlib
import pytest
import httpx


# ──────────────────────────────────────────────────────────────────
# Resolve project root (tests/ is one level below)
# ──────────────────────────────────────────────────────────────────
PROJECT_ROOT = pathlib.Path(__file__).parent.parent

BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "http://localhost:6565")


def _read_token_file(filename: str) -> str | None:
    """Read a single-line token file from the project root."""
    p = PROJECT_ROOT / filename
    if p.exists():
        return p.read_text().strip() or None
    return None


def _resolve_token(env_var: str, token_file: str) -> str:
    token = os.environ.get(env_var) or _read_token_file(token_file)
    if not token:
        pytest.skip(
            f"No token available: set {env_var} env var or ensure {token_file} exists."
        )
    return token


# ──────────────────────────────────────────────────────────────────
# Fixtures – synchronous httpx clients (httpx.Client)
# ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def admin_token() -> str:
    return _resolve_token("ADMIN_TOKEN", ".admin_token")


@pytest.fixture(scope="session")
def api_token() -> str:
    return _resolve_token("API_TOKEN", ".api_token")


@pytest.fixture(scope="session")
def admin_client(admin_token: str) -> httpx.Client:
    """Synchronous HTTPX client pre-configured with an admin bearer token."""
    with httpx.Client(
        base_url=BASE_URL,
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=30,
    ) as client:
        yield client


@pytest.fixture(scope="session")
def api_client(api_token: str) -> httpx.Client:
    """Synchronous HTTPX client pre-configured with a standard (non-admin) API token."""
    with httpx.Client(
        base_url=BASE_URL,
        headers={"Authorization": f"Bearer {api_token}"},
        timeout=30,
    ) as client:
        yield client


@pytest.fixture(scope="session")
def raw_client() -> httpx.Client:
    """Unauthenticated client for testing auth rejection."""
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        yield client


# ──────────────────────────────────────────────────────────────────
# Fixtures – Mock / Temporary state
# ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def mock_streaming_provider(admin_client: httpx.Client):
    """
    Creates a temporary provider, credential, and model mapped to 'lite'
    tier, pointing base_url to http://localhost:9999/v1 for testing 
    streaming failure cases or mock backends. Cleans up after the module.
    """
    import uuid
    prov_name = f"mock-stream-{uuid.uuid4().hex[:6]}"
    
    r_prov = admin_client.post("/api/admin/providers", json={
        "name": prov_name,
        "display_name": "Mock Streaming Provider",
        "auth_type": "api_key",
        "base_url": "http://localhost:9999/v1",
        "enabled": True
    })
    r_prov.raise_for_status()
    prov_id = r_prov.json()["id"]

    r_cred = admin_client.post("/api/admin/credentials", json={
        "provider_id": prov_id,
        "label": "mock-api-key",
        "secret_key": "sk-mock-doesntexist",
        "enabled": True
    })
    r_cred.raise_for_status()

    r_mod = admin_client.post("/api/admin/models", json={
        "provider_id": prov_id,
        "model_id": "openai/gpt-mock-stream",
        "tier": "lite",
        "cost_in_1m": 0.5,
        "cost_out_1m": 1.5,
        "enabled": True
    })
    r_mod.raise_for_status()
    
    yield r_prov.json()
    
    # cleanup
    admin_client.delete(f"/api/admin/providers/{prov_id}")
