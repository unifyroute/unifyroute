"""
Incident Tracker — Redis-backed failure recording with circuit breaker.

Records every provider failure with error categorisation, maintains
per‑provider failure counters in a sliding window, and exposes a
circuit‑breaker interface so the router can skip providers that are
consistently failing.
"""

import logging
import time
from enum import Enum
from typing import Optional
from uuid import UUID

from shared.events import log_event_isolated
from router.quota import get_redis

logger = logging.getLogger("selfheal.incident_tracker")

# ── Configuration ──────────────────────────────────────────────────
INCIDENT_WINDOW_SECONDS = 3600        # 1‑hour sliding window
CIRCUIT_OPEN_THRESHOLD = 10           # failures within window to trip breaker
CIRCUIT_HALF_OPEN_AFTER_SECONDS = 300 # 5 min before trying a half-open probe


class ErrorCategory(str, Enum):
    RATE_LIMIT = "rate_limit"
    AUTH = "auth"
    TIMEOUT = "timeout"
    SERVER_ERROR = "server_error"
    CONNECTION = "connection"
    UNKNOWN = "unknown"


def classify_error(error_str: str) -> ErrorCategory:
    """Classify an error string into a category."""
    lower = error_str.lower()
    if "rate limit" in lower or "429" in lower or "too many" in lower:
        return ErrorCategory.RATE_LIMIT
    if "auth" in lower or "401" in lower or "403" in lower or "unauthorized" in lower:
        return ErrorCategory.AUTH
    if "timeout" in lower or "timed out" in lower:
        return ErrorCategory.TIMEOUT
    if "connection" in lower or "connect" in lower or "refused" in lower:
        return ErrorCategory.CONNECTION
    if "500" in lower or "502" in lower or "503" in lower or "server error" in lower:
        return ErrorCategory.SERVER_ERROR
    return ErrorCategory.UNKNOWN


def _incident_key(credential_id: UUID, model_id: str) -> str:
    return f"incidents:{credential_id}:{model_id}"


def _circuit_key(credential_id: UUID, model_id: str) -> str:
    return f"circuit:{credential_id}:{model_id}"


# ── Public API ─────────────────────────────────────────────────────

async def record_incident(
    credential_id: UUID,
    model_id: str,
    error_msg: str,
    provider: str = "",
) -> int:
    """
    Record a provider failure incident.

    Adds a timestamped entry to a Redis sorted set (score = epoch) so we
    can cheaply count events inside the sliding window.

    Returns the number of incidents in the current window.
    """
    category = classify_error(error_msg)
    try:
        r = get_redis()
        key = _incident_key(credential_id, model_id)
        now = time.time()
        member = f"{now}:{category.value}:{error_msg[:200]}"

        # Add incident and prune entries outside the window in a pipeline
        async with r.pipeline(transaction=False) as pipe:
            pipe.zadd(key, {member: now})
            pipe.zremrangebyscore(key, 0, now - INCIDENT_WINDOW_SECONDS)
            pipe.zcard(key)
            pipe.expire(key, INCIDENT_WINDOW_SECONDS + 60)
            results = await pipe.execute()

        count = results[2]
        logger.info(
            "Incident recorded: provider=%s model=%s category=%s count=%d/%d",
            provider, model_id, category.value, count, CIRCUIT_OPEN_THRESHOLD,
        )

        # Auto-open circuit if threshold crossed
        if count >= CIRCUIT_OPEN_THRESHOLD:
            await _open_circuit(credential_id, model_id)

        return count

    except Exception as e:
        logger.error("Failed to record incident: %s", e)
        return 0


async def get_incident_count(credential_id: UUID, model_id: str) -> int:
    """Return the number of incidents in the current sliding window."""
    try:
        r = get_redis()
        key = _incident_key(credential_id, model_id)
        now = time.time()
        await r.zremrangebyscore(key, 0, now - INCIDENT_WINDOW_SECONDS)
        return await r.zcard(key)
    except Exception as e:
        logger.error("Failed to get incident count: %s", e)
        return 0


async def get_incident_summary() -> dict:
    """
    Return a summary of all active incidents across all providers.
    Useful for the /health endpoint and the `doctor` CLI command.
    """
    try:
        r = get_redis()
        summary = {"total_tracked": 0, "open_circuits": 0, "providers": {}}
        now = time.time()

        # Scan for incident keys
        async for key in r.scan_iter(match="incidents:*", count=100):
            await r.zremrangebyscore(key, 0, now - INCIDENT_WINDOW_SECONDS)
            count = await r.zcard(key)
            if count > 0:
                # key format: incidents:{cred_id}:{model_id}
                parts = key.split(":", 2)
                label = f"{parts[1][:8]}…/{parts[2]}" if len(parts) == 3 else key
                summary["providers"][label] = count
                summary["total_tracked"] += count

        # Count open circuits
        async for _ in r.scan_iter(match="circuit:*", count=100):
            summary["open_circuits"] += 1

        return summary

    except Exception as e:
        logger.error("Failed to get incident summary: %s", e)
        return {"total_tracked": 0, "open_circuits": 0, "providers": {}, "error": str(e)}


async def is_circuit_open(credential_id: UUID, model_id: str) -> bool:
    """Check whether the circuit breaker is tripped for this provider+model."""
    try:
        r = get_redis()
        key = _circuit_key(credential_id, model_id)
        return await r.exists(key) > 0
    except Exception as e:
        logger.error("Circuit check failed: %s", e)
        return False


async def close_circuit(credential_id: UUID, model_id: str) -> None:
    """Close (reset) the circuit breaker — called when a provider recovers."""
    try:
        r = get_redis()
        key = _circuit_key(credential_id, model_id)
        await r.delete(key)
        # Also clear the incident history
        await r.delete(_incident_key(credential_id, model_id))
        logger.info("Circuit closed (recovered): cred=%s model=%s", credential_id, model_id)
    except Exception as e:
        logger.error("Failed to close circuit: %s", e)


async def cleanup_old_incidents() -> None:
    """Scheduled job: prune expired incident entries from all tracked keys."""
    try:
        r = get_redis()
        pruned = 0
        now = time.time()
        async for key in r.scan_iter(match="incidents:*", count=100):
            removed = await r.zremrangebyscore(key, 0, now - INCIDENT_WINDOW_SECONDS)
            pruned += removed
            # Delete the key entirely if empty
            if await r.zcard(key) == 0:
                await r.delete(key)
        if pruned:
            logger.info("Pruned %d expired incident entries.", pruned)
    except Exception as e:
        logger.error("Incident cleanup failed: %s", e)


# ── Internal helpers ───────────────────────────────────────────────

async def _open_circuit(credential_id: UUID, model_id: str) -> None:
    """Trip the circuit breaker open for CIRCUIT_HALF_OPEN_AFTER_SECONDS."""
    try:
        r = get_redis()
        key = _circuit_key(credential_id, model_id)
        await r.setex(key, CIRCUIT_HALF_OPEN_AFTER_SECONDS, "open")
        logger.warning(
            "Circuit OPEN: cred=%s model=%s (>=%d failures in %ds window, cooldown %ds)",
            credential_id, model_id,
            CIRCUIT_OPEN_THRESHOLD, INCIDENT_WINDOW_SECONDS,
            CIRCUIT_HALF_OPEN_AFTER_SECONDS,
        )
        await log_event_isolated(
            level="ERROR",
            component="selfheal",
            event_type="circuit_open",
            message=f"Circuit opened for {credential_id}/{model_id} after {CIRCUIT_OPEN_THRESHOLD} failures.",
            details={"credential_id": str(credential_id), "model_id": model_id, "window_sec": INCIDENT_WINDOW_SECONDS}
        )
    except Exception as e:
        logger.error("Failed to open circuit: %s", e)
