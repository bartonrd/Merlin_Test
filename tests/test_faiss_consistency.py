"""Tests for FAISS/FTS5 index consistency check in ingest_directory.

When the server is killed between ``insert_chunks`` (which commits to SQLite)
and ``build_faiss_index`` (which writes the FAISS file), the DB contains chunk
IDs that are absent from the FAISS map.  On the next startup, ``skip_known``
causes the file to be skipped so the FAISS is never repaired – leaving those
chunks permanently invisible to vector search.

The fix is ``_faiss_missing_ids``: if the DB has chunk IDs not in the FAISS map,
``ingest_directory`` rebuilds both the FTS5 and FAISS indexes even when no new
documents are present.
"""
import pickle
import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np
import pytest

from app.ingestion.ingest import (
    _faiss_missing_ids,
    init_db,
    insert_chunks,
    ingest_directory,
)
from app.ingestion.chunking import Chunk


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chunk(doc_id: str = "doc1", text: str = "hello world") -> Chunk:
    return Chunk(
        doc_id=doc_id,
        title="Test Doc",
        path=f"/docs/{doc_id}.txt",
        doc_type="general",
        section="",
        chunk_index=0,
        text=text,
    )


def _write_faiss_map(map_path: str, faiss_map: dict) -> None:
    with open(map_path, "wb") as fh:
        pickle.dump(faiss_map, fh)


# ---------------------------------------------------------------------------
# _faiss_missing_ids unit tests
# ---------------------------------------------------------------------------


def test_faiss_missing_ids_returns_true_when_map_absent(tmp_path):
    """If the FAISS map file doesn't exist, report missing IDs (needs rebuild)."""
    db_path = str(tmp_path / "db.sqlite")
    conn = init_db(db_path)
    insert_chunks(conn, [_make_chunk()])
    conn.close()

    missing_map = str(tmp_path / "nonexistent.pkl")
    conn2 = sqlite3.connect(db_path)
    assert _faiss_missing_ids(missing_map, conn2) is True
    conn2.close()


def test_faiss_missing_ids_returns_true_when_chunk_not_in_map(tmp_path):
    """DB has chunk id=1 but FAISS map only covers id=99 → missing."""
    db_path = str(tmp_path / "db.sqlite")
    map_path = str(tmp_path / "map.pkl")

    conn = init_db(db_path)
    insert_chunks(conn, [_make_chunk()])
    conn.close()

    # FAISS map that does NOT include the DB chunk id
    _write_faiss_map(map_path, {0: 99})  # maps faiss_idx=0 → db_id=99 (not 1)

    conn2 = sqlite3.connect(db_path)
    assert _faiss_missing_ids(map_path, conn2) is True
    conn2.close()


def test_faiss_missing_ids_returns_false_when_all_present(tmp_path):
    """All DB chunk IDs present in FAISS map → no rebuild needed."""
    db_path = str(tmp_path / "db.sqlite")
    map_path = str(tmp_path / "map.pkl")

    conn = init_db(db_path)
    insert_chunks(conn, [_make_chunk()])
    # The inserted chunk gets id=1 (AUTOINCREMENT starts at 1)
    conn.close()

    _write_faiss_map(map_path, {0: 1})  # faiss_idx=0 → db_id=1

    conn2 = sqlite3.connect(db_path)
    assert _faiss_missing_ids(map_path, conn2) is False
    conn2.close()


def test_faiss_missing_ids_returns_true_on_corrupt_map(tmp_path):
    """A corrupt/unreadable FAISS map file triggers a rebuild."""
    db_path = str(tmp_path / "db.sqlite")
    map_path = str(tmp_path / "map.pkl")

    conn = init_db(db_path)
    insert_chunks(conn, [_make_chunk()])
    conn.close()

    Path(map_path).write_bytes(b"not valid pickle data")

    conn2 = sqlite3.connect(db_path)
    assert _faiss_missing_ids(map_path, conn2) is True
    conn2.close()


# ---------------------------------------------------------------------------
# ingest_directory integration test: stale FAISS triggers rebuild
# ---------------------------------------------------------------------------


def test_ingest_directory_rebuilds_indexes_when_faiss_stale(tmp_path):
    """ingest_directory rebuilds FAISS+FTS5 when DB chunks are absent from FAISS.

    Simulates the crash scenario: chunk is in the DB but the FAISS map is
    missing its ID.  On the next call with skip_known=True (no new files),
    the stale-FAISS branch must trigger a rebuild.
    """
    db_path = str(tmp_path / "db.sqlite")
    faiss_path = str(tmp_path / "index.faiss")
    map_path = str(tmp_path / "map.pkl")
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    # Pre-populate DB with a chunk (simulating a previous partial run)
    conn = init_db(db_path)
    insert_chunks(conn, [_make_chunk("preloaded", "content about FWF266")])
    conn.close()

    # Write a stale FAISS map that does NOT include the preloaded chunk id
    _write_faiss_map(map_path, {})  # empty → all DB ids are missing

    rebuild_fts_called = []
    rebuild_faiss_called = []

    def fake_build_fts(conn):
        rebuild_fts_called.append(True)

    def fake_build_faiss(conn, fp, mp):
        rebuild_faiss_called.append(True)

    with (
        patch("app.ingestion.ingest.build_fts_index", side_effect=fake_build_fts),
        patch("app.ingestion.ingest.build_faiss_index", side_effect=fake_build_faiss),
    ):
        ingest_directory(
            input_dir=str(docs_dir),  # empty dir → no new files processed
            db_path=db_path,
            faiss_path=faiss_path,
            faiss_map_path=map_path,
            skip_known=True,
        )

    assert rebuild_fts_called, "build_fts_index was not called for stale FAISS"
    assert rebuild_faiss_called, "build_faiss_index was not called for stale FAISS"
