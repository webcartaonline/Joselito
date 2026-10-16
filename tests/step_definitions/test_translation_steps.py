"""BDD step definitions for translating the article."""

from unittest.mock import create_autospec, patch

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from rich.console import Console
from typer.testing import CliRunner

import cli
from tests.helpers.fake_adapters import (
    FakeContentEnricher,
    FakeDocumentExporter,
    FakeTranslator,
    FakeWikipediaSource,
)
from application.wiki_enrichment_orchestrator import WikiEnrichmentOrchestrator
from domain.exceptions import ProviderTimeoutError, WikiEnrichmentError
from domain.ports import ContentSummarizer

scenarios("../features/translation.feature")

runner = CliRunner()


@pytest.fixture(autouse=True)
def plain_console(monkeypatch, tmp_path):
    """Print without colors, and save any file in a temporary folder."""
    monkeypatch.setattr(cli, "PENDING_STEP_SECONDS", 0)
    monkeypatch.setattr(cli, "EXPORT_FOLDER", str(tmp_path))
    monkeypatch.setattr(
        cli,
        "console",
        Console(force_terminal=False, color_system=None, highlight=False, width=120),
    )


@pytest.fixture
def context() -> dict:
    """Return a scenario context with services that work by default."""
    return {
        "wikipedia": FakeWikipediaSource(),
        "enricher": FakeContentEnricher(),
        "translator": FakeTranslator(),
        "summarizer": create_autospec(ContentSummarizer, instance=True),
    }


@given("the translator works")
def working_translator(context) -> None:
    """Translation returns its fixed tagged text (already the default)."""
    assert isinstance(context["translator"], FakeTranslator)


@given("the translator is slow")
def slow_translator(context) -> None:
    """Translation always times out."""
    context["translator"] = FakeTranslator(failure=ProviderTimeoutError("slow"))


@given("the translator fails")
def failing_translator(context) -> None:
    """Translation always fails with a provider error."""
    context["translator"] = FakeTranslator(
        failure=WikiEnrichmentError("provider unavailable")
    )


@when(parsers.parse('I research "{topic}" responding "{answers}"'))
def research_answering(context, topic: str, answers: str) -> None:
    """Give the topic and language as options and type these answers, in order."""
    user_input = "".join(f"{answer.strip()}\n" for answer in answers.split(","))
    orchestrator = WikiEnrichmentOrchestrator(
        context["wikipedia"],
        context["enricher"],
        context["translator"],
        FakeDocumentExporter(),
        context["summarizer"],
    )
    with patch("cli.build_orchestrator", return_value=orchestrator):
        context["result"] = runner.invoke(
            cli.app, ["--tema", topic, "--idioma", "inglés"], input=user_input
        )


@then(parsers.parse('I see the message "{message}"'))
def message_is_shown(context, message: str) -> None:
    """The user reads the expected message on screen."""
    assert message in context["result"].output


@then("the application finishes normally")
def normal_exit(context) -> None:
    """The app keeps going until the goodbye message."""
    result = context["result"]
    assert result.exit_code == 0, result.output
    assert "Mi trabajo aquí ha terminado" in result.output


@then("the application ends in a controlled way")
def controlled_exit(context) -> None:
    """The app stops on its own with exit code 1 instead of crashing."""
    result = context["result"]
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
