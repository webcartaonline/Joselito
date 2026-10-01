"""Integration test: Wikipedia adapter running inside the orchestrator."""

from unittest.mock import MagicMock, create_autospec, patch

from wiki_enrichment.application.use_cases import WikiEnrichmentOrchestrator
from wiki_enrichment.domain.models import EnrichedContent
from wiki_enrichment.domain.ports import (
    ContentEnricher,
    DocumentExporter,
    Translator,
)
from wiki_enrichment.infrastructure.wikipedia import WikipediaSourceAdapter

GET = "wiki_enrichment.infrastructure.wikipedia.requests.get"


def make_response(json_data=None, text=""):
    response = MagicMock()
    response.json.return_value = json_data
    response.text = text
    response.status_code = 200
    response.raise_for_status.return_value = None
    return response


@patch(GET)
def test_orchestrator_runs_with_real_wikipedia_adapter(mock_get) -> None:
    """The scraped article flows through the full pipeline."""
    mock_get.side_effect = [
        make_response(json_data={"query": {"search": [{"title": "Python"}]}}),
        make_response(text='<div id="mw-content-text"><p>A language.</p></div>'),
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