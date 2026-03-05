"""
Unit tests for quota poller implementations in router/src/router/adapters.py.
Tests use mocking to avoid real API calls.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def make_mock_response(status_code: int = 200, headers: dict = None, json_data: dict = None):
    """Create a mock httpx response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = headers or {}
    if json_data is not None:
        resp.json = MagicMock(return_value=json_data)
    return resp


def make_async_client(response):
    """Create a mock httpx.AsyncClient that returns the given response."""
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.get = AsyncMock(return_value=response)
    return client


# ------------------------------------------------------------------
# Import all adapters
# ------------------------------------------------------------------
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'router', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared', 'src'))

from router.adapters import (
    GoogleGeminiAdapter, GroqAdapter, MistralAdapter, CohereAdapter,
    TogetherAdapter, PerplexityAdapter, DeepSeekAdapter, CerebrasAdapter,
    XAIAdapter, UnifyRouterAdapter, FireworksAdapter, ZaiAdapter, QuotaInfo
)


# ------------------------------------------------------------------
# Helper
# ------------------------------------------------------------------
async def get_quota(adapter, api_key: str, response):
    with patch("httpx.AsyncClient", return_value=make_async_client(response)):
        return await adapter._get_quota_impl(api_key)


# ------------------------------------------------------------------
# Tests: invalid key → tokens_remaining=0
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_groq_invalid_key_returns_zero():
    resp = make_mock_response(status_code=401)
    result = await get_quota(GroqAdapter(), "bad-key", resp)
    assert result.tokens_remaining == 0

@pytest.mark.asyncio
async def test_mistral_invalid_key_returns_zero():
    resp = make_mock_response(status_code=401)
    result = await get_quota(MistralAdapter(), "bad-key", resp)
    assert result.tokens_remaining == 0

@pytest.mark.asyncio
async def test_cohere_invalid_key_returns_zero():
    resp = make_mock_response(status_code=401)
    result = await get_quota(CohereAdapter(), "bad-key", resp)
    assert result.tokens_remaining == 0

@pytest.mark.asyncio
async def test_gemini_invalid_key_returns_zero():
    resp = make_mock_response(status_code=403)
    result = await get_quota(GoogleGeminiAdapter(), "bad-key", resp)
    assert result.tokens_remaining == 0

@pytest.mark.asyncio
async def test_deepseek_invalid_key_returns_zero():
    resp = make_mock_response(status_code=401)
    result = await get_quota(DeepSeekAdapter(), "bad-key", resp)
    assert result.tokens_remaining == 0


# ------------------------------------------------------------------
# Tests: valid key with rate-limit headers → use header values
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_groq_reads_ratelimit_headers():
    resp = make_mock_response(
        status_code=200,
        headers={"x-ratelimit-remaining-tokens": "75000", "x-ratelimit-remaining-requests": "500"},
        json_data={"data": []}
    )
    result = await get_quota(GroqAdapter(), "sk-valid", resp)
    assert result.tokens_remaining == 75000
    assert result.requests_remaining == 500

@pytest.mark.asyncio
async def test_mistral_reads_ratelimit_headers():
    resp = make_mock_response(
        status_code=200,
        headers={"x-ratelimit-remaining-tokens": "150000"},
        json_data={"data": []}
    )
    result = await get_quota(MistralAdapter(), "sk-valid", resp)
    assert result.tokens_remaining == 150000

@pytest.mark.asyncio
async def test_cohere_reads_ratelimit_headers():
    resp = make_mock_response(
        status_code=200,
        headers={"x-ratelimit-remaining-tokens": "80000"},
        json_data={"models": []}
    )
    result = await get_quota(CohereAdapter(), "sk-valid", resp)
    assert result.tokens_remaining == 80000

@pytest.mark.asyncio
async def test_together_reads_ratelimit_headers():
    resp = make_mock_response(
        status_code=200,
        headers={"x-ratelimit-remaining-tokens": "42000"},
        json_data={"data": []}
    )
    result = await get_quota(TogetherAdapter(), "sk-valid", resp)
    assert result.tokens_remaining == 42000

@pytest.mark.asyncio
async def test_xai_reads_ratelimit_headers():
    resp = make_mock_response(
        status_code=200,
        headers={"x-ratelimit-remaining-tokens": "99000"},
        json_data={"data": []}
    )
    result = await get_quota(XAIAdapter(), "sk-valid", resp)
    assert result.tokens_remaining == 99000


# ------------------------------------------------------------------
# Tests: valid key without rate-limit headers → use sensible defaults
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_groq_falls_back_to_default_without_headers():
    resp = make_mock_response(status_code=200, headers={}, json_data={"data": []})
    result = await get_quota(GroqAdapter(), "sk-valid", resp)
    assert result.tokens_remaining == 100_000  # groq default

@pytest.mark.asyncio
async def test_perplexity_falls_back_to_default_without_headers():
    resp = make_mock_response(status_code=200, headers={}, json_data={"data": []})
    result = await get_quota(PerplexityAdapter(), "sk-valid", resp)
    assert result.tokens_remaining == 50_000  # perplexity default

@pytest.mark.asyncio
async def test_cerebras_falls_back_to_default_without_headers():
    resp = make_mock_response(status_code=200, headers={}, json_data={"data": []})
    result = await get_quota(CerebrasAdapter(), "sk-valid", resp)
    assert result.tokens_remaining == 100_000

@pytest.mark.asyncio
async def test_gemini_falls_back_to_1m_default():
    resp = make_mock_response(status_code=200, headers={}, json_data={"models": []})
    result = await get_quota(GoogleGeminiAdapter(), "key-valid", resp)
    assert result.tokens_remaining == 1_000_000

@pytest.mark.asyncio
async def test_gemini_reads_ratelimit_headers_when_present():
    resp = make_mock_response(
        status_code=200,
        headers={"x-ratelimit-remaining-tokens": "250000"},
        json_data={"models": []}
    )
    result = await get_quota(GoogleGeminiAdapter(), "key-valid", resp)
    assert result.tokens_remaining == 250000


if __name__ == "__main__":
    print("Running quota poller unit tests...")
    tests = [
        test_groq_invalid_key_returns_zero,
        test_mistral_invalid_key_returns_zero,
        test_cohere_invalid_key_returns_zero,
        test_gemini_invalid_key_returns_zero,
        test_deepseek_invalid_key_returns_zero,
        test_groq_reads_ratelimit_headers,
        test_mistral_reads_ratelimit_headers,
        test_cohere_reads_ratelimit_headers,
        test_together_reads_ratelimit_headers,
        test_xai_reads_ratelimit_headers,
        test_groq_falls_back_to_default_without_headers,
        test_perplexity_falls_back_to_default_without_headers,
        test_cerebras_falls_back_to_default_without_headers,
        test_gemini_falls_back_to_1m_default,
        test_gemini_reads_ratelimit_headers_when_present,
    ]
    for test in tests:
        asyncio.run(test())
        print(f"  ✅ {test.__name__}")
    print(f"\n✅ All {len(tests)} quota poller tests passed!")
