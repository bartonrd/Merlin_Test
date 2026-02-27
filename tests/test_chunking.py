"""Tests for the document chunking utilities."""
import pytest

from app.ingestion.chunking import chunk_document, detect_doc_type, split_by_size


def test_detect_doc_type_runbook():
    text = "# Symptoms\nApp crashes\n## Cause\nMemory leak"
    assert detect_doc_type("database runbook", text) == "runbook"


def test_detect_doc_type_incident():
    text = "# What Happened\n## Root Cause\nBug in code"
    assert detect_doc_type("INC-2024-001 postmortem", text) == "incident"


def test_detect_doc_type_arch():
    text = "# Platform Architecture Overview\n## Services\nThe platform has many services."
    assert detect_doc_type("architecture overview", text) == "arch"


def test_split_by_size_single_chunk():
    """Short text should not be split."""
    text = "This is a short text."
    chunks = split_by_size(text, max_size=200, overlap=20)
    assert chunks == [text]


def test_split_by_size_multiple_chunks():
    text = "word " * 200
    chunks = split_by_size(text, max_size=100, overlap=20)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 150  # Allow some margin for overlap


def test_split_by_size_overlap():
    """Verify overlap: later chunks begin with words from the previous chunk."""
    text = " ".join(f"word{i}" for i in range(100))
    chunks = split_by_size(text, max_size=50, overlap=15)
    assert len(chunks) >= 2
    # Last word(s) of chunk[0] should appear at the start of chunk[1]
    last_words_of_first = chunks[0].split()[-2:]
    first_words_of_second = chunks[1].split()[:3]
    overlap_found = any(w in first_words_of_second for w in last_words_of_first)
    assert overlap_found


def test_chunk_document_runbook():
    text = """# Test Runbook
## Symptoms
App is down
## Cause
Memory exhausted
## Procedure
Restart the service
## Verification
Check health endpoint
"""
    chunks = chunk_document(text, "rb-001", "Test Runbook", "/docs/test.md", doc_type="runbook")
    assert len(chunks) >= 1
    for chunk in chunks:
        assert chunk.doc_id == "rb-001"
        assert chunk.doc_type == "runbook"
        assert len(chunk.text) > 0


def test_chunk_document_incident():
    text = """# INC-2024-001
## What Happened
Service was down
## Root Cause
Database lock
## Fix
Restarted the pod
## Prevention
Added monitoring
"""
    chunks = chunk_document(text, "inc-001", "INC-2024-001", "/docs/inc.md", doc_type="incident")
    assert len(chunks) >= 1
    for chunk in chunks:
        assert chunk.doc_id == "inc-001"
        assert chunk.doc_type == "incident"


def test_chunk_document_general():
    text = "word " * 400
    chunks = chunk_document(text, "gen-001", "General Doc", "/docs/gen.md", doc_type="general")
    assert len(chunks) >= 1


def test_chunk_document_auto_detects_type():
    """doc_type=None should trigger auto-detection."""
    text = "# Symptoms\nApp crashes\n## Cause\nOOM\n## Procedure\nRestart"
    chunks = chunk_document(text, "rb-auto", "DB Runbook", "/docs/rb.md")
    assert all(c.doc_type == "runbook" for c in chunks)


def test_chunk_index_is_sequential():
    text = "word " * 600
    chunks = chunk_document(text, "seq-001", "Seq Doc", "/docs/seq.md", doc_type="general")
    indices = [c.chunk_index for c in chunks]
    assert indices == list(range(len(indices)))
