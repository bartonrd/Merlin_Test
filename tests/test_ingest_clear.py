"""Tests for the SQL-based DB clear logic in ingest_directory(clear=True).

On Windows, ``Path.unlink()`` raises ``WinError 32`` when the target file is
held open by another process (e.g. the running FastAPI server).  The fix
replaces the file-deletion approach with a SQL ``DELETE FROM chunks`` so the
file is never removed.
"""
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db(db_path: str) -> None:
    """Create a minimal DB with the expected schema and one dummy chunk."""
    from app.ingestion.ingest import init_db, insert_chunks
    from app.ingestion.chunking import Chunk

    conn = init_db(db_path)
    chunk = Chunk(
        doc_id="testdoc1",
        title="Test Doc",
        path=str(Path(db_path).parent / "testdoc1.txt"),
        doc_type="general",
        section="",
        chunk_index=0,
        text="hello world",
    )
    insert_chunks(conn, [chunk])
    conn.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_clear_does_not_unlink_db_file(tmp_path):
    """clear=True must NOT delete the DB file (avoids WinError 32 on Windows)."""
    db_path = str(tmp_path / "db.sqlite")
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    _make_db(db_path)

    # Spy on Path.unlink – if called for the DB file the test fails.
    original_unlink = Path.unlink
    unlinked = []

    def spy_unlink(self, *args, **kwargs):
        unlinked.append(str(self))
        original_unlink(self, *args, **kwargs)

    from app.ingestion.ingest import ingest_directory

    with patch.object(Path, "unlink", spy_unlink):
        ingest_directory(
            input_dir=str(docs_dir),
            db_path=db_path,
            faiss_path=str(tmp_path / "index.faiss"),
            faiss_map_path=str(tmp_path / "map.pkl"),
            clear=True,
            skip_known=False,
        )

    assert Path(db_path).exists(), "DB file was deleted – WinError 32 risk on Windows"
    assert db_path not in unlinked, (
        f"Path.unlink() was called on the DB file: {unlinked}"
    )


def test_clear_removes_existing_chunks(tmp_path):
    """After clear=True the chunks table must be empty."""
    db_path = str(tmp_path / "db.sqlite")
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    _make_db(db_path)

    # Verify the pre-condition: DB has data.
    conn = sqlite3.connect(db_path)
    before = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    conn.close()
    assert before > 0, "Pre-condition: DB should have at least one chunk"

    from app.ingestion.ingest import ingest_directory

    ingest_directory(
        input_dir=str(docs_dir),
        db_path=db_path,
        faiss_path=str(tmp_path / "index.faiss"),
        faiss_map_path=str(tmp_path / "map.pkl"),
        clear=True,
        skip_known=False,
    )

    conn = sqlite3.connect(db_path)
    after = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    conn.close()
    assert after == 0, "DB was not cleared – old chunks still present after reindex"


def test_clear_safe_when_db_does_not_exist(tmp_path):
    """clear=True is a no-op when the DB file does not yet exist (no crash)."""
    db_path = str(tmp_path / "new_db.sqlite")
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    assert not Path(db_path).exists(), "Pre-condition: DB file must not exist"

    from app.ingestion.ingest import ingest_directory

    # Should not raise even though there is nothing to clear.
    ingest_directory(
        input_dir=str(docs_dir),
        db_path=db_path,
        faiss_path=str(tmp_path / "index.faiss"),
        faiss_map_path=str(tmp_path / "map.pkl"),
        clear=True,
        skip_known=False,
    )
