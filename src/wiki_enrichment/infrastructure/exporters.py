"""Document exporter adapter for TXT and PDF files."""

from pathlib import Path
from typing import Callable

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from fpdf.errors import FPDFException

from wiki_enrichment.domain.exceptions import ExportError
from wiki_enrichment.domain.models import EnrichedContent

ORIGINAL_HEADING = "Contenido original (Wikipedia)"
ENRICHED_HEADING = "Contenido enriquecido (IA)"
TRANSLATED_HEADING = "Contenido traducido"
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


def build_sections(content: EnrichedContent) -> list[tuple[str, str]]:
    """Return the three document sections as (heading, text) pairs.

    Empty sections get EMPTY_SECTION_TEXT so the reader knows they are missing.
    """

    sections = [
        (ORIGINAL_HEADING, content.original_article.full_text),
        (ENRICHED_HEADING, content.ai_summary),
        (TRANSLATED_HEADING, content.translated_summary),
    ]
    return [(heading, text.strip() or EMPTY_SECTION_TEXT) for heading, text in sections]


def underline(text: str, character: str) -> str:
    """Return the text followed by a line of characters of the same length."""

    return f"{text}\n{character * len(text)}"


def build_txt_document(content: EnrichedContent) -> str:
    """Build the plain-text document with the title and the three sections."""

    blocks = [underline(content.original_article.title, TITLE_UNDERLINE)]
    blocks += [
        f"{underline(heading, SECTION_UNDERLINE)}\n{text}"
        for heading, text in build_sections(content)
    ]
    return BLOCK_SEPARATOR.join(blocks) + "\n"


def write_pdf_block(pdf: FPDF, text: str, style: str, size: int, line_height: int) -> None:
    """Write a block of text that wraps lines and starts again at the left margin."""

    pdf.set_font(PDF_FONT_FAMILY, style, size)
    pdf.multi_cell(FULL_WIDTH, line_height, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def build_pdf_document(content: EnrichedContent) -> FPDF:
    """Build the PDF document with the title and the three sections.

    Uses the DejaVu font so accents, dashes, Greek or Cyrillic letters work.
    """

    pdf = FPDF(format=PDF_PAGE_FORMAT)
    pdf.set_margins(PDF_MARGIN_MM, PDF_MARGIN_MM, PDF_MARGIN_MM)
    pdf.set_auto_page_break(auto=True, margin=PDF_MARGIN_MM)
    pdf.add_font(PDF_FONT_FAMILY, REGULAR_STYLE, PDF_REGULAR_FONT_FILE)
    pdf.add_font(PDF_FONT_FAMILY, BOLD_STYLE, PDF_BOLD_FONT_FILE)
    pdf.set_title(content.original_article.title)
    pdf.add_page()

    write_pdf_block(
        pdf, content.original_article.title, BOLD_STYLE,
        PDF_TITLE_FONT_SIZE, PDF_TITLE_LINE_HEIGHT_MM,
    )
    for heading, text in build_sections(content):
        pdf.ln(PDF_SECTION_SPACING_MM)
        write_pdf_block(
            pdf, heading, BOLD_STYLE, PDF_HEADING_FONT_SIZE, PDF_HEADING_LINE_HEIGHT_MM
        )
        write_pdf_block(
            pdf, text, REGULAR_STYLE, PDF_BODY_FONT_SIZE, PDF_BODY_LINE_HEIGHT_MM
        )
    return pdf


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
    """Save enriched content as TXT or PDF documents."""

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
