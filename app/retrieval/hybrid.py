"""
app/retrieval/hybrid.py – Hybrid BM25 + vector search with optional reranking.

Algorithm:
1. Run BM25 (top_k_bm25) and vector search (top_k_vector) in parallel.
2. Deduplicate by chunk_id.
3. Min-max normalize scores within each source, then combine.
4. Sort by combined score, take top_k_final.
5. If reranker is configured, rerank the top_k_final candidates.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from app.retrieval.bm25 import SearchResult, bm25_search
from app.retrieval.faiss_store import vector_search

logger = logging.getLogger(__name__)

_reranker_cache: dict[str, object] = {}


def _normalize(scores: list[float]) -> list[float]:
    """Min-max normalize a list of floats to [0, 1]."""
    if not scores:
        return scores
    arr = np.array(scores, dtype=np.float32)
    lo, hi = arr.min(), arr.max()
    if hi == lo:
        return [1.0] * len(scores)
    return ((arr - lo) / (hi - lo)).tolist()


def _get_reranker(model_name: str):
    """Load (and cache) a sentence-transformers CrossEncoder model."""
    if model_name not in _reranker_cache:
        from sentence_transformers import CrossEncoder  # type: ignore

        logger.info("Loading reranker: %s", model_name)
        _reranker_cache[model_name] = CrossEncoder(model_name)
    return _reranker_cache[model_name]


def hybrid_search(
    query: str,
    query_embedding: np.ndarray,
    db_path: str,
    faiss_path: str,
    faiss_map_path: str,
    top_k_bm25: int = 10,
    top_k_vector: int = 10,
    top_k_final: int = 5,
    reranker_model: Optional[str] = None,
    doc_type_filter: Optional[str] = None,
) -> list[SearchResult]:
    """Run hybrid retrieval and return top_k_final ranked chunks.

    Parameters
    ----------
    query:           Original user query (for BM25 and reranker).
    query_embedding: Embedding of *query*, shape (1, D).
    db_path:         SQLite path.
    faiss_path:      FAISS index path.
    faiss_map_path:  FAISS id-map path.
    top_k_bm25:      BM25 candidate count.
    top_k_vector:    Vector candidate count.
    top_k_final:     Final results count (before optional rerank).
    reranker_model:  Cross-encoder model name or None.
    doc_type_filter: Restrict to a specific doc_type.
    """
    bm25_results = bm25_search(query, db_path, top_k=top_k_bm25, doc_type_filter=doc_type_filter)
    vec_results = vector_search(
        query_embedding, db_path, faiss_path, faiss_map_path,
        top_k=top_k_vector, doc_type_filter=doc_type_filter,
    )

    # Deduplicate: merge into a dict keyed by chunk_id keeping highest score per source
    by_id: dict[str, SearchResult] = {}
    bm25_scores: dict[str, float] = {}
    vec_scores: dict[str, float] = {}

    for r in bm25_results:
        bm25_scores[r.chunk_id] = r.score
        by_id[r.chunk_id] = r

    for r in vec_results:
        vec_scores[r.chunk_id] = r.score
        if r.chunk_id not in by_id:
            by_id[r.chunk_id] = r

    if not by_id:
        return []

    all_ids = list(by_id.keys())

    # Normalize scores independently
    bm25_norm = _normalize([bm25_scores.get(cid, 0.0) for cid in all_ids])
    vec_norm = _normalize([vec_scores.get(cid, 0.0) for cid in all_ids])

    # Reciprocal-rank-style combination: 0.5 * bm25 + 0.5 * vector
    combined = {
        cid: 0.5 * b + 0.5 * v
        for cid, b, v in zip(all_ids, bm25_norm, vec_norm)
    }

    ranked = sorted(all_ids, key=lambda cid: combined[cid], reverse=True)[:top_k_final]
    candidates = [by_id[cid] for cid in ranked]

    # Assign combined score for downstream use
    for r in candidates:
        r.score = combined[r.chunk_id]

    if reranker_model:
        candidates = _rerank(query, candidates, reranker_model)

    return candidates


def _rerank(
    query: str,
    candidates: list[SearchResult],
    model_name: str,
) -> list[SearchResult]:
    """Re-score candidates with a cross-encoder and return sorted by new score."""
    try:
        reranker = _get_reranker(model_name)
        pairs = [[query, r.text] for r in candidates]
        scores = reranker.predict(pairs)
        for r, s in zip(candidates, scores):
            r.score = float(s)
        candidates.sort(key=lambda r: r.score, reverse=True)
    except Exception as exc:
        logger.warning("Reranking failed, using hybrid scores: %s", exc)
    return candidates
