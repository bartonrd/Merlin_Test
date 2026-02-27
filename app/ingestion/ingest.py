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
from typing import List

import faiss
import numpy as np

from app.ingestion.chunking import Chunk, chunk_document
from app.ingestion.embed import embed_texts
from app.ingestion.loaders import load_text
from config import settings

SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx"}

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
    conn.execute("DELETE FROM chunks_fts")
    conn.execute(
        """
        INSERT INTO chunks_fts (rowid, text, title, section, doc_type)
        SELECT id, text, title, section, doc_type FROM chunks
        """
    )
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
        help="Drop and recreate the DB before ingesting",
    )
    args = parser.parse_args()

    input_dir = Path(args.input)
    if not input_dir.exists():
        print(f"Input directory not found: {input_dir}")
        return

    if args.clear and Path(args.db).exists():
        Path(args.db).unlink()
        print(f"Cleared existing DB: {args.db}")

    conn = init_db(args.db)

    all_chunks: List[Chunk] = []
    files = [f for f in input_dir.rglob("*") if f.suffix.lower() in SUPPORTED_EXTENSIONS]

    if not files:
        print(f"No supported documents found in {input_dir}")
        return

    for file_path in sorted(files):
        try:
            chunks = process_file(file_path)
            insert_chunks(conn, chunks)
            all_chunks.extend(chunks)
            print(f"  {file_path.name}: {len(chunks)} chunks")
        except Exception as exc:
            print(f"  ERROR processing {file_path.name}: {exc}")

    print(f"\nTotal chunks inserted: {len(all_chunks)}")

    print("Building FTS5 index …")
    build_fts_index(conn)

    print("Building FAISS index …")
    build_faiss_index(conn, args.faiss, args.faiss_map)

    conn.close()
    print("Ingestion complete.")


if __name__ == "__main__":
    main()
