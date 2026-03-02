"""Tests for the /generate API endpoint."""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_RESULTS = []  # empty retrieval results – sufficient for unit tests


# ---------------------------------------------------------------------------
# /generate – basic happy paths
# ---------------------------------------------------------------------------


def test_generate_returns_answer():
    with (
        patch("app.main.ingest_directory"),
        patch("app.main.route_and_retrieve", return_value=(_FAKE_RESULTS, False)),
        patch("app.main.get_llm_client") as mock_factory,
        patch("app.main._audit"),
    ):
        mock_llm = MagicMock()
        mock_llm.chat.return_value = "Test answer"
        mock_factory.return_value = mock_llm

        from app.main import app

        client = TestClient(app)
        response = client.post("/generate", json={"prompt": "What is power flow?"})

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "Test answer"
    assert "citations" in data
    assert "is_triage" in data
    assert "chunk_ids" in data


def test_generate_uses_default_temperature():
    """Without a temperature override, the endpoint uses settings.llm_temperature."""
    with (
        patch("app.main.ingest_directory"),
        patch("app.main.route_and_retrieve", return_value=(_FAKE_RESULTS, False)),
        patch("app.main.get_llm_client") as mock_factory,
        patch("app.main._audit"),
        patch("app.main.settings") as mock_settings,
    ):
        mock_settings.llm_temperature = 0.5
        mock_settings.llm_max_tokens = 512
        mock_settings.max_context_chars = 6000
        mock_settings.db_path = ":memory:"
        mock_settings.faiss_path = "/tmp/test.faiss"
        mock_settings.faiss_map_path = "/tmp/test.pkl"

        mock_llm = MagicMock()
        mock_llm.chat.return_value = "answer"
        mock_factory.return_value = mock_llm

        from app.main import app

        client = TestClient(app)
        client.post("/generate", json={"prompt": "hello"})

    mock_llm.chat.assert_called_once()
    _, kwargs = mock_llm.chat.call_args
    assert kwargs["temperature"] == 0.5


def test_generate_uses_custom_temperature():
    """A temperature value in the request overrides the default."""
    with (
        patch("app.main.ingest_directory"),
        patch("app.main.route_and_retrieve", return_value=(_FAKE_RESULTS, False)),
        patch("app.main.get_llm_client") as mock_factory,
        patch("app.main._audit"),
        patch("app.main.settings") as mock_settings,
    ):
        mock_settings.llm_temperature = 0.1
        mock_settings.llm_max_tokens = 512
        mock_settings.max_context_chars = 6000
        mock_settings.db_path = ":memory:"
        mock_settings.faiss_path = "/tmp/test.faiss"
        mock_settings.faiss_map_path = "/tmp/test.pkl"

        mock_llm = MagicMock()
        mock_llm.chat.return_value = "answer"
        mock_factory.return_value = mock_llm

        from app.main import app

        client = TestClient(app)
        client.post("/generate", json={"prompt": "hello", "temperature": 0.9})

    mock_llm.chat.assert_called_once()
    _, kwargs = mock_llm.chat.call_args
    assert kwargs["temperature"] == 0.9


def test_generate_uses_custom_system_prompt():
    """A system_prompt in the request is forwarded to build_chat_messages."""
    with (
        patch("app.main.ingest_directory"),
        patch("app.main.route_and_retrieve", return_value=(_FAKE_RESULTS, False)),
        patch("app.main.get_llm_client") as mock_factory,
        patch("app.main.build_chat_messages", return_value=[]) as mock_build,
        patch("app.main._audit"),
    ):
        mock_llm = MagicMock()
        mock_llm.chat.return_value = "answer"
        mock_factory.return_value = mock_llm

        from app.main import app

        client = TestClient(app)
        client.post(
            "/generate",
            json={"prompt": "hello", "system_prompt": "Custom instructions here"},
        )

    mock_build.assert_called_once()
    _, kwargs = mock_build.call_args
    assert kwargs["system_prompt"] == "Custom instructions here"


# ---------------------------------------------------------------------------
# /generate – validation
# ---------------------------------------------------------------------------


def test_generate_empty_prompt_returns_400():
    with (
        patch("app.main.ingest_directory"),
        patch("app.main.route_and_retrieve", return_value=(_FAKE_RESULTS, False)),
        patch("app.main.get_llm_client"),
    ):
        from app.main import app

        client = TestClient(app)
        response = client.post("/generate", json={"prompt": "   "})

    assert response.status_code == 400


def test_generate_missing_prompt_returns_422():
    with (
        patch("app.main.ingest_directory"),
        patch("app.main.get_llm_client"),
    ):
        from app.main import app

        client = TestClient(app)
        response = client.post("/generate", json={})

    assert response.status_code == 422


def test_generate_llm_timeout_returns_503():
    """A RuntimeError from the LLM (e.g. timeout) should yield HTTP 503."""
    with (
        patch("app.main.ingest_directory"),
        patch("app.main.route_and_retrieve", return_value=(_FAKE_RESULTS, False)),
        patch("app.main.get_llm_client") as mock_factory,
        patch("app.main._audit"),
    ):
        mock_llm = MagicMock()
        mock_llm.chat.side_effect = RuntimeError("LLM server did not respond within 120s")
        mock_factory.return_value = mock_llm

        from app.main import app

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/generate", json={"prompt": "hello"})

    assert response.status_code == 503
