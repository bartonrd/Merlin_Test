"""Hybrid BM25 + vector search with optional cross-encoder reranking."""
from typing import Dict, List, Optional

from app.retrieval.bm25 import SearchResult, bm25_search
from app.retrieval.faiss_store import vector_search


def _normalize_scores(results: List[SearchResult]) -> Dict[int, float]:
    """Min-max normalise scores to [0, 1], keyed by chunk_id."""
    if not results:
        return {}
    scores = [r.score for r in results]
    min_s, max_s = min(scores), max(scores)
    span = max_s - min_s
    if span == 0:
        return {r.chunk_id: 1.0 for r in results}
    return {r.chunk_id: (r.score - min_s) / span for r in results}


def hybrid_search(
    query: str,
    db_path: str,
    faiss_path: str,
    faiss_map_path: str,
    top_k_bm25: int = 10,
    top_k_vector: int = 10,
    top_k_final: int = 5,
    embed_model: str = "all-MiniLM-L6-v2",
    embed_device: str = "cpu",
    doc_type_filter: Optional[List[str]] = None,
    reranker_enabled: bool = False,
    reranker_model: str = "",
    query_text: Optional[str] = None,
) -> List[SearchResult]:
    """Run BM25 and vector search, fuse scores, optionally rerank.

    Score fusion:
        combined = 0.5 * bm25_norm + 0.5 * vector_norm
    """
    effective_query = query_text or query

    bm25_results = bm25_search(
        effective_query,
        db_path=db_path,
        top_k=top_k_bm25,
        doc_type_filter=doc_type_filter,
    )
    vector_results = vector_search(
        effective_query,
        faiss_path=faiss_path,
        faiss_map_path=faiss_map_path,
        db_path=db_path,
        top_k=top_k_vector,
        embed_model=embed_model,
        embed_device=embed_device,
        doc_type_filter=doc_type_filter,
    )

    # Build a map of chunk_id -> SearchResult (deduplicated)
    all_results: Dict[int, SearchResult] = {}
    for r in bm25_results + vector_results:
        if r.chunk_id not in all_results:
            all_results[r.chunk_id] = r

    bm25_norm = _normalize_scores(bm25_results)
    vector_norm = _normalize_scores(vector_results)

    # Fuse scores
    fused: Dict[int, float] = {}
    for chunk_id in all_results:
        b = bm25_norm.get(chunk_id, 0.0)
        v = vector_norm.get(chunk_id, 0.0)
        fused[chunk_id] = 0.5 * b + 0.5 * v

    # Sort by fused score and take top_k_final
    ranked = sorted(all_results.values(), key=lambda r: fused[r.chunk_id], reverse=True)
    ranked = ranked[:top_k_final]

    if reranker_enabled and reranker_model and ranked:
        ranked = _rerank(effective_query, ranked, reranker_model)

    return ranked


def _rerank(
    query: str,
    results: List[SearchResult],
    reranker_model: str,
) -> List[SearchResult]:
    """Rerank *results* using a cross-encoder model."""
    try:
        from sentence_transformers import CrossEncoder

        model = CrossEncoder(reranker_model)
        pairs = [(query, r.text) for r in results]
        scores = model.predict(pairs)
        ranked = sorted(zip(scores, results), key=lambda x: x[0], reverse=True)
        for score, result in ranked:
            result.score = float(score)
        return [r for _, r in ranked]
    except Exception:
        # Fallback: return original order if reranker fails
        return results
