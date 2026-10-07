"""Unit tests for the wiki enrichment application workflow."""

from unittest.mock import create_autospec

import pytest

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


def test_fetch_article_only_queries_the_wikipedia_source() -> None:
    """Fetching an article does not trigger enrichment, translation, or export."""

    article = make_article(title="Python", paragraphs=["A programming language."])
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


def make_orchestrator_with_exporter():
    """Build an orchestrator whose ports are all autospec mocks."""

    exporter = create_autospec(DocumentExporter, instance=True)
    orchestrator = WikiEnrichmentOrchestrator(
        create_autospec(WikipediaSource, instance=True),
        create_autospec(ContentEnricher, instance=True),
        create_autospec(Translator, instance=True),
        exporter,
    )
    return orchestrator, exporter


def test_export_document_as_pdf_only_creates_the_pdf() -> None:
    """Choosing PDF exports a single PDF file with the given path."""

    content = make_enriched(make_article(), "A concise summary.", "Un résumé.")
    orchestrator, exporter = make_orchestrator_with_exporter()

    orchestrator.export_document(content, "PDF", "output/notes.pdf")

    exporter.export_pdf.assert_called_once_with(content, "output/notes.pdf")
    exporter.export_txt.assert_not_called()


def test_export_document_as_txt_only_creates_the_txt() -> None:
    """Choosing TXT exports a single text file with the given path."""

    content = make_enriched(make_article(), "A concise summary.", "Un résumé.")
    orchestrator, exporter = make_orchestrator_with_exporter()

    orchestrator.export_document(content, "TXT", "output/notes.txt")

    exporter.export_txt.assert_called_once_with(content, "output/notes.txt")
    exporter.export_pdf.assert_not_called()


def test_export_document_rejects_unknown_formats() -> None:
    """An unsupported format raises an error and exports nothing."""

    content = make_enriched(make_article(), "A concise summary.")
    orchestrator, exporter = make_orchestrator_with_exporter()

    with pytest.raises(ValueError, match="DOCX"):
        orchestrator.export_document(content, "DOCX", "output/notes.docx")

    exporter.export_txt.assert_not_called()
    exporter.export_pdf.assert_not_called()


def test_enrich_article_only_calls_the_enricher() -> None:
    """Enriching an article does not fetch, translate or export anything."""

    article = make_article()
    enriched = make_enriched(article, "A concise summary.")
    source = create_autospec(WikipediaSource, instance=True)
    enricher = create_autospec(ContentEnricher, instance=True)
    translator = create_autospec(Translator, instance=True)
    exporter = create_autospec(DocumentExporter, instance=True)
    enricher.enrich.return_value = enriched
    orchestrator = WikiEnrichmentOrchestrator(source, enricher, translator, exporter)

    assert orchestrator.enrich_article(article) == enriched
    enricher.enrich.assert_called_once_with(article)
    source.fetch_article.assert_not_called()
    translator.translate.assert_not_called()
    exporter.export_txt.assert_not_called()
    exporter.export_pdf.assert_not_called()
