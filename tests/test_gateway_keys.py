"""
Consolidated gateway key tests.

Merges: test_keys.py + test_key_reveal.py + test_key_update.py

Covers:
- List keys
- Create (api / no-scope) and verify functional token
- Delete
- Reveal (password-protected plaintext)
- Update label
- Revocation: deleted key rejected on next use
"""
import os
import pytest
import httpx
import uuid


BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "http://localhost:6565")


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────

def _master_password() -> str:
    """Return the master password used by the reveal endpoint."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    try:
        from shared.security import unwrap_secret
        return unwrap_secret(
            os.environ.get("MASTER_PASSWORD") or os.environ.get("ADMIN_PASSWORD", "admin")
        )
    except Exception:
        return os.environ.get("MASTER_PASSWORD") or os.environ.get("ADMIN_PASSWORD", "admin")


# ──────────────────────────────────────────────────────────────────
# List
# ──────────────────────────────────────────────────────────────────

class TestKeysList:

    def test_list_keys_returns_list(self, admin_client: httpx.Client):
        r = admin_client.get("/api/admin/keys")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_list_keys_schema(self, admin_client: httpx.Client):
        r = admin_client.get("/api/admin/keys")
        assert r.status_code == 200
        for k in r.json():
            assert "id" in k
            assert "label" in k
            assert "scopes" in k


# ──────────────────────────────────────────────────────────────────
# Create
# ──────────────────────────────────────────────────────────────────

class TestKeyCreate:

    def test_create_api_key_returns_sk_token(self, admin_client: httpx.Client):
        r = admin_client.post("/api/admin/keys", json={
            "label": f"test-api-key-{uuid.uuid4().hex[:6]}",
            "scopes": ["api"],
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["token"].startswith("sk-")
        admin_client.delete(f"/api/admin/keys/{body['id']}")

    def test_create_key_without_scope(self, admin_client: httpx.Client):
        """Empty scopes list is valid (inference-only key)."""
        r = admin_client.post("/api/admin/keys", json={
            "label": f"no-scope-key-{uuid.uuid4().hex[:6]}",
            "scopes": [],
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert "token" in body
        admin_client.delete(f"/api/admin/keys/{body['id']}")

    def test_created_api_key_is_functional(self, admin_client: httpx.Client):
        """A freshly created API key must authenticate against /v1/models."""
        r = admin_client.post("/api/admin/keys", json={
            "label": f"functional-key-{uuid.uuid4().hex[:6]}",
            "scopes": ["api"],
        })
        assert r.status_code == 200
        token = r.json()["token"]
        key_id = r.json()["id"]

        with httpx.Client(
            base_url=BASE_URL,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        ) as c:
            check = c.get("/api/v1/models")
            assert check.status_code == 200

        admin_client.delete(f"/api/admin/keys/{key_id}")


# ──────────────────────────────────────────────────────────────────
# Delete
# ──────────────────────────────────────────────────────────────────

class TestKeyDelete:

    def test_delete_key_success(self, admin_client: httpx.Client):
        r = admin_client.post("/api/admin/keys", json={
            "label": f"to-delete-{uuid.uuid4().hex[:6]}",
            "scopes": ["api"],
        })
        assert r.status_code == 200
        kid = r.json()["id"]
        r2 = admin_client.delete(f"/api/admin/keys/{kid}")
        assert r2.status_code == 200
        assert r2.json()["status"] == "success"

    def test_delete_nonexistent_key(self, admin_client: httpx.Client):
        r = admin_client.delete(f"/api/admin/keys/{uuid.uuid4()}")
        assert r.status_code == 404

    def test_deleted_key_is_rejected(self, admin_client: httpx.Client):
        """A deleted key must no longer authenticate."""
        r = admin_client.post("/api/admin/keys", json={
            "label": f"rev-key-{uuid.uuid4().hex[:6]}",
            "scopes": ["api"],
        })
        assert r.status_code == 200
        token = r.json()["token"]
        kid = r.json()["id"]
        admin_client.delete(f"/api/admin/keys/{kid}")

        with httpx.Client(
            base_url=BASE_URL,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        ) as c:
            check = c.get("/api/v1/models")
            assert check.status_code == 401


# ──────────────────────────────────────────────────────────────────
# Reveal (plaintext token)
# ──────────────────────────────────────────────────────────────────

class TestKeyReveal:

    def test_reveal_key_returns_sk_prefix(self, admin_client: httpx.Client):
        pwd = _master_password()
        r_create = admin_client.post("/api/admin/keys", json={
            "label": f"label-reveal-{uuid.uuid4().hex[:6]}",
            "scopes": ["api"],
        })
        assert r_create.status_code == 200
        key_id = r_create.json()["id"]

        r_reveal = admin_client.post(
            f"/api/admin/keys/{key_id}/reveal",
            json={"password": pwd},
        )
        assert r_reveal.status_code == 200
        reveal_info = r_reveal.json()["reveal_info"]
        assert reveal_info.startswith("sk-")

        admin_client.delete(f"/api/admin/keys/{key_id}")

    def test_reveal_nonexistent_key_404(self, admin_client: httpx.Client):
        pwd = _master_password()
        r = admin_client.post(
            f"/api/admin/keys/{uuid.uuid4()}/reveal",
            json={"password": pwd},
        )
        assert r.status_code == 404


# ──────────────────────────────────────────────────────────────────
# Update label
# ──────────────────────────────────────────────────────────────────

class TestKeyUpdate:

    def test_update_key_label_success(self, admin_client: httpx.Client):
        r_create = admin_client.post("/api/admin/keys", json={
            "label": f"label-to-update-{uuid.uuid4().hex[:6]}",
            "scopes": ["api"],
        })
        assert r_create.status_code == 200
        key_id = r_create.json()["id"]

        new_label = f"updated-label-{uuid.uuid4().hex[:6]}"
        r_update = admin_client.patch(f"/api/admin/keys/{key_id}", json={"label": new_label})
        assert r_update.status_code == 200
        assert r_update.json()["label"] == new_label

        admin_client.delete(f"/api/admin/keys/{key_id}")

    def test_update_nonexistent_key_404(self, admin_client: httpx.Client):
        r = admin_client.patch(f"/api/admin/keys/{uuid.uuid4()}", json={"label": "should-fail"})
        assert r.status_code == 404

    def test_update_key_blank_label_rejected(self, admin_client: httpx.Client):
        r_create = admin_client.post("/api/admin/keys", json={
            "label": f"empty-test-{uuid.uuid4().hex[:6]}",
            "scopes": ["api"],
        })
        assert r_create.status_code == 200
        key_id = r_create.json()["id"]

        r_update = admin_client.patch(f"/api/admin/keys/{key_id}", json={"label": "   "})
        assert r_update.status_code == 422

        admin_client.delete(f"/api/admin/keys/{key_id}")
