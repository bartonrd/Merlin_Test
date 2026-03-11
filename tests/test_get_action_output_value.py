"""Tests for the /get_action_output_value endpoint."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_PAYLOAD = [
    {
        "variable_name": "answer",
        "variable_value": "To restore power after a relay trip, follow procedure X.",
        "variable_description": "The LLM-generated answer",
    },
    {
        "variable_name": "status",
        "variable_value": "success",
        "variable_description": "Operation status",
    },
    {
        "variable_name": "citations",
        "variable_value": "relay-runbook.md § Relay Trip Recovery",
        "variable_description": "Source citations for the answer",
    },
]


# ---------------------------------------------------------------------------
# Happy-path tests – match found
# ---------------------------------------------------------------------------


def test_returns_matched_variable():
    """Endpoint returns the correct variable fields when a match is found."""
    with patch("app.main.ingest_directory"):
        from app.main import app

        client = TestClient(app)
        response = client.post(
            "/get_action_output_value",
            json={
                "action_payload_output": _SAMPLE_PAYLOAD,
                "output_variable_name": "answer",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["variable_name"] == "answer"
    assert data["variable_value"] == "To restore power after a relay trip, follow procedure X."
    assert data["variable_description"] == "The LLM-generated answer"


def test_returns_second_variable():
    """Endpoint correctly finds non-first variables in the payload."""
    with patch("app.main.ingest_directory"):
        from app.main import app

        client = TestClient(app)
        response = client.post(
            "/get_action_output_value",
            json={
                "action_payload_output": _SAMPLE_PAYLOAD,
                "output_variable_name": "status",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["variable_name"] == "status"
    assert data["variable_value"] == "success"
    assert data["variable_description"] == "Operation status"


def test_returns_last_variable():
    """Endpoint correctly finds the last variable in the payload."""
    with patch("app.main.ingest_directory"):
        from app.main import app

        client = TestClient(app)
        response = client.post(
            "/get_action_output_value",
            json={
                "action_payload_output": _SAMPLE_PAYLOAD,
                "output_variable_name": "citations",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["variable_name"] == "citations"
    assert data["variable_value"] == "relay-runbook.md § Relay Trip Recovery"
    assert data["variable_description"] == "Source citations for the answer"


# ---------------------------------------------------------------------------
# No match – all fields return "N/A"
# ---------------------------------------------------------------------------


def test_returns_na_when_no_match():
    """When no variable matches, all output fields must be 'N/A'."""
    with patch("app.main.ingest_directory"):
        from app.main import app

        client = TestClient(app)
        response = client.post(
            "/get_action_output_value",
            json={
                "action_payload_output": _SAMPLE_PAYLOAD,
                "output_variable_name": "nonexistent_variable",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["variable_name"] == "N/A"
    assert data["variable_value"] == "N/A"
    assert data["variable_description"] == "N/A"


def test_returns_na_for_empty_payload():
    """An empty action_payload_output list results in 'N/A' for all fields."""
    with patch("app.main.ingest_directory"):
        from app.main import app

        client = TestClient(app)
        response = client.post(
            "/get_action_output_value",
            json={
                "action_payload_output": [],
                "output_variable_name": "answer",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["variable_name"] == "N/A"
    assert data["variable_value"] == "N/A"
    assert data["variable_description"] == "N/A"


# ---------------------------------------------------------------------------
# Case-sensitivity
# ---------------------------------------------------------------------------


def test_match_is_case_sensitive():
    """Variable name matching must be case-sensitive (no match on wrong case)."""
    with patch("app.main.ingest_directory"):
        from app.main import app

        client = TestClient(app)
        response = client.post(
            "/get_action_output_value",
            json={
                "action_payload_output": _SAMPLE_PAYLOAD,
                "output_variable_name": "Answer",  # capital A – should not match "answer"
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["variable_name"] == "N/A"
    assert data["variable_value"] == "N/A"
    assert data["variable_description"] == "N/A"


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


def test_missing_output_variable_name_returns_422():
    """Omitting output_variable_name should return 422 Unprocessable Entity."""
    with patch("app.main.ingest_directory"):
        from app.main import app

        client = TestClient(app)
        response = client.post(
            "/get_action_output_value",
            json={"action_payload_output": _SAMPLE_PAYLOAD},
        )

    assert response.status_code == 422


def test_missing_action_payload_output_returns_422():
    """Omitting action_payload_output should return 422 Unprocessable Entity."""
    with patch("app.main.ingest_directory"):
        from app.main import app

        client = TestClient(app)
        response = client.post(
            "/get_action_output_value",
            json={"output_variable_name": "answer"},
        )

    assert response.status_code == 422
