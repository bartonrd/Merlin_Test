"""Embedding utilities with lazy singleton model loading."""
import logging
from typing import List, Optional

import numpy as np
from sentence_transformers import SentenceTransformer

from config import settings

_model: Optional[SentenceTransformer] = None
_model_name: Optional[str] = None


def get_model(model_name: str, device: str = "cpu") -> SentenceTransformer:
    """Lazy-load the embedding model (singleton per process).

    The sentence-transformers library prints a verbose ``BertModel LOAD REPORT``
    at INFO level when a model weight key (e.g. ``embeddings.position_ids``) is
    present in the architecture but absent from the saved checkpoint.  This key
    was added in newer PyTorch versions as a non-persistent buffer and can be
    safely ignored.  We temporarily raise the ``sentence_transformers`` logger
    to WARNING during model construction to suppress the noisy report, then
    restore the original level.
    """
    global _model, _model_name
    if _model is None or _model_name != model_name:
        _st_logger = logging.getLogger("sentence_transformers")
        _prev_level = _st_logger.level
        _st_logger.setLevel(logging.WARNING)
        try:
            _model = SentenceTransformer(
                model_name,
                device=device,
                local_files_only=settings.embed_local_files_only,
            )
        finally:
            _st_logger.setLevel(_prev_level)
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
