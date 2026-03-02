"""Embedding utilities with lazy singleton model loading."""
from typing import List, Optional

import numpy as np
from sentence_transformers import SentenceTransformer

from config import settings

_model: Optional[SentenceTransformer] = None
_model_name: Optional[str] = None


def get_model(model_name: str, device: str = "cpu") -> SentenceTransformer:
    """Lazy-load the embedding model (singleton per process)."""
    global _model, _model_name
    if _model is None or _model_name != model_name:
        _model = SentenceTransformer(
            model_name,
            device=device,
            local_files_only=settings.embed_local_files_only,
        )
        _model_name = model_name
    return _model


def embed_texts(
    texts: List[str],
    model_name: str,
    device: str = "cpu",
) -> np.ndarray:
    """Embed a list of texts, return float32 array of shape (N, dim).

    Vectors are L2-normalised so that inner-product equals cosine similarity.
    """
    model = get_model(model_name, device)
    embeddings: np.ndarray = model.encode(
        texts,
        convert_to_numpy=True,
        show_progress_bar=False,
        normalize_embeddings=True,
    ).astype(np.float32)
    return embeddings
