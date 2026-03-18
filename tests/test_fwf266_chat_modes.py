"""Tests for FWF266 Action Mode / Triage Mode switching in the /chat endpoint."""
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_FAKE_RESULTS = []  # empty retrieval results – sufficient for unit tests

_FWF266_TRIAGE_QUERY = (
    "-F-,FWF266,PH382E$4115222E,"
    "Line conductor model was not found in global data.,"
    "Record name: Line Field name: CondModA,"
    "Station External Device: PH382E$4115222E,"
    "OH_653_A_2PH_653_A_N_2.9KV,,,,ALOLA,,PH382E$4115222E,ENG"
)

_FWF266_ACTION_QUERY = "give me the action_payload for " + _FWF266_TRIAGE_QUERY


def _make_mock_resolution():
    """Return a minimal FWF266Resolution-like mock."""
    res = MagicMock()
    res.global_csv_line_text = "Conductor_Model,1,COND_578aa,OH_653_A_2PH_653_A_N_2.9KV,TRUE"
    res.global_csv_line_number = 767
    res.confidence = 0.92
    res.notes = "Closest reference at index 766"
    return res


# ---------------------------------------------------------------------------
# Action Mode tests – /chat
# ---------------------------------------------------------------------------


def test_chat_action_mode_returns_is_action_mode_true():
    """When the query requests action_payload, is_action_mode must be True."""
    with (
        patch("app.main.ingest_directory"),
        patch("app.main.route_and_retrieve", return_value=(_FAKE_RESULTS, False)),
        patch("app.main.resolve_fwf266", return_value=_make_mock_resolution()),
        patch("app.main._audit"),
    ):
        from app.main import app

        client = TestClient(app)
        response = client.post("/chat", json={"message": _FWF266_ACTION_QUERY})

    assert response.status_code == 200
    data = response.json()
    assert data["is_action_mode"] is True


def test_chat_action_mode_answer_is_only_json_code_block():
    """Action Mode answer must be a bare JSON code block with no extra prose."""
    with (
        patch("app.main.ingest_directory"),
        patch("app.main.route_and_retrieve", return_value=(_FAKE_RESULTS, False)),
        patch("app.main.resolve_fwf266", return_value=_make_mock_resolution()),
        patch("app.main._audit"),
    ):
        from app.main import app

        client = TestClient(app)
        response = client.post("/chat", json={"message": _FWF266_ACTION_QUERY})

    answer = response.json()["answer"]
    assert answer.startswith("```json"), f"Expected bare JSON code block, got: {answer[:120]}"
    assert answer.strip().endswith("```")


def test_chat_action_mode_answer_contains_valid_action_payload():
    """Action Mode JSON must decode and include propose_global_csv_insert."""
    with (
        patch("app.main.ingest_directory"),
        patch("app.main.route_and_retrieve", return_value=(_FAKE_RESULTS, False)),
        patch("app.main.resolve_fwf266", return_value=_make_mock_resolution()),
        patch("app.main._audit"),
    ):
        from app.main import app

        client = TestClient(app)
        response = client.post("/chat", json={"message": _FWF266_ACTION_QUERY})

    answer = response.json()["answer"]
    json_str = answer.replace("```json", "").replace("```", "").strip()
    payload = json.loads(json_str)
    assert payload["actions"][0]["action"] == "propose_global_csv_insert"


def test_chat_action_mode_does_not_call_llm():
    """Action Mode must skip the LLM entirely – the payload is programmatic."""
    with (
        patch("app.main.ingest_directory"),
        patch("app.main.route_and_retrieve", return_value=(_FAKE_RESULTS, False)),
        patch("app.main.resolve_fwf266", return_value=_make_mock_resolution()),
        patch("app.main.get_llm_client") as mock_factory,
        patch("app.main._audit"),
    ):
        mock_llm = MagicMock()
        mock_factory.return_value = mock_llm

        from app.main import app

        client = TestClient(app)
        client.post("/chat", json={"message": _FWF266_ACTION_QUERY})

    mock_llm.chat.assert_not_called()


# ---------------------------------------------------------------------------
# Triage Mode tests – /chat (FWF266 without action_payload keyword)
# ---------------------------------------------------------------------------


def test_chat_triage_mode_is_action_mode_false():
    """A plain FWF266 error log (no action keyword) must set is_action_mode=False."""
    with (
        patch("app.main.ingest_directory"),
        patch("app.main.route_and_retrieve", return_value=(_FAKE_RESULTS, False)),
        patch("app.main.resolve_fwf266", return_value=_make_mock_resolution()),
        patch("app.main.get_llm_client") as mock_factory,
        patch("app.main._audit"),
    ):
        mock_llm = MagicMock()
        mock_llm.chat.return_value = "Triage text explanation"
        mock_factory.return_value = mock_llm

        from app.main import app

        client = TestClient(app)
        response = client.post("/chat", json={"message": _FWF266_TRIAGE_QUERY})

    assert response.status_code == 200
    data = response.json()
    assert data["is_action_mode"] is False


def test_chat_triage_mode_answer_is_llm_text():
    """Triage Mode answer must be the LLM text with no appended action_payload block."""
    with (
        patch("app.main.ingest_directory"),
        patch("app.main.route_and_retrieve", return_value=(_FAKE_RESULTS, False)),
        patch("app.main.resolve_fwf266", return_value=_make_mock_resolution()),
        patch("app.main.get_llm_client") as mock_factory,
        patch("app.main._audit"),
    ):
        mock_llm = MagicMock()
        mock_llm.chat.return_value = "Triage text explanation"
        mock_factory.return_value = mock_llm

        from app.main import app

        client = TestClient(app)
        response = client.post("/chat", json={"message": _FWF266_TRIAGE_QUERY})

    answer = response.json()["answer"]
    assert answer == "Triage text explanation"
    # No JSON code block should be appended
    assert "propose_global_csv_insert" not in answer


def test_chat_triage_mode_calls_llm():
    """Triage Mode must call the LLM for the text explanation."""
    with (
        patch("app.main.ingest_directory"),
        patch("app.main.route_and_retrieve", return_value=(_FAKE_RESULTS, False)),
        patch("app.main.resolve_fwf266", return_value=_make_mock_resolution()),
        patch("app.main.get_llm_client") as mock_factory,
        patch("app.main._audit"),
    ):
        mock_llm = MagicMock()
        mock_llm.chat.return_value = "Explanation text"
        mock_factory.return_value = mock_llm

        from app.main import app

        client = TestClient(app)
        client.post("/chat", json={"message": _FWF266_TRIAGE_QUERY})

    mock_llm.chat.assert_called_once()


# ---------------------------------------------------------------------------
# Non-FWF266 queries – baseline (is_action_mode must default to False)
# ---------------------------------------------------------------------------


def test_chat_non_fwf266_is_action_mode_false():
    """Non-FWF266 queries must have is_action_mode=False."""
    with (
        patch("app.main.ingest_directory"),
        patch("app.main.route_and_retrieve", return_value=(_FAKE_RESULTS, False)),
        patch("app.main.get_llm_client") as mock_factory,
        patch("app.main._audit"),
    ):
        mock_llm = MagicMock()
        mock_llm.chat.return_value = "Normal answer"
        mock_factory.return_value = mock_llm

        from app.main import app

        client = TestClient(app)
        response = client.post("/chat", json={"message": "What is power flow?"})

    assert response.status_code == 200
    assert response.json()["is_action_mode"] is False
