"""Document exporter adapter for TXT and PDF files."""

from pathlib import Path
from typing import Callable

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from fpdf.errors import FPDFException

from domain.exceptions import ExportError
from domain.models import BriefSummary, EnrichedContent

ORIGINAL_HEADING = "Contenido original (Wikipedia)"
ENRICHED_HEADING = "Contenido enriquecido (IA)"
TRANSLATED_HEADING = "Contenido traducido"
SUMMARY_HEADING = "Resumen breve"
TRANSLATED_SUMMARY_HEADING = "Resumen traducido"
EMPTY_SECTION_TEXT = "(No disponible)"
TITLE_UNDERLINE = "="
SECTION_UNDERLINE = "-"
BLOCK_SEPARATOR = "\n\n\n"
TEXT_ENCODING = "utf-8"

FONTS_FOLDER = Path(__file__).parent / "fonts"
PDF_FONT_FAMILY = "DejaVu"
PDF_REGULAR_FONT_FILE = FONTS_FOLDER / "DejaVuSans.ttf"
PDF_BOLD_FONT_FILE = FONTS_FOLDER / "DejaVuSans-Bold.ttf"
REGULAR_STYLE = ""
BOLD_STYLE = "B"
PDF_PAGE_FORMAT = "A4"
PDF_MARGIN_MM = 20
PDF_TITLE_FONT_SIZE = 20
PDF_HEADING_FONT_SIZE = 14
PDF_BODY_FONT_SIZE = 11
PDF_TITLE_LINE_HEIGHT_MM = 10
PDF_HEADING_LINE_HEIGHT_MM = 8
PDF_BODY_LINE_HEIGHT_MM = 6
PDF_SECTION_SPACING_MM = 6
FULL_WIDTH = 0  # In fpdf2, a width of 0 means "up to the right margin".


def mark_empty_sections(sections: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Return the sections with EMPTY_SECTION_TEXT in place of any empty text."""

    return [(heading, text.strip() or EMPTY_SECTION_TEXT) for heading, text in sections]


def build_sections(content: EnrichedContent) -> list[tuple[str, str]]:
    """Return the three document sections as (heading, text) pairs.

    Empty sections get EMPTY_SECTION_TEXT so the reader knows they are missing.
    """

    return mark_empty_sections([
        (ORIGINAL_HEADING, content.original_article.full_text),
        (ENRICHED_HEADING, content.ai_summary),
        (TRANSLATED_HEADING, content.translated_summary),
    ])


def build_summary_sections(summary: BriefSummary) -> list[tuple[str, str]]:
    """Return the two summary sections as (heading, text) pairs.

    Empty sections get EMPTY_SECTION_TEXT so the reader knows they are missing.
    """

    return mark_empty_sections([
        (SUMMARY_HEADING, summary.text),
        (TRANSLATED_SUMMARY_HEADING, summary.translated_text),
    ])


def underline(text: str, character: str) -> str:
    """Return the text followed by a line of characters of the same length."""

    return f"{text}\n{character * len(text)}"


def format_txt_document(title: str, sections: list[tuple[str, str]]) -> str:
    """Build a plain-text document with a title and its sections."""

    blocks = [underline(title, TITLE_UNDERLINE)]
    blocks += [
        f"{underline(heading, SECTION_UNDERLINE)}\n{text}" for heading, text in sections
    ]
    return BLOCK_SEPARATOR.join(blocks) + "\n"


def build_txt_document(content: EnrichedContent) -> str:
    """Build the plain-text document with the title and the three sections."""

    return format_txt_document(content.original_article.title, build_sections(content))


def build_summary_txt_document(summary: BriefSummary) -> str:
    """Build the plain-text document with the title and the two summaries."""

    return format_txt_document(summary.title, build_summary_sections(summary))


def write_pdf_block(pdf: FPDF, text: str, style: str, size: int, line_height: int) -> None:
    """Write a block of text that wraps lines and starts again at the left margin."""

    pdf.set_font(PDF_FONT_FAMILY, style, size)
    pdf.multi_cell(FULL_WIDTH, line_height, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def create_pdf_document(title: str, sections: list[tuple[str, str]]) -> FPDF:
    """Build a PDF document with a title and its sections.

    Uses the DejaVu font so accents, dashes, Greek or Cyrillic letters work.
    """

    pdf = FPDF(format=PDF_PAGE_FORMAT)
    pdf.set_margins(PDF_MARGIN_MM, PDF_MARGIN_MM, PDF_MARGIN_MM)
    pdf.set_auto_page_break(auto=True, margin=PDF_MARGIN_MM)
    pdf.add_font(PDF_FONT_FAMILY, REGULAR_STYLE, PDF_REGULAR_FONT_FILE)
    pdf.add_font(PDF_FONT_FAMILY, BOLD_STYLE, PDF_BOLD_FONT_FILE)
    pdf.set_title(title)
    pdf.add_page()

    write_pdf_block(pdf, title, BOLD_STYLE, PDF_TITLE_FONT_SIZE, PDF_TITLE_LINE_HEIGHT_MM)
    for heading, text in sections:
        pdf.ln(PDF_SECTION_SPACING_MM)
        write_pdf_block(
            pdf, heading, BOLD_STYLE, PDF_HEADING_FONT_SIZE, PDF_HEADING_LINE_HEIGHT_MM
        )
        write_pdf_block(
            pdf, text, REGULAR_STYLE, PDF_BODY_FONT_SIZE, PDF_BODY_LINE_HEIGHT_MM
        )
    return pdf


def build_pdf_document(content: EnrichedContent) -> FPDF:
    """Build the PDF document with the title and the three sections."""

    return create_pdf_document(content.original_article.title, build_sections(content))


def build_summary_pdf_document(summary: BriefSummary) -> FPDF:
    """Build the PDF document with the title and the two summaries."""

    return create_pdf_document(summary.title, build_summary_sections(summary))


def save_file(path: str, write: Callable[[Path], None]) -> None:
    """Create the missing folders and write the file, overwriting it if it exists.

    Raises:
        ExportError: If the file cannot be created or written.
    """

    file_path = Path(path)
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        write(file_path)
    except (OSError, FPDFException) as error:
        raise ExportError(f"Could not save the file {path}") from error


class DocumentExporterAdapter:
    """Save enriched content and brief summaries as TXT or PDF documents."""

    def export_txt(self, content: EnrichedContent, path: str) -> None:
        """Save the original, enriched and translated content as a text file.

        Missing folders are created and an existing file is overwritten.

        Raises:
            ExportError: If the file cannot be written.
        """

        save_file(
            path,
            lambda file_path: file_path.write_text(
                build_txt_document(content), encoding=TEXT_ENCODING
            ),
        )

    def export_pdf(self, content: EnrichedContent, path: str) -> None:
        """Save the original, enriched and translated content as a PDF file.

        Missing folders are created and an existing file is overwritten.

        Raises:
            ExportError: If the file cannot be written.
        """

        save_file(path, lambda file_path: build_pdf_document(content).output(str(file_path)))

    def export_summary_txt(self, summary: BriefSummary, path: str) -> None:
        """Save the brief summary and its translation as a text file.

        Missing folders are created and an existing file is overwritten.

        Raises:
            ExportError: If the file cannot be written.
        """

        save_file(
            path,
            lambda file_path: file_path.write_text(
                build_summary_txt_document(summary), encoding=TEXT_ENCODING
            ),
        )

    def export_summary_pdf(self, summary: BriefSummary, path: str) -> None:
        """Save the brief summary and its translation as a PDF file.

        Missing folders are created and an existing file is overwritten.

        Raises:
            ExportError: If the file cannot be written.
        """

        save_file(
            path,
            lambda file_path: build_summary_pdf_document(summary).output(str(file_path)),
        )