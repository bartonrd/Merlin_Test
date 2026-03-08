"""Tests for the POST /reindex endpoint."""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# /reindex – happy paths
# ---------------------------------------------------------------------------


def test_reindex_returns_chunk_count():
    """A successful reindex returns the number of new chunks."""
    with (
        patch("app.main.ingest_directory", return_value=42) as mock_ingest,
        patch("app.main.Path") as mock_path_cls,
    ):
        mock_path = mock_path_cls.return_value
        mock_path.exists.return_value = True

        from app.main import app

        client = TestClient(app)
        response = client.post("/reindex")

    assert response.status_code == 200
    data = response.json()
    assert data["new_chunks"] == 42
    assert "42" in data["message"]


def test_reindex_no_documents_found():
    """When no documents exist, new_chunks is 0 and the message reflects that."""
    with (
        patch("app.main.ingest_directory", return_value=0),
        patch("app.main.Path") as mock_path_cls,
    ):
        mock_path = mock_path_cls.return_value
        mock_path.exists.return_value = True

        from app.main import app

        client = TestClient(app)
        response = client.post("/reindex")

    assert response.status_code == 200
    data = response.json()
    assert data["new_chunks"] == 0
    assert "no documents" in data["message"].lower()


def test_reindex_calls_ingest_with_clear():
    """The /reindex endpoint always passes clear=True and skip_known=False."""
    with (
        patch("app.main.ingest_directory", return_value=5) as mock_ingest,
        patch("app.main.settings") as mock_settings,
        patch("app.main.Path") as mock_path_cls,
    ):
        mock_settings.docs_dir = "./docs"
        mock_settings.db_path = ":memory:"
        mock_settings.faiss_path = "/tmp/test.faiss"
        mock_settings.faiss_map_path = "/tmp/test.pkl"

        mock_path = mock_path_cls.return_value
        mock_path.exists.return_value = True

        from app.main import app

        client = TestClient(app)
        client.post("/reindex")

    mock_ingest.assert_called_once()
    _, kwargs = mock_ingest.call_args
    assert kwargs["clear"] is True
    assert kwargs["skip_known"] is False


# ---------------------------------------------------------------------------
# /reindex – error handling
# ---------------------------------------------------------------------------


def test_reindex_docs_dir_missing_returns_404():
    """If the docs directory does not exist, /reindex returns HTTP 404."""
    with (
        patch("app.main.ingest_directory"),
        patch("app.main.Path") as mock_path_cls,
    ):
        mock_path = mock_path_cls.return_value
        mock_path.exists.return_value = False

        from app.main import app

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/reindex")

    assert response.status_code == 404


def test_reindex_ingest_exception_returns_500():
    """An unexpected error during ingestion returns HTTP 500."""
    with (
        patch("app.main.ingest_directory", side_effect=RuntimeError("disk full")),
        patch("app.main.Path") as mock_path_cls,
    ):
        mock_path = mock_path_cls.return_value
        mock_path.exists.return_value = True

        from app.main import app

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/reindex")

    assert response.status_code == 500
    assert "disk full" in response.json()["detail"]
