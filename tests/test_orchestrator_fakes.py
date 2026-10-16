"""Pipeline tests running the orchestrator only with contract fakes."""

from unittest.mock import create_autospec

from tests.helpers.content_mocks import (
    DEFAULT_EXPORT_BASE,
    DEFAULT_TARGET_LANG,
    DEFAULT_TOPIC,
    make_article,
)
from tests.helpers.fake_adapters import (
    FakeContentEnricher,
    FakeDocumentExporter,
    FakeTranslator,
    FakeWikipediaSource,
)

from application.wiki_enrichment_orchestrator import WikiEnrichmentOrchestrator
from domain.ports import ContentSummarizer


def test_execute_runs_full_pipeline_with_fakes(
    fake_source: FakeWikipediaSource,
    fake_enricher: FakeContentEnricher,
    fake_translator: FakeTranslator,
    fake_exporter: FakeDocumentExporter,
) -> None:
    """Coordinate all ports and export both documents without any I/O."""
    orchestrator = WikiEnrichmentOrchestrator(
        fake_source,
        fake_enricher,
        fake_translator,
        fake_exporter,
        create_autospec(ContentSummarizer, instance=True),
    )

    result = orchestrator.execute(DEFAULT_TOPIC, DEFAULT_TARGET_LANG, DEFAULT_EXPORT_BASE)

    assert result.original_article == make_article()
    assert result.translated_summary == "A concise summary. [fr]"
    assert fake_source.requested_topics == [DEFAULT_TOPIC]
    assert fake_translator.received_calls == [("A concise summary.", "fr")]
    assert [path for _, path in fake_exporter.saved_txt] == ["output/article.txt"]
    assert [path for _, path in fake_exporter.saved_pdf] == ["output/article.pdf"]
