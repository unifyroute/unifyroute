# Full provider catalog — mirrors UnifyRouter's supported providers
_PROVIDER_SEED = [
    # ── OAuth / subscription providers ──────────────────────────────────────
    # Google Antigravity: uses gemini-cli PKCE credentials, no user config needed
    {"name": "google-antigravity", "display_name": "Google Antigravity (Gemini CLI)",
     "auth_type": "oauth2", "enabled": True},
    # Anthropic Claude Pro/Max OAuth subscription
    {"name": "anthropic-oauth", "display_name": "Anthropic (Claude Pro/Max OAuth)",
     "auth_type": "oauth2", "enabled": True,
     "oauth_meta": {
         "auth_url": "https://claude.ai/oauth/authorize",
         "token_url": "https://claude.ai/oauth/token",
         "scopes": "user:inference",
     }},
    # OpenAI Codex / ChatGPT OAuth subscription
    {"name": "openai-codex", "display_name": "OpenAI Codex (ChatGPT OAuth)",
     "auth_type": "oauth2", "enabled": True,
     "oauth_meta": {
         "auth_url": "https://auth.openai.com/authorize",
         "token_url": "https://auth.openai.com/oauth/token",
         "scopes": "openid profile email model.request",
     }},
    # ── API-key providers ────────────────────────────────────────────────────
    {"name": "anthropic",       "display_name": "Anthropic",              "auth_type": "api_key", "enabled": True},
    {"name": "openai",          "display_name": "OpenAI",                 "auth_type": "api_key", "enabled": True},
    {"name": "google",          "display_name": "Google Gemini API",      "auth_type": "api_key", "enabled": True},
    {"name": "groq",            "display_name": "Groq",                   "auth_type": "api_key", "enabled": True},
    {"name": "mistral",         "display_name": "Mistral",                "auth_type": "api_key", "enabled": True},
    {"name": "together",        "display_name": "Together AI",            "auth_type": "api_key", "enabled": True},
    {"name": "openrouter",      "display_name": "OpenRouter",             "auth_type": "api_key", "enabled": True},
    {"name": "xai",             "display_name": "xAI (Grok)",             "auth_type": "api_key", "enabled": True},
    {"name": "nvidia",          "display_name": "NVIDIA NIM",             "auth_type": "api_key", "enabled": True},
    {"name": "unifyroute",      "display_name": "UnifyRouter",             "auth_type": "api_key", "enabled": True},
    {"name": "ollama",          "display_name": "Ollama (local)",         "auth_type": "api_key", "enabled": True},
    {"name": "ollama-cloud",    "display_name": "Ollama Cloud",           "auth_type": "api_key", "enabled": True},
    {"name": "zai",             "display_name": "Z.AI",                   "auth_type": "api_key", "enabled": True},
    {"name": "litellm",         "display_name": "LiteLLM",                "auth_type": "api_key", "enabled": True},
    {"name": "vllm",            "display_name": "vLLM (self-hosted)",     "auth_type": "api_key", "enabled": True},
    {"name": "amazon-bedrock",  "display_name": "Amazon Bedrock",         "auth_type": "api_key", "enabled": True},
    {"name": "github-copilot",  "display_name": "GitHub Copilot",         "auth_type": "api_key", "enabled": True},
    {"name": "deepseek",        "display_name": "DeepSeek",               "auth_type": "api_key", "enabled": True},
    {"name": "perplexity",      "display_name": "Perplexity",             "auth_type": "api_key", "enabled": True},
    {"name": "cerebras",        "display_name": "Cerebras",               "auth_type": "api_key", "enabled": True},
    {"name": "huggingface",     "display_name": "Hugging Face",           "auth_type": "api_key", "enabled": True},
    {"name": "fireworks",       "display_name": "Fireworks AI",           "auth_type": "api_key", "enabled": True},
]
