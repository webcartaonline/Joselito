"""Tests for the document exporter adapter."""

import pytest
from fpdf.errors import FPDFException
from pypdf import PdfReader

from tests.helpers.content_mocks import make_article, make_enriched
from tests.helpers.document_readers import read_pdf
from domain.exceptions import ExportError
from infrastructure import exporters
from infrastructure.exporters import (
    EMPTY_SECTION_TEXT,
    ENRICHED_HEADING,
    ORIGINAL_HEADING,
    SUMMARY_HEADING,
    TEXT_ENCODING,
    TRANSLATED_HEADING,
    TRANSLATED_SUMMARY_HEADING,
    DocumentExporterAdapter,
)
from domain.models import BriefSummary

ARTICLE = make_article("Agujero negro", ["Primer párrafo.", "Segundo párrafo."])
CONTENT = make_enriched(ARTICLE, "Texto ampliado por la IA.", "Black hole text.")
SUMMARY = BriefSummary("Agujero negro", "Resumen breve.", "Brief summary.")


def read(path) -> str:
    return path.read_text(encoding=TEXT_ENCODING)




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


def test_export_summary_txt_saves_title_and_both_summaries(tmp_path) -> None:
    """The summary file contains the title and the two summary sections."""

    path = tmp_path / "apuntes_summary.txt"

    DocumentExporterAdapter().export_summary_txt(SUMMARY, str(path))

    text = read(path)
    assert text.startswith("Agujero negro\n=============\n")
    positions = [text.index(part) for part in (
        SUMMARY_HEADING, "Resumen breve.",
        TRANSLATED_SUMMARY_HEADING, "Brief summary.",
    )]
    assert positions == sorted(positions)


def test_export_summary_txt_marks_missing_translation(tmp_path) -> None:
    """An empty translated summary is marked as not available."""

    path = tmp_path / "apuntes_summary.txt"

    DocumentExporterAdapter().export_summary_txt(
        BriefSummary("Agujero negro", "Resumen breve.", ""), str(path)
    )

    assert read(path).count(EMPTY_SECTION_TEXT) == 1


def test_export_summary_txt_raises_export_error_when_it_cannot_write(tmp_path) -> None:
    """A summary path that cannot be written becomes a domain ExportError."""

    folder_with_the_same_name = tmp_path / "apuntes_summary.txt"
    folder_with_the_same_name.mkdir()

    with pytest.raises(ExportError):
        DocumentExporterAdapter().export_summary_txt(
            SUMMARY, str(folder_with_the_same_name)
        )


def test_export_summary_pdf_saves_title_and_both_summaries(tmp_path) -> None:
    """The summary PDF opens and contains the title and both summaries."""

    path = tmp_path / "apuntes_summary.pdf"

    DocumentExporterAdapter().export_summary_pdf(SUMMARY, str(path))

    text, _ = read_pdf(path)
    positions = [text.index(part) for part in (
        "Agujero negro",
        SUMMARY_HEADING, "Resumen breve.",
        TRANSLATED_SUMMARY_HEADING, "Brief summary.",
    )]
    assert positions == sorted(positions)


def test_export_summary_pdf_marks_missing_translation(tmp_path) -> None:
    """An empty translated summary is marked as not available in the PDF."""

    path = tmp_path / "apuntes_summary.pdf"

    DocumentExporterAdapter().export_summary_pdf(
        BriefSummary("Agujero negro", "Resumen breve.", ""), str(path)
    )

    text, _ = read_pdf(path)
    assert text.count(EMPTY_SECTION_TEXT) == 1


def test_export_summary_pdf_raises_export_error_when_it_cannot_write(tmp_path) -> None:
    """A summary PDF path that cannot be written becomes a domain ExportError."""

    folder_with_the_same_name = tmp_path / "apuntes_summary.pdf"
    folder_with_the_same_name.mkdir()

    with pytest.raises(ExportError):
        DocumentExporterAdapter().export_summary_pdf(
            SUMMARY, str(folder_with_the_same_name)
        )
