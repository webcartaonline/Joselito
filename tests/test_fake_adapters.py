"""Unit tests for the contract-level fake adapters."""

import pytest

from tests.helpers.content_mocks import make_article, make_enriched
from tests.helpers.fake_adapters import (
    FakeContentEnricher,
    FakeDocumentExporter,
    FakeTranslator,
    FakeWikipediaSource,
)
from wiki_enrichment.domain.exceptions import (
    ProviderTimeoutError,
    ResourceNotFoundError,
    WikiEnrichmentError,
)


def test_fake_source_returns_fixed_article() -> None:
    """Return the configured article and record the requested topic."""
    article = make_article(title="Python")
    source = FakeWikipediaSource(article=article)

    result = source.fetch_article("Python")

    assert result == article
    assert source.requested_topics == ["Python"]


def test_fake_source_raises_configured_failure() -> None:
    """Raise the configured domain failure instead of returning content."""
    source = FakeWikipediaSource(failure=ResourceNotFoundError("missing"))

    with pytest.raises(ResourceNotFoundError):
        source.fetch_article("unknown")


def test_fake_enricher_attaches_summary() -> None:
    """Attach the fixed summary while keeping the original article."""
    article = make_article()
    enricher = FakeContentEnricher(ai_summary="A concise summary.")

    result = enricher.enrich(article)

    assert result == make_enriched(article, "A concise summary.")
    assert enricher.received_articles == [article]


def test_fake_enricher_raises_configured_failure() -> None:
    """Raise the configured failure when enrichment is not available."""
    enricher = FakeContentEnricher(failure=WikiEnrichmentError("ai down"))

    with pytest.raises(WikiEnrichmentError):
        enricher.enrich(make_article())


def test_fake_translator_tags_language() -> None:
    """Return deterministic output carrying the requested language."""
    translator = FakeTranslator()

    result = translator.translate("A concise summary.", "fr")

    assert result == "A concise summary. [fr]"
    assert translator.received_calls == [("A concise summary.", "fr")]


def test_fake_translator_raises_configured_failure() -> None:
    """Raise the configured failure instead of translating."""
    translator = FakeTranslator(failure=ProviderTimeoutError("slow provider"))

    with pytest.raises(ProviderTimeoutError):
        translator.translate("text", "es")


def test_fake_exporter_records_both_formats() -> None:
    """Record txt and pdf exports without writing any files."""
    content = make_enriched(translated_summary="Un résumé concis.")
    exporter = FakeDocumentExporter()

    exporter.export_txt(content, "output/article.txt")
    exporter.export_pdf(content, "output/article.pdf")

    assert exporter.saved_txt == [(content, "output/article.txt")]
    assert exporter.saved_pdf == [(content, "output/article.pdf")]
