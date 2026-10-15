"""Protocol-based ports defining the domain's external capabilities."""

from typing import Protocol

from wiki_enrichment.domain.models import ArticleContent, BriefSummary, EnrichedContent


class WikipediaSource(Protocol):
    """Port for retrieving article content."""

    def fetch_article(self, topic: str) -> ArticleContent:
        """Fetch an article for a topic."""


class ContentEnricher(Protocol):
    """Port for enriching an article with an AI-generated summary."""

    def enrich(self, article: ArticleContent) -> EnrichedContent:
        """Generate enrichment for an article."""


class Translator(Protocol):
    """Port for translating text into a target language."""

    def translate(self, text: str, target_lang: str) -> str:
        """Translate text into the requested language."""


class DocumentExporter(Protocol):
    """Port for exporting enriched content and summaries to supported formats."""

    def export_txt(self, content: EnrichedContent, path: str) -> None:
        """Export content as a plain-text document."""

    def export_pdf(self, content: EnrichedContent, path: str) -> None:
        """Export content as a PDF document."""

    def export_summary_txt(self, summary: BriefSummary, path: str) -> None:
        """Export a brief summary as a plain-text document."""

    def export_summary_pdf(self, summary: BriefSummary, path: str) -> None:
        """Export a brief summary as a PDF document."""


class ContentSummarizer(Protocol):
    """Port for generating a brief summary of a text."""

    def summarize(self, text: str) -> str:
        """Generate a brief summary for the given text."""