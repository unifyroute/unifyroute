"""Brain configuration — tracks assigned providers/credentials/models.

BrainConfig rows (in DB) define what resources Brain may use.
This module exposes a typed dataclass for in-memory representation.
"""
from dataclasses import dataclass, field
from typing import List
from uuid import UUID


@dataclass
class BrainProviderEntry:
    """In-memory representation of a brain_configs row."""
    id: UUID
    provider_id: UUID
    provider_name: str
    credential_id: UUID
    credential_label: str
    model_id: str
    priority: int = 100   # lower = higher priority
    enabled: bool = True


# Mapping from provider name → health-check URL
# All use Bearer token auth unless noted otherwise.
PROVIDER_HEALTH_URLS: dict[str, str] = {
    "openai":       "https://api.openai.com/v1/models",
    "anthropic":    "https://api.anthropic.com/v1/models",
    "google":       "https://generativelanguage.googleapis.com/v1beta/models",
    # google-antigravity uses OAuth2 (cloud-platform scope); the generativelanguage
    # endpoint requires an API key or generativelanguage scope. Use the OpenID Connect
    # userinfo endpoint instead — valid for ANY Google OAuth2 Bearer token.
    "google-antigravity": "https://openidconnect.googleapis.com/v1/userinfo",
    "groq":         "https://api.groq.com/openai/v1/models",
    "mistral":      "https://api.mistral.ai/v1/models",
    "cohere":       "https://api.cohere.com/v2/models",
    "together":     "https://api.together.xyz/v1/models",
    "unifyroute":   "https://unifyroute.ai/api/v1/models",
    "fireworks":    "https://api.fireworks.ai/inference/v1/models",
    "zai":          "https://api.z.ai/api/paas/v4/models",
    "ollama":       "https://ollama.com/v1/models",
    "nvidia":       "https://integrate.api.nvidia.com/v1/models",
    "deepseek":     "https://api.deepseek.com/v1/models",
    "perplexity":   "https://api.perplexity.ai/models",
    "cerebras":     "https://api.cerebras.ai/v1/models",
    "huggingface":  "https://huggingface.co/api/models",
    "xai":          "https://api.x.ai/v1/models",
}

# Providers that use a custom auth header (not Bearer token)
PROVIDER_CUSTOM_AUTH: dict[str, dict] = {
    "anthropic": {"x-api-key": "{key}", "anthropic-version": "2023-06-01"},
    "google":    {"x-goog-api-key": "{key}"},
    # google-antigravity stores an OAuth2 access token — must send as Bearer
    "google-antigravity": {"Authorization": "Bearer {key}"},
}
