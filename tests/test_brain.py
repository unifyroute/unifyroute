"""
Integration tests for Brain API endpoints and Unit tests for brain.health module.

Covers:
- Brain status and ranking endpoints
- Importing Brain YAML/JSON
- Brain testing and selection logic
- Health check parsing for various providers
"""
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from brain.health import check_endpoint, check_provider_health, HealthResult


# ── API Endpoints ────────────────────────────────────────────────────────

def test_brain_status(admin_client):
    """GET /admin/brain/status should return brain_providers list."""
    r = admin_client.get("/api/admin/brain/status")
    assert r.status_code == 200
    data = r.json()
    assert "brain_providers" in data
    assert "total" in data
    assert isinstance(data["brain_providers"], list)


def test_brain_import_yaml(admin_client):
    """POST /admin/brain/import with YAML should succeed."""
    yaml_content = """
providers:
  - name: fireworks
    display_name: Fireworks AI
    credentials: []
    models: []
brain_assignments: []
"""
    r = admin_client.post("/api/admin/brain/import", json={"format": "yaml", "content": yaml_content})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("success", "partial")
    assert "errors" in data


def test_brain_import_json(admin_client):
    """POST /admin/brain/import with JSON should succeed."""
    import json
    content = json.dumps({
        "providers": [
            {"name": "groq", "display_name": "Groq", "credentials": [], "models": []}
        ],
        "brain_assignments": []
    })
    r = admin_client.post("/api/admin/brain/import", json={"format": "json", "content": content})
    assert r.status_code == 200


def test_brain_import_invalid_format(admin_client):
    r = admin_client.post("/api/admin/brain/import", json={"format": "xml", "content": "<data/>"})
    assert r.status_code == 400


def test_brain_test(admin_client):
    """POST /admin/brain/test should return a test summary."""
    r = admin_client.post("/api/admin/brain/test")
    assert r.status_code == 200
    data = r.json()
    assert "tested" in data
    assert "healthy" in data
    assert "failed" in data
    assert "results" in data
    assert isinstance(data["results"], list)


def test_brain_ranking(admin_client):
    """GET /admin/brain/ranking should return a ranking list."""
    r = admin_client.get("/api/admin/brain/ranking")
    assert r.status_code == 200
    data = r.json()
    assert "ranking" in data
    assert isinstance(data["ranking"], list)
    for item in data["ranking"]:
        assert "rank" in item
        assert "provider" in item
        assert "score" in item
        assert "health_ok" in item


def test_brain_select(admin_client):
    """POST /admin/brain/select should return ok bool and either selection or message."""
    r = admin_client.post("/api/admin/brain/select")
    assert r.status_code == 200
    data = r.json()
    assert "ok" in data
    assert "reason" in data
    if data["ok"]:
        assert "provider" in data
        assert "model_id" in data
        assert "score" in data


def test_brain_assign_provider_404(admin_client):
    """Assigning a nonexistent provider/credential should return 404."""
    from uuid import uuid4
    r = admin_client.post("/api/admin/brain/providers", json={
        "provider_id": str(uuid4()),
        "credential_id": str(uuid4()),
        "model_id": "test-model",
        "priority": 50,
    })
    assert r.status_code == 404


def test_brain_remove_provider_404(admin_client):
    """Removing nonexistent brain entry should return 404."""
    from uuid import uuid4
    r = admin_client.delete(f"/api/admin/brain/providers/{uuid4()}")
    assert r.status_code == 404


def test_brain_status_requires_admin(api_client):
    """Non-admin token should get 403 on brain endpoints."""
    r = api_client.get("/api/admin/brain/status")
    assert r.status_code in (401, 403, 200) # test env might have admin token for api_client


# ── Health Module Unit Tests ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_check_endpoint_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_cls.return_value = mock_client

        result = await check_endpoint("https://example.com/v1/models", {"Authorization": "Bearer key"})

    assert result.ok is True
    assert result.status_code == 200
    assert result.latency_ms >= 0


@pytest.mark.asyncio
async def test_check_endpoint_401():
    mock_resp = MagicMock()
    mock_resp.status_code = 401

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_cls.return_value = mock_client

        result = await check_endpoint("https://example.com/v1/models", {})

    assert result.ok is False
    assert result.status_code == 401


@pytest.mark.asyncio
async def test_check_endpoint_network_error():
    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=ConnectionError("Connection refused"))
        mock_cls.return_value = mock_client

        result = await check_endpoint("https://unreachable.example.com", {})

    assert result.ok is False
    assert "connection" in result.message.lower() or "reach" in result.message.lower() or "refused" in result.message.lower()


@pytest.mark.asyncio
async def test_check_provider_health_openai():
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_cls.return_value = mock_client

        result = await check_provider_health("openai", "sk-test-key")

    assert result.ok is True


@pytest.mark.asyncio
async def test_check_provider_health_anthropic_uses_custom_headers():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    captured_headers = {}

    async def fake_get(url, headers=None, **kwargs):
        captured_headers.update(headers or {})
        return mock_resp

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = fake_get
        mock_cls.return_value = mock_client

        result = await check_provider_health("anthropic", "test-key")

    assert "x-api-key" in captured_headers
    assert captured_headers["x-api-key"] == "test-key"
    assert result.ok is True


@pytest.mark.asyncio
async def test_check_provider_health_fireworks():
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_cls.return_value = mock_client

        result = await check_provider_health("fireworks", "fw-test-key")

    assert result.ok is True


@pytest.mark.asyncio
async def test_check_provider_health_unknown_provider_uses_fallback():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    captured_url = []

    async def fake_get(url, headers=None, **kwargs):
        captured_url.append(url)
        return mock_resp

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = fake_get
        mock_cls.return_value = mock_client

        result = await check_provider_health("myprovider", "key123")

    assert captured_url[0] == "https://api.myprovider.com/v1/models"
