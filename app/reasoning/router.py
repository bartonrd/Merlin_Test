"""Query routing: decide retrieval strategy based on input type."""
from typing import List, Optional, Tuple

from app.reasoning.log_parser import build_search_query, is_error_log, parse_log_signature
from app.retrieval.bm25 import SearchResult
from app.retrieval.hybrid import hybrid_search
from config import settings


def route_and_retrieve(
    query: str,
    db_path: str,
    faiss_path: str,
    faiss_map_path: str,
) -> Tuple[List[SearchResult], bool]:
    """Determine query type and retrieve relevant chunks.

    Returns (results, is_triage).

    - Normal question:  search runbooks + architecture + general docs
    - Error log/trace:  search incidents + runbooks + architecture (priority on incidents)
    """
    is_triage = is_error_log(query)

    if is_triage:
        sig = parse_log_signature(query)
        search_query = build_search_query(query, sig)
        doc_type_filter: Optional[List[str]] = ["incident", "runbook", "arch"]
    else:
        search_query = query
        doc_type_filter = ["runbook", "arch", "general"]

    results = hybrid_search(
        query=search_query,
        db_path=db_path,
        faiss_path=faiss_path,
        faiss_map_path=faiss_map_path,
        top_k_bm25=settings.top_k_bm25,
        top_k_vector=settings.top_k_vector,
        top_k_final=settings.top_k_final,
        embed_model=settings.embed_model,
        embed_device=settings.embed_device,
        doc_type_filter=doc_type_filter,
        reranker_enabled=settings.reranker_enabled,
        reranker_model=settings.reranker_model,
        query_text=search_query,
    )

    # If filtered search returned nothing, fall back to an unfiltered search
    if not results:
        results = hybrid_search(
            query=search_query,
            db_path=db_path,
            faiss_path=faiss_path,
            faiss_map_path=faiss_map_path,
            top_k_bm25=settings.top_k_bm25,
            top_k_vector=settings.top_k_vector,
            top_k_final=settings.top_k_final,
            embed_model=settings.embed_model,
            embed_device=settings.embed_device,
            doc_type_filter=None,
            reranker_enabled=settings.reranker_enabled,
            reranker_model=settings.reranker_model,
            query_text=search_query,
        )

    return results, is_triage
