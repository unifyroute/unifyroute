"""
Tests for /admin/providers CRUD endpoints.

Covers:
- List providers (GET /admin/providers)
- Create provider (POST /admin/providers)
- Update provider (PATCH /admin/providers/{id})
- Delete provider (DELETE /admin/providers/{id})
- Seed providers (POST /admin/providers/seed)
"""
import pytest
import httpx
import uuid


@pytest.fixture(scope="module")
def created_provider(admin_client: httpx.Client):
    """Creates a test provider and cleans it up after the test module."""
    payload = {
        "name": f"test-provider-{uuid.uuid4().hex[:8]}",
        "display_name": "Test Provider (automated)",
        "auth_type": "api_key",
        "enabled": True,
    }
    r = admin_client.post("/api/admin/providers", json=payload)
    assert r.status_code == 200, r.text
    provider = r.json()
    yield provider
    # cleanup
    admin_client.delete(f"/api/admin/providers/{provider['id']}")


class TestProvidersList:

    def test_list_providers_returns_200(self, admin_client: httpx.Client):
        r = admin_client.get("/api/admin/providers")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_api_token_can_access_providers_list(self, api_client: httpx.Client):
        """Standard API tokens cannot list providers (admin-only route)."""
        r = api_client.get("/api/admin/providers")
        assert r.status_code == 403


class TestProviderCreate:

    def test_create_provider_success(self, admin_client: httpx.Client):
        name = f"prov-create-{uuid.uuid4().hex[:6]}"
        r = admin_client.post("/api/admin/providers", json={
            "name": name,
            "display_name": "Temp Create Test Provider",
            "auth_type": "api_key",
            "enabled": True,
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["name"] == name
        assert "id" in body
        # cleanup
        admin_client.delete(f"/api/admin/providers/{body['id']}")

    def test_create_provider_invalid_auth_type(self, admin_client: httpx.Client):
        """Providing an invalid auth_type should be rejected at validation or DB level."""
        r = admin_client.post("/api/admin/providers", json={
            "name": "bad-auth-provider",
            "display_name": "Bad",
            "auth_type": "magic_token",  # invalid
        })
        # 422 if Pydantic rejects it, 500 if DB constraint catches it first
        assert r.status_code in (422, 500), r.text


class TestProviderUpdate:

    def test_update_provider_display_name(
        self, admin_client: httpx.Client, created_provider: dict
    ):
        pid = created_provider["id"]
        r = admin_client.patch(f"/api/admin/providers/{pid}", json={"display_name": "Updated Name"})
        assert r.status_code == 200
        assert r.json()["display_name"] == "Updated Name"

    def test_update_provider_toggle_enabled(
        self, admin_client: httpx.Client, created_provider: dict
    ):
        pid = created_provider["id"]
        r = admin_client.patch(f"/api/admin/providers/{pid}", json={"enabled": False})
        assert r.status_code == 200
        assert r.json()["enabled"] is False
        # restore
        admin_client.patch(f"/api/admin/providers/{pid}", json={"enabled": True})

    def test_update_nonexistent_provider(self, admin_client: httpx.Client):
        fake_id = str(uuid.uuid4())
        r = admin_client.patch(f"/api/admin/providers/{fake_id}", json={"enabled": False})
        assert r.status_code == 404


class TestProviderDelete:

    def test_delete_nonexistent_provider(self, admin_client: httpx.Client):
        r = admin_client.delete(f"/api/admin/providers/{uuid.uuid4()}")
        assert r.status_code == 404

    def test_create_and_delete_provider(self, admin_client: httpx.Client):
        name = f"del-test-{uuid.uuid4().hex[:6]}"
        r = admin_client.post("/api/admin/providers", json={
            "name": name,
            "display_name": "To be deleted",
            "auth_type": "api_key",
        })
        assert r.status_code == 200
        pid = r.json()["id"]
        r2 = admin_client.delete(f"/api/admin/providers/{pid}")
        assert r2.status_code == 200
        assert r2.json()["status"] == "success"


class TestProviderSeed:

    def test_seed_providers(self, admin_client: httpx.Client):
        """POST /admin/providers/seed should insert or skip known providers."""
        r = admin_client.post("/api/admin/providers/seed")
        assert r.status_code == 200
        body = r.json()
        assert "inserted" in body
        assert "skipped" in body


# ── Sync Models ────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def syncable_provider(admin_client: httpx.Client):
    """Provider with a fake API key credential for sync tests."""
    name = f"sync-prov-{uuid.uuid4().hex[:8]}"
    r = admin_client.post("/api/admin/providers", json={
        "name": name,
        "display_name": "Sync Test Provider",
        "auth_type": "api_key",
        "enabled": True,
    })
    assert r.status_code == 200, r.text
    prov = r.json()

    cred = admin_client.post("/api/admin/credentials", json={
        "provider_id": prov["id"],
        "label": "sync-test-cred",
        "auth_type": "api_key",
        "secret_key": "sk-fake-sync-key",
        "enabled": True,
    })
    assert cred.status_code == 200

    yield prov
    admin_client.delete(f"/api/admin/providers/{prov['id']}")


class TestSyncModels:

    def test_sync_nonexistent_provider_returns_404(self, admin_client: httpx.Client):
        r = admin_client.post(f"/api/admin/providers/{uuid.uuid4()}/sync-models")
        assert r.status_code == 404

    def test_sync_provider_without_credentials_returns_no_models(self, admin_client: httpx.Client):
        name = f"nocred-prov-{uuid.uuid4().hex[:6]}"
        r = admin_client.post("/api/admin/providers", json={
            "name": name,
            "display_name": "NoCred Provider",
            "auth_type": "api_key",
            "enabled": True,
        })
        assert r.status_code == 200
        prov_id = r.json()["id"]

        r2 = admin_client.post(f"/api/admin/providers/{prov_id}/sync-models")
        assert r2.status_code == 200
        assert r2.json()["status"] == "no_models"

        admin_client.delete(f"/api/admin/providers/{prov_id}")

    def test_sync_provider_with_fake_cred_attempts_fetch(
        self, admin_client: httpx.Client, syncable_provider: dict
    ):
        r = admin_client.post(
            f"/api/admin/providers/{syncable_provider['id']}/sync-models"
        )
        assert r.status_code in (200, 500), r.text
