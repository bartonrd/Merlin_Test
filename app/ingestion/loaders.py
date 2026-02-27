"""
app/ingestion/loaders.py – Extract raw text from .txt, .md, .pdf, .docx files.

Each loader returns the full text as a string.  PDF and DOCX preserve
heading structure as much as possible using newlines between blocks.
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_txt(path: Path) -> str:
    """Load a plain text or markdown file."""
    return path.read_text(encoding="utf-8", errors="replace")


def load_md(path: Path) -> str:
    """Load a Markdown file (same as text; headings are preserved via # syntax)."""
    return load_txt(path)


def load_pdf(path: Path) -> str:
    """Extract text from a PDF using pdfplumber.

    Falls back to pypdf if pdfplumber is unavailable.
    """
    try:
        import pdfplumber  # type: ignore

        pages: list[str] = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
        return "\n\n".join(pages)
    except ImportError:
        logger.warning("pdfplumber not available, falling back to pypdf")
        try:
            from pypdf import PdfReader  # type: ignore

            reader = PdfReader(str(path))
            return "\n\n".join(
                page.extract_text() or "" for page in reader.pages
            )
        except ImportError as exc:
            raise RuntimeError(
                "Neither pdfplumber nor pypdf is installed. "
                "Install one of them to read PDF files."
            ) from exc


def load_docx(path: Path) -> str:
    """Extract text from a .docx file preserving heading structure."""
    try:
        from docx import Document  # type: ignore
        from docx.oxml.ns import qn  # type: ignore

        doc = Document(str(path))
        lines: list[str] = []
        for para in doc.paragraphs:
            style = para.style.name if para.style else ""
            text = para.text.strip()
            if not text:
                continue
            # Mark headings with Markdown-style prefix for downstream chunker
            if style.startswith("Heading"):
                level_str = style.replace("Heading", "").strip()
                level = int(level_str) if level_str.isdigit() else 1
                lines.append("#" * level + " " + text)
            else:
                lines.append(text)
        return "\n\n".join(lines)
    except ImportError as exc:
        raise RuntimeError(
            "python-docx is not installed. Install it to read .docx files."
        ) from exc


# Dispatch map
_LOADERS = {
    ".txt": load_txt,
    ".md": load_md,
    ".markdown": load_md,
    ".pdf": load_pdf,
    ".docx": load_docx,
}


def load_document(path: Path) -> str:
    """Dispatch to the correct loader based on file extension.

    Returns the full extracted text of the document.
    Raises ValueError for unsupported extensions.
    """
    suffix = path.suffix.lower()
    loader = _LOADERS.get(suffix)
    if loader is None:
        raise ValueError(f"Unsupported file type: {suffix} ({path})")
    logger.debug("Loading %s with %s", path, loader.__name__)
    return loader(path)


def supported_extensions() -> frozenset[str]:
    """Return the set of supported file extensions."""
    return frozenset(_LOADERS.keys())
