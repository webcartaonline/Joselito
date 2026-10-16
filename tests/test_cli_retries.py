"""Tests for retrying when Wikipedia has no connection, is slow or asks to wait."""

import sys
from types import SimpleNamespace
from unittest.mock import create_autospec, patch

import pytest
from rich.console import Console
from typer.testing import CliRunner

import cli
from tests.helpers.fake_time import FakeTime
from application.wiki_enrichment_orchestrator import WikiEnrichmentOrchestrator
from domain.exceptions import (
    ProviderTimeoutError,
    RateLimitError,
    WikiEnrichmentError,
)
from domain.models import ArticleContent, EnrichedContent, SearchResult

ARTICLE = ArticleContent("Python", ["A programming language."])
ENRICHED = EnrichedContent(original_article=ARTICLE, ai_summary="Texto enriquecido.")
RESULTS = [
    SearchResult("Python", "Un lenguaje."),
    SearchResult("Python (animal)", "Una serpiente."),
    SearchResult("IronPython", "Otra versión."),
]
OPTIONS = ["--tema", "Python", "--idioma", "inglés"]
OFFLINE = WikiEnrichmentError("offline")
SLOW = ProviderTimeoutError("slow")

runner = CliRunner()


def run_cli(user_input: str):
    return runner.invoke(cli.app, OPTIONS, input=user_input)


@pytest.fixture(autouse=True)
def fast_plain_console(monkeypatch):
    monkeypatch.setattr(cli, "PENDING_STEP_SECONDS", 0)
    monkeypatch.setattr(cli.BriefSummaryFlow, "request", lambda self, content, language: None)
    monkeypatch.setattr(
        cli,
        "console",
        Console(force_terminal=False, color_system=None, highlight=False, width=120),
    )


@pytest.fixture
def clock(monkeypatch):
    fake = FakeTime()
    monkeypatch.setattr(cli, "time", fake)
    return fake


@pytest.fixture
def orchestrator():
    fake = create_autospec(WikiEnrichmentOrchestrator, instance=True)
    fake.search_articles.return_value = RESULTS
    fake.fetch_article_by_title.return_value = ARTICLE
    fake.translate_article.return_value = "A programming language."
    fake.enrich_article.return_value = ENRICHED
    with patch("cli.build_orchestrator", return_value=fake):
        yield fake


# ---- No connection -----------------------------------------------------------


def test_search_without_connection_asks_to_retry_and_then_works(orchestrator) -> None:
    orchestrator.search_articles.side_effect = [OFFLINE, RESULTS]

    result = run_cli("Y\nY\nN\n")

    assert result.exit_code == 0, result.output
    assert "No he podido conectar con Wikipedia (intento 1 de 3)" in result.output
    assert cli.RETRY_QUESTION in result.output
    assert orchestrator.search_articles.call_count == 2


def test_third_connection_failure_closes_with_an_explanation(orchestrator) -> None:
    orchestrator.search_articles.side_effect = OFFLINE

    result = run_cli("Y\nY\n")

    assert result.exit_code == 1
    assert "intento 2 de 3" in result.output
    assert "después de 3 intentos" in result.output
    assert orchestrator.search_articles.call_count == 3


def test_not_retrying_closes_the_program(orchestrator) -> None:
    orchestrator.search_articles.side_effect = OFFLINE

    result = run_cli("N\n")

    assert result.exit_code == 1
    assert cli.NO_RETRY_MESSAGE in result.output
    assert orchestrator.search_articles.call_count == 1


def test_download_without_connection_asks_to_retry(orchestrator) -> None:
    orchestrator.fetch_article_by_title.side_effect = [ARTICLE, OFFLINE, ARTICLE]

    result = run_cli("N\n1\nY\nN\n")

    assert result.exit_code == 0, result.output
    assert "intento 1 de 3" in result.output
    assert orchestrator.fetch_article_by_title.call_count == 3


def test_counters_start_again_after_a_success(orchestrator) -> None:
    orchestrator.search_articles.side_effect = [OFFLINE, OFFLINE, RESULTS]
    orchestrator.fetch_article_by_title.side_effect = [ARTICLE, OFFLINE, ARTICLE]

    result = run_cli("Y\nY\nN\n1\nY\nN\n")

    assert result.exit_code == 0, result.output
    assert result.output.count("intento 1 de 3") == 2
    assert "después de 3 intentos" not in result.output


def test_a_failed_prefetch_does_not_count_as_a_failure(orchestrator) -> None:
    orchestrator.search_articles.side_effect = [OFFLINE, OFFLINE, RESULTS]
    orchestrator.fetch_article_by_title.side_effect = [OFFLINE, ARTICLE]

    result = run_cli("Y\nY\nY\nN\n")

    assert result.exit_code == 0, result.output
    assert "después de 3 intentos" not in result.output


# ---- Too many requests (countdown) ----------------------------------------------


def test_too_many_requests_waits_the_seconds_wikipedia_asks(orchestrator, clock) -> None:
    orchestrator.search_articles.side_effect = [RateLimitError("429", retry_after_seconds=5), RESULTS]

    result = run_cli("Y\nY\nN\n")

    assert result.exit_code == 0, result.output
    assert "Wikipedia ha recibido demasiadas peticiones" in result.output
    assert cli.COUNTDOWN_DONE in result.output
    assert 5 <= clock.slept < 6


def test_too_many_requests_waits_60_seconds_if_wikipedia_does_not_say(
    orchestrator, clock
) -> None:
    orchestrator.search_articles.side_effect = [RateLimitError("429"), RESULTS]

    result = run_cli("Y\nY\nN\n")

    assert result.exit_code == 0, result.output
    assert cli.DEFAULT_RETRY_WAIT_SECONDS <= clock.slept < cli.DEFAULT_RETRY_WAIT_SECONDS + 1


def test_keys_pressed_during_the_countdown_only_show_patience(
    orchestrator, clock, monkeypatch
) -> None:
    orchestrator.search_articles.side_effect = [RateLimitError("429", retry_after_seconds=5), RESULTS]
    keys = iter([False, True, True])
    monkeypatch.setattr(cli, "key_was_pressed", lambda: next(keys, False))

    result = run_cli("Y\nY\nN\n")

    assert result.exit_code == 0, result.output
    assert cli.PATIENCE_MESSAGE in result.output
    assert 5 <= clock.slept < 6
    assert orchestrator.search_articles.call_count == 2


# ---- Too slow -------------------------------------------------------------------


def test_slow_search_is_retried_automatically(orchestrator) -> None:
    orchestrator.search_articles.side_effect = [SLOW, RESULTS]

    result = run_cli("Y\nN\n")

    assert result.exit_code == 0, result.output
    assert cli.WIKIPEDIA_RETRYING in result.output
    assert cli.RETRY_QUESTION not in result.output


def test_second_slow_search_asks_to_write_the_topic_again(orchestrator) -> None:
    orchestrator.search_articles.side_effect = [SLOW, SLOW, RESULTS]

    result = run_cli("Python lenguaje\nY\nN\n")

    assert result.exit_code == 0, result.output
    assert "Prueba a escribir el tema de otra manera" in result.output
    calls = [call.args[0] for call in orchestrator.search_articles.call_args_list]
    assert calls == ["Python", "Python", "Python lenguaje"]


def test_third_slow_answer_closes_with_an_explanation(orchestrator) -> None:
    orchestrator.search_articles.side_effect = SLOW

    result = run_cli("Python lenguaje\n")

    assert result.exit_code == 1
    assert "Wikipedia no está respondiendo a tiempo" in result.output


def test_slow_download_from_the_list_sends_back_to_the_list(orchestrator) -> None:
    orchestrator.fetch_article_by_title.side_effect = [ARTICLE, SLOW, SLOW, ARTICLE]

    result = run_cli("N\n1\n2\nN\n")

    assert result.exit_code == 0, result.output
    assert cli.WIKIPEDIA_RETRYING in result.output
    assert "Wikipedia sigue tardando demasiado con 'Python (animal)'. Elige otro resultado." in result.output
    assert result.output.count("Otros resultados") == 2


def test_slow_download_of_the_confirmed_result_asks_to_retry(orchestrator) -> None:
    orchestrator.fetch_article_by_title.side_effect = [OFFLINE, SLOW, SLOW, ARTICLE]

    result = run_cli("Y\nY\nN\n")

    assert result.exit_code == 0, result.output
    assert cli.RETRY_DOWNLOAD_QUESTION in result.output
    assert "Otros resultados" not in result.output


def test_not_retrying_the_slow_download_closes_the_program(orchestrator) -> None:
    orchestrator.fetch_article_by_title.side_effect = [OFFLINE, SLOW, SLOW]

    result = run_cli("Y\nN\n")

    assert result.exit_code == 1
    assert cli.NO_RETRY_MESSAGE in result.output


def test_third_slow_download_closes_with_an_explanation(orchestrator) -> None:
    orchestrator.fetch_article_by_title.side_effect = [OFFLINE, SLOW, SLOW, SLOW]

    result = run_cli("Y\nY\n")

    assert result.exit_code == 1
    assert "Wikipedia no está respondiendo a tiempo" in result.output


# ---- Reading the keyboard ---------------------------------------------------------


class FakeMsvcrt:
    """Windows keyboard with some keys waiting to be read."""

    def __init__(self, keys: str) -> None:
        self.keys = list(keys)

    def kbhit(self) -> bool:
        return bool(self.keys)

    def getwch(self) -> str:
        return self.keys.pop(0)


class FakeStdin:
    """Mac/Linux keyboard with some typed lines waiting to be read."""

    def __init__(self, lines: list[str], tty: bool = True) -> None:
        self.lines = lines
        self.tty = tty

    def isatty(self) -> bool:
        return self.tty

    def readline(self) -> str:
        return self.lines.pop(0) if self.lines else ""


def fake_select(stdin: FakeStdin):
    """Say the keyboard has something to read while there are lines left."""
    return lambda read, write, error, timeout: (read if stdin.lines else [], [], [])


@pytest.mark.parametrize(("keys", "pressed"), [("ab", True), ("", False)])
def test_windows_keys_are_read_and_thrown_away(monkeypatch, keys, pressed) -> None:
    keyboard = FakeMsvcrt(keys)
    monkeypatch.setattr(cli, "IS_WINDOWS", True)
    monkeypatch.setitem(sys.modules, "msvcrt", keyboard)

    assert cli.key_was_pressed() is pressed
    assert keyboard.keys == []


@pytest.mark.parametrize(("lines", "pressed"), [(["y\n"], True), ([], False), ([""], False)])
def test_mac_and_linux_typed_lines_are_read_and_thrown_away(monkeypatch, lines, pressed) -> None:
    stdin = FakeStdin(lines)
    monkeypatch.setattr(cli, "IS_WINDOWS", False)
    monkeypatch.setattr(sys, "stdin", stdin)
    monkeypatch.setattr(cli.select, "select", fake_select(stdin))

    assert cli.key_was_pressed() is pressed
    assert stdin.lines == []


def test_nothing_is_read_when_the_input_is_not_a_keyboard(monkeypatch) -> None:
    monkeypatch.setattr(cli, "IS_WINDOWS", False)
    monkeypatch.setattr(sys, "stdin", FakeStdin(["y\n"], tty=False))

    assert cli.key_was_pressed() is False
    cli.discard_typed_keys()


def test_windows_discards_pending_keys(monkeypatch) -> None:
    keyboard = FakeMsvcrt("abc")
    monkeypatch.setattr(cli, "IS_WINDOWS", True)
    monkeypatch.setitem(sys.modules, "msvcrt", keyboard)

    cli.discard_typed_keys()

    assert keyboard.keys == []


def test_mac_and_linux_discard_the_unfinished_line(monkeypatch) -> None:
    flushed = []
    termios = SimpleNamespace(TCIFLUSH=0, tcflush=lambda stream, queue: flushed.append(queue))
    monkeypatch.setattr(cli, "IS_WINDOWS", False)
    monkeypatch.setattr(sys, "stdin", FakeStdin([]))
    monkeypatch.setitem(sys.modules, "termios", termios)

    cli.discard_typed_keys()

    assert flushed == [0]
