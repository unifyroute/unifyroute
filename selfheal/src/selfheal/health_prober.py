"""
Health Prober — Proactive provider health checks.

Runs as a scheduled job (every 2 minutes) and sends lightweight test
requests to each enabled provider.  Proactively marks providers as
failed/healthy so the router doesn't have to discover failures on live
user requests.

Auto‑recovery: when a previously-failed provider passes the health check,
its failure state and adaptive cooldown counter are cleared.
"""

import logging
import time
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from shared.database import async_session_maker
from shared.models import Credential, Provider, ProviderModel
from router.quota import get_redis, mark_provider_failed, is_provider_failed
from router.adapters import get_adapter
from shared.events import log_event_isolated

from selfheal.adaptive_cooldown import reset_failure_count
from selfheal.incident_tracker import close_circuit

logger = logging.getLogger("selfheal.health_prober")

# ── Configuration ──────────────────────────────────────────────────
HEALTH_KEY_PREFIX = "health"
HEALTH_TTL_SECONDS = 300  # 5 min — data goes stale if prober stops


def _health_key(credential_id: UUID, model_id: str) -> str:
    return f"{HEALTH_KEY_PREFIX}:{credential_id}:{model_id}"


async def probe_all_providers() -> dict:
    """
    Iterate over every enabled credential+model and run a lightweight
    health check via the provider adapter.

    Returns a summary dict with counts of healthy/unhealthy/errors.
    """
    summary = {"healthy": 0, "unhealthy": 0, "errors": 0, "recovered": 0, "total": 0}

    try:
        async with async_session_maker() as session:
            stmt = (
                select(Credential)
                .where(Credential.enabled == True)
                .options(
                    selectinload(Credential.provider)
                    .selectinload(Provider.models)
                )
            )
            result = await session.execute(stmt)
            credentials = result.scalars().all()

        import asyncio

        # Filter and prepare probes
        probe_tasks = []
        for cred in credentials:
            if not cred.provider or not cred.provider.enabled:
                continue

            provider_name = cred.provider.name
            adapter = get_adapter(provider_name)

            # Pick the first enabled model for the probe
            probe_model = next((m for m in cred.provider.models if m.enabled), None)
            if not probe_model:
                continue

            summary["total"] += 1
            probe_tasks.append(_probe_single_provider(cred, provider_name, probe_model, adapter))

        # Run all probes concurrently
        results = await asyncio.gather(*probe_tasks, return_exceptions=True)

        for res in results:
            if isinstance(res, dict):
                if res["ok"]:
                    summary["healthy"] += 1
                    if res.get("recovered"):
                        summary["recovered"] += 1
                else:
                    summary["unhealthy"] += 1
            else:
                summary["errors"] += 1

    except Exception as e:
        summary["errors"] += 1
        logger.error("Health prober error: %s", e, exc_info=True)

    logger.info(
        "Health probe complete: %d total, %d healthy, %d unhealthy, %d recovered, %d errors",
        summary["total"], summary["healthy"], summary["unhealthy"],
        summary["recovered"], summary["errors"],
    )
    return summary


async def _probe_single_provider(cred: Credential, provider_name: str, probe_model, adapter) -> dict:
    """Helper to probe a single provider and update its Redis status."""
    import asyncio
    start = time.time()
    ok = False
    error_msg = ""
    recovered = False

    try:
        if hasattr(adapter, "health_check"):
            ok = await asyncio.wait_for(adapter.health_check(cred), timeout=5.0)
        else:
            models = await asyncio.wait_for(adapter.list_models(cred), timeout=5.0)
            ok = models is not None
    except asyncio.TimeoutError:
        error_msg = "Health check timed out after 5 seconds"
        ok = False
    except Exception as exc:
        error_msg = str(exc)
        ok = False

    latency_ms = int((time.time() - start) * 1000)

    # Store health status in Redis
    await _store_health(cred.id, probe_model.model_id, ok, latency_ms)

    if ok:
        # Auto‑recovery: clear failure state if it was set
        was_failed = await is_provider_failed(cred.id, probe_model.model_id)
        if was_failed:
            recovered = True
            logger.info(
                "Provider RECOVERED: %s/%s (latency=%dms) — clearing failure state",
                provider_name, probe_model.model_id, latency_ms,
            )
            # Clear failed marker in Redis
            r = get_redis()
            await r.delete(f"failed:{cred.id}:{probe_model.model_id}")
            # Reset adaptive cooldown
            from selfheal.adaptive_cooldown import reset_failure_count
            await reset_failure_count(cred.id, probe_model.model_id)
            # Close circuit breaker
            from selfheal.incident_tracker import close_circuit
            await close_circuit(cred.id, probe_model.model_id)
            
            await log_event_isolated(
                level="INFO",
                component="selfheal",
                event_type="provider_recovered",
                message=f"Provider {provider_name}/{probe_model.model_id} recovered (latency {latency_ms}ms).",
                details={"credential_id": str(cred.id), "model": probe_model.model_id, "latency_ms": latency_ms}
            )
    else:
        logger.warning(
            "Provider UNHEALTHY: %s/%s (latency=%dms): %s",
            provider_name, probe_model.model_id, latency_ms,
            error_msg[:200] if error_msg else "health check failed",
        )
        # We only log critical if it fails when it was healthy, but without state here just emit warning
        await log_event_isolated(
            level="WARNING",
            component="selfheal",
            event_type="health_probe_failed",
            message=f"Probe failed for {provider_name}/{probe_model.model_id}.",
            details={"error": error_msg, "latency_ms": latency_ms, "model": probe_model.model_id}
        )

    return {"ok": ok, "recovered": recovered}



async def get_provider_health(credential_id: UUID, model_id: str) -> dict | None:
    """Retrieve the latest cached health status for a provider+model."""
    try:
        r = get_redis()
        key = _health_key(credential_id, model_id)
        data = await r.hgetall(key)
        if data:
            return {
                "ok": data.get("ok") == "1",
                "latency_ms": int(data.get("latency_ms", 0)),
                "checked_at": float(data.get("checked_at", 0)),
            }
    except Exception as e:
        logger.error("Failed to get provider health: %s", e)
    return None


async def get_health_summary() -> dict:
    """Return an aggregate health summary across all probed providers."""
    try:
        r = get_redis()
        healthy = 0
        unhealthy = 0

        async for key in r.scan_iter(match=f"{HEALTH_KEY_PREFIX}:*", count=100):
            data = await r.hgetall(key)
            if data.get("ok") == "1":
                healthy += 1
            else:
                unhealthy += 1

        return {"healthy": healthy, "unhealthy": unhealthy, "total": healthy + unhealthy}
    except Exception as e:
        logger.error("Failed to get health summary: %s", e)
        return {"healthy": 0, "unhealthy": 0, "total": 0, "error": str(e)}


# ── Internal helpers ───────────────────────────────────────────────

async def _store_health(
    credential_id: UUID,
    model_id: str,
    ok: bool,
    latency_ms: int,
) -> None:
    """Persist the health probe result in Redis."""
    try:
        r = get_redis()
        key = _health_key(credential_id, model_id)
        await r.hset(key, mapping={
            "ok": "1" if ok else "0",
            "latency_ms": str(latency_ms),
            "checked_at": str(time.time()),
        })
        await r.expire(key, HEALTH_TTL_SECONDS)
    except Exception as e:
        logger.error("Failed to store health result: %s", e)
