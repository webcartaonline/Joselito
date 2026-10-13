"""Application use cases composed exclusively from domain ports."""

import logging
from pathlib import Path

from wiki_enrichment.domain.exceptions import WikiEnrichmentError
from wiki_enrichment.domain.models import ArticleContent, EnrichedContent
from wiki_enrichment.domain.ports import (
    ContentEnricher,
    DocumentExporter,
    Translator,
    WikipediaSource,
)

logger = logging.getLogger(__name__)


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

        logger.info("Fetching article: topic=%s", topic)
        try:
            article = self._wikipedia_source.fetch_article(topic)
        except WikiEnrichmentError:
            logger.error("Article fetch failed: topic=%s", topic, exc_info=True)
            raise
        logger.debug(
            "Article fetched: title=%s paragraphs=%d",
            article.title,
            len(article.paragraphs),
        )
        return article

    def enrich_article(self, article: ArticleContent) -> EnrichedContent:
        """Enrich an already fetched article without translating or exporting it."""

        logger.info("Enriching article: title=%s", article.title)
        try:
            enriched = self._content_enricher.enrich(article)
        except WikiEnrichmentError:
            logger.error(
                "Article enrichment failed: title=%s", article.title, exc_info=True
            )
            raise
        logger.debug(
            "Article enriched: title=%s characters=%d",
            article.title,
            len(enriched.ai_summary),
        )
        return enriched

    def export_document(
        self, content: EnrichedContent, export_format: str, path: str
    ) -> None:
        """Export content only in the format chosen by the user.

        ``export_format`` must be ``"TXT"`` or ``"PDF"`` and ``path`` is the
        full file path, extension included (for example ``output/notes.pdf``).
        """

        exporters = {
            "TXT": self._document_exporter.export_txt,
            "PDF": self._document_exporter.export_pdf,
        }
        if export_format not in exporters:
            logger.error("Unsupported export format: %s", export_format)
            raise ValueError(f"Unsupported export format: {export_format}")
        file_name = Path(path).name
        logger.info("Exporting document: format=%s file=%s", export_format, file_name)
        try:
            exporters[export_format](content, path)
        except WikiEnrichmentError:
            logger.error(
                "Document export failed: format=%s file=%s",
                export_format,
                file_name,
                exc_info=True,
            )
            raise
        logger.debug("Document exported: file=%s", file_name)

    def translate_text(self, text: str, target_lang: str) -> str:
        """Translate a text into the target language."""

        logger.info("Translating text: target=%s", target_lang)
        try:
            translated = self._translator.translate(text, target_lang)
        except WikiEnrichmentError:
            logger.error("Translation failed: target=%s", target_lang, exc_info=True)
            raise
        logger.debug(
            "Text translated: target=%s characters=%d", target_lang, len(translated)
        )
        return translated

    def execute(
        self, topic: str, target_lang: str, export_path: str
    ) -> EnrichedContent:
        """Run the workflow and export both TXT and PDF representations.

        ``export_path`` is treated as a base path. The exporter receives
        ``<base>.txt`` and ``<base>.pdf`` respectively.
        """

        logger.info("Pipeline started: topic=%s target=%s", topic, target_lang)
        article = self.fetch_article(topic)
        enriched = self.enrich_article(article)
        translated_summary = self.translate_text(enriched.ai_summary, target_lang)
        completed = EnrichedContent(
            original_article=enriched.original_article,
            ai_summary=enriched.ai_summary,
            translated_summary=translated_summary,
        )
        self.export_document(completed, "TXT", f"{export_path}.txt")
        self.export_document(completed, "PDF", f"{export_path}.pdf")
        logger.info("Pipeline finished: topic=%s", topic)
        return completed

