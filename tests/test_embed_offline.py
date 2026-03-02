"""Tests for offline embedding: local_files_only setting."""
from unittest.mock import MagicMock, call, patch


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
    """When embed_local_files_only=False (default), SentenceTransformer is called with local_files_only=False."""
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
