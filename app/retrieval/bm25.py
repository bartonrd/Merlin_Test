"""BM25 search via SQLite FTS5."""
import sqlite3
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class SearchResult:
    chunk_id: int
    score: float
    doc_id: str
    title: str
    path: str
    doc_type: str
    section: str
    chunk_index: int
    text: str


def bm25_search(
    query: str,
    db_path: str,
    top_k: int = 10,
    doc_type_filter: Optional[List[str]] = None,
) -> List[SearchResult]:
    """Search the FTS5 index using BM25.

    FTS5 bm25() returns negative scores (lower = more relevant), so we
    negate them so that higher score = more relevant.
    """
    if not query.strip():
        return []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        if doc_type_filter:
            placeholders = ",".join("?" * len(doc_type_filter))
            sql = f"""
                SELECT
                    chunks.id,
                    chunks.doc_id,
                    chunks.title,
                    chunks.path,
                    chunks.doc_type,
                    chunks.section,
                    chunks.chunk_index,
                    chunks.text,
                    -bm25(chunks_fts) AS score
                FROM chunks_fts
                JOIN chunks ON chunks.id = chunks_fts.rowid
                WHERE chunks_fts MATCH ?
                  AND chunks.doc_type IN ({placeholders})
                ORDER BY score DESC
                LIMIT ?
            """
            params: List = [query, *doc_type_filter, top_k]
        else:
            sql = """
                SELECT
                    chunks.id,
                    chunks.doc_id,
                    chunks.title,
                    chunks.path,
                    chunks.doc_type,
                    chunks.section,
                    chunks.chunk_index,
                    chunks.text,
                    -bm25(chunks_fts) AS score
                FROM chunks_fts
                JOIN chunks ON chunks.id = chunks_fts.rowid
                WHERE chunks_fts MATCH ?
                ORDER BY score DESC
                LIMIT ?
            """
            params = [query, top_k]

        rows = conn.execute(sql, params).fetchall()
        return [
            SearchResult(
                chunk_id=row["id"],
                score=row["score"],
                doc_id=row["doc_id"],
                title=row["title"],
                path=row["path"],
                doc_type=row["doc_type"],
                section=row["section"],
                chunk_index=row["chunk_index"],
                text=row["text"],
            )
            for row in rows
        ]
    except sqlite3.OperationalError:
        # FTS table may not exist yet or query syntax error
        return []
    finally:
        conn.close()
