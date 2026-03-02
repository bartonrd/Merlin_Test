"""Tests for min_vector_score threshold in vector_search."""
import pickle
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import faiss
import numpy as np
import pytest

from app.retrieval.faiss_store import vector_search


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DIM = 4          # small dimension – enough to test score filtering
_EPSILON = 1e-8   # small value added to norm denominator to avoid div-by-zero


# ---------------------------------------------------------------------------
# Helpers to build a tiny in-memory FAISS index + SQLite DB on disk
# ---------------------------------------------------------------------------


def _make_index_and_db(tmp_path: Path, vectors_and_ids):
    """
    Build a FAISS IndexFlatIP and a SQLite DB with the given vectors.

    vectors_and_ids: list of (np.ndarray shape (DIM,), db_id, text)
    """
    faiss_path = str(tmp_path / "test.faiss")
    map_path = str(tmp_path / "test_map.pkl")
    db_path = str(tmp_path / "test.db")

    # --- FAISS index ---
    index = faiss.IndexFlatIP(_DIM)
    faiss_map = {}
    for faiss_idx, (vec, db_id, _text) in enumerate(vectors_and_ids):
        norm = vec / (np.linalg.norm(vec) + _EPSILON)
        index.add(norm.reshape(1, -1).astype(np.float32))
        faiss_map[faiss_idx] = db_id

    faiss.write_index(index, faiss_path)
    with open(map_path, "wb") as fh:
        pickle.dump(faiss_map, fh)

    # --- SQLite DB ---
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS chunks (
            id           INTEGER PRIMARY KEY,
            doc_id       TEXT,
            title        TEXT,
            path         TEXT,
            doc_type     TEXT,
            section      TEXT,
            chunk_index  INTEGER,
            text         TEXT
        );
    """)
    _DOC_ID = "doc1"
    _TITLE = "Title"
    _PATH = "/p"
    _DOC_TYPE = "general"
    _SECTION = "intro"
    _CHUNK_INDEX = 0
    for _vec, db_id, text in vectors_and_ids:
        conn.execute(
            "INSERT INTO chunks (id, doc_id, title, path, doc_type, section, chunk_index, text) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (db_id, _DOC_ID, _TITLE, _PATH, _DOC_TYPE, _SECTION, _CHUNK_INDEX, text),
        )
    conn.commit()
    conn.close()

    return faiss_path, map_path, db_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_vector_search_filters_low_score_results(tmp_path):
    """
    Results with cosine similarity below min_vector_score are excluded.

    We create two vectors:
      - v_hi: identical to the query → cosine similarity ≈ 1.0  (above 0.3)
      - v_lo: orthogonal to the query → cosine similarity ≈ 0.0  (below 0.3)

    With min_vector_score=0.3, only v_hi should be returned.
    """
    query_vec = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    v_hi = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)   # cos sim ≈ 1.0
    v_lo = np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)   # cos sim ≈ 0.0

    faiss_path, map_path, db_path = _make_index_and_db(
        tmp_path,
        [(v_hi, 1, "high-relevance chunk"), (v_lo, 2, "low-relevance chunk")],
    )

    # Patch embed_texts to return the query vector and settings.min_vector_score=0.3
    with (
        patch("app.retrieval.faiss_store.embed_texts", return_value=query_vec.reshape(1, -1)),
        patch("app.retrieval.faiss_store.settings") as mock_settings,
    ):
        mock_settings.min_vector_score = 0.3
        results = vector_search(
            query="test",
            faiss_path=faiss_path,
            faiss_map_path=map_path,
            db_path=db_path,
            top_k=10,
        )

    texts = [r.text for r in results]
    assert "high-relevance chunk" in texts
    assert "low-relevance chunk" not in texts


def test_vector_search_zero_threshold_includes_all_results(tmp_path):
    """With min_vector_score=0.0 (no filtering), all results are returned."""
    query_vec = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    v_hi = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    v_lo = np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)

    faiss_path, map_path, db_path = _make_index_and_db(
        tmp_path,
        [(v_hi, 1, "high-relevance chunk"), (v_lo, 2, "low-relevance chunk")],
    )

    with (
        patch("app.retrieval.faiss_store.embed_texts", return_value=query_vec.reshape(1, -1)),
        patch("app.retrieval.faiss_store.settings") as mock_settings,
    ):
        mock_settings.min_vector_score = 0.0
        results = vector_search(
            query="test",
            faiss_path=faiss_path,
            faiss_map_path=map_path,
            db_path=db_path,
            top_k=10,
        )

    assert len(results) == 2


def test_vector_search_returns_empty_when_all_below_threshold(tmp_path):
    """When no vectors exceed the threshold, vector_search returns an empty list."""
    query_vec = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    # Both vectors are orthogonal to the query → cos sim ≈ 0.0
    v1 = np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)
    v2 = np.array([0.0, 0.0, 1.0, 0.0], dtype=np.float32)

    faiss_path, map_path, db_path = _make_index_and_db(
        tmp_path,
        [(v1, 1, "unrelated chunk A"), (v2, 2, "unrelated chunk B")],
    )

    with (
        patch("app.retrieval.faiss_store.embed_texts", return_value=query_vec.reshape(1, -1)),
        patch("app.retrieval.faiss_store.settings") as mock_settings,
    ):
        mock_settings.min_vector_score = 0.3
        results = vector_search(
            query="hi",
            faiss_path=faiss_path,
            faiss_map_path=map_path,
            db_path=db_path,
            top_k=10,
        )

    assert results == []
