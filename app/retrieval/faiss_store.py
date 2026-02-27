"""Vector search using FAISS with metadata look-up from SQLite."""
import pickle
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

import faiss
import numpy as np

from app.ingestion.embed import embed_texts
from app.retrieval.bm25 import SearchResult


def vector_search(
    query: str,
    faiss_path: str,
    faiss_map_path: str,
    db_path: str,
    top_k: int = 10,
    embed_model: str = "all-MiniLM-L6-v2",
    embed_device: str = "cpu",
    doc_type_filter: Optional[List[str]] = None,
) -> List[SearchResult]:
    """Embed query, search FAISS, fetch metadata from SQLite.

    Returns up to *top_k* results sorted by cosine similarity (descending).
    If *doc_type_filter* is provided, results are post-filtered to matching
    doc_types (we over-fetch to compensate for filtered-out results).
    """
    if not Path(faiss_path).exists() or not Path(faiss_map_path).exists():
        return []

    # Load FAISS index and ID map
    index = faiss.read_index(faiss_path)
    with open(faiss_map_path, "rb") as fh:
        faiss_map: Dict[int, int] = pickle.load(fh)

    # Embed query (already L2-normalised by embed_texts)
    query_vec = embed_texts([query], embed_model, embed_device)  # shape (1, dim)

    # Over-fetch if filtering to reduce chance of empty results
    fetch_k = top_k * 3 if doc_type_filter else top_k
    fetch_k = min(fetch_k, index.ntotal)
    if fetch_k == 0:
        return []

    scores, indices = index.search(query_vec, fetch_k)
    # scores shape: (1, fetch_k); indices shape: (1, fetch_k)

    candidate_db_ids = [
        (faiss_map[int(idx)], float(scores[0][rank]))
        for rank, idx in enumerate(indices[0])
        if int(idx) != -1 and int(idx) in faiss_map
    ]

    if not candidate_db_ids:
        return []

    # Fetch metadata from SQLite
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        id_to_score = {db_id: score for db_id, score in candidate_db_ids}
        placeholders = ",".join("?" * len(id_to_score))
        rows = conn.execute(
            f"SELECT id, doc_id, title, path, doc_type, section, chunk_index, text "
            f"FROM chunks WHERE id IN ({placeholders})",
            list(id_to_score.keys()),
        ).fetchall()
    finally:
        conn.close()

    results: List[SearchResult] = []
    for row in rows:
        if doc_type_filter and row["doc_type"] not in doc_type_filter:
            continue
        results.append(
            SearchResult(
                chunk_id=row["id"],
                score=id_to_score[row["id"]],
                doc_id=row["doc_id"],
                title=row["title"],
                path=row["path"],
                doc_type=row["doc_type"],
                section=row["section"],
                chunk_index=row["chunk_index"],
                text=row["text"],
            )
        )

    # Sort by score descending and take top_k
    results.sort(key=lambda r: r.score, reverse=True)
    return results[:top_k]
