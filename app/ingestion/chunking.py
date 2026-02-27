"""
app/ingestion/chunking.py – Intelligent document chunking.

Strategy:
- Runbooks / SOPs   → split by known section headings
  (Symptoms, Cause, Procedure, Verification, Rollback, …)
- Incidents / Postmortems → split by
  (What happened, Signals, Root cause, Fix, Prevention, …)
- General docs      → split by Markdown headings, then by size

Each chunk is a ``Chunk`` Pydantic model with metadata.
"""
from __future__ import annotations

import re
import uuid
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

class Chunk(BaseModel):
    """A single text chunk with metadata."""

    chunk_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    doc_id: str
    title: str
    path: str
    doc_type: str  # runbook | incident | architecture | general
    section: str = ""
    chunk_index: int = 0
    text: str
    timestamp: Optional[str] = None


# ---------------------------------------------------------------------------
# Section heading patterns
# ---------------------------------------------------------------------------

_RUNBOOK_HEADINGS = re.compile(
    r"^#{1,6}\s*(symptoms?|cause|procedure|steps?|verification|rollback|"
    r"overview|prerequisites?|summary|background|impact|mitigation|recovery|"
    r"escalation|contact|references?|notes?)\b",
    re.IGNORECASE | re.MULTILINE,
)

_INCIDENT_HEADINGS = re.compile(
    r"^#{1,6}\s*(what happened|signals?|root cause|fix|prevention|timeline|"
    r"incident summary|impact|detection|remediation|action items?|"
    r"contributing factors?|lessons? learned|follow.?up)\b",
    re.IGNORECASE | re.MULTILINE,
)

_GENERIC_HEADING = re.compile(r"^#{1,6}\s+.+", re.MULTILINE)

MAX_CHUNK_CHARS = 1200  # soft max characters per chunk before splitting further
OVERLAP_CHARS = 100      # overlap between size-split sub-chunks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _split_by_pattern(text: str, pattern: re.Pattern) -> list[tuple[str, str]]:
    """Split *text* on *pattern* matches.

    Returns list of (heading, body) pairs where heading is the matched line
    and body is everything up to the next match.
    """
    sections: list[tuple[str, str]] = []
    matches = list(pattern.finditer(text))
    if not matches:
        return [("", text)]
    # Text before first heading
    preamble = text[: matches[0].start()].strip()
    if preamble:
        sections.append(("", preamble))
    for i, m in enumerate(matches):
        heading = m.group(0).lstrip("#").strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        sections.append((heading, body))
    return sections


def _size_split(text: str, max_chars: int = MAX_CHUNK_CHARS, overlap: int = OVERLAP_CHARS) -> list[str]:
    """Split long text into overlapping sub-chunks at sentence or newline boundaries."""
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            # Try to break at sentence boundary
            boundary = max(
                text.rfind(". ", start, end),
                text.rfind("\n", start, end),
            )
            if boundary > start:
                end = boundary + 1
        chunks.append(text[start:end].strip())
        start = end - overlap if end - overlap > start else end
    return [c for c in chunks if c]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _detect_doc_type(title: str, path: str) -> str:
    """Heuristic doc-type detection from title / path."""
    combined = (title + " " + path).lower()
    if any(k in combined for k in ("runbook", "sop", "playbook", "procedure")):
        return "runbook"
    if any(k in combined for k in ("incident", "postmortem", "post-mortem", "outage", "pagerduty", "oncall")):
        return "incident"
    if any(k in combined for k in ("architecture", "arch", "design", "diagram", "adr")):
        return "architecture"
    return "general"


def chunk_document(
    text: str,
    doc_id: str,
    title: str,
    path: str,
    doc_type: Optional[str] = None,
    timestamp: Optional[str] = None,
) -> list[Chunk]:
    """Chunk a document into ``Chunk`` objects.

    Parameters
    ----------
    text:     Full extracted text of the document.
    doc_id:   Unique document identifier.
    title:    Human-readable document title.
    path:     File path (for citation).
    doc_type: One of runbook/incident/architecture/general (auto-detected if None).
    timestamp: Optional document timestamp.
    """
    if doc_type is None:
        doc_type = _detect_doc_type(title, path)

    # Pick splitting pattern based on doc_type
    if doc_type == "runbook":
        raw_sections = _split_by_pattern(text, _RUNBOOK_HEADINGS)
    elif doc_type == "incident":
        raw_sections = _split_by_pattern(text, _INCIDENT_HEADINGS)
    else:
        # architecture / general: split by any heading, fall back to size
        raw_sections = _split_by_pattern(text, _GENERIC_HEADING)

    chunks: list[Chunk] = []
    idx = 0
    for heading, body in raw_sections:
        if not body.strip():
            continue
        sub_texts = _size_split(body)
        for sub in sub_texts:
            if not sub.strip():
                continue
            chunks.append(
                Chunk(
                    doc_id=doc_id,
                    title=title,
                    path=path,
                    doc_type=doc_type,
                    section=heading,
                    chunk_index=idx,
                    text=sub,
                    timestamp=timestamp,
                )
            )
            idx += 1
    return chunks
