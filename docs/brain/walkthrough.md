# LLMWay Brain Module + Fireworks.ai — Walkthrough

## What Was Built

### 1. Fireworks.ai Provider Support

Added `FireworksAdapter` in [adapters.py](file:///home/himanshu/code/unifyroute/router/src/router/adapters.py):
- OpenAI-compatible at `https://api.fireworks.ai/inference/v1`
- Uses `fireworks_ai` litellm prefix
- Model list + quota check via `/v1/models`
- Registered as `"fireworks"` in the adapters registry

Updated [main.py](file:///home/himanshu/code/unifyroute/api-gateway/src/api_gateway/main.py):
- Added `fireworks` to `_PROVIDER_SEED` (auto-appears in `/admin/providers/seed`)
- Added Fireworks branch in `verify_credential` (`GET /inference/v1/models`)
- Added Fireworks branch in `sync_provider_models`

---

### 2. LLMWay Brain Package

New package at `brain/` with the following modules:

| Module | Purpose |
|---|---|
| [config.py](file:///home/himanshu/code/unifyroute/brain/src/brain/config.py) | `BrainProviderEntry` dataclass + health URL registry for all providers |
| [health.py](file:///home/himanshu/code/unifyroute/brain/src/brain/health.py) | `check_endpoint()` + `check_provider_health()` — async HTTP health checks, all exceptions caught |
| [importer.py](file:///home/himanshu/code/unifyroute/brain/src/brain/importer.py) | `import_from_yaml_str()` / `import_from_json_str()` — idempotent bulk import |
| [tester.py](file:///home/himanshu/code/unifyroute/brain/src/brain/tester.py) | `test_all_brain_credentials()` — tests every brain credential, caches to Redis |
| [ranker.py](file:///home/himanshu/code/unifyroute/brain/src/brain/ranker.py) | `rank_brain_providers()` — multi-factor composite scoring |
| [selector.py](file:///home/himanshu/code/unifyroute/brain/src/brain/selector.py) | `select_for_brain()` — picks best healthy option |
| [errors.py](file:///home/himanshu/code/unifyroute/brain/src/brain/errors.py) | `brain_safe_message()` — maps exceptions to friendly strings |

**Ranking factors** (all normalised 0→1):

| Factor | Weight |
|---|---|
| Priority (lower = better) | 40% |
| Health status | 30% |
| Quota remaining | 20% |
| Latency | 10% |

---

### 3. Brain API Endpoints

7 new admin-only endpoints in [main.py](file:///home/himanshu/code/unifyroute/api-gateway/src/api_gateway/main.py):

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/admin/brain/status` | All assigned providers + cached health |
| `POST` | `/admin/brain/providers` | Assign provider/credential/model to Brain |
| `DELETE` | `/admin/brain/providers/{id}` | Remove a brain assignment |
| `POST` | `/admin/brain/import` | Bulk import via YAML or JSON |
| `POST` | `/admin/brain/test` | Run live health tests, cache to Redis |
| `GET` | `/admin/brain/ranking` | Ranked list with scores |
| `POST` | `/admin/brain/select` | Returns best current option for system use |

---

### 4. DB Migration

[a9b8c7d6e5f4_add_brain_configs.py](file:///home/himanshu/code/unifyroute/migrations/versions/a9b8c7d6e5f4_add_brain_configs.py) creates:
```sql
CREATE TABLE brain_configs (
    id UUID PRIMARY KEY,
    provider_id UUID REFERENCES providers(id) ON DELETE CASCADE,
    credential_id UUID REFERENCES credentials(id) ON DELETE CASCADE,
    model_id TEXT NOT NULL,
    priority INTEGER DEFAULT 100,
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);
```

`BrainConfig` SQLAlchemy model added to [shared/models.py](file:///home/himanshu/code/unifyroute/shared/src/shared/models.py)

---

## Test Results

```
tests/test_fireworks.py           6 passed
tests/test_brain_health.py        3 passed  (check_endpoint, network errors, custom auth)
tests/test_brain_importer.py      7 passed  (yaml/json parse, idempotency, error cases)
tests/test_brain_ranker.py        4 passed  (empty, healthy>unhealthy, priority, fields)
─────────────────────────────────────────
TOTAL                            20 passed  ✅
```

Integration tests (`tests/test_brain_api.py`) require a running gateway and will run via `./run-tests.sh` after `./unifyroute start`.

---

## How to Run

### Apply migration (production)
```bash
# Run from unifyroute root with the gateway stopped
alembic upgrade head
```

### Seed Fireworks.ai provider
```bash
curl -X POST http://localhost:8000/admin/providers/seed \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Import credentials + assign to Brain
```bash
curl -X POST http://localhost:8000/admin/brain/import \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "format": "yaml",
    "content": "providers:\n  - name: fireworks\n    credentials:\n      - label: my-key\n        api_key: fw-xxx\n    models:\n      - accounts/fireworks/models/llama-v3p1-8b-instruct\nbrain_assignments:\n  - provider: fireworks\n    credential_label: my-key\n    models: [accounts/fireworks/models/llama-v3p1-8b-instruct]\n    priority: 10\n"
  }'
```

### Test all brain credentials + get ranking
```bash
curl -X POST http://localhost:8000/admin/brain/test -H "Authorization: Bearer $ADMIN_TOKEN"
curl http://localhost:8000/admin/brain/ranking -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Select best provider for system use
```bash
curl -X POST http://localhost:8000/admin/brain/select -H "Authorization: Bearer $ADMIN_TOKEN"
```
