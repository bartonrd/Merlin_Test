"""Tests for offline embedding: local_files_only setting."""
import logging
from unittest.mock import MagicMock, patch


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


def test_get_model_suppresses_sentence_transformers_logger_during_load():
    """The sentence_transformers logger is raised to WARNING while the model loads.

    This prevents the noisy ``BertModel LOAD REPORT`` (e.g. the harmless
    ``embeddings.position_ids | UNEXPECTED`` key) from cluttering startup logs.
    After loading completes the logger level is restored to its original value.
    """
    import app.ingestion.embed as embed_mod

    embed_mod._model = None
    embed_mod._model_name = None

    observed_levels = []

    def _recording_constructor(model_name, device, local_files_only):
        # Capture the sentence_transformers logger level at load time
        level = logging.getLogger("sentence_transformers").level
        observed_levels.append(level)
        return MagicMock()

    st_logger = logging.getLogger("sentence_transformers")
    original_level = st_logger.level  # capture before the call

    with (
        patch("app.ingestion.embed.SentenceTransformer", side_effect=_recording_constructor),
        patch("app.ingestion.embed.settings") as mock_settings,
    ):
        mock_settings.embed_local_files_only = False
        embed_mod.get_model("all-MiniLM-L6-v2", device="cpu")

    # During construction the level must have been WARNING (or higher)
    assert observed_levels, "SentenceTransformer constructor was not called"
    assert observed_levels[0] >= logging.WARNING, (
        f"Expected logger level >= WARNING during load, got {observed_levels[0]}"
    )
    # After the call the level must be restored
    assert st_logger.level == original_level, (
        f"Logger level was not restored after load: {st_logger.level!r}"
    )
