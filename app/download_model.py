"""Pre-download the configured embedding model into the local cache.

This script is called by setup_requirements.bat/sh and start.bat/sh
during the (online) setup phase so the server can run fully offline
afterwards.  Running this script when the model is already cached is
a fast no-op.

Usage:
    python -m app.download_model
"""
from config import settings
from sentence_transformers import SentenceTransformer

print(f"[download_model] Checking embedding model: {settings.embed_model}")
SentenceTransformer(settings.embed_model, device="cpu")
print("[download_model] Embedding model is ready in local cache.")
