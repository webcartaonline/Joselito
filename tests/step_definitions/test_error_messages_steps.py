"""BDD step definitions for clear error messages, with simulated failures."""

from unittest.mock import MagicMock, patch

import pytest
import requests
from pytest_bdd import given, parsers, scenarios, then, when
from rich.console import Console
from typer.testing import CliRunner

import re
from types import SimpleNamespace

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
TECHNICAL_WORDS = [
    "Traceback", "Exception", "Error:", "timed out", "Max retries", "division by zero",
]
VALID_TOPIC = "Python"
REPEATED_TEXT = re.compile(r"\((?P<count>\d+) (?P<text>\w)\)")

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


def expand(text: str) -> str:
    """Turn "(301 x)" into 301 x letters, so long texts fit in the feature file."""
    match = REPEATED_TEXT.fullmatch(text)
    return match["text"] * int(match["count"]) if match else text


def run_app(context, options: list[str], user_input: str) -> None:
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
        context["result"] = runner.invoke(cli.app, options, input=user_input)


@given("an unexpected error happens while searching")
def unexpected_error(context) -> None:
    """Simulate a bug that nobody expected."""
    context["wikipedia"] = MagicMock()
    context["wikipedia"].fetch_article.side_effect = ZeroDivisionError("division by zero")


@given("the user presses Ctrl+C while searching")
def user_cancels(context) -> None:
    """Simulate the user stopping the app in the middle of the search."""
    context["wikipedia"] = MagicMock()
    context["wikipedia"].fetch_article.side_effect = KeyboardInterrupt()


@given("the AI returns a broken answer")
def broken_ai_answer(context) -> None:
    """Use the real Hugging Face adapter with a client that answers nothing."""
    client = MagicMock()
    client.chat_completion.return_value = SimpleNamespace(choices=[])
    context["enricher"] = HuggingFaceEnricher(model="test/model", client=client)


@when(parsers.parse('I research "{topic}"'))
def research(context, topic: str) -> None:
    """Give the topic and language as options."""
    run_app(context, ["--tema", topic, "--idioma", LANGUAGE], context["user_input"])


@when(parsers.re(r'I type the topic "(?P<topic>.*)" and then "(?P<valid_topic>.+)"'))
def type_topic(context, topic: str, valid_topic: str) -> None:
    """Type a wrong topic, then a valid one when the app asks again."""
    run_app(context, [], f"{expand(topic)}\n{valid_topic}\n{LANGUAGE}\n{NO_EXPORT}")


@when(parsers.re(r'I type the language "(?P<language>.*)" and then "(?P<valid_language>.+)"'))
def type_language(context, language: str, valid_language: str) -> None:
    """Type a wrong language, then a valid one when the app asks again."""
    run_app(context, [], f"{VALID_TOPIC}\n{language}\n{valid_language}\n{NO_EXPORT}")


@then(parsers.parse('I see the message "{message}"'))
def message_is_shown(context, message: str) -> None:
    """The user reads a clear message in Spanish."""
    assert message in context["result"].output


@then(parsers.parse('Wikipedia only receives the topic "{topic}"'))
def only_valid_topic_is_searched(context, topic: str) -> None:
    """Wrong topics never reach Wikipedia."""
    assert context["wikipedia"].requested_topics == [topic]


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
