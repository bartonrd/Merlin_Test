"""
app/reasoning/router.py – Query routing logic.

Decides how to retrieve context based on whether the user input is a
normal question or an error log.  Returns a ranked list of chunks via
hybrid search, using appropriate doc_type priorities.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from app.reasoning.log_parser import parse_log, LogSignature
from app.retrieval.hybrid import hybrid_search
from app.retrieval.bm25 import SearchResult

logger = logging.getLogger(__name__)


def route_and_retrieve(
    query: str,
    db_path: str,
    faiss_path: str,
    faiss_map_path: str,
    embedding_model: str = "all-MiniLM-L6-v2",
    top_k_bm25: int = 10,
    top_k_vector: int = 10,
    top_k_final: int = 5,
    reranker_model: Optional[str] = None,
) -> tuple[list[SearchResult], LogSignature]:
    """Route a user query and return (ranked chunks, log signature).

    If the query looks like an error log:
    - Primary: incident docs
    - Secondary: runbooks + architecture
    Results are merged in priority order.

    If it is a normal question:
    - Runbooks + architecture + general docs (no filter → all types).
    """
    from app.ingestion.embed import embed_query  # lazy import to avoid circular

    sig = parse_log(query)
    effective_query = sig.search_query if sig.is_log and sig.search_query else query
    logger.debug("Router: is_log=%s, effective_query=%r", sig.is_log, effective_query[:80])

    query_vec = embed_query(effective_query, model_name=embedding_model)

    if sig.is_log:
        # First pass: prioritise incident documents
        incident_results = hybrid_search(
            effective_query, query_vec,
            db_path=db_path, faiss_path=faiss_path, faiss_map_path=faiss_map_path,
            top_k_bm25=top_k_bm25, top_k_vector=top_k_vector,
            top_k_final=top_k_final,
            reranker_model=reranker_model,
            doc_type_filter="incident",
        )
        # Second pass: runbooks & architecture (no filter picks up everything)
        general_results = hybrid_search(
            effective_query, query_vec,
            db_path=db_path, faiss_path=faiss_path, faiss_map_path=faiss_map_path,
            top_k_bm25=top_k_bm25, top_k_vector=top_k_vector,
            top_k_final=top_k_final,
            reranker_model=reranker_model,
        )
        # Merge: incidents first, then fill with other results (deduped)
        seen: set[str] = {r.chunk_id for r in incident_results}
        merged = list(incident_results)
        for r in general_results:
            if r.chunk_id not in seen:
                merged.append(r)
                seen.add(r.chunk_id)
        results = merged[:top_k_final]
    else:
        results = hybrid_search(
            effective_query, query_vec,
            db_path=db_path, faiss_path=faiss_path, faiss_map_path=faiss_map_path,
            top_k_bm25=top_k_bm25, top_k_vector=top_k_vector,
            top_k_final=top_k_final,
            reranker_model=reranker_model,
        )

    return results, sig
