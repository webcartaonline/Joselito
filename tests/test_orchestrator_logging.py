"""Tests for the pipeline logging emitted by the orchestrator."""

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.helpers.content_mocks import (
    DEFAULT_EXPORT_BASE,
    DEFAULT_TARGET_LANG,
    DEFAULT_TOPIC,
    make_article,
    make_enriched,
)
from tests.helpers.fake_adapters import (
    FakeContentEnricher,
    FakeDocumentExporter,
    FakeTranslator,
    FakeWikipediaSource,
)
from wiki_enrichment.application.use_cases import WikiEnrichmentOrchestrator
from wiki_enrichment.domain.exceptions import (
    EnrichmentError,
    ExportError,
    ProviderTimeoutError,
    ResourceNotFoundError,
)
from wiki_enrichment.infrastructure.logging_config import (
    DEFAULT_RUN_ID,
    LOGGER_NAME,
    configure_logging,
    set_run_id,
)

LOG_FILE = Path("logs") / "app.log"
HUGGING_FACE_TOKEN = "hf_abcdefghijklmnop"


@pytest.fixture(autouse=True)
def log_workspace(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[Path]:
    """Run each test in a temporary directory with a clean logger."""

    logger = logging.getLogger(LOGGER_NAME)
    monkeypatch.chdir(tmp_path)
    set_run_id(DEFAULT_RUN_ID)
    yield tmp_path
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


def build_orchestrator(
    source: FakeWikipediaSource | None = None,
    enricher: FakeContentEnricher | None = None,
    translator: FakeTranslator | None = None,
    exporter: FakeDocumentExporter | None = None,
) -> WikiEnrichmentOrchestrator:
    """Build an orchestrator wired with fakes and optional failures."""

    return WikiEnrichmentOrchestrator(
        source if source is not None else FakeWikipediaSource(),
        enricher if enricher is not None else FakeContentEnricher(),
        translator if translator is not None else FakeTranslator(),
        exporter if exporter is not None else FakeDocumentExporter(),
    )


def read_log(workspace: Path) -> str:
    """Return the contents of the application log file."""

    return (workspace / LOG_FILE).read_text(encoding="utf-8")


def test_execute_logs_each_pipeline_stage(log_workspace: Path) -> None:
    """Every stage of the pipeline leaves an INFO milestone in the log."""
    configure_logging()

    build_orchestrator().execute(DEFAULT_TOPIC, DEFAULT_TARGET_LANG, DEFAULT_EXPORT_BASE)

    content = read_log(log_workspace)
    for message in (
        "Pipeline started",
        "Fetching article",
        "Enriching article",
        "Translating text",
        "Exporting document",
        "Pipeline finished",
    ):
        assert message in content


def test_fetch_failure_is_logged_as_error(log_workspace: Path) -> None:
    """A failing source logs an ERROR with the topic."""
    source = FakeWikipediaSource(failure=ResourceNotFoundError("missing"))
    configure_logging()

    with pytest.raises(ResourceNotFoundError):
        build_orchestrator(source=source).fetch_article(DEFAULT_TOPIC)

    content = read_log(log_workspace)
    assert "| ERROR |" in content
    assert "Article fetch failed" in content


def test_unknown_export_format_is_logged_as_error(log_workspace: Path) -> None:
    """An unsupported format logs an ERROR before raising."""
    configure_logging()

    with pytest.raises(ValueError, match="DOCX"):
        build_orchestrator().export_document(
            make_enriched(), "DOCX", "output/notes.docx"
        )

    content = read_log(log_workspace)
    assert "| ERROR |" in content
    assert "Unsupported export format" in content


def test_enrich_failure_is_logged_as_error(log_workspace: Path) -> None:
    """A failing enricher logs an ERROR with the article title."""
    enricher = FakeContentEnricher(failure=EnrichmentError("no credits"))
    configure_logging()

    with pytest.raises(EnrichmentError):
        build_orchestrator(enricher=enricher).enrich_article(make_article())

    content = read_log(log_workspace)
    assert "| ERROR |" in content
    assert "Article enrichment failed" in content


def test_export_failure_is_logged_as_error(log_workspace: Path) -> None:
    """A failing exporter logs an ERROR with the file name."""
    exporter = FakeDocumentExporter(failure=ExportError("no space"))
    configure_logging()

    with pytest.raises(ExportError):
        build_orchestrator(exporter=exporter).export_document(
            make_enriched(), "TXT", "output/notes.txt"
        )

    content = read_log(log_workspace)
    assert "| ERROR |" in content
    assert "Document export failed" in content


def test_translate_failure_is_logged_as_error(log_workspace: Path) -> None:
    """A failing translator logs an ERROR with the target language."""
    translator = FakeTranslator(failure=ProviderTimeoutError("slow"))
    configure_logging()

    with pytest.raises(ProviderTimeoutError):
        build_orchestrator(translator=translator).translate_text("text", "fr")

    content = read_log(log_workspace)
    assert "| ERROR |" in content
    assert "Translation failed" in content


def test_debug_details_are_hidden_at_info_level(log_workspace: Path) -> None:
    """Detail records are not written when the level is INFO."""
    configure_logging()

    build_orchestrator().fetch_article(DEFAULT_TOPIC)

    assert "Article fetched" not in read_log(log_workspace)


def test_debug_details_are_logged_at_debug_level(log_workspace: Path) -> None:
    """Detail records are written when the level is DEBUG."""
    configure_logging("DEBUG")

    build_orchestrator().fetch_article(DEFAULT_TOPIC)

    assert "Article fetched" in read_log(log_workspace)


def test_exception_trace_redacts_hugging_face_token(log_workspace: Path) -> None:
    """The traceback of a logged failure does not leak the token."""
    source = FakeWikipediaSource(
        failure=ResourceNotFoundError(f"auth failed for {HUGGING_FACE_TOKEN}")
    )
    configure_logging()

    with pytest.raises(ResourceNotFoundError):
        build_orchestrator(source=source).fetch_article(DEFAULT_TOPIC)

    content = read_log(log_workspace)
    assert HUGGING_FACE_TOKEN not in content
    assert "***" in content
