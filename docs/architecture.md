# Architecture Overview

UnifyRoute is a gateway-centric architecture for OpenAI-compatible traffic.

## High-Level Flow

1. Client calls `POST /api/v1/chat/completions`.
2. API gateway authenticates and normalizes request.
3. Router selects candidate providers by tier and policy.
4. Provider adapter executes request with failover handling.
5. Usage and operational metadata are recorded.

## Main Components

- `api-gateway`: HTTP API and admin routes.
- `router`: tiering, ranking, failover decisions.
- `credential-vault`: secure credential handling.
- `quota-poller`: model and quota synchronization.
- `gui`: management dashboard.
- `shared`: common models and utilities.

## Data And Control Services

- SQLite for primary local state.
- Redis for transient routing/failure state.

## Related Documents

- Legacy deep-dive design doc: `docs/unifyroute-architecture.md`
- Progress tracker: `docs/progress-and-todo.md`
