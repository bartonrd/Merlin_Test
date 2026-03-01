"""
app/ingestion/ingest.py – CLI ingestion pipeline.

Usage:
    python -m app.ingestion.ingest --input ./docs --db ./data/db.sqlite --faiss ./data/index.faiss

Steps:
1. Walk input folder(s) for supported document types.
2. Extract text with loaders.py.
3. Chunk with chunking.py.
4. Store chunks in SQLite (FTS5).
5. Embed chunks and store in FAISS.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import sys
import uuid
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Path bootstrap – ensures project root is on sys.path so that `from app.*`
# imports work when this file is run directly (e.g. `python ingest.py` from
# inside app/ingestion/) as well as via `python -m app.ingestion.ingest`.
# ---------------------------------------------------------------------------
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _ensure_dirs(*paths: str) -> None:
    for p in paths:
        Path(p).parent.mkdir(parents=True, exist_ok=True)


def _init_db(conn: sqlite3.Connection) -> None:
    """Create schema if not present."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id   TEXT PRIMARY KEY,
            doc_id     TEXT NOT NULL,
            title      TEXT NOT NULL,
            path       TEXT NOT NULL,
            doc_type   TEXT NOT NULL,
            section    TEXT,
            chunk_index INTEGER,
            text       TEXT NOT NULL,
            timestamp  TEXT
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
        USING fts5(
            chunk_id UNINDEXED,
            text,
            title,
            section,
            content='chunks',
            content_rowid='rowid'
        );

        CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
            INSERT INTO chunks_fts(rowid, chunk_id, text, title, section)
            VALUES (new.rowid, new.chunk_id, new.text, new.title, new.section);
        END;

        CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
            INSERT INTO chunks_fts(chunks_fts, rowid, chunk_id, text, title, section)
            VALUES ('delete', old.rowid, old.chunk_id, old.text, old.title, old.section);
        END;
        """
    )
    conn.commit()


def _insert_chunks(conn: sqlite3.Connection, chunks) -> None:
    conn.executemany(
        """
        INSERT OR REPLACE INTO chunks
          (chunk_id, doc_id, title, path, doc_type, section, chunk_index, text, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                c.chunk_id,
                c.doc_id,
                c.title,
                c.path,
                c.doc_type,
                c.section,
                c.chunk_index,
                c.text,
                c.timestamp,
            )
            for c in chunks
        ],
    )
    conn.commit()


def _build_faiss(
    embeddings: np.ndarray,
    chunk_ids: list[str],
    faiss_path: str,
    map_path: str,
) -> None:
    import faiss  # type: ignore

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)  # inner product = cosine when vectors are normalized
    index.add(embeddings)
    faiss.write_index(index, faiss_path)
    with open(map_path, "w") as fh:
        json.dump(chunk_ids, fh)
    logger.info("FAISS index written: %d vectors, dim=%d", index.ntotal, dim)


def ingest(
    input_dirs: list[str],
    db_path: str,
    faiss_path: str,
    faiss_map_path: str,
    embedding_model: str = "all-MiniLM-L6-v2",
    embedding_batch_size: int = 64,
    doc_type_override: Optional[str] = None,
) -> int:
    """Run the full ingestion pipeline.

    Returns the total number of chunks stored.
    """
    from app.ingestion.loaders import load_document, supported_extensions
    from app.ingestion.chunking import chunk_document
    from app.ingestion.embed import embed_texts

    _ensure_dirs(db_path, faiss_path, faiss_map_path)

    conn = sqlite3.connect(db_path)
    _init_db(conn)

    all_chunks = []
    exts = supported_extensions()

    for input_dir in input_dirs:
        root = Path(input_dir)
        if not root.exists():
            logger.warning("Input path does not exist: %s", input_dir)
            continue
        files = [f for f in root.rglob("*") if f.is_file() and f.suffix.lower() in exts]
        logger.info("Found %d files in %s", len(files), input_dir)

        for file_path in files:
            try:
                text = load_document(file_path)
            except Exception as exc:
                logger.warning("Failed to load %s: %s", file_path, exc)
                continue

            doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, str(file_path.resolve())))
            title = file_path.stem.replace("_", " ").replace("-", " ").title()
            chunks = chunk_document(
                text=text,
                doc_id=doc_id,
                title=title,
                path=str(file_path),
                doc_type=doc_type_override,
            )
            all_chunks.extend(chunks)
            logger.info("  %s → %d chunks (doc_type=%s)", file_path.name, len(chunks), chunks[0].doc_type if chunks else "n/a")

    if not all_chunks:
        logger.warning("No chunks produced – check input path and file types.")
        conn.close()
        return 0

    logger.info("Inserting %d chunks into SQLite…", len(all_chunks))
    _insert_chunks(conn, all_chunks)
    conn.close()

    logger.info("Embedding %d chunks…", len(all_chunks))
    texts = [c.text for c in all_chunks]
    embeddings = embed_texts(texts, model_name=embedding_model, batch_size=embedding_batch_size)

    _build_faiss(embeddings, [c.chunk_id for c in all_chunks], faiss_path, faiss_map_path)

    logger.info("Ingestion complete: %d chunks stored.", len(all_chunks))
    return len(all_chunks)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Merlin document ingestion pipeline")
    parser.add_argument(
        "--input", nargs="+", required=True,
        help="One or more directories containing documents to ingest",
    )
    parser.add_argument("--db", default="./data/db.sqlite", help="SQLite DB path")
    parser.add_argument("--faiss", default="./data/index.faiss", help="FAISS index path")
    parser.add_argument("--faiss-map", default="./data/faiss_map.json", help="FAISS id→chunk_id map path")
    parser.add_argument("--embedding-model", default="all-MiniLM-L6-v2", help="Embedding model name")
    parser.add_argument("--doc-type", default=None, choices=["runbook", "incident", "architecture", "general"],
                        help="Force doc type for all documents (auto-detected by default)")
    args = parser.parse_args()

    count = ingest(
        input_dirs=args.input,
        db_path=args.db,
        faiss_path=args.faiss,
        faiss_map_path=args.faiss_map,
        embedding_model=args.embedding_model,
        doc_type_override=args.doc_type,
    )
    sys.exit(0 if count >= 0 else 1)


if __name__ == "__main__":
    main()
