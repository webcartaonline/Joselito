"""BDD step definitions for application logging with simulated services."""

import logging
import re
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import create_autospec

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.helpers.fake_adapters import (
    FakeContentEnricher,
    FakeDocumentExporter,
    FakeTranslator,
    FakeWikipediaSource,
)
from application.wiki_enrichment_orchestrator import WikiEnrichmentOrchestrator
from domain.exceptions import ResourceNotFoundError
from domain.ports import ContentSummarizer
from infrastructure.logging_config import (
    DEFAULT_RUN_ID,
    LOGGER_NAME,
    configure_logging,
    set_run_id,
)

scenarios("../features/logging.feature")

LOG_FILE = Path("logs") / "app.log"
HUGGING_FACE_TOKEN = "hf_abcdefghijklmnop"
DEEPSEEK_API_KEY = "sk-abcdefghijklmnop"
TARGET_LANG = "fr"
EXPORT_BASE = "output/article"
LOG_LINE = re.compile(
    r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \| "
    r"(DEBUG|INFO|WARNING|ERROR|CRITICAL) \|"
)


@pytest.fixture
def context(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[dict]:
    """Run each scenario in a temporary folder with a clean logger."""

    logger = logging.getLogger(LOGGER_NAME)
    monkeypatch.chdir(tmp_path)
    set_run_id(DEFAULT_RUN_ID)
    yield {"folder": tmp_path}
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


def read_log(context: dict) -> str:
    """Return the contents of the application log file."""

    return (context["folder"] / LOG_FILE).read_text(encoding="utf-8")


def build_orchestrator(context: dict) -> WikiEnrichmentOrchestrator:
    """Wire the use case with fakes, honouring a configured source failure."""

    return WikiEnrichmentOrchestrator(
        context.get("source", FakeWikipediaSource()),
        FakeContentEnricher(),
        FakeTranslator(),
        FakeDocumentExporter(),
        create_autospec(ContentSummarizer, instance=True),
    )


@given("the logging is configured in a temporary folder")
def logging_is_configured(context: dict) -> None:
    """Configure the application logger without touching the real folder."""
    configure_logging()


@given("the Wikipedia source cannot find the article")
def source_cannot_find_article(context: dict) -> None:
    """Configure the fake source to raise a not-found error."""
    context["source"] = FakeWikipediaSource(failure=ResourceNotFoundError("missing"))


@given("the Wikipedia source fails with a Hugging Face token")
def source_fails_with_token(context: dict) -> None:
    """Configure the fake source to fail with a message carrying the token."""
    context["source"] = FakeWikipediaSource(
        failure=ResourceNotFoundError(f"auth failed for {HUGGING_FACE_TOKEN}")
    )


@given("the Wikipedia source fails with a DeepSeek API key")
def source_fails_with_deepseek_key(context: dict) -> None:
    """Configure the fake source to fail with a message carrying a DeepSeek key."""
    context["source"] = FakeWikipediaSource(
        failure=ResourceNotFoundError(f"auth failed for {DEEPSEEK_API_KEY}")
    )


@when(
    parsers.parse('I run a research session for the topic "{topic}"'),
    target_fixture="context",
)
def run_research_session(context: dict, topic: str) -> dict:
    """Run the pipeline, keeping any raised error for the next step."""
    try:
        build_orchestrator(context).execute(topic, TARGET_LANG, EXPORT_BASE)
        context["error"] = None
    except Exception as error:
        context["error"] = error
    return context


@then("the log records the pipeline stages")
def log_records_pipeline_stages(context: dict) -> None:
    content = read_log(context)
    for stage in (
        "Pipeline started",
        "Fetching article",
        "Enriching article",
        "Translating text",
        "Exporting document",
        "Pipeline finished",
    ):
        assert stage in content


@then("the log file exists")
def log_file_exists(context: dict) -> None:
    assert (context["folder"] / LOG_FILE).is_file()


@then("every log line has a date and a level")
def every_log_line_has_date_and_level(context: dict) -> None:
    lines = read_log(context).splitlines()
    assert lines
    assert all(LOG_LINE.match(line) for line in lines)


@then("the log records an error")
def log_records_an_error(context: dict) -> None:
    assert "| ERROR |" in read_log(context)


@then("the log does not contain the token")
def log_does_not_contain_token(context: dict) -> None:
    content = read_log(context)
    assert HUGGING_FACE_TOKEN not in content
    assert "***" in content


@then("the log does not contain the DeepSeek key")
def log_does_not_contain_deepseek_key(context: dict) -> None:
    content = read_log(context)
    assert DEEPSEEK_API_KEY not in content
    assert "***" in content
