import httpx
from typing import Dict, Any, List
from shared.security import decrypt_secret
from .base import ProviderAdapter, ModelInfo, QuotaInfo

class _OpenAICompatAdapter(ProviderAdapter):
    """Reusable base for OpenAI-compatible APIs that expose x-ratelimit headers."""

    def __init__(self, name: str, litellm_prefix: str, base_url: str, default_tokens: int = 200_000):
        super().__init__(name, litellm_prefix)
        self._base_url = base_url
        self._default_tokens = default_tokens

    async def _list_models_impl(self, api_key: str) -> List[ModelInfo]:
        from .base import fetch_json_safe
        
        data = await fetch_json_safe(
            url=f"{self._base_url}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout_ms=10000,
            method="GET"
        )
        
        if not data or not isinstance(data, dict):
            return []
            
        return [
            ModelInfo(
                model_id=m.get("id", ""),
                display_name=m.get("id", ""),
                context_window=m.get("context_window", 32768),
                supports_functions=True,
            )
            for m in data.get("data", [])
        ]

    async def _get_quota_impl(self, api_key: str) -> QuotaInfo:
        from .base import fetch_json_safe
        import httpx
        
        # Rate limits in OpenAI-compat are in the headers generally, not JSON body
        # For the pure fetch resilience, we still run the request but we need the raw headers.
        # However, OpenClaw extracts headers using raw HTTP clients wrapped in timeouts.
        # Since fetch_json_safe returns only the parsed JSON, we implement a safe header-fetch here
        # mirroring the timeout abstraction.
        try:
            timeout = httpx.Timeout(10.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                r = await client.get(
                    f"{self._base_url}/models",
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                r.raise_for_status()
                x_tokens = r.headers.get("x-ratelimit-remaining-tokens", "")
                x_requests = r.headers.get("x-ratelimit-remaining-requests", "")
                
                return QuotaInfo(
                    tokens_remaining=int(x_tokens) if x_tokens.isdigit() else self._default_tokens,
                    requests_remaining=int(x_requests) if x_requests.isdigit() else 1_000,
                )
        except Exception:
            # Mirroring OpenClaw's infra gracefully swallowing failures
            return QuotaInfo(tokens_remaining=self._default_tokens)


class TogetherAdapter(_OpenAICompatAdapter):
    """Together AI (api.together.xyz) — uses together_ai/ prefix in litellm."""
    def __init__(self):
        super().__init__("together", "together_ai", "https://api.together.xyz/v1", 100_000)


class UnifyRouterAdapter(_OpenAICompatAdapter):
    """UnifyRouter (unifyroute.ai) — OpenAI-compatible, token headers present on requests."""
    def __init__(self):
        super().__init__("unifyroute", "unifyroute", "https://unifyroute.ai/api/v1", 100_000)


class PerplexityAdapter(_OpenAICompatAdapter):
    """Perplexity AI — OpenAI-compatible at api.perplexity.ai."""
    def __init__(self):
        super().__init__("perplexity", "perplexity", "https://api.perplexity.ai", 50_000)


class DeepSeekAdapter(_OpenAICompatAdapter):
    """DeepSeek — OpenAI-compatible at api.deepseek.com/v1."""
    def __init__(self):
        super().__init__("deepseek", "deepseek", "https://api.deepseek.com/v1", 100_000)


class CerebrasAdapter(_OpenAICompatAdapter):
    """Cerebras — OpenAI-compatible inference at api.cerebras.ai/v1."""
    def __init__(self):
        super().__init__("cerebras", "cerebras", "https://api.cerebras.ai/v1", 100_000)


class XAIAdapter(_OpenAICompatAdapter):
    """xAI Grok — OpenAI-compatible at api.x.ai/v1."""
    def __init__(self):
        super().__init__("xai", "xai", "https://api.x.ai/v1", 100_000)
