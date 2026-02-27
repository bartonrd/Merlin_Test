"""
app/ingestion/embed.py – Local sentence-transformer embedding helper.

Wraps SentenceTransformer so it can be used as a singleton and
batches inputs for efficiency.  No network calls are made after the
model is loaded from the local cache.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

_model_instance = None
_model_name_loaded: Optional[str] = None


def get_model(model_name: str):
    """Return a cached SentenceTransformer model, loading it once."""
    global _model_instance, _model_name_loaded
    if _model_instance is None or _model_name_loaded != model_name:
        from sentence_transformers import SentenceTransformer  # type: ignore

        logger.info("Loading embedding model: %s", model_name)
        _model_instance = SentenceTransformer(model_name)
        _model_name_loaded = model_name
    return _model_instance


def embed_texts(
    texts: list[str],
    model_name: str = "all-MiniLM-L6-v2",
    batch_size: int = 64,
    normalize: bool = True,
) -> np.ndarray:
    """Embed a list of texts and return a float32 numpy array of shape (N, D).

    Parameters
    ----------
    texts:      List of strings to embed.
    model_name: Sentence-Transformers model name.
    batch_size: Number of texts per batch.
    normalize:  If True, L2-normalize the embeddings (recommended for cosine sim).
    """
    model = get_model(model_name)
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=normalize,
    )
    return embeddings.astype(np.float32)


def embed_query(
    query: str,
    model_name: str = "all-MiniLM-L6-v2",
    normalize: bool = True,
) -> np.ndarray:
    """Embed a single query string, returning shape (1, D)."""
    return embed_texts([query], model_name=model_name, normalize=normalize)
