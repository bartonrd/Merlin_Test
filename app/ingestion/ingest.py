"""
Ingestion CLI – index documents into SQLite FTS5 + FAISS.

Usage:
    python -m app.ingestion.ingest --input ./docs --db ./data/db.sqlite --faiss ./data/index.faiss
"""
import argparse
import hashlib
import pickle
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Set, Union

import faiss
import numpy as np

from app.ingestion.chunking import Chunk, chunk_document
from app.ingestion.embed import embed_texts
from app.ingestion.loaders import load_text
from config import settings

SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".csv"}

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS chunks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id       TEXT    NOT NULL,
    title        TEXT    NOT NULL,
    path         TEXT    NOT NULL,
    doc_type     TEXT    NOT NULL,
    section      TEXT    NOT NULL,
    chunk_index  INTEGER NOT NULL,
    text         TEXT    NOT NULL,
    timestamp    TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text,
    title,
    section,
    doc_type,
    content=chunks,
    content_rowid=id
);
"""


def _clear_db_contents(db_path: str) -> None:
    """Clear all ingested data from an existing DB without deleting the file.

    Deleting the file with ``Path.unlink()`` raises ``WinError 32`` on Windows
    when any process (e.g. the running FastAPI server) still holds the file
    open.  Using SQL DELETE keeps the file intact while producing the same
    empty-slate result.
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("DELETE FROM chunks")
        # Rebuild the FTS5 index so it stays in sync with the now-empty content table.
        try:
            conn.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")
        except sqlite3.OperationalError:
            pass  # FTS table may not exist yet in a brand-new DB
        conn.commit()
    finally:
        conn.close()
    print(f"[ingest] Cleared existing DB: {db_path}")


def init_db(db_path: str) -> sqlite3.Connection:
    """Create SQLite DB with FTS5 and chunks tables."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(_DDL)
    conn.commit()
    return conn


def insert_chunks(conn: sqlite3.Connection, chunks: List[Chunk]) -> List[int]:
    """Insert chunks into the chunks table, return rowids."""
    rowids: List[int] = []
    cur = conn.cursor()
    for chunk in chunks:
        cur.execute(
            """
            INSERT INTO chunks (doc_id, title, path, doc_type, section, chunk_index, text, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chunk.doc_id,
                chunk.title,
                chunk.path,
                chunk.doc_type,
                chunk.section,
                chunk.chunk_index,
                chunk.text,
                chunk.timestamp,
            ),
        )
        rowids.append(cur.lastrowid)  # type: ignore[arg-type]
    conn.commit()
    return rowids


def build_fts_index(conn: sqlite3.Connection) -> None:
    """Populate the FTS5 table from the chunks table."""
    conn.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")
    conn.commit()


def build_faiss_index(
    conn: sqlite3.Connection,
    faiss_path: str,
    map_path: str,
) -> None:
    """Embed all chunks and build a FAISS IndexFlatIP (cosine via L2-norm)."""
    cur = conn.execute("SELECT id, text FROM chunks ORDER BY id")
    rows = cur.fetchall()
    if not rows:
        print("No chunks found – skipping FAISS index build.")
        return

    db_ids = [row[0] for row in rows]
    texts = [row[1] for row in rows]

    print(f"Embedding {len(texts)} chunks …")
    vectors = embed_texts(texts, settings.embed_model, settings.embed_device)

    dim = vectors.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(vectors)

    Path(faiss_path).parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, faiss_path)

    faiss_map = {faiss_idx: db_id for faiss_idx, db_id in enumerate(db_ids)}
    with open(map_path, "wb") as fh:
        pickle.dump(faiss_map, fh)

    print(f"FAISS index saved: {faiss_path}  ({len(db_ids)} vectors, dim={dim})")


# ---------------------------------------------------------------------------
# Document processing
# ---------------------------------------------------------------------------


def _doc_id(path: Path) -> str:
    """Generate a stable doc_id from the file path."""
    return hashlib.md5(str(path).encode()).hexdigest()[:12]


def process_file(path: Path) -> List[Chunk]:
    """Load and chunk a single document."""
    text = load_text(path)
    doc_id = _doc_id(path)
    title = path.stem.replace("_", " ").replace("-", " ").title()
    return chunk_document(text, doc_id, title, str(path))


# ---------------------------------------------------------------------------
# Reusable ingestion function (also used by the server startup handler)
# ---------------------------------------------------------------------------


def get_known_doc_ids(conn: sqlite3.Connection) -> Set[str]:
    """Return the set of doc_ids already present in the chunks table."""
    cur = conn.execute("SELECT DISTINCT doc_id FROM chunks")
    return {row[0] for row in cur.fetchall()}


def ingest_directory(
    input_dir: Union[str, Path],
    db_path: str,
    faiss_path: str,
    faiss_map_path: str,
    clear: bool = False,
    skip_known: bool = True,
) -> Dict[str, Any]:
    """Ingest all supported documents in *input_dir* into the index.

    Args:
        input_dir:      Directory to scan for documents.
        db_path:        SQLite DB path.
        faiss_path:     FAISS index path.
        faiss_map_path: FAISS map pickle path.
        clear:          If True, clear all existing data from the DB before ingesting.
        skip_known:     If True (default), skip files whose doc_id is already
                        in the DB so repeated startups don't create duplicates.

    Returns:
        A dict with keys:
            ``total`` – number of new chunks inserted during this run.
            ``files`` – list of ``{"name": str, "chunks": int}`` dicts, one
                        per successfully processed file.
    """
    input_dir = Path(input_dir)
    if not input_dir.exists():
        print(f"[ingest] Input directory not found: {input_dir}")
        return {"total": 0, "files": []}

    if clear and Path(db_path).exists():
        _clear_db_contents(db_path)

    conn = init_db(db_path)
    known_ids = get_known_doc_ids(conn) if skip_known else set()

    files = [f for f in input_dir.rglob("*") if f.suffix.lower() in SUPPORTED_EXTENSIONS]
    if not files:
        print(f"[ingest] No supported documents found in {input_dir}")
        conn.close()
        return {"total": 0, "files": []}

    new_chunks: List[Chunk] = []
    file_details: List[Dict[str, Any]] = []
    for file_path in sorted(files):
        doc_id = _doc_id(file_path)
        if doc_id in known_ids:
            print(f"[ingest] Skipping already-indexed: {file_path.name}")
            continue
        try:
            chunks = process_file(file_path)
            insert_chunks(conn, chunks)
            new_chunks.extend(chunks)
            file_details.append({"name": file_path.name, "chunks": len(chunks)})
            print(f"[ingest]   {file_path.name}: {len(chunks)} chunks")
        except Exception as exc:
            print(f"[ingest]   ERROR processing {file_path.name}: {exc}")

    if new_chunks:
        print(f"[ingest] {len(new_chunks)} new chunk(s) inserted – rebuilding indexes …")
        build_fts_index(conn)
        build_faiss_index(conn, faiss_path, faiss_map_path)
        print("[ingest] Ingestion complete.")
    else:
        print("[ingest] No new documents – indexes unchanged.")

    conn.close()
    return {"total": len(new_chunks), "files": file_details}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point for document ingestion."""
    parser = argparse.ArgumentParser(description="Ingest documents into the index.")
    parser.add_argument("--input", default=settings.docs_dir, help="Input directory")
    parser.add_argument("--db", default=settings.db_path, help="SQLite DB path")
    parser.add_argument("--faiss", default=settings.faiss_path, help="FAISS index path")
    parser.add_argument("--faiss-map", default=settings.faiss_map_path, help="FAISS map path")
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear all data from the DB before ingesting",
    )
    args = parser.parse_args()

    ingest_directory(
        input_dir=args.input,
        db_path=args.db,
        faiss_path=args.faiss,
        faiss_map_path=args.faiss_map,
        clear=args.clear,
        skip_known=False,  # CLI always re-processes (matches original behaviour)
    )


if __name__ == "__main__":
    main()
