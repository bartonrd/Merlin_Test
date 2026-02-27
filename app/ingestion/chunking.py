"""Document chunking utilities with type-aware strategies."""
import re
from typing import List, Optional

from pydantic import BaseModel


class Chunk(BaseModel):
    doc_id: str
    title: str
    path: str
    doc_type: str  # runbook / arch / incident / general
    section: str
    chunk_index: int
    text: str
    timestamp: Optional[str] = None


# ---------------------------------------------------------------------------
# Document type detection
# ---------------------------------------------------------------------------

_RUNBOOK_KEYWORDS = re.compile(
    r"\b(runbook|symptoms?|procedure|verification|rollback|remediation)\b",
    re.IGNORECASE,
)
_INCIDENT_KEYWORDS = re.compile(
    r"\b(incident|INC-\d+|postmortem|root\s+cause|what\s+happened|timeline|prevention)\b",
    re.IGNORECASE,
)
_ARCH_KEYWORDS = re.compile(
    r"\b(architecture|overview|services?|deployment|infrastructure|platform|stack)\b",
    re.IGNORECASE,
)


def detect_doc_type(title: str, text: str) -> str:
    """Heuristic detection of doc type from title and content."""
    combined = f"{title}\n{text[:2000]}"

    runbook_score = len(_RUNBOOK_KEYWORDS.findall(combined))
    incident_score = len(_INCIDENT_KEYWORDS.findall(combined))
    arch_score = len(_ARCH_KEYWORDS.findall(combined))

    # Also check title explicitly
    title_lower = title.lower()
    if "runbook" in title_lower:
        runbook_score += 5
    if re.search(r"inc[-_]\d+", title_lower):
        incident_score += 5
    if any(kw in title_lower for kw in ("architecture", "overview", "platform")):
        arch_score += 5

    best = max(runbook_score, incident_score, arch_score)
    if best == 0:
        return "general"
    if best == runbook_score and runbook_score >= incident_score:
        return "runbook"
    if incident_score > arch_score:
        return "incident"
    if arch_score > 0:
        return "arch"
    return "general"


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------


def chunk_document(
    text: str,
    doc_id: str,
    title: str,
    path: str,
    doc_type: Optional[str] = None,
    max_chunk_size: int = 800,
    overlap: int = 100,
) -> List[Chunk]:
    """Main chunking function that dispatches to specialised chunkers."""
    if doc_type is None:
        doc_type = detect_doc_type(title, text)

    if doc_type == "runbook":
        return chunk_runbook(text, doc_id, title, path, max_chunk_size, overlap)
    if doc_type == "incident":
        return chunk_incident(text, doc_id, title, path, max_chunk_size, overlap)
    return chunk_general(text, doc_id, title, path, max_chunk_size, overlap)


# ---------------------------------------------------------------------------
# Specialised chunkers
# ---------------------------------------------------------------------------

# Known section headings for each doc type
_RUNBOOK_SECTIONS = ["symptoms", "cause", "procedure", "verification", "rollback"]
_INCIDENT_SECTIONS = [
    "what happened",
    "signals",
    "root cause",
    "fix",
    "prevention",
    "timeline",
]


def _extract_sections(
    text: str, known_sections: List[str]
) -> List[tuple[str, str]]:
    """
    Split *text* into (section_name, section_text) pairs by looking for
    markdown headings or heading-like lines that match *known_sections*.

    Returns all text up to the first match as a 'preamble' section (if any),
    then each detected section in order.
    """
    lines = text.splitlines(keepends=True)

    # Build a regex that matches any known section heading
    pattern = re.compile(
        r"^\s*#{1,4}\s*(?P<title>.+)$|^(?P<title2>[A-Z][^\n]{2,80})$",
        re.MULTILINE,
    )

    sections: List[tuple[str, str]] = []
    current_name = "preamble"
    current_lines: List[str] = []

    for line in lines:
        # Check if this line is a heading
        m = re.match(r"^\s*(#{1,4})\s+(.+)", line)
        heading_text = m.group(2).strip() if m else None

        if heading_text is None:
            # Try all-caps or "Word Word:" pattern
            stripped = line.strip().rstrip(":")
            if re.match(r"^[A-Z][A-Za-z ]{2,60}$", stripped) and len(stripped) < 60:
                heading_text = stripped

        if heading_text:
            normalized = heading_text.lower()
            matched = any(s in normalized for s in known_sections)
            if matched or (m is not None):  # Accept any markdown heading
                if current_lines:
                    sections.append((current_name, "".join(current_lines)))
                current_name = heading_text.strip()
                current_lines = []
                continue

        current_lines.append(line)

    if current_lines:
        sections.append((current_name, "".join(current_lines)))

    return sections


def chunk_runbook(
    text: str,
    doc_id: str,
    title: str,
    path: str,
    max_size: int,
    overlap: int,
) -> List[Chunk]:
    """Chunk by runbook sections: Symptoms/Cause/Procedure/Verification/Rollback."""
    sections = _extract_sections(text, _RUNBOOK_SECTIONS)
    return _sections_to_chunks(
        sections, doc_id, title, path, "runbook", max_size, overlap
    )


def chunk_incident(
    text: str,
    doc_id: str,
    title: str,
    path: str,
    max_size: int,
    overlap: int,
) -> List[Chunk]:
    """Chunk by incident sections: What happened/Signals/Root cause/Fix/Prevention."""
    sections = _extract_sections(text, _INCIDENT_SECTIONS)
    return _sections_to_chunks(
        sections, doc_id, title, path, "incident", max_size, overlap
    )


def chunk_general(
    text: str,
    doc_id: str,
    title: str,
    path: str,
    max_size: int,
    overlap: int,
) -> List[Chunk]:
    """Chunk by headings, then by size with overlap."""
    # Split by any markdown heading or all-caps line
    heading_re = re.compile(r"^#{1,4}\s+.+", re.MULTILINE)
    matches = list(heading_re.finditer(text))

    if not matches:
        # No headings – split purely by size
        sub_chunks = split_by_size(text, max_size, overlap)
        return [
            Chunk(
                doc_id=doc_id,
                title=title,
                path=path,
                doc_type="general",
                section="content",
                chunk_index=i,
                text=sc.strip(),
            )
            for i, sc in enumerate(sub_chunks)
            if sc.strip()
        ]

    sections: List[tuple[str, str]] = []
    for idx, match in enumerate(matches):
        section_title = match.group(0).lstrip("#").strip()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        sections.append((section_title, text[start:end]))

    # Include any text before the first heading
    if matches[0].start() > 0:
        sections.insert(("preamble", text[: matches[0].start()]), 0)  # type: ignore[call-overload]

    return _sections_to_chunks(
        sections, doc_id, title, path, "general", max_size, overlap
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sections_to_chunks(
    sections: List[tuple[str, str]],
    doc_id: str,
    title: str,
    path: str,
    doc_type: str,
    max_size: int,
    overlap: int,
) -> List[Chunk]:
    """Convert (section_name, section_text) pairs into Chunk objects."""
    chunks: List[Chunk] = []
    chunk_index = 0

    for section_name, section_text in sections:
        section_text = section_text.strip()
        if not section_text:
            continue

        sub_texts = split_by_size(section_text, max_size, overlap)
        for sub in sub_texts:
            sub = sub.strip()
            if not sub:
                continue
            chunks.append(
                Chunk(
                    doc_id=doc_id,
                    title=title,
                    path=path,
                    doc_type=doc_type,
                    section=section_name,
                    chunk_index=chunk_index,
                    text=sub,
                )
            )
            chunk_index += 1

    # Fallback: if no chunks were produced, treat the whole text as one chunk
    if not chunks:
        chunks.append(
            Chunk(
                doc_id=doc_id,
                title=title,
                path=path,
                doc_type=doc_type,
                section="content",
                chunk_index=0,
                text=sections[0][1].strip() if sections else "",
            )
        )

    return chunks


def split_by_size(text: str, max_size: int, overlap: int) -> List[str]:
    """Split text by word boundaries respecting max_size with overlap."""
    if len(text) <= max_size:
        return [text]

    words = text.split()
    chunks: List[str] = []
    current_words: List[str] = []
    current_len = 0

    for word in words:
        word_len = len(word) + 1  # +1 for space
        if current_len + word_len > max_size and current_words:
            chunks.append(" ".join(current_words))
            # Keep last `overlap` characters worth of words for the next chunk
            overlap_words: List[str] = []
            overlap_len = 0
            for w in reversed(current_words):
                if overlap_len + len(w) + 1 > overlap:
                    break
                overlap_words.insert(0, w)
                overlap_len += len(w) + 1
            current_words = overlap_words
            current_len = overlap_len

        current_words.append(word)
        current_len += word_len

    if current_words:
        chunks.append(" ".join(current_words))

    return chunks
