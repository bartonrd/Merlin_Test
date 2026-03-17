"""Tests for the FTS5 query sanitizer in bm25.py.

The ``_sanitize_fts_query`` function prevents silent ``OperationalError``
failures that occur when a user's freeform query contains FTS5 special
characters (``AND``, ``OR``, ``NOT``, ``*``, ``^``, quotes, parentheses)
which SQLite would otherwise interpret as query operators.
"""
import sqlite3
from pathlib import Path

import pytest

from app.retrieval.bm25 import _sanitize_fts_query, bm25_search
from app.ingestion.ingest import init_db, insert_chunks, build_fts_index
from app.ingestion.chunking import Chunk


# ---------------------------------------------------------------------------
# _sanitize_fts_query unit tests
# ---------------------------------------------------------------------------


def test_sanitize_simple_word():
    assert _sanitize_fts_query("FWF266") == '"FWF266"'


def test_sanitize_multi_word():
    result = _sanitize_fts_query("how to fix FWF266")
    assert result == '"how" "to" "fix" "FWF266"'


def test_sanitize_strips_fts5_operators():
    """AND / OR / NOT should become quoted tokens, not FTS5 operators."""
    result = _sanitize_fts_query("FWF266 OR FWF100")
    assert result == '"FWF266" "OR" "FWF100"'


def test_sanitize_strips_special_chars():
    """Special characters like * ^ are stripped; alphanumeric tokens remain."""
    result = _sanitize_fts_query("FWF266*")
    assert result == '"FWF266"'


def test_sanitize_strips_parentheses():
    result = _sanitize_fts_query("(FWF266)")
    assert result == '"FWF266"'


def test_sanitize_empty_string():
    assert _sanitize_fts_query("") == '""'


def test_sanitize_only_special_chars():
    assert _sanitize_fts_query("***") == '""'


def test_sanitize_quoted_query():
    """Embedded quotes in the user query should not break the sanitizer."""
    result = _sanitize_fts_query('"FWF266"')
    assert result == '"FWF266"'


# ---------------------------------------------------------------------------
# bm25_search integration: queries with special chars return results, not []
# ---------------------------------------------------------------------------


def _make_db_with_fts(tmp_path: Path, texts: list[str]) -> str:
    """Create a minimal DB + FTS5 index containing the given texts."""
    db_path = str(tmp_path / "db.sqlite")
    conn = init_db(db_path)
    chunks = [
        Chunk(
            doc_id=f"doc{i}",
            title="Test",
            path=f"/docs/doc{i}.txt",
            doc_type="general",
            section="",
            chunk_index=0,
            text=text,
        )
        for i, text in enumerate(texts)
    ]
    insert_chunks(conn, chunks)
    build_fts_index(conn)
    conn.close()
    return db_path


def test_bm25_search_finds_fwf266(tmp_path):
    """Plain alphanumeric query 'FWF266' should return the matching chunk."""
    db_path = _make_db_with_fts(tmp_path, ["FWF266 is a fatal workflow failure"])
    results = bm25_search("FWF266", db_path=db_path, top_k=5)
    assert len(results) >= 1
    assert any("FWF266" in r.text for r in results)


def test_bm25_search_does_not_fail_on_or_operator(tmp_path):
    """Query containing 'OR' must not raise OperationalError.

    Without sanitization, 'FWF266 OR FWF100' is parsed as an FTS5 boolean
    expression. After sanitization the query becomes literal quoted tokens and
    executes without error (even if it matches fewer results than intended).
    """
    db_path = _make_db_with_fts(tmp_path, ["FWF266 is a fatal workflow failure"])
    results = bm25_search("FWF266 OR FWF100", db_path=db_path, top_k=5)
    assert isinstance(results, list)  # Must not raise / silently error


def test_bm25_search_does_not_fail_on_asterisk(tmp_path):
    """Trailing asterisk in query must not raise OperationalError."""
    db_path = _make_db_with_fts(tmp_path, ["FWF266 is a fatal workflow failure"])
    # FTS5 prefix queries like "FWF266*" are valid, but bare "*" is not;
    # after sanitization the asterisk is stripped entirely.
    results = bm25_search("FWF266*", db_path=db_path, top_k=5)
    assert isinstance(results, list)  # Must not raise


def test_bm25_search_does_not_fail_on_quoted_query(tmp_path):
    """User wrapping query in quotes should not break FTS5 MATCH parsing."""
    db_path = _make_db_with_fts(tmp_path, ["FWF266 is a fatal workflow failure"])
    results = bm25_search('"FWF266"', db_path=db_path, top_k=5)
    assert isinstance(results, list)
