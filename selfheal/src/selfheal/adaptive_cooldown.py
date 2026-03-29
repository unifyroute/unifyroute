"""
Adaptive Cooldown — Exponential backoff for recurring provider failures.

Replaces the fixed 60 s TTL with an adaptive TTL that grows with each
consecutive failure:  60 → 120 → 300 → 600 → 1800 (cap at 30 min).

On a successful request the failure counter is reset so the provider
returns to the fast lane immediately.
"""

import logging
from uuid import UUID

from router.quota import get_redis

logger = logging.getLogger("selfheal.adaptive_cooldown")

# ── Configuration ──────────────────────────────────────────────────
BASE_TTL = 60           # seconds — first failure cooldown
MAX_TTL = 1800          # seconds — 30 min ceiling
BACKOFF_MULTIPLIER = 2  # each failure doubles the cooldown
# The TTL sequence values (clamped to MAX_TTL):
# failure 1 → 60, 2 → 120, 3 → 240, 4 → 480, 5 → 960, 6+ → 1800


def _counter_key(credential_id: UUID, model_id: str) -> str:
    return f"cooldown:count:{credential_id}:{model_id}"


def compute_ttl(consecutive_failures: int) -> int:
    """Calculate the adaptive TTL for a given failure count.

    Returns a value between BASE_TTL and MAX_TTL.
    """
    if consecutive_failures <= 0:
        return BASE_TTL
    ttl = int(BASE_TTL * (BACKOFF_MULTIPLIER ** (consecutive_failures - 1)))
    return min(ttl, MAX_TTL)


async def record_failure(credential_id: UUID, model_id: str) -> int:
    """
    Increment the consecutive failure counter and return the adaptive TTL
    to use for ``mark_provider_failed()``.
    """
    try:
        r = get_redis()
        key = _counter_key(credential_id, model_id)

        count = await r.incr(key)
        # Keep the counter around for 2× MAX_TTL so it auto-expires if
        # nobody touches it (i.e. the provider hasn't been tried in a while).
        await r.expire(key, MAX_TTL * 2)

        ttl = compute_ttl(count)
        logger.info(
            "Adaptive cooldown: cred=%s model=%s failures=%d → ttl=%ds",
            credential_id, model_id, count, ttl,
        )
        return ttl

    except Exception as e:
        logger.error("Failed to record adaptive failure: %s", e)
        return BASE_TTL  # safe default


async def reset_failure_count(credential_id: UUID, model_id: str) -> None:
    """Reset the consecutive failure counter after a successful request."""
    try:
        r = get_redis()
        key = _counter_key(credential_id, model_id)
        deleted = await r.delete(key)
        if deleted:
            logger.info(
                "Adaptive cooldown reset: cred=%s model=%s",
                credential_id, model_id,
            )
    except Exception as e:
        logger.error("Failed to reset adaptive cooldown: %s", e)


async def get_failure_count(credential_id: UUID, model_id: str) -> int:
    """Return the current consecutive failure count (0 if healthy)."""
    try:
        r = get_redis()
        key = _counter_key(credential_id, model_id)
        val = await r.get(key)
        return int(val) if val else 0
    except Exception as e:
        logger.error("Failed to get failure count: %s", e)
        return 0
