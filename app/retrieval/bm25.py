"""
app/retrieval/bm25.py – BM25 lexical search via SQLite FTS5.

The FTS5 virtual table ``chunks_fts`` is created by the ingestion pipeline.
This module provides a query function that returns scored ``SearchResult``
objects.
"""
from __future__ import annotations

import logging
import sqlite3
from typing import Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class SearchResult(BaseModel):
    """A single search result with metadata and score."""

    chunk_id: str
    doc_id: str
    title: str
    path: str
    doc_type: str
    section: str
    chunk_index: int
    text: str
    timestamp: Optional[str]
    score: float = 0.0
    source: str = "bm25"  # "bm25" | "vector"


def bm25_search(
    query: str,
    db_path: str,
    top_k: int = 10,
    doc_type_filter: Optional[str] = None,
) -> list[SearchResult]:
    """Run a BM25 search using SQLite FTS5.

    Parameters
    ----------
    query:           User query string.
    db_path:         Path to the SQLite database.
    top_k:           Maximum number of results to return.
    doc_type_filter: If set, restrict results to this doc_type.

    Returns a list of ``SearchResult`` sorted by BM25 score descending.
    """
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        logger.warning("DB not found or not readable: %s", db_path)
        return []

    try:
        # FTS5 bm25() returns negative values (lower = better match).
        # We negate to get a positive score where higher = better.
        base_query = """
            SELECT
                c.chunk_id, c.doc_id, c.title, c.path, c.doc_type,
                c.section, c.chunk_index, c.text, c.timestamp,
                -bm25(chunks_fts) AS score
            FROM chunks_fts
            JOIN chunks c ON c.rowid = chunks_fts.rowid
            WHERE chunks_fts MATCH ?
        """
        params: list = [_fts5_escape(query)]

        if doc_type_filter:
            base_query += " AND c.doc_type = ?"
            params.append(doc_type_filter)

        base_query += " ORDER BY score DESC LIMIT ?"
        params.append(top_k)

        rows = conn.execute(base_query, params).fetchall()
    except sqlite3.OperationalError as exc:
        logger.warning("BM25 query failed: %s", exc)
        return []
    finally:
        conn.close()

    results = []
    for row in rows:
        results.append(
            SearchResult(
                chunk_id=row[0],
                doc_id=row[1],
                title=row[2],
                path=row[3],
                doc_type=row[4],
                section=row[5],
                chunk_index=row[6],
                text=row[7],
                timestamp=row[8],
                score=float(row[9]),
                source="bm25",
            )
        )
    return results


def _fts5_escape(query: str) -> str:
    """Escape/clean a query string for FTS5 MATCH.

    FTS5 is sensitive to special characters.  We keep it simple:
    strip non-alphanumeric characters (except spaces/hyphens) and
    fall back to a phrase query if the cleaned string is multi-word.
    """
    # Remove characters that break FTS5 syntax
    cleaned = " ".join(
        word.strip('!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~')
        for word in query.split()
        if word.strip('!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~')
    )
    if not cleaned:
        return '""'
    return cleaned
