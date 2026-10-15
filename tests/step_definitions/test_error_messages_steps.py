"""BDD step definitions for clear error messages, with simulated failures."""

from unittest.mock import MagicMock, create_autospec, patch

import pytest
import requests
from pytest_bdd import given, parsers, scenarios, then, when
from rich.console import Console
from typer.testing import CliRunner

import re
from contextlib import nullcontext

import cli
from tests.helpers.fake_time import FakeTime
from tests.helpers.wikipedia_mocks import (
    build_article_html,
    make_article_response,
    make_response,
    make_results_response,
)
from tests.helpers.fake_adapters import (
    FakeContentEnricher,
    FakeDocumentExporter,
    FakeTranslator,
    FakeWikipediaSource,
)
from wiki_enrichment.application.use_cases import WikiEnrichmentOrchestrator
from wiki_enrichment.domain.ports import ContentSummarizer
from wiki_enrichment.infrastructure.deepseek_enricher import DeepSeekEnricher
from wiki_enrichment.infrastructure.wikipedia import WikipediaSourceAdapter

REQUESTS_GET = "wiki_enrichment.infrastructure.wikipedia.requests.get"
DEEPSEEK_POST = "wiki_enrichment.infrastructure.deepseek_enricher.requests.post"
LANGUAGE = "inglés"
CONFIRM = "Y\n"  # Answer to "¿Era esto lo que buscabas?"
NO_EXPORT = "N\n"
TECHNICAL_WORDS = [
    "Traceback", "Exception", "Error:", "timed out", "Max retries", "division by zero",
]
VALID_TOPIC = "Python"
REPEATED_TEXT = re.compile(r"\((?P<count>\d+) (?P<text>\w)\)")

scenarios("../features/error_messages.feature")

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


@pytest.fixture(autouse=True)
def skip_summary_question(monkeypatch):
    """The summary question has its own tests, so these scenarios skip it."""
    monkeypatch.setattr(cli.BriefSummaryFlow, "request", lambda self, content, language: None)


@pytest.fixture
def clock(monkeypatch):
    """Replace the clock so countdowns finish at once."""
    fake = FakeTime()
    monkeypatch.setattr(cli, "time", fake)
    return fake


def working_wikipedia() -> list:
    """Return the answers of a Wikipedia that works: the search and the article."""
    return [
        make_results_response([("Python", "Un lenguaje.")]),
        make_article_response(build_article_html(["Un lenguaje de programación."])),
    ]


@pytest.fixture
def context(clock):
    """Return a scenario context with services that work by default."""
    return {
        "clock": clock,
        "wikipedia": FakeWikipediaSource(),
        "enricher": FakeContentEnricher(),
        "user_input": CONFIRM + NO_EXPORT,
    }


@given("there is no internet connection")
def no_internet(context) -> None:
    """Use the real Wikipedia adapter, but make every request fail."""
    context["wikipedia"] = WikipediaSourceAdapter(language=cli.WIKIPEDIA_LANGUAGE)
    context["http_failure"] = requests.ConnectionError("Max retries exceeded")


@given("the connection fails once and then works")
def connection_comes_back(context) -> None:
    """The first request fails, then Wikipedia answers normally."""
    context["wikipedia"] = WikipediaSourceAdapter(language=cli.WIKIPEDIA_LANGUAGE)
    context["http_failure"] = [requests.ConnectionError("Max retries exceeded")] + working_wikipedia()


@given("Wikipedia is slow once and then works")
def slow_once(context) -> None:
    """The first request times out, then Wikipedia answers normally."""
    context["wikipedia"] = WikipediaSourceAdapter(language=cli.WIKIPEDIA_LANGUAGE)
    context["http_failure"] = [requests.Timeout("Read timed out")] + working_wikipedia()


@given(parsers.parse("Wikipedia asks to wait {seconds:d} seconds and then works"))
def rate_limited(context, seconds: int) -> None:
    """The first answer is 429 (too many requests), then Wikipedia works."""
    too_many = make_response(status_code=429)
    too_many.headers = {"Retry-After": str(seconds)}
    context["wikipedia"] = WikipediaSourceAdapter(language=cli.WIKIPEDIA_LANGUAGE)
    context["http_failure"] = [too_many] + working_wikipedia()


@given("the user presses a key during the countdown")
def impatient_user(monkeypatch) -> None:
    """The user presses a key once while waiting."""
    keys = iter([True])
    monkeypatch.setattr(cli, "key_was_pressed", lambda: next(keys, False))


@given("Wikipedia takes too long to respond")
def slow_wikipedia(context) -> None:
    """Use the real Wikipedia adapter, but make every request time out."""
    context["wikipedia"] = WikipediaSourceAdapter(language=cli.WIKIPEDIA_LANGUAGE)
    context["http_failure"] = requests.Timeout("Read timed out")


@given("the AI takes too long to respond")
def slow_ai(context) -> None:
    """Use the real DeepSeek adapter, but make its request time out."""
    context["enricher"] = DeepSeekEnricher(api_key="test-key")
    context["ai_request"] = patch(DEEPSEEK_POST, side_effect=requests.Timeout("timed out"))


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
        create_autospec(ContentSummarizer, instance=True),
    )
    with patch("cli.build_orchestrator", return_value=orchestrator), patch(
        REQUESTS_GET, side_effect=context.get("http_failure")
    ) as get, context.get("ai_request", nullcontext()):
        context["result"] = runner.invoke(cli.app, options, input=user_input)
    context["requests"] = get.call_count


@given("an unexpected error happens while searching")
def unexpected_error(context) -> None:
    """Simulate a bug that nobody expected."""
    context["wikipedia"] = MagicMock()
    context["wikipedia"].search.side_effect = ZeroDivisionError("division by zero")


@given("the user presses Ctrl+C while searching")
def user_cancels(context) -> None:
    """Simulate the user stopping the app in the middle of the search."""
    context["wikipedia"] = MagicMock()
    context["wikipedia"].search.side_effect = KeyboardInterrupt()


@given("the AI returns a broken answer")
def broken_ai_answer(context) -> None:
    """Use the real DeepSeek adapter, but make it answer without any text."""
    response = MagicMock()
    response.json.return_value = {"choices": []}
    context["enricher"] = DeepSeekEnricher(api_key="test-key")
    context["ai_request"] = patch(DEEPSEEK_POST, return_value=response)


@when(parsers.parse('I research "{topic}"'))
def research(context, topic: str) -> None:
    """Give the topic and language as options."""
    run_app(context, ["--tema", topic, "--idioma", LANGUAGE], context["user_input"])


@when(parsers.parse('I research "{topic}" answering "{answers}"'))
def research_answering(context, topic: str, answers: str) -> None:
    """Give the topic and language as options and type these answers, in order."""
    user_input = "".join(f"{answer.strip()}\n" for answer in answers.split(","))
    run_app(context, ["--tema", topic, "--idioma", LANGUAGE], user_input)


@when(parsers.re(r'I type the topic "(?P<topic>.*)" and then "(?P<valid_topic>.+)"'))
def type_topic(context, topic: str, valid_topic: str) -> None:
    """Type a wrong topic, then a valid one when the app asks again."""
    run_app(context, [], f"{expand(topic)}\n{valid_topic}\n{LANGUAGE}\n{CONFIRM}{NO_EXPORT}")


@when(parsers.re(r'I type the language "(?P<language>.*)" and then "(?P<valid_language>.+)"'))
def type_language(context, language: str, valid_language: str) -> None:
    """Type a wrong language, then a valid one when the app asks again."""
    run_app(context, [], f"{VALID_TOPIC}\n{language}\n{valid_language}\n{CONFIRM}{NO_EXPORT}")


@then(parsers.parse('I see the message "{message}"'))
def message_is_shown(context, message: str) -> None:
    """The user reads a clear message in Spanish."""
    assert message in context["result"].output


@then(parsers.parse('Wikipedia only receives the topic "{topic}"'))
def only_valid_topic_is_searched(context, topic: str) -> None:
    """Wrong topics never reach Wikipedia."""
    assert context["wikipedia"].requested_topics == [topic]


@then(parsers.parse("Wikipedia was asked {times:d} times"))
def wikipedia_was_asked(context, times: int) -> None:
    """The app tried exactly this many times."""
    assert context["requests"] == times


@then(parsers.parse("the countdown lasted {seconds:d} seconds"))
def countdown_lasted(context, seconds: int) -> None:
    """The countdown kept its pace even though the user pressed a key."""
    assert seconds <= context["clock"].slept < seconds + 1


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
