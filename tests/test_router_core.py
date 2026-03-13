"""
Unit tests for router.core module.
"""
import pytest
from unittest.mock import MagicMock

from router.core import Candidate, _detect_task_type, _auto_select_tier


def _make_request(content: str = "hello", num_messages: int = 1, max_tokens: int = None):
    """Build a minimal ChatRequest-like mock for routing tests."""
    msg = MagicMock()
    msg.role = "user"
    msg.content = content

    req = MagicMock()
    req.messages = [msg] * num_messages
    req.max_tokens = max_tokens
    req.model_extra = {}
    return req


# ── Candidate class ──────────────────────────────────────────────────────

def test_candidate_instantiation():
    """Verify Candidate stores fields correctly."""
    from uuid import uuid4
    cid = uuid4()
    cand = Candidate(
        credential_id=cid,
        provider="openai",
        model_id="gpt-4o",
        cost=1.5,
        quota=1000,
        input_cost_per_1k=0.5,
        output_cost_per_1k=1.0,
    )
    assert cand.provider == "openai"
    assert cand.model_id == "gpt-4o"
    assert cand.cost == 1.5
    assert cand.input_cost_per_1k == 0.5
    assert cand.output_cost_per_1k == 1.0
    assert cand.credential_id == cid


# ── Task type detection ──────────────────────────────────────────────────

def test_detect_task_type_simple():
    req = _make_request("Say hello")
    assert _detect_task_type(req) == "simple"


def test_detect_task_type_coding():
    req = _make_request("Write a python function to parse JSON")
    result = _detect_task_type(req)
    assert result == "code"


def test_detect_task_type_analysis():
    req = _make_request("Analyze this data and summarize the key insights")
    result = _detect_task_type(req)
    assert result == "analysis"


def test_detect_task_type_creative():
    req = _make_request("Write a creative short story about a dragon")
    result = _detect_task_type(req)
    assert result == "creative"


def test_detect_task_type_translation():
    req = _make_request("Translate this sentence to French: Hello world")
    result = _detect_task_type(req)
    assert result == "translation"


def test_detect_task_type_empty_message():
    """Empty content returns 'simple'."""
    req = _make_request("")
    assert _detect_task_type(req) == "simple"


# ── Auto tier selection ───────────────────────────────────────────────────

def test_auto_select_tier_simple_returns_lite():
    """Short simple request -> lite tier."""
    req = _make_request("hi", num_messages=1)
    assert _auto_select_tier(req) == "lite"


def test_auto_select_tier_coding_returns_thinking():
    """Coding task -> thinking tier regardless of size."""
    req = _make_request("Write a python flask API with JWT auth")
    assert _auto_select_tier(req) == "thinking"


def test_auto_select_tier_many_messages_returns_thinking():
    """More than 10 messages -> thinking tier (long conversation)."""
    req = _make_request("hello", num_messages=11)
    assert _auto_select_tier(req) == "thinking"


def test_auto_select_tier_medium_conversation_base():
    """4-10 messages with a simple topic -> base tier."""
    req = _make_request("hello", num_messages=5)
    assert _auto_select_tier(req) == "base"


def test_auto_select_tier_high_max_tokens_thinking():
    """Requesting many tokens -> thinking tier."""
    req = _make_request("Summarize this", num_messages=1, max_tokens=5000)
    assert _auto_select_tier(req) == "thinking"


# ── LiteLLM Error Mocking ────────────────────────────────────────────────

def test_litellm_ratelimit_error_instantiation():
    """Verify LiteLLM rate limit error shapes for adapter parsing."""
    import litellm
    try:
        raise litellm.RateLimitError(
            message=b'{\n  "error": {\n    "code": 429,\n    "message": "Quota exceeded"\n  }\n}',
            model="gemini-3-pro",
            llm_provider="gemini",
            response=""
        )
    except Exception as e:
        assert isinstance(e, litellm.RateLimitError)
        assert hasattr(e, "message")
