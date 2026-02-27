"""
app/retrieval/faiss_store.py – FAISS vector similarity search.

Loads a FAISS index and a JSON mapping of vector-id → chunk_id,
then looks up chunk metadata from SQLite.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Optional

import numpy as np

from app.retrieval.bm25 import SearchResult

logger = logging.getLogger(__name__)

_index_cache: dict[str, object] = {}
_map_cache: dict[str, list[str]] = {}


def _load_index(faiss_path: str):
    """Load (and cache) the FAISS index from disk."""
    if faiss_path not in _index_cache:
        import faiss  # type: ignore

        if not Path(faiss_path).exists():
            raise FileNotFoundError(f"FAISS index not found: {faiss_path}")
        _index_cache[faiss_path] = faiss.read_index(faiss_path)
        logger.info("Loaded FAISS index from %s (%d vectors)", faiss_path, _index_cache[faiss_path].ntotal)
    return _index_cache[faiss_path]


def _load_map(map_path: str) -> list[str]:
    """Load (and cache) the vector-id → chunk_id mapping."""
    if map_path not in _map_cache:
        with open(map_path) as fh:
            _map_cache[map_path] = json.load(fh)
    return _map_cache[map_path]


def _fetch_chunks(db_path: str, chunk_ids: list[str]) -> dict[str, dict]:
    """Retrieve chunk metadata from SQLite for a list of chunk_ids."""
    if not chunk_ids:
        return {}
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        placeholders = ",".join("?" * len(chunk_ids))
        rows = conn.execute(
            f"""
            SELECT chunk_id, doc_id, title, path, doc_type, section,
                   chunk_index, text, timestamp
            FROM chunks WHERE chunk_id IN ({placeholders})
            """,
            chunk_ids,
        ).fetchall()
    finally:
        conn.close()

    return {
        row[0]: {
            "doc_id": row[1],
            "title": row[2],
            "path": row[3],
            "doc_type": row[4],
            "section": row[5],
            "chunk_index": row[6],
            "text": row[7],
            "timestamp": row[8],
        }
        for row in rows
    }


def vector_search(
    query_embedding: np.ndarray,
    db_path: str,
    faiss_path: str,
    faiss_map_path: str,
    top_k: int = 10,
    doc_type_filter: Optional[str] = None,
) -> list[SearchResult]:
    """Search the FAISS index for the most similar chunks.

    Parameters
    ----------
    query_embedding:  Shape (1, D) float32 numpy array.
    db_path:          SQLite path for metadata lookup.
    faiss_path:       FAISS index file path.
    faiss_map_path:   JSON file mapping FAISS position → chunk_id.
    top_k:            Number of nearest neighbours to retrieve.
    doc_type_filter:  If set, only return results of this doc_type.
    """
    try:
        index = _load_index(faiss_path)
        id_map = _load_map(faiss_map_path)
    except (FileNotFoundError, Exception) as exc:
        logger.warning("Vector search unavailable: %s", exc)
        return []

    # Over-fetch if filtering, so we have enough after the filter
    fetch_k = top_k * 3 if doc_type_filter else top_k
    scores, indices = index.search(query_embedding, min(fetch_k, index.ntotal))

    # Flatten (search returns 2-D arrays for batch queries)
    scores = scores[0].tolist()
    indices = indices[0].tolist()

    candidate_ids = [
        id_map[i] for i in indices if 0 <= i < len(id_map)
    ]
    score_map = {id_map[i]: s for i, s in zip(indices, scores) if 0 <= i < len(id_map)}

    meta = _fetch_chunks(db_path, candidate_ids)

    results: list[SearchResult] = []
    for cid in candidate_ids:
        m = meta.get(cid)
        if m is None:
            continue
        if doc_type_filter and m["doc_type"] != doc_type_filter:
            continue
        results.append(
            SearchResult(
                chunk_id=cid,
                doc_id=m["doc_id"],
                title=m["title"],
                path=m["path"],
                doc_type=m["doc_type"],
                section=m["section"],
                chunk_index=m["chunk_index"],
                text=m["text"],
                timestamp=m["timestamp"],
                score=float(score_map.get(cid, 0.0)),
                source="vector",
            )
        )
        if len(results) >= top_k:
            break

    return results


def invalidate_cache() -> None:
    """Clear in-memory FAISS and map caches (call after re-ingestion)."""
    _index_cache.clear()
    _map_cache.clear()
