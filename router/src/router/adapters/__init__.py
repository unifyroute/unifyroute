from typing import Dict
from .base import ProviderAdapter, ModelInfo, QuotaInfo

from .openai import OpenAIAdapter
from .anthropic import AnthropicAdapter
from .google_adapter import GoogleGeminiAdapter
from .groq_adapter import GroqAdapter
from .mistral_adapter import MistralAdapter
from .cohere_adapter import CohereAdapter
from .zai_adapter import ZaiAdapter
from .fireworks_adapter import FireworksAdapter
from .compat_adapters import (
    TogetherAdapter, 
    UnifyRouterAdapter,
    PerplexityAdapter,
    DeepSeekAdapter,
    CerebrasAdapter,
    XAIAdapter
)

# Registry
adapters: Dict[str, ProviderAdapter] = {
    # ── Providers with custom subclasses ──
    "openai": OpenAIAdapter(),
    "anthropic": AnthropicAdapter(),
    "google": GoogleGeminiAdapter(),
    "google-antigravity": GoogleGeminiAdapter(),   # same backend
    "groq": GroqAdapter(),
    "mistral": MistralAdapter(),
    "cohere": CohereAdapter(),
    "zai": ZaiAdapter(),
    "fireworks": FireworksAdapter(),
    "together": TogetherAdapter(),
    "unifyroute": UnifyRouterAdapter(),
    "perplexity": PerplexityAdapter(),
    "deepseek": DeepSeekAdapter(),
    "cerebras": CerebrasAdapter(),
    "xai": XAIAdapter(),
    # ── Providers using generic adapter with correct litellm prefix ──
    "nvidia": ProviderAdapter("nvidia", "nvidia_nim"),
    "ollama": ProviderAdapter("ollama", "ollama"),
    "huggingface": ProviderAdapter("huggingface", "huggingface"),
    "vllm": ProviderAdapter("vllm", "hosted_vllm"),
    "litellm": ProviderAdapter("litellm", "openai"),  # LiteLLM proxy is OpenAI-compatible
    "amazon-bedrock": ProviderAdapter("amazon-bedrock", "bedrock"),
    "github-copilot": ProviderAdapter("github-copilot", "openai"),
    "openai-codex": ProviderAdapter("openai-codex", "openai"),
    "anthropic-oauth": AnthropicAdapter(),
}

def get_adapter(provider_name: str) -> ProviderAdapter:
    """Return the adapter for the given provider name, falling back to a generic LiteLLM adapter."""
    if provider_name in adapters:
        return adapters[provider_name]
    # Generic fallback: just call litellm with the provider name as prefix
    return ProviderAdapter(provider_name)

__all__ = [
    "ProviderAdapter",
    "ModelInfo",
    "QuotaInfo",
    "get_adapter",
    "adapters"
]
