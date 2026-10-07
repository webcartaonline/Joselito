"""Tests for the document exporter adapter."""

import pytest
from fpdf.errors import FPDFException
from pypdf import PdfReader

from tests.helpers.content_mocks import make_article, make_enriched
from wiki_enrichment.domain.exceptions import ExportError
from wiki_enrichment.infrastructure import exporters
from wiki_enrichment.infrastructure.exporters import (
    EMPTY_SECTION_TEXT,
    ENRICHED_HEADING,
    ORIGINAL_HEADING,
    TEXT_ENCODING,
    TRANSLATED_HEADING,
    DocumentExporterAdapter,
)

ARTICLE = make_article("Agujero negro", ["Primer párrafo.", "Segundo párrafo."])
CONTENT = make_enriched(ARTICLE, "Texto ampliado por la IA.", "Black hole text.")


def read(path) -> str:
    return path.read_text(encoding=TEXT_ENCODING)


def read_pdf(path) -> tuple[str, int]:
    """Open the PDF like a viewer would and return its text and page count."""
    reader = PdfReader(path)
    text = "\n".join(page.extract_text() for page in reader.pages)
    return " ".join(text.split()), len(reader.pages)


def test_export_txt_saves_title_and_the_three_contents(tmp_path) -> None:
    """The text file contains the title and the three sections in order."""

    path = tmp_path / "apuntes.txt"

    DocumentExporterAdapter().export_txt(CONTENT, str(path))

    text = read(path)
    assert text.startswith("Agujero negro\n=============\n")
    expected_order = [
        ORIGINAL_HEADING, "Primer párrafo.\n\nSegundo párrafo.",
        ENRICHED_HEADING, "Texto ampliado por la IA.",
        TRANSLATED_HEADING, "Black hole text.",
    ]
    positions = [text.index(part) for part in expected_order]
    assert positions == sorted(positions)


def test_export_txt_marks_missing_contents(tmp_path) -> None:
    """Empty enriched and translated contents are marked as not available."""

    path = tmp_path / "apuntes.txt"

    DocumentExporterAdapter().export_txt(make_enriched(ARTICLE, "", "  "), str(path))

    assert read(path).count(EMPTY_SECTION_TEXT) == 2


def test_export_txt_creates_missing_folders(tmp_path) -> None:
    """The output folder is created when it does not exist yet."""

    path = tmp_path / "output" / "apuntes.txt"

    DocumentExporterAdapter().export_txt(CONTENT, str(path))

    assert path.exists()


def test_export_txt_overwrites_an_existing_file(tmp_path) -> None:
    """Saving twice with the same name keeps only the latest content."""

    path = tmp_path / "apuntes.txt"
    path.write_text("contenido antiguo", encoding=TEXT_ENCODING)

    DocumentExporterAdapter().export_txt(CONTENT, str(path))

    assert "contenido antiguo" not in read(path)


def test_export_txt_raises_export_error_when_it_cannot_write(tmp_path) -> None:
    """A path that cannot be written becomes a domain ExportError."""

    folder_with_the_same_name = tmp_path / "apuntes.txt"
    folder_with_the_same_name.mkdir()

    with pytest.raises(ExportError):
        DocumentExporterAdapter().export_txt(CONTENT, str(folder_with_the_same_name))


def test_export_pdf_saves_title_and_the_three_contents(tmp_path) -> None:
    """The PDF opens and contains the title and the three sections in order."""

    path = tmp_path / "apuntes.pdf"

    DocumentExporterAdapter().export_pdf(CONTENT, str(path))

    text, _ = read_pdf(path)
    expected_order = [
        "Agujero negro",
        ORIGINAL_HEADING, "Primer párrafo.", "Segundo párrafo.",
        ENRICHED_HEADING, "Texto ampliado por la IA.",
        TRANSLATED_HEADING, "Black hole text.",
    ]
    positions = [text.index(part) for part in expected_order]
    assert positions == sorted(positions)
    assert PdfReader(path).metadata.title == "Agujero negro"


def test_export_pdf_marks_missing_contents(tmp_path) -> None:
    """Empty enriched and translated contents are marked as not available."""

    path = tmp_path / "apuntes.pdf"

    DocumentExporterAdapter().export_pdf(make_enriched(ARTICLE, "", ""), str(path))

    text, _ = read_pdf(path)
    assert text.count(EMPTY_SECTION_TEXT) == 2


def test_export_pdf_supports_special_characters(tmp_path) -> None:
    """Dashes, quotes, symbols and Cyrillic letters do not break the PDF."""

    special = "Luz —ni fotones— «curvatura» 12.000 °C · Чёрная дыра"
    path = tmp_path / "apuntes.pdf"

    DocumentExporterAdapter().export_pdf(make_enriched(ARTICLE, special, ""), str(path))

    text, _ = read_pdf(path)
    assert "Чёрная дыра" in text
    assert "«curvatura»" in text


def test_export_pdf_adds_pages_for_long_texts(tmp_path) -> None:
    """Long contents continue on new pages instead of being cut."""

    long_article = make_article("Largo", ["Una frase bastante larga de ejemplo. " * 40] * 20)
    path = tmp_path / "largo.pdf"

    DocumentExporterAdapter().export_pdf(make_enriched(long_article, "", ""), str(path))

    _, pages = read_pdf(path)
    assert pages > 1


def test_export_pdf_creates_missing_folders(tmp_path) -> None:
    """The output folder is created when it does not exist yet."""

    path = tmp_path / "output" / "apuntes.pdf"

    DocumentExporterAdapter().export_pdf(CONTENT, str(path))

    assert path.exists()


def test_export_pdf_raises_export_error_when_it_cannot_write(tmp_path) -> None:
    """A path that cannot be written becomes a domain ExportError."""

    folder_with_the_same_name = tmp_path / "apuntes.pdf"
    folder_with_the_same_name.mkdir()

    with pytest.raises(ExportError):
        DocumentExporterAdapter().export_pdf(CONTENT, str(folder_with_the_same_name))


def test_export_pdf_raises_export_error_when_the_pdf_cannot_be_built(
    tmp_path, monkeypatch
) -> None:
    """An internal fpdf2 failure also becomes a domain ExportError."""

    def broken_builder(_content):
        raise FPDFException("broken")

    monkeypatch.setattr(exporters, "build_pdf_document", broken_builder)

    with pytest.raises(ExportError):
        DocumentExporterAdapter().export_pdf(CONTENT, str(tmp_path / "apuntes.pdf"))
