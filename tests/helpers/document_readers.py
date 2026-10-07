"""Helpers to open exported documents the way a user would."""

from pathlib import Path

from pypdf import PdfReader

TEXT_ENCODING = "utf-8"
PDF_EXTENSION = ".pdf"


def read_pdf(path: Path) -> tuple[str, int]:
    """Open a PDF and return its text (single spaced) and its page count."""
    reader = PdfReader(path)
    text = "\n".join(page.extract_text() for page in reader.pages)
    return " ".join(text.split()), len(reader.pages)


def read_document(path: Path) -> str:
    """Return the text of an exported TXT or PDF file, single spaced."""
    if path.suffix == PDF_EXTENSION:
        text, _ = read_pdf(path)
        return text
    return " ".join(path.read_text(encoding=TEXT_ENCODING).split())
