"""Unit tests for the wiki enrichment application workflow."""

from unittest.mock import create_autospec

from wiki_enrichment.application.use_cases import WikiEnrichmentOrchestrator
from wiki_enrichment.domain.models import ArticleContent, EnrichedContent
from wiki_enrichment.domain.ports import (
    ContentEnricher,
    DocumentExporter,
    Translator,
    WikipediaSource,
)


def test_execute_orchestrates_the_full_pipeline() -> None:
    """The use case coordinates ports without invoking real integrations."""

    article = ArticleContent("Python", ["A programming language."])
    enriched = EnrichedContent(article, "A concise summary.")
    source = create_autospec(WikipediaSource, instance=True)
    enricher = create_autospec(ContentEnricher, instance=True)
    translator = create_autospec(Translator, instance=True)
    exporter = create_autospec(DocumentExporter, instance=True)

    source.fetch_article.return_value = article
    enricher.enrich.return_value = enriched
    translator.translate.return_value = "Un résumé concis."
    orchestrator = WikiEnrichmentOrchestrator(
        source, enricher, translator, exporter
    )

    result = orchestrator.execute("Python", "fr", "output/article")

    expected = EnrichedContent(article, "A concise summary.", "Un résumé concis.")
    assert result == expected
    source.fetch_article.assert_called_once_with("Python")
    enricher.enrich.assert_called_once_with(article)
    translator.translate.assert_called_once_with("A concise summary.", "fr")
    exporter.export_txt.assert_called_once_with(expected, "output/article.txt")
    exporter.export_pdf.assert_called_once_with(expected, "output/article.pdf")


def test_fetch_article_only_queries_the_wikipedia_source() -> None:
    """Fetching an article does not trigger enrichment, translation, or export."""

    article = ArticleContent("Python", ["A programming language."])
    source = create_autospec(WikipediaSource, instance=True)
    enricher = create_autospec(ContentEnricher, instance=True)
    translator = create_autospec(Translator, instance=True)
    exporter = create_autospec(DocumentExporter, instance=True)

    source.fetch_article.return_value = article
    orchestrator = WikiEnrichmentOrchestrator(
        source, enricher, translator, exporter
    )

    assert orchestrator.fetch_article("Python") == article
    source.fetch_article.assert_called_once_with("Python")
    enricher.enrich.assert_not_called()
    translator.translate.assert_not_called()
    exporter.export_txt.assert_not_called()
    exporter.export_pdf.assert_not_called()
