"""Document exporter adapter placeholder."""

from wiki_enrichment.domain.models import EnrichedContent


class DocumentExporterAdapter:
    """Placeholder adapter for future TXT and PDF exporters."""

    def export_txt(self, content: EnrichedContent, path: str) -> None:
        """Export plain text once an exporter implementation is configured."""

        raise NotImplementedError("TXT export is not implemented yet")

    def export_pdf(self, content: EnrichedContent, path: str) -> None:
        """Export PDF once an exporter implementation is configured."""

        raise NotImplementedError("PDF export is not implemented yet")

