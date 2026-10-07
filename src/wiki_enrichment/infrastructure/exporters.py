"""Document exporter adapter for TXT and PDF files."""

from pathlib import Path

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


class DocumentExporterAdapter:
    """Save enriched content as TXT or PDF documents."""

    def export_txt(self, content: EnrichedContent, path: str) -> None:
        """Save the original, enriched and translated content as a text file.

        Missing folders are created and an existing file is overwritten.

        Raises:
            ExportError: If the file cannot be written.
        """

        file_path = Path(path)
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(build_txt_document(content), encoding=TEXT_ENCODING)
        except OSError as error:
            raise ExportError(f"Could not save the file {path}") from error

    def export_pdf(self, content: EnrichedContent, path: str) -> None:
        """Export PDF once an exporter implementation is configured."""

        raise NotImplementedError("PDF export is not implemented yet")
