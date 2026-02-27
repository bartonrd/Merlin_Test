"""Loaders for various document file types."""
from pathlib import Path


def load_text(path: Path) -> str:
    """Dispatch to the right loader based on file extension."""
    ext = path.suffix.lower()
    dispatch = {
        ".txt": load_txt,
        ".md": load_md,
        ".pdf": load_pdf,
        ".docx": load_docx,
    }
    loader = dispatch.get(ext)
    if loader is None:
        raise ValueError(f"Unsupported file extension: {ext}")
    return loader(path)


def load_txt(path: Path) -> str:
    """Load plain text file."""
    return path.read_text(encoding="utf-8", errors="replace")


def load_md(path: Path) -> str:
    """Load markdown file as plain text."""
    return path.read_text(encoding="utf-8", errors="replace")


def load_pdf(path: Path) -> str:
    """Use pdfplumber to extract text page by page."""
    import pdfplumber

    pages: list[str] = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
    return "\n\n".join(pages)


def load_docx(path: Path) -> str:
    """Use python-docx to extract paragraphs."""
    from docx import Document

    doc = Document(str(path))
    paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
    return "\n\n".join(paragraphs)
