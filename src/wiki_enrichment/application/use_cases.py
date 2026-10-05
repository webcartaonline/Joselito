"""Application use cases composed exclusively from domain ports."""

from wiki_enrichment.domain.models import ArticleContent, EnrichedContent
from wiki_enrichment.domain.ports import (
    ContentEnricher,
    DocumentExporter,
    Translator,
    WikipediaSource,
)


class WikiEnrichmentOrchestrator:
    """Coordinate article retrieval, enrichment, translation, and export."""

    def __init__(
        self,
        wikipedia_source: WikipediaSource,
        content_enricher: ContentEnricher,
        translator: Translator,
        document_exporter: DocumentExporter,
    ) -> None:
        """Configure the use case with its required ports."""

        self._wikipedia_source = wikipedia_source
        self._content_enricher = content_enricher
        self._translator = translator
        self._document_exporter = document_exporter

    def fetch_article(self, topic: str) -> ArticleContent:
        """Retrieve the source article for a topic without further processing.

        Lets the presentation layer show the article while the remaining
        stages (enrichment, translation, and export) are still in progress.
        """

        return self._wikipedia_source.fetch_article(topic)

    def execute(
        self, topic: str, target_lang: str, export_path: str
    ) -> EnrichedContent:
        """Run the workflow and export both TXT and PDF representations.

        ``export_path`` is treated as a base path. The exporter receives
        ``<base>.txt`` and ``<base>.pdf`` respectively.
        """

        article = self._wikipedia_source.fetch_article(topic)
        enriched = self._content_enricher.enrich(article)
        translated_summary = self._translator.translate(
            enriched.ai_summary, target_lang
        )
        completed = EnrichedContent(
            original_article=enriched.original_article,
            ai_summary=enriched.ai_summary,
            translated_summary=translated_summary,
        )
        self._document_exporter.export_txt(completed, f"{export_path}.txt")
        self._document_exporter.export_pdf(completed, f"{export_path}.pdf")
        return completed

