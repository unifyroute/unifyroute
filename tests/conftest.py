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
