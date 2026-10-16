"""Application use cases composed exclusively from domain ports."""

import logging
from pathlib import Path

from domain.exceptions import WikiEnrichmentError
from domain.models import (
    ArticleContent,
    BriefSummary,
    EnrichedContent,
    SearchResult,
)
from domain.ports import (
    ContentEnricher,
    ContentSummarizer,
    DocumentExporter,
    Translator,
    WikipediaSource,
)
from infrastructure.logging_config import LOGGER_NAME

logger = logging.getLogger(f"{LOGGER_NAME}.{__name__}")


class WikiEnrichmentOrchestrator:
    """Coordinate article retrieval, enrichment, translation, and export."""

    def __init__(
        self,
        wikipedia_source: WikipediaSource,
        content_enricher: ContentEnricher,
        translator: Translator,
        document_exporter: DocumentExporter,
        content_summarizer: ContentSummarizer,
    ) -> None:
        """Configure the use case with its required ports."""

        self._wikipedia_source = wikipedia_source
        self._content_enricher = content_enricher
        self._translator = translator
        self._document_exporter = document_exporter
        self._content_summarizer = content_summarizer

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

    def search_articles(self, topic: str) -> list[SearchResult]:
        """Return the search results so the user can confirm or choose one."""

        logger.info("Searching articles: topic=%s", topic)
        try:
            results = self._wikipedia_source.search(topic)
        except WikiEnrichmentError:
            logger.error("Article search failed: topic=%s", topic, exc_info=True)
            raise
        logger.debug(
            "Search finished: topic=%s results=%d",
            topic,
            len(results),
        )
        return results

    def fetch_article_by_title(self, title: str) -> ArticleContent:
        """Download only the article that the user has chosen."""

        logger.info("Fetching chosen article: title=%s", title)
        try:
            article = self._wikipedia_source.fetch_article_by_title(title)
        except WikiEnrichmentError:
            logger.error("Chosen article fetch failed: title=%s", title, exc_info=True)
            raise
        logger.debug(
            "Chosen article ready: title=%s paragraphs=%d",
            title,
            len(article.paragraphs),
        )
        return article

    def translate_article(self, article: ArticleContent, target_lang: str) -> str:
        """Translate the fetched article while keeping provider I/O in its adapter."""

        return self._translator.translate(article.full_text, target_lang)

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

    def summarize(self, content: EnrichedContent, target_lang: str) -> BriefSummary:
        """Generate a brief summary of the enriched text without translating it."""

        title = content.original_article.title
        logger.info("Summarizing text: title=%s target=%s", title, target_lang)
        try:
            text = self._content_summarizer.summarize(content.ai_summary)
        except WikiEnrichmentError:
            logger.error("Summarization failed: title=%s", title, exc_info=True)
            raise
        logger.debug("Text summarized: title=%s characters=%d", title, len(text))
        return BriefSummary(
            title=title,
            text=text,
        )

    def export_summary(
        self, summary: BriefSummary, export_format: str, path: str
    ) -> None:
        """Export the brief summary only in the format chosen by the user.

        ``export_format`` must be ``"TXT"`` or ``"PDF"`` and ``path`` is the
        full file path, extension included.
        """

        exporters = {
            "TXT": self._document_exporter.export_summary_txt,
            "PDF": self._document_exporter.export_summary_pdf,
        }
        if export_format not in exporters:
            logger.error("Unsupported summary export format: %s", export_format)
            raise ValueError(f"Unsupported export format: {export_format}")
        file_name = Path(path).name
        logger.info("Exporting summary: format=%s file=%s", export_format, file_name)
        try:
            exporters[export_format](summary, path)
        except WikiEnrichmentError:
            logger.error(
                "Summary export failed: format=%s file=%s",
                export_format,
                file_name,
                exc_info=True,
            )
            raise
        logger.debug("Summary exported: file=%s", file_name)

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
