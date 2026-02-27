"""
tests/test_chunking.py – Unit tests for the intelligent document chunker.
"""
import pytest

from app.ingestion.chunking import (
    Chunk,
    chunk_document,
    _size_split,
    _detect_doc_type,
)


# ---------------------------------------------------------------------------
# _detect_doc_type
# ---------------------------------------------------------------------------

class TestDetectDocType:
    def test_runbook_from_path(self):
        assert _detect_doc_type("title", "/docs/runbooks/my_runbook.md") == "runbook"

    def test_incident_from_title(self):
        assert _detect_doc_type("INC-2024 Incident Report", "/docs/x.md") == "incident"

    def test_postmortem_from_path(self):
        assert _detect_doc_type("t", "/reports/postmortem_2024.txt") == "incident"

    def test_architecture_from_title(self):
        assert _detect_doc_type("System Architecture Overview", "/docs/arch.md") == "architecture"

    def test_general_fallback(self):
        assert _detect_doc_type("Random Doc", "/docs/notes.md") == "general"


# ---------------------------------------------------------------------------
# _size_split
# ---------------------------------------------------------------------------

class TestSizeSplit:
    def test_short_text_not_split(self):
        text = "Short text under limit."
        result = _size_split(text, max_chars=500)
        assert result == [text]

    def test_long_text_produces_multiple_chunks(self):
        text = ("A sentence. " * 200).strip()
        result = _size_split(text, max_chars=200, overlap=20)
        assert len(result) > 1

    def test_all_chunks_nonempty(self):
        text = "Word " * 500
        result = _size_split(text, max_chars=100, overlap=10)
        assert all(c.strip() for c in result)

    def test_overlap_creates_shared_content(self):
        text = "Alpha Beta Gamma Delta Epsilon Zeta Eta Theta Iota Kappa " * 10
        chunks = _size_split(text, max_chars=80, overlap=20)
        if len(chunks) >= 2:
            # The end of chunk 0 should overlap with the start of chunk 1
            end_of_first = chunks[0][-20:]
            assert any(word in chunks[1] for word in end_of_first.split())


# ---------------------------------------------------------------------------
# chunk_document
# ---------------------------------------------------------------------------

RUNBOOK_TEXT = """\
# Overview
Brief overview.

## Symptoms
- High CPU
- Slow queries

## Procedure
1. Connect to database.
2. Run EXPLAIN ANALYZE.

## Verification
CPU drops below 40%.

## Rollback
Restart the service.
"""

INCIDENT_TEXT = """\
# Incident: INC-001

## What Happened
Database went down at 14:00 UTC.

## Signals
- Alert fired: error_rate > 5%
- Logs showed connection refused

## Root Cause
Misconfigured firewall rule.

## Fix
Reverted firewall change.

## Prevention
Added deployment checklist item.
"""

GENERAL_TEXT = """\
# Introduction
This is the introduction.

## Section A
Content for section A.

## Section B
Content for section B that is somewhat longer and may span multiple paragraphs
if we add enough text here to trigger size splitting in a later test.
"""


class TestChunkDocument:
    def _make(self, text, doc_type=None):
        return chunk_document(text, doc_id="d1", title="Test Doc", path="/test.md", doc_type=doc_type)

    def test_runbook_produces_chunks(self):
        chunks = self._make(RUNBOOK_TEXT, doc_type="runbook")
        assert len(chunks) >= 3

    def test_runbook_sections_captured(self):
        chunks = self._make(RUNBOOK_TEXT, doc_type="runbook")
        sections = {c.section for c in chunks}
        assert any("ymptom" in s for s in sections)
        assert any("rocedure" in s for s in sections)

    def test_incident_produces_chunks(self):
        chunks = self._make(INCIDENT_TEXT, doc_type="incident")
        assert len(chunks) >= 4

    def test_incident_sections_captured(self):
        chunks = self._make(INCIDENT_TEXT, doc_type="incident")
        sections = {c.section for c in chunks}
        assert any("Root cause" in s or "root cause" in s.lower() for s in sections)

    def test_general_doc_chunked(self):
        chunks = self._make(GENERAL_TEXT, doc_type="general")
        assert len(chunks) >= 2

    def test_chunk_metadata(self):
        chunks = self._make(RUNBOOK_TEXT, doc_type="runbook")
        for c in chunks:
            assert c.doc_id == "d1"
            assert c.title == "Test Doc"
            assert c.path == "/test.md"
            assert c.doc_type == "runbook"
            assert isinstance(c.chunk_index, int)
            assert c.text.strip()

    def test_chunk_index_increments(self):
        chunks = self._make(RUNBOOK_TEXT, doc_type="runbook")
        indices = [c.chunk_index for c in chunks]
        assert indices == list(range(len(chunks)))

    def test_auto_detect_doc_type(self):
        chunks = chunk_document(
            RUNBOOK_TEXT, doc_id="d2", title="DB Runbook", path="/runbooks/db.md"
        )
        assert all(c.doc_type == "runbook" for c in chunks)

    def test_empty_sections_skipped(self):
        text = "## Symptoms\n\n## Procedure\nDo something.\n"
        chunks = self._make(text, doc_type="runbook")
        for c in chunks:
            assert c.text.strip()

    def test_returns_list_of_chunk_objects(self):
        chunks = self._make(RUNBOOK_TEXT, doc_type="runbook")
        assert all(isinstance(c, Chunk) for c in chunks)
