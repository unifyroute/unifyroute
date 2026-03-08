"""
model_catalog.py

Provides a static catalog of popular models across different AI providers.
Used by the setup wizard to suggest models.
"""

from typing import List, Dict, Any
from pydantic import BaseModel

class ModelEntry(BaseModel):
    model_id: str
    display_name: str
    tier: str = ""
    context_window: int = 128000
    input_cost_per_1k: float = 0.0
    output_cost_per_1k: float = 0.0
    supports_streaming: bool = True
    supports_functions: bool = True
    enabled: bool = True

_CATALOG: Dict[str, List[Dict[str, Any]]] = {
    "OpenAI": [
        {
            "model_id": "gpt-4o",
            "display_name": "GPT-4o",
            "tier": "base",
            "context_window": 128000,
            "input_cost_per_1k": 0.005,
            "output_cost_per_1k": 0.015,
        },
        {
            "model_id": "gpt-4o-mini",
            "display_name": "GPT-4o Mini",
            "tier": "lite",
            "context_window": 128000,
            "input_cost_per_1k": 0.00015,
            "output_cost_per_1k": 0.0006,
        },
        {
            "model_id": "o1-preview",
            "display_name": "o1 Preview",
            "tier": "thinking",
            "context_window": 128000,
            "input_cost_per_1k": 0.015,
            "output_cost_per_1k": 0.060,
        }
    ],
    "Anthropic": [
        {
            "model_id": "claude-3-5-sonnet-latest",
            "display_name": "Claude 3.5 Sonnet",
            "tier": "base",
            "context_window": 200000,
            "input_cost_per_1k": 0.003,
            "output_cost_per_1k": 0.015,
        },
         {
            "model_id": "claude-3-5-haiku-latest",
            "display_name": "Claude 3.5 Haiku",
            "tier": "lite",
            "context_window": 200000,
            "input_cost_per_1k": 0.001,
            "output_cost_per_1k": 0.005,
        }
    ],
    "Google": [
        {
            "model_id": "gemini-1.5-pro",
            "display_name": "Gemini 1.5 Pro",
            "tier": "base",
            "context_window": 2000000,
            "input_cost_per_1k": 0.00125,
            "output_cost_per_1k": 0.005,
        },
        {
            "model_id": "gemini-1.5-flash",
            "display_name": "Gemini 1.5 Flash",
            "tier": "lite",
            "context_window": 1000000,
            "input_cost_per_1k": 0.000075,
            "output_cost_per_1k": 0.0003,
        }
    ],
    "Groq": [
        {
            "model_id": "llama-3.1-70b-versatile",
            "display_name": "Llama 3.1 70B",
            "tier": "base",
            "context_window": 8192,
            "input_cost_per_1k": 0.00059,
            "output_cost_per_1k": 0.00079,
        },
        {
            "model_id": "llama-3.1-8b-instant",
            "display_name": "Llama 3.1 8B",
            "tier": "lite",
            "context_window": 8192,
            "input_cost_per_1k": 0.00005,
            "output_cost_per_1k": 0.00008,
        }
    ]
}

def get_catalog(provider_name: str) -> List[ModelEntry]:
    """Return the static model catalog for a provider."""
    models_data = _CATALOG.get(provider_name, [])
    return [ModelEntry(**m) for m in models_data]

def all_providers_with_catalog() -> List[str]:
    """Return a list of provider names that have a catalog entry."""
    return list(_CATALOG.keys())
