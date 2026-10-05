"""Unit tests for the wiki enrichment application workflow."""

from unittest.mock import create_autospec

from tests.helpers.content_mocks import make_article, make_enriched
from wiki_enrichment.application.use_cases import WikiEnrichmentOrchestrator
from wiki_enrichment.domain.ports import (
    ContentEnricher,
    DocumentExporter,
    Translator,
    WikipediaSource,
)


def test_execute_orchestrates_the_full_pipeline() -> None:
    """The use case coordinates ports without invoking real integrations."""

    article = make_article(title="Python", paragraphs=["A programming language."])
    enriched = make_enriched(article, "A concise summary.")
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

    expected = make_enriched(article, "A concise summary.", "Un résumé concis.")
    assert result == expected
    source.fetch_article.assert_called_once_with("Python")
    enricher.enrich.assert_called_once_with(article)
    translator.translate.assert_called_once_with("A concise summary.", "fr")
    exporter.export_txt.assert_called_once_with(expected, "output/article.txt")
    exporter.export_pdf.assert_called_once_with(expected, "output/article.pdf")

