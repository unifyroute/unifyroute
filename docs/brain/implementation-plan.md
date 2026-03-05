# LLMWay Brain Module + Fireworks.ai Support

## Background

LLMWay is an AI gateway with a router, credential vault, and API gateway. This plan adds:

1. **Fireworks.ai** as a new provider (OpenAI-compatible, `api.fireworks.ai/inference/v1`)
2. **LLMWay Brain** — an internal-only Python module assigned specific providers/models to use for managing the LLMWay system itself (not for routing external user requests). Brain provides: health checking, bulk credential import, key testing, and provider/model ranking.

> [!IMPORTANT]
> The Brain module is **for LLMWay system management only** — it never surfaces outputs to end-users. It selects which provider/credential/model the internal system (admin automations, health bots, system prompts) should use.

---

## Proposed Changes

### 1. Fireworks.ai Provider

---

#### [MODIFY] [adapters.py](file:///home/himanshu/code/unifyroute/router/src/router/adapters.py)

Add new `FireworksAdapter` class and register it in the `adapters` dict:

```python
class FireworksAdapter(ProviderAdapter):
    def __init__(self):
        super().__init__("fireworks", "fireworks_ai")  # litellm prefix: fireworks_ai

    async def _list_models_impl(self, api_key: str) -> List[ModelInfo]:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://api.fireworks.ai/inference/v1/models",
                headers={"Authorization": f"Bearer {api_key}"}
            )
        if r.status_code != 200:
            return []
        return [ModelInfo(model_id=m.get("id",""), display_name=m.get("id",""))
                for m in r.json().get("data", [])]

    async def _get_quota_impl(self, api_key: str) -> QuotaInfo:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://api.fireworks.ai/inference/v1/models",
                headers={"Authorization": f"Bearer {api_key}"}
            )
        return QuotaInfo(tokens_remaining=500_000 if r.status_code == 200 else 0)
```

Register: `"fireworks": FireworksAdapter()`

---

#### [MODIFY] [main.py](file:///home/himanshu/code/unifyroute/api-gateway/src/api_gateway/main.py)

- Add `fireworks` to `_PROVIDER_SEED` list
- Add Fireworks.ai branch in `verify_credential` (uses Bearer token, GET `/inference/v1/models`)
- Add Fireworks.ai branch in `sync_provider_models`

---

### 2. LLMWay Brain Package

#### [NEW] `brain/` (new top-level package alongside `router/`, `shared/`, `api-gateway/`)

```
brain/
  pyproject.toml
  src/
    brain/
      __init__.py
      config.py      # Brain's assigned providers/models + brain settings
      health.py      # HTTP endpoint reachability + key validity tests
      importer.py    # Import providers + credentials from YAML/JSON
      tester.py      # Run live tests against all brain credentials
      ranker.py      # Score and rank provider/credential/model triples
      selector.py    # Pick the best ranked option for system use
      errors.py      # Friendly error handling / safe message formatting
```

---

#### [NEW] [brain/pyproject.toml](file:///home/himanshu/code/unifyroute/brain/pyproject.toml)

Standard Python package, depends on `shared`, `httpx`, `pydantic`.

---

#### [NEW] [brain/src/brain/config.py](file:///home/himanshu/code/unifyroute/brain/src/brain/config.py)

```python
# Tracks which providers/credentials/models the Brain may use.
# Loaded from DB (BrainProvider table) or env override.

@dataclass
class BrainProviderEntry:
    provider_name: str
    credential_id: UUID
    models: List[str]          # specific model IDs Brain may use
    priority: int = 100        # lower = higher priority
    enabled: bool = True
```

Includes a DB model `BrainConfig` (new table) storing these assignments, so they persist across restarts.

---

#### [NEW] [brain/src/brain/health.py](file:///home/himanshu/code/unifyroute/brain/src/brain/health.py)

- `check_endpoint(url, headers, timeout=5) -> HealthResult`
- `test_provider_health(provider_name, api_key, base_url=None) -> HealthResult`
- Returns structured `HealthResult(ok: bool, latency_ms: int, message: str)`
- All exceptions caught, returns `HealthResult(ok=False, message=friendly_msg)`

---

#### [NEW] [brain/src/brain/importer.py](file:///home/himanshu/code/unifyroute/brain/src/brain/importer.py)

- `import_from_dict(data: dict, session) -> ImportResult` — parses JSON/YAML-loaded dict
- `import_from_yaml_str(yaml_str: str, session) -> ImportResult`
- `import_from_json_str(json_str: str, session) -> ImportResult`
- Input format:
```yaml
providers:
  - name: fireworks
    credentials:
      - label: "my-fw-key"
        api_key: "fw-..."
    models:
      - accounts/fireworks/models/llama-v3p1-8b-instruct
brain_assignments:
  - provider: fireworks
    credential_label: "my-fw-key"
    models: [accounts/fireworks/models/llama-v3p1-8b-instruct]
    priority: 10
```
- Idempotent: skips existing provider+credential combos

---

#### [NEW] [brain/src/brain/tester.py](file:///home/himanshu/code/unifyroute/brain/src/brain/tester.py)

- `test_all_brain_credentials(session) -> List[TestResult]`
- For each brain-assigned credential: calls `health.test_provider_health()`
- Updates a Redis key `brain:health:{credential_id}` with result + timestamp
- Returns list of `TestResult(provider, credential_id, ok, message, latency_ms)`
- All exceptions caught per-credential — failure in one doesn't stop others

---

#### [NEW] [brain/src/brain/ranker.py](file:///home/himanshu/code/unifyroute/brain/src/brain/ranker.py)

Scores each brain provider/credential/model triple:

| Factor | Weight |
|---|---|
| `priority` (user-configured, lower=better) | 40% |
| Health status (ok=1, failed=0) | 30% |
| Quota remaining (from Redis) | 20% |
| Latency (from last health check) | 10% |

- `rank_brain_providers(session) -> List[RankedEntry]`
- Returns sorted list, best first

---

#### [NEW] [brain/src/brain/selector.py](file:///home/himanshu/code/unifyroute/brain/src/brain/selector.py)

- `select_for_brain(session) -> BrainSelection`
- Returns `BrainSelection(provider, credential_id, model_id, reason)`
- Used by internal LLMWay automation to know which provider to call
- Falls back gracefully if all fail: returns `BrainSelection(ok=False, message="...")`

---

#### [NEW] [brain/src/brain/errors.py](file:///home/himanshu/code/unifyroute/brain/src/brain/errors.py)

- `brain_safe_message(exc: Exception) -> str` — maps exceptions to friendly messages
- Same pattern as `get_friendly_error_message` in `main.py` but for brain context

---

### 3. Brain API Endpoints in api-gateway

#### [MODIFY] [main.py](file:///home/himanshu/code/unifyroute/api-gateway/src/api_gateway/main.py)

New endpoints under `/admin/brain/` (all require admin key):

| Method | Path | Description |
|---|---|---|
| `GET` | `/admin/brain/status` | Brain config, health of each assigned provider |
| `POST` | `/admin/brain/providers` | Assign provider+credential to Brain |
| `DELETE` | `/admin/brain/providers/{entry_id}` | Unassign from Brain |
| `POST` | `/admin/brain/import` | Import providers+credentials+assignments from JSON/YAML |
| `POST` | `/admin/brain/test` | Trigger full test run of all brain credentials |
| `GET` | `/admin/brain/ranking` | Get current ranked list |
| `POST` | `/admin/brain/select` | Return best provider/model for brain use |

---

### 4. DB Migration

#### [NEW] `brain_configs` table (via Alembic migration)

```sql
CREATE TABLE brain_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID REFERENCES providers(id) ON DELETE CASCADE,
    credential_id UUID REFERENCES credentials(id) ON DELETE CASCADE,
    model_id TEXT NOT NULL,
    priority INTEGER DEFAULT 100,
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);
```

Add `BrainConfig` SQLAlchemy model to `shared/src/shared/models.py`.
Generate a new Alembic migration.

---

## Verification Plan

### Automated Tests

#### Existing test suite (regression check)
```bash
cd /home/himanshu/code/unifyroute
uv run pytest tests/ -v --tb=short
```

#### New unit tests
```bash
cd /home/himanshu/code/unifyroute
uv run pytest tests/test_fireworks.py tests/test_brain_health.py tests/test_brain_importer.py tests/test_brain_ranker.py -v
```

#### New integration tests (requires running gateway)
```bash
cd /home/himanshu/code/unifyroute
uv run pytest tests/test_brain_api.py -v
```

### Manual Verification (API)

1. **Brain status**: `curl -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost:8000/admin/brain/status`
2. **Import from YAML**:
```bash
curl -X POST http://localhost:8000/admin/brain/import \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"format": "yaml", "content": "providers:\n  - name: fireworks\n    credentials:\n      - label: test\n        api_key: fw-xxx\n"}'
```
3. **Run tests**: `curl -X POST http://localhost:8000/admin/brain/test -H "Authorization: Bearer $ADMIN_TOKEN"`
4. **Get ranking**: `curl http://localhost:8000/admin/brain/ranking -H "Authorization: Bearer $ADMIN_TOKEN"`
