"""BDD step definitions for clear error messages, with simulated failures."""

from unittest.mock import MagicMock, patch

import pytest
import requests
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
from wiki_enrichment.application.use_cases import WikiEnrichmentOrchestrator
from wiki_enrichment.infrastructure.huggingface_enricher import HuggingFaceEnricher
from wiki_enrichment.infrastructure.wikipedia import WikipediaSourceAdapter

REQUESTS_GET = "wiki_enrichment.infrastructure.wikipedia.requests.get"
LANGUAGE = "inglés"
NO_EXPORT = "N\n"
TECHNICAL_WORDS = ["Traceback", "Exception", "Error:", "timed out", "Max retries"]

scenarios("../features/error_messages.feature")

runner = CliRunner()


@pytest.fixture(autouse=True)
def plain_console(monkeypatch):
    """Print without colors so the messages can be read in the output."""
    monkeypatch.setattr(cli, "PENDING_STEP_SECONDS", 0)
    monkeypatch.setattr(
        cli,
        "console",
        Console(force_terminal=False, color_system=None, highlight=False, width=120),
    )


@pytest.fixture
def context():
    """Return a scenario context with services that work by default."""
    return {
        "wikipedia": FakeWikipediaSource(),
        "enricher": FakeContentEnricher(),
        "user_input": NO_EXPORT,
    }


@given("there is no internet connection")
def no_internet(context) -> None:
    """Use the real Wikipedia adapter, but make every request fail."""
    context["wikipedia"] = WikipediaSourceAdapter(language=cli.WIKIPEDIA_LANGUAGE)
    context["http_failure"] = requests.ConnectionError("Max retries exceeded")


@given("Wikipedia takes too long to respond")
def slow_wikipedia(context) -> None:
    """Use the real Wikipedia adapter, but make every request time out."""
    context["wikipedia"] = WikipediaSourceAdapter(language=cli.WIKIPEDIA_LANGUAGE)
    context["http_failure"] = requests.Timeout("Read timed out")


@given("the AI takes too long to respond")
def slow_ai(context) -> None:
    """Use the real Hugging Face adapter with a client that times out."""
    client = MagicMock()
    client.chat_completion.side_effect = TimeoutError("timed out")
    context["enricher"] = HuggingFaceEnricher(model="test/model", client=client)


@when(parsers.parse('I research "{topic}"'))
def research(context, topic: str) -> None:
    """Run the whole app from the terminal with the simulated services."""
    orchestrator = WikiEnrichmentOrchestrator(
        context["wikipedia"],
        context["enricher"],
        FakeTranslator(),
        FakeDocumentExporter(),
    )
    with patch("cli.build_orchestrator", return_value=orchestrator), patch(
        REQUESTS_GET, side_effect=context.get("http_failure")
    ):
        context["result"] = runner.invoke(
            cli.app, ["--tema", topic, "--idioma", LANGUAGE], input=context["user_input"]
        )


@then(parsers.parse('I see the message "{message}"'))
def message_is_shown(context, message: str) -> None:
    """The user reads a clear message in Spanish."""
    assert message in context["result"].output


@then("I do not see any technical error")
def no_technical_error(context) -> None:
    """No traceback or technical text reaches the screen."""
    output = context["result"].output
    assert not [word for word in TECHNICAL_WORDS if word in output]


@then("the application ends in a controlled way")
def controlled_exit(context) -> None:
    """The app stops on its own with exit code 1 instead of crashing."""
    result = context["result"]
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)


@then("the application finishes normally")
def normal_exit(context) -> None:
    """The app keeps going until the goodbye message."""
    result = context["result"]
    assert result.exit_code == 0, result.output
    assert "Mi trabajo aquí ha terminado" in result.output
