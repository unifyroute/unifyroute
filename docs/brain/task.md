# LLMWay Brain Module + Fireworks.ai Support

## Phase 1: Add Fireworks.ai Provider
- [x] Add `FireworksAdapter` in `router/src/router/adapters.py`
- [x] Register `fireworks` in the `adapters` registry
- [x] Add `fireworks` to `_PROVIDER_SEED` in `api-gateway/src/api_gateway/main.py`
- [x] Add Fireworks.ai credential verification in `verify_credential` endpoint
- [x] Add Fireworks.ai model sync in `sync_provider_models` endpoint

## Phase 2: Create `brain` Module
- [x] Create `brain/` package directory
- [x] Create `brain/pyproject.toml`
- [x] Create `brain/src/brain/__init__.py`
- [x] Create `brain/src/brain/config.py` — assigned providers/models config for the Brain
- [x] Create `brain/src/brain/health.py` — provider health checks (URL ping + key validity)
- [x] Create `brain/src/brain/importer.py` — import providers & credentials from YAML/JSON/dict
- [x] Create `brain/src/brain/tester.py` — test all credentials, update health status
- [x] Create `brain/src/brain/ranker.py` — ranking logic: provider/credential/model scoring
- [x] Create `brain/src/brain/selector.py` — select best ranked provider/model for the Brain
- [x] Create `brain/src/brain/errors.py` — friendly error message formatting

## Phase 3: Brain API Endpoints in api-gateway
- [ ] `GET /admin/brain/status` — show brain config, health of each assigned provider
- [ ] `POST /admin/brain/providers` — assign a provider+credential to Brain
- [ ] `DELETE /admin/brain/providers/{provider_id}` — unassign provider from Brain
- [ ] `POST /admin/brain/import` — import providers + credentials from JSON/YAML payload
- [ ] `POST /admin/brain/test` — trigger full test of all brain credentials
- [ ] `GET /admin/brain/ranking` — get current ranked list of providers/models for brain use
- [ ] `POST /admin/brain/select` — select best provider/model (used internally by unifyroute system)

## Phase 4: Brain-aware Error Handling
- [x] Brain catches all exceptions, returns structured error messages (no raw tracebacks)
- [x] Health check failures update provider status in DB/Redis

## Phase 5: Tests
- [x] Add `tests/test_fireworks.py` — unit test for `FireworksAdapter`
- [x] Add `tests/test_brain_health.py` — health check tests (mocked HTTP)
- [x] Add `tests/test_brain_importer.py` — import functionality tests
- [x] Add `tests/test_brain_ranker.py` — ranking algorithm tests
- [x] Add `tests/test_brain_api.py` — API endpoint tests (integration)

## Phase 6: Verification
- [x] 20/20 unit tests pass (Fireworks, health, importer, ranker)
- [x] DB migration created (`a9b8c7d6e5f4_add_brain_configs.py`)
- [x] `uv sync` completes successfully with `brain` in workspace
- [ ] Integration tests (require running gateway): `test_brain_api.py`
