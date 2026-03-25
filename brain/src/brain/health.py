"""Brain health checking — tests whether a provider endpoint is reachable and a key is valid.

All exceptions are caught. Results are always returned as HealthResult objects,
never as raw exceptions. This makes Brain resilient to individual provider failures.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import httpx

from .config import PROVIDER_HEALTH_URLS, PROVIDER_CUSTOM_AUTH
from .errors import brain_safe_message

logger = logging.getLogger("brain.health")


@dataclass
class HealthResult:
    ok: bool
    latency_ms: int = 0
    message: str = ""
    status_code: int = 0


async def check_endpoint(
    url: str,
    headers: dict,
    timeout: float = 20.0,
) -> HealthResult:
    """Low-level HTTP GET health check against a URL with given headers."""
    logger.info("Health check: GET %s (timeout=%ss)", url, timeout)
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            r = await client.get(url, headers=headers)
        
        latency = int((time.monotonic() - start) * 1000)
        
        if r.status_code >= 400:
            err_msg = ""
            try:
                # Attempt to parse json error
                data = r.json()
                err_msg = data.get("error", {}).get("message") or data.get("error") or r.text
            except Exception:
                err_msg = r.text
            err_msg = str(err_msg).strip() or f"HTTP {r.status_code}"
            
            # Raise so it is caught below and passed through brain_safe_message
            raise Exception(f"HTTP {r.status_code}: {err_msg}")
            
        logger.info("Health check OK: %s (%dms)", url, latency)
        return HealthResult(ok=True, latency_ms=latency, status_code=r.status_code, message="OK")
    except Exception as exc:
        latency = int((time.monotonic() - start) * 1000)
        logger.warning("Health check FAILED: %s (%dms) — %s", url, latency, exc)
        status_code = getattr(exc, "status_code", 0)
        if str(exc).startswith("HTTP "):
            try:
                status_code = int(str(exc).split(" ")[1].strip(":"))
            except Exception:
                pass
        return HealthResult(ok=False, latency_ms=latency, status_code=status_code, message=brain_safe_message(exc))


async def check_provider_health(
    provider_name: str,
    api_key: str,
    base_url: str | None = None,
) -> HealthResult:
    """Check connectivity and key validity for a named provider.

    Uses the known health URL for the provider, or falls back to
    a generic /v1/models endpoint on the provided base_url.
    """
    # Build headers
    if provider_name in PROVIDER_CUSTOM_AUTH:
        template = PROVIDER_CUSTOM_AUTH[provider_name]
        headers = {k: v.replace("{key}", api_key) for k, v in template.items()}
    else:
        headers = {"Authorization": f"Bearer {api_key}"}

    # Determine URL
    url = base_url
    if not url:
        url = PROVIDER_HEALTH_URLS.get(provider_name)
    if not url:
        # Generic fallback
        url = f"https://api.{provider_name}.com/v1/models"

    # Google Generative Language API requires key as query parameter
    if provider_name == "google" and "generativelanguage.googleapis.com" in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}key={api_key}"

    logger.info("Checking provider '%s' at %s", provider_name, url.split("?")[0])
    return await check_endpoint(url, headers)

