"""Tests for offline embedding: local_files_only setting."""
import os
from unittest.mock import MagicMock, call, patch


def test_settings_embed_local_files_only_defaults_to_true(tmp_path, monkeypatch):
    """The default value of embed_local_files_only must be True so the app
    runs fully offline without any .env configuration needed."""
    # Ensure no env var override is present.
    monkeypatch.delenv("EMBED_LOCAL_FILES_ONLY", raising=False)

    # Point pydantic-settings at a blank temp env file so the real project .env
    # (if it exists on disk) cannot influence the result.
    blank_env = str(tmp_path / ".env")
    with open(blank_env, "w"):
        pass

    # Import Settings fresh without a .env file overriding the default.
    import config as config_mod
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class _IsolatedSettings(config_mod.Settings):
        model_config = SettingsConfigDict(
            env_file=blank_env, env_file_encoding="utf-8"
        )

    assert _IsolatedSettings().embed_local_files_only is True, (
        "embed_local_files_only should default to True so the app never "
        "attempts to contact HuggingFace Hub at runtime."
    )


def test_get_model_passes_local_files_only_true():
    """When embed_local_files_only=True, SentenceTransformer is called with local_files_only=True."""
    import app.ingestion.embed as embed_mod

    # Reset the singleton so it re-creates the model
    embed_mod._model = None
    embed_mod._model_name = None

    mock_st = MagicMock()
    with (
        patch("app.ingestion.embed.SentenceTransformer", return_value=mock_st) as mock_cls,
        patch("app.ingestion.embed.settings") as mock_settings,
    ):
        mock_settings.embed_local_files_only = True
        embed_mod.get_model("all-MiniLM-L6-v2", device="cpu")

    mock_cls.assert_called_once_with(
        "all-MiniLM-L6-v2",
        device="cpu",
        local_files_only=True,
    )


def test_get_model_passes_local_files_only_false():
    """When embed_local_files_only=False, SentenceTransformer is called with local_files_only=False."""
    import app.ingestion.embed as embed_mod

    embed_mod._model = None
    embed_mod._model_name = None

    mock_st = MagicMock()
    with (
        patch("app.ingestion.embed.SentenceTransformer", return_value=mock_st) as mock_cls,
        patch("app.ingestion.embed.settings") as mock_settings,
    ):
        mock_settings.embed_local_files_only = False
        embed_mod.get_model("all-MiniLM-L6-v2", device="cpu")

    mock_cls.assert_called_once_with(
        "all-MiniLM-L6-v2",
        device="cpu",
        local_files_only=False,
    )
