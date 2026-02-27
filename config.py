"""Application configuration via pydantic-settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # LLM settings
    llm_base_url: str = "http://localhost:8080"
    llm_model: str = "local-model"
    llm_max_tokens: int = 2048
    llm_temperature: float = 0.1
    llm_context_window: int = 4096

    # Embedding settings
    embed_model: str = "all-MiniLM-L6-v2"
    embed_device: str = "cpu"

    # Retrieval settings
    top_k_bm25: int = 10
    top_k_vector: int = 10
    top_k_final: int = 5
    reranker_enabled: bool = False
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # Storage paths
    db_path: str = "./data/db.sqlite"
    faiss_path: str = "./data/index.faiss"
    faiss_map_path: str = "./data/faiss_map.pkl"
    docs_dir: str = "./docs"
    audit_log_path: str = "./data/audit.log"

    # Context limits
    max_context_chars: int = 6000

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
