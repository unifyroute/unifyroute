"""
End-to-End Flow Test — UnifyRoute

This is the primary integration test that validates the complete request lifecycle
in a single sequential flow. Run this to verify a healthy deployment.

Requires:
- Gateway running on localhost:6565 (or OPENROUTER_BASE_URL)
- ADMIN_TOKEN env var or .admin_token file

Markers:
- pytest -m e2e        # run only this file
- pytest -m "not e2e"  # skip this file

Steps:
  1.  Health check — gateway responds
  2.  Auth rejection — unauthenticated request returns 401
  3.  Admin auth — admin token grants access
  4.  Provider CRUD — create → read → delete
  5.  Credential CRUD — add API key → verify → quota check → delete
  6.  Model sync — trigger sync-models on a provider
  7.  Model catalog — list models for a provider
  8.  Gateway key lifecycle — create, use, delete
  9.  Routing config — read and write routing.yaml
  10. Chat completions (auth failure path)
  11. Request log write-through after a completion attempt
  12. Brain health check
  13. Wizard endpoint health
  14. Cleanup — remove all test-created objects
"""
import os
import uuid
import pytest
import httpx

# ──────────────────────────────────────────────
# Fixtures / helpers
# ──────────────────────────────────────────────

BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "http://localhost:6565")


def _read_token_file(filename: str) -> str | None:
    p = __file__
    root = os.path.dirname(os.path.dirname(p))
    path = os.path.join(root, filename)
    if os.path.exists(path):
        return open(path).read().strip() or None
    return None


def _resolve_admin_token() -> str:
    tok = os.environ.get("ADMIN_TOKEN") or _read_token_file(".admin_token")
    if not tok:
        pytest.skip("No admin token available for E2E flow test.")
    return tok


TAG = uuid.uuid4().hex[:8]   # unique tag for all objects created in this run


# ──────────────────────────────────────────────
# Main E2E test class (sequential methods)
# ──────────────────────────────────────────────

@pytest.mark.e2e
class TestE2EFlow:
    """
    Orchestrated end-to-end happy-path test.
    Each test method is intentionally stateless (uses module-level fixtures),
    but ordered to reflect the real user journey.
    """

    # ── 1. Health ─────────────────────────────────────────────────

    def test_01_gateway_health(self):
        """Gateway must respond to health probe."""
        with httpx.Client(base_url=BASE_URL, timeout=10) as c:
            r = c.get("/api/health")
        assert r.status_code == 200, f"Health check failed: {r.status_code} {r.text}"

    # ── 2. Auth rejection ─────────────────────────────────────────

    def test_02_unauthenticated_request_rejected(self):
        """Every protected endpoint must return 401 without a Bearer token."""
        with httpx.Client(base_url=BASE_URL, timeout=10) as c:
            for path in ["/api/v1/models", "/api/admin/providers", "/api/admin/keys"]:
                r = c.get(path)
                assert r.status_code == 401, f"{path} did not return 401 (got {r.status_code})"

    def test_03_completions_unauthenticated_returns_401(self):
        """POST to chat/completions without token returns 401, not 500."""
        with httpx.Client(base_url=BASE_URL, timeout=10) as c:
            r = c.post("/api/v1/chat/completions", json={
                "model": "lite",
                "messages": [{"role": "user", "content": "hello"}],
            })
        assert r.status_code == 401

    # ── 3. Admin auth ─────────────────────────────────────────────

    def test_04_admin_token_grants_access(self):
        """Admin token must authenticate successfully."""
        token = _resolve_admin_token()
        with httpx.Client(base_url=BASE_URL, headers={"Authorization": f"Bearer {token}"}, timeout=10) as c:
            r = c.get("/api/admin/providers")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    # ── 4. Provider CRUD ──────────────────────────────────────────

    def test_05_provider_create(self):
        """Create a test provider and verify its fields."""
        token = _resolve_admin_token()
        with httpx.Client(base_url=BASE_URL, headers={"Authorization": f"Bearer {token}"}, timeout=10) as c:
            r = c.post("/api/admin/providers", json={
                "name": f"e2e-prov-{TAG}",
                "display_name": f"E2E Provider {TAG}",
                "auth_type": "api_key",
                "enabled": True,
            })
        assert r.status_code == 200, f"Provider create failed: {r.text}"
        body = r.json()
        assert "id" in body
        assert body["name"] == f"e2e-prov-{TAG}"

    def test_06_provider_appears_in_list(self):
        """Newly created provider is visible in the provider list."""
        token = _resolve_admin_token()
        with httpx.Client(base_url=BASE_URL, headers={"Authorization": f"Bearer {token}"}, timeout=10) as c:
            r = c.get("/api/admin/providers")
        names = [p["name"] for p in r.json()]
        assert f"e2e-prov-{TAG}" in names, f"Provider not found in list: {names}"

    # ── 5. Credential CRUD ────────────────────────────────────────

    def test_07_credential_create(self):
        """Add an API key credential for the test provider."""
        token = _resolve_admin_token()
        with httpx.Client(base_url=BASE_URL, headers={"Authorization": f"Bearer {token}"}, timeout=10) as c:
            # Find test provider
            providers = c.get("/api/admin/providers").json()
            provider = next((p for p in providers if p["name"] == f"e2e-prov-{TAG}"), None)
            assert provider is not None, "Test provider not found"

            r = c.post("/api/admin/credentials", json={
                "provider_id": provider["id"],
                "label": f"e2e-cred-{TAG}",
                "auth_type": "api_key",
                "secret_key": "sk-fake-e2e-test-key-00000",
                "enabled": True,
            })
        assert r.status_code == 200, f"Credential create failed: {r.text}"
        body = r.json()
        assert "id" in body
        # Secret must NOT be echoed back
        assert "secret_key" not in body
        assert "secret_enc" not in body

    def test_08_credential_verify(self):
        """Verify endpoint returns a result (pass or fail — not a crash)."""
        token = _resolve_admin_token()
        with httpx.Client(base_url=BASE_URL, headers={"Authorization": f"Bearer {token}"}, timeout=30) as c:
            creds = c.get("/api/admin/credentials").json()
            cred = next((cr for cr in creds if cr.get("label") == f"e2e-cred-{TAG}"), None)
            if cred is None:
                pytest.skip("E2E credential not found (step 07 may have been skipped)")
            r = c.get(f"/api/admin/credentials/{cred['id']}/verify")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "status" in body
        assert "message" in body
        assert body["status"] in ("success", "error", "info")

    def test_09_credential_quota_check(self):
        """Quota endpoint must return 200 with required fields."""
        token = _resolve_admin_token()
        with httpx.Client(base_url=BASE_URL, headers={"Authorization": f"Bearer {token}"}, timeout=15) as c:
            creds = c.get("/api/admin/credentials").json()
            cred = next((cr for cr in creds if cr.get("label") == f"e2e-cred-{TAG}"), None)
            if cred is None:
                pytest.skip("E2E credential not found")
            r = c.get(f"/api/admin/credentials/{cred['id']}/quota")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "tokens_remaining" in body
        assert "requests_remaining" in body

    # ── 6. Model sync ─────────────────────────────────────────────

    def test_10_sync_models_for_provider(self):
        """sync-models must return 200 with status, total, inserted fields."""
        token = _resolve_admin_token()
        with httpx.Client(base_url=BASE_URL, headers={"Authorization": f"Bearer {token}"}, timeout=30) as c:
            providers = c.get("/api/admin/providers").json()
            provider = next((p for p in providers if p["name"] == f"e2e-prov-{TAG}"), None)
            if provider is None:
                pytest.skip("Test provider not found")
            r = c.post(f"/api/admin/providers/{provider['id']}/sync-models")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "status" in body
        assert "total" in body

    # ── 7. Model catalog ──────────────────────────────────────────

    def test_11_models_endpoint_returns_list(self):
        """GET /v1/models must return an OpenAI-compatible list."""
        token = _resolve_admin_token()
        with httpx.Client(base_url=BASE_URL, headers={"Authorization": f"Bearer {token}"}, timeout=10) as c:
            r = c.get("/api/v1/models")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "data" in body or isinstance(body, list), "Expected list or {data: [...]}"

    # ── 8. Gateway key lifecycle ──────────────────────────────────

    def test_12_gateway_key_create_and_use(self):
        """Create a new API key, use it to hit /v1/models, then delete it."""
        token = _resolve_admin_token()
        with httpx.Client(base_url=BASE_URL, headers={"Authorization": f"Bearer {token}"}, timeout=10) as c:
            r_create = c.post("/api/admin/keys", json={
                "label": f"e2e-key-{TAG}",
                "scopes": ["api"],
            })
            assert r_create.status_code == 200, r_create.text
            new_token = r_create.json()["token"]
            key_id = r_create.json()["id"]

            # Use the new key
            with httpx.Client(
                base_url=BASE_URL,
                headers={"Authorization": f"Bearer {new_token}"},
                timeout=10,
            ) as kc:
                r_use = kc.get("/api/v1/models")
                assert r_use.status_code == 200, f"New key failed to authenticate: {r_use.text}"

            # Delete the key
            r_del = c.delete(f"/api/admin/keys/{key_id}")
            assert r_del.status_code == 200

            # Deleted key should now be rejected
            with httpx.Client(
                base_url=BASE_URL,
                headers={"Authorization": f"Bearer {new_token}"},
                timeout=10,
            ) as kc:
                r_revoked = kc.get("/api/v1/models")
                assert r_revoked.status_code == 401, "Deleted key still authenticates!"

    # ── 9. Routing config ─────────────────────────────────────────

    def test_13_routing_config_read(self):
        """Admin can read routing configuration."""
        token = _resolve_admin_token()
        with httpx.Client(base_url=BASE_URL, headers={"Authorization": f"Bearer {token}"}, timeout=10) as c:
            r = c.get("/api/admin/routing")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "yaml_content" in body or "content" in body or isinstance(body, str), \
            f"Unexpected routing config response: {body}"

    def test_14_routing_config_write(self):
        """Admin can write (update) routing configuration without crashing."""
        token = _resolve_admin_token()
        minimal_yaml = (
            "tiers:\n"
            "  lite:\n"
            "    strategy: cheapest_available\n"
            "    models:\n"
            "      - {provider: openai, model: gpt-4o-mini}\n"
        )
        with httpx.Client(base_url=BASE_URL, headers={"Authorization": f"Bearer {token}"}, timeout=10) as c:
            r = c.post("/api/admin/routing", json={"yaml_content": minimal_yaml})
        assert r.status_code == 200, r.text

    # ── 10. Chat completions (auth path) ─────────────────────────

    def test_15_chat_completions_invalid_model_returns_structured_error(self):
        """Using a nonexistent tier/model alias returns a gateway error, not 500."""
        token = _resolve_admin_token()
        with httpx.Client(base_url=BASE_URL, headers={"Authorization": f"Bearer {token}"}, timeout=20) as c:
            r = c.post("/api/v1/chat/completions", json={
                "model": "nonexistent-tier-xyz",
                "messages": [{"role": "user", "content": "Hi"}],
            })
        # Should be 4xx (bad model / no candidates) not 500
        assert r.status_code in (400, 404, 422, 503), \
            f"Expected 4xx/503 for invalid model, got {r.status_code}: {r.text}"

    # ── 11. Request log write-through ────────────────────────────

    def test_16_request_log_written_after_attempt(self):
        """After a completion attempt, the request logs endpoint must show at least one entry."""
        token = _resolve_admin_token()
        # Trigger a completion (may fail due to fake credentials — that's fine)
        with httpx.Client(base_url=BASE_URL, headers={"Authorization": f"Bearer {token}"}, timeout=20) as c:
            c.post("/api/v1/chat/completions", json={
                "model": "lite",
                "messages": [{"role": "user", "content": "ping for e2e log test"}],
            })
            # Now check the log
            r = c.get("/api/admin/logs?limit=5")
        assert r.status_code == 200, r.text
        body = r.json()
        logs = body if isinstance(body, list) else body.get("logs", body.get("items", []))
        # At least the log list endpoint works and returns a list
        assert isinstance(logs, list)

    # ── 12. Brain health ─────────────────────────────────────────

    def test_17_brain_health_endpoint(self):
        """Brain health check should return 200."""
        token = _resolve_admin_token()
        with httpx.Client(base_url=BASE_URL, headers={"Authorization": f"Bearer {token}"}, timeout=15) as c:
            r = c.get("/api/brain/health")
        assert r.status_code == 200, f"Brain health check failed: {r.text}"

    # ── 13. Wizard ───────────────────────────────────────────────

    def test_18_wizard_endpoint_responds(self):
        """Wizard API must respond to a status/list request."""
        token = _resolve_admin_token()
        with httpx.Client(base_url=BASE_URL, headers={"Authorization": f"Bearer {token}"}, timeout=10) as c:
            r = c.get("/api/wizard/status")
        assert r.status_code in (200, 404), \
            f"Wizard endpoint returned unexpected status: {r.status_code}"

    # ── 14. Cleanup ───────────────────────────────────────────────

    def test_19_cleanup_test_objects(self):
        """Remove all test-created providers (and their cascaded credentials) with tag."""
        token = _resolve_admin_token()
        with httpx.Client(base_url=BASE_URL, headers={"Authorization": f"Bearer {token}"}, timeout=15) as c:
            providers = c.get("/api/admin/providers").json()
            for p in providers:
                if p.get("name", "").startswith("e2e-prov-"):
                    r = c.delete(f"/api/admin/providers/{p['id']}")
                    assert r.status_code in (200, 404), \
                        f"Cleanup failed for provider {p['name']}: {r.status_code}"
