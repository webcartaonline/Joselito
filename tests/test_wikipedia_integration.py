"""Integration tests for the orchestrator with a mocked Wikipedia adapter."""

from unittest.mock import create_autospec, patch

from tests.helpers.wikipedia_mocks import (
    REQUEST_TARGET,
    build_article_html,
    make_article_response,
    make_search_response,
)
from wiki_enrichment.application.use_cases import WikiEnrichmentOrchestrator
from wiki_enrichment.domain.models import EnrichedContent
from wiki_enrichment.domain.ports import (
    ContentEnricher,
    DocumentExporter,
    Translator,
)
from wiki_enrichment.infrastructure.wikipedia import WikipediaSourceAdapter


@patch(REQUEST_TARGET)
def test_orchestrator_runs_with_real_wikipedia_adapter(mock_get) -> None:
    """Run the pipeline with a real adapter and mocked HTTP responses."""
    mock_get.side_effect = [
        make_search_response("Python"),
        make_article_response(build_article_html(["A language."])),
    ]
    enricher = create_autospec(ContentEnricher, instance=True)
    enricher.enrich.side_effect = lambda article: EnrichedContent(article, "Summary")
    translator = create_autospec(Translator, instance=True)
    translator.translate.return_value = "Resumen"
    exporter = create_autospec(DocumentExporter, instance=True)

    orchestrator = WikiEnrichmentOrchestrator(
        WikipediaSourceAdapter(), enricher, translator, exporter
    )
    result = orchestrator.execute("python", "es", "output/article")

    assert result.original_article.title == "Python"
    assert result.original_article.paragraphs == ["A language."]
    assert result.translated_summary == "Resumen"
    exporter.export_txt.assert_called_once()
    exporter.export_pdf.assert_called_once()
