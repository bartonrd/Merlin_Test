"""Tests for the LLM client backends and factory."""
import sys
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.llm.client import (
    LLMClient,
    LocalLLMClient,
    NoLLMClient,
    get_llm_client,
)


# ---------------------------------------------------------------------------
# NoLLMClient
# ---------------------------------------------------------------------------


def test_no_llm_client_health_check():
    assert NoLLMClient().health_check() is True


def test_no_llm_client_returns_header():
    client = NoLLMClient()
    result = client.chat([{"role": "user", "content": "hello"}])
    assert "No LLM configured" in result


def test_no_llm_client_extracts_context():
    client = NoLLMClient()
    messages = [
        {"role": "system", "content": "You are an assistant."},
        {
            "role": "user",
            "content": "<context>\nDoc excerpt here\n</context>\n\nWhat is this?",
        },
    ]
    result = client.chat(messages)
    assert "Doc excerpt here" in result
    assert "No LLM configured" in result


def test_no_llm_client_fallback_no_context_tag():
    client = NoLLMClient()
    messages = [{"role": "user", "content": "plain user message"}]
    result = client.chat(messages)
    assert "plain user message" in result


# ---------------------------------------------------------------------------
# LocalLLMClient – missing dependency
# ---------------------------------------------------------------------------


def test_local_llm_client_missing_dep_raises():
    """LocalLLMClient should raise a clear RuntimeError when llama_cpp is absent."""
    client = LocalLLMClient(model_path="/tmp/nonexistent.gguf")
    # Remove llama_cpp from sys.modules if present, then simulate ImportError
    with patch.dict(sys.modules, {"llama_cpp": None}):
        with pytest.raises(RuntimeError, match="llama-cpp-python is not installed"):
            client._load()


def test_local_llm_client_health_check_false_on_missing_dep():
    client = LocalLLMClient(model_path="/tmp/nonexistent.gguf")
    with patch.dict(sys.modules, {"llama_cpp": None}):
        assert client.health_check() is False


# ---------------------------------------------------------------------------
# LLMClient – timeout handling
# ---------------------------------------------------------------------------


def test_llm_client_timeout_raises_runtime_error():
    """httpx.TimeoutException should be converted to a RuntimeError."""
    client = LLMClient(base_url="http://localhost:8080", model="test-model")
    with patch("httpx.post", side_effect=httpx.TimeoutException("timed out")):
        with pytest.raises(RuntimeError, match="did not respond within"):
            client.chat([{"role": "user", "content": "hello"}])


# ---------------------------------------------------------------------------
# get_llm_client factory
# ---------------------------------------------------------------------------


def test_factory_returns_llm_client_for_remote():
    client = get_llm_client(mode="remote", base_url="http://localhost:8080")
    assert isinstance(client, LLMClient)


def test_factory_returns_no_llm_client_for_none():
    client = get_llm_client(mode="none")
    assert isinstance(client, NoLLMClient)


def test_factory_returns_local_client_for_local():
    client = get_llm_client(mode="local", model_path="/tmp/model.gguf")
    assert isinstance(client, LocalLLMClient)
    assert client.model_path == "/tmp/model.gguf"


def test_factory_local_mode_without_model_path_raises():
    with pytest.raises(RuntimeError, match="LLM_MODEL_PATH"):
        get_llm_client(mode="local", model_path="")


def test_factory_unknown_mode_defaults_to_remote():
    """Unrecognised mode values fall back to remote."""
    client = get_llm_client(mode="typo", base_url="http://localhost:9999")
    assert isinstance(client, LLMClient)
