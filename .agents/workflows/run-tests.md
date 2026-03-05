---
description: Run the LLMWay test suite after code changes
---

## Run LLMWay Tests

Use this workflow after every code change to run the full test suite.

### Prerequisites
- Virtual environment set up: `./unifyroute setup`
- API gateway running (for integration tests): `./unifyroute start`
- `.admin_token` file exists at project root: `./unifyroute key --admin`

---

### Step 1: Run Unit Tests (no server required, always safe to run)

// turbo
Run: `./run-tests.sh --unit` from the project root `/home/himanshu/code/unifyroute`.

✅ Expected: all pass in < 5 seconds. Covers: brain health/importer/ranker/selector/tester, router core, shared security, stream cost.

---

### Step 2: Ensure Gateway is Running

Check that the API gateway is up:
```bash
curl -s http://localhost:6565/api/ | python3 -m json.tool
```
If it returns an error, start it first: `./unifyroute start`

---

### Step 3: Run Integration Tests (requires live gateway)

// turbo
Run: `./run-tests.sh --integration` from the project root `/home/himanshu/code/unifyroute`.

✅ Expected: all pass. Covers: auth, providers, credentials, keys, models, routing, brain API, wizard, chat completions, OAuth, gateway health.

---

### Step 4: Run Full Suite (unit + integration)

// turbo
Run: `./run-tests.sh` from the project root `/home/himanshu/code/unifyroute`.

✅ Expected: 0 failures, 0 errors.

---

### Quick Reference

| Command | Description |
|---|---|
| `./run-tests.sh` | All tests (unit + integration) |
| `./run-tests.sh --unit` | Unit tests only (no server needed) |
| `./run-tests.sh --integration` | Integration tests only |
| `./run-tests.sh -k auth` | Only auth-related tests |
| `./run-tests.sh -x` | Stop on first failure |
| `uv run pytest tests/test_router_core.py` | Single test file |
