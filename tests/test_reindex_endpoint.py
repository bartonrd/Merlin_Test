"""Tests for the POST /reindex endpoint."""
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# _abs path-resolution helper
# ---------------------------------------------------------------------------


def test_abs_resolves_relative_to_project_root():
    """A relative path is anchored at the project root, not the CWD."""
    from app.main import _abs, _project_root

    result = _abs("./docs")
    assert result.is_absolute()
    assert result == _project_root / "docs"


def test_abs_preserves_absolute_path():
    """An absolute path is returned unchanged."""
    from app.main import _abs

    # Use this test file's resolved path – guaranteed to be absolute on all platforms
    abs_path = str(Path(__file__).resolve())
    assert _abs(abs_path) == Path(abs_path)


# ---------------------------------------------------------------------------
# /reindex – happy paths
# ---------------------------------------------------------------------------


def test_reindex_returns_chunk_count():
    """A successful reindex returns the number of new chunks."""
    with (
        patch("app.main.ingest_directory", return_value={"total": 42, "files": [{"name": "a.txt", "chunks": 42}]}) as mock_ingest,
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
    assert data["files"] == [{"name": "a.txt", "chunks": 42}]


def test_reindex_no_documents_found():
    """When no documents exist, new_chunks is 0 and the message reflects that."""
    with (
        patch("app.main.ingest_directory", return_value={"total": 0, "files": []}),
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
    assert data["files"] == []


def test_reindex_no_documents_message_includes_path():
    """The 'no documents found' message includes the directory that was scanned."""
    with (
        patch("app.main.ingest_directory", return_value={"total": 0, "files": []}),
        patch("app.main.settings") as mock_settings,
        patch("app.main.Path") as mock_path_cls,
    ):
        mock_settings.docs_dir = "./docs"
        mock_settings.db_path = ":memory:"
        mock_settings.faiss_path = "/tmp/test.faiss"
        mock_settings.faiss_map_path = "/tmp/test.pkl"

        mock_path = mock_path_cls.return_value
        mock_path.exists.return_value = True
        docs_path = str(Path(__file__).resolve().parent / "docs")
        mock_path.__str__ = lambda self: docs_path

        from app.main import app

        client = TestClient(app)
        response = client.post("/reindex")

    assert response.status_code == 200
    message = response.json()["message"].lower()
    assert "no documents" in message
    assert docs_path in response.json()["message"]


def test_reindex_calls_ingest_with_clear():
    """The /reindex endpoint always passes clear=True and skip_known=False."""
    with (
        patch("app.main.ingest_directory", return_value={"total": 5, "files": [{"name": "x.pdf", "chunks": 5}]}) as mock_ingest,
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


def test_reindex_response_includes_file_details():
    """The /reindex response includes a per-file breakdown of indexed chunks."""
    file_data = [
        {"name": "runbook_a.pdf", "chunks": 10},
        {"name": "notes.txt", "chunks": 3},
    ]
    with (
        patch("app.main.ingest_directory", return_value={"total": 13, "files": file_data}),
        patch("app.main.Path") as mock_path_cls,
    ):
        mock_path = mock_path_cls.return_value
        mock_path.exists.return_value = True

        from app.main import app

        client = TestClient(app)
        response = client.post("/reindex")

    assert response.status_code == 200
    data = response.json()
    assert data["new_chunks"] == 13
    assert len(data["files"]) == 2
    assert data["files"][0] == {"name": "runbook_a.pdf", "chunks": 10}
    assert data["files"][1] == {"name": "notes.txt", "chunks": 3}


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
