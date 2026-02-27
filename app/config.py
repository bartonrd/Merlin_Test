"""
app/config.py – Application configuration loaded from config.yaml and env vars.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings


def _load_yaml(path: str) -> dict:
    """Load YAML config file if it exists, otherwise return empty dict."""
    p = Path(path)
    if p.exists():
        with p.open() as fh:
            return yaml.safe_load(fh) or {}
    return {}


class Settings(BaseSettings):
    """Central configuration for Merlin.

    Values are read (in priority order) from:
    1. Environment variables (prefixed MERLIN_)
    2. config.yaml in the current working directory
    3. Defaults below
    """

    # LLM backend
    llm_base_url: str = Field("http://localhost:8080", description="llama.cpp server URL")
    llm_model: str = Field("local-model", description="Model name sent to llama.cpp")
    llm_max_tokens: int = Field(1024, description="Max completion tokens")
    llm_temperature: float = Field(0.2, description="Sampling temperature")
    llm_context_window: int = Field(4096, description="Max context window tokens (chars/4 approx)")

    # Embedding
    embedding_model: str = Field("all-MiniLM-L6-v2", description="Sentence-Transformers model name")
    embedding_batch_size: int = Field(64, description="Embedding batch size")

    # Optional reranker
    reranker_model: Optional[str] = Field(None, description="Cross-encoder model name or null")

    # Paths
    db_path: str = Field("./data/db.sqlite", description="SQLite DB file path")
    faiss_path: str = Field("./data/index.faiss", description="FAISS index file path")
    faiss_map_path: str = Field("./data/faiss_map.json", description="FAISS id→chunk_id map path")
    docs_dir: str = Field("./docs", description="Default documents directory")

    # Search
    top_k_bm25: int = Field(10, description="BM25 candidates per query")
    top_k_vector: int = Field(10, description="Vector candidates per query")
    top_k_final: int = Field(5, description="Final chunks to include in context")

    # Audit
    audit_log_path: str = Field("./data/audit.jsonl", description="Audit log path")

    # UI
    ui_enabled: bool = Field(True, description="Serve minimal web UI")

    model_config = {"env_prefix": "MERLIN_", "case_sensitive": False}


def load_settings(config_file: str = "config.yaml") -> Settings:
    """Load settings merging YAML file with env overrides."""
    yaml_data = _load_yaml(config_file)
    return Settings(**yaml_data)


# Module-level singleton loaded once at import time
settings: Settings = load_settings()
