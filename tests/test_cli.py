"""Tests for the interactive command-line interface."""

import re
from unittest.mock import MagicMock, create_autospec, patch

import pytest
import requests
from rich.console import Console
from typer.testing import CliRunner

import cli
from wiki_enrichment.application.use_cases import WikiEnrichmentOrchestrator
from wiki_enrichment.domain.exceptions import (
    ProviderTimeoutError,
    ResourceNotFoundError,
    WikiEnrichmentError,
)
from wiki_enrichment.domain.models import ArticleContent

ARTICLE = ArticleContent("Python", ["A programming language."])
GET = "wiki_enrichment.infrastructure.wikipedia.requests.get"
OPTIONS = ["--tema", "Python", "--idioma", "inglés"]
EMPTY_TEXT_ERROR = "No has escrito nada. Inténtalo de nuevo."
NETWORK_ERROR = "No he podido conectar con Wikipedia"
ANSI_CODES = re.compile(r"\x1b\[[0-9;]*m")

runner = CliRunner()


def run_cli(args: list[str] | None = None, user_input: str = ""):
    return runner.invoke(cli.app, args or [], input=user_input)


def make_response(json_data=None, text=""):
    response = MagicMock()
    response.json.return_value = json_data
    response.text = text
    response.status_code = 200
    response.raise_for_status.return_value = None
    return response


@pytest.fixture(autouse=True)
def fast_plain_console(monkeypatch):
    monkeypatch.setattr(cli, "PENDING_STEP_SECONDS", 0)
    monkeypatch.setattr(
        cli,
        "console",
        Console(force_terminal=False, color_system=None, highlight=False, width=120),
    )


@pytest.fixture
def orchestrator():
    fake = create_autospec(WikiEnrichmentOrchestrator, instance=True)
    fake.fetch_article.return_value = ARTICLE
    with patch("cli.build_orchestrator", return_value=fake):
        yield fake


@pytest.fixture
def summary():
    with patch("cli.show_summary") as mock_summary:
        yield mock_summary


def test_help_lists_the_available_options() -> None:
    result = run_cli(["--help"])
    help_text = ANSI_CODES.sub("", result.output)

    assert result.exit_code == 0
    assert "--tema" in help_text
    assert "--idioma" in help_text


def test_unknown_option_is_rejected_with_a_usage_error(orchestrator) -> None:
    result = run_cli(["--color", "rojo"])

    assert result.exit_code == 2
    orchestrator.fetch_article.assert_not_called()


def test_options_skip_the_topic_and_language_questions(orchestrator, summary) -> None:
    result = run_cli(OPTIONS, "N\n")

    assert result.exit_code == 0, result.output
    assert cli.TOPIC_QUESTION not in result.output
    assert cli.LANGUAGE_QUESTION not in result.output
    orchestrator.fetch_article.assert_called_once_with("Python")
    summary.assert_called_once_with("Python", "inglés", cli.NOT_EXPORTED)


def test_missing_options_are_asked_interactively(orchestrator, summary) -> None:
    result = run_cli(user_input="Python\ninglés\nN\n")

    assert result.exit_code == 0, result.output
    assert cli.TOPIC_QUESTION in result.output
    assert cli.LANGUAGE_QUESTION in result.output
    orchestrator.fetch_article.assert_called_once_with("Python")
    summary.assert_called_once_with("Python", "inglés", cli.NOT_EXPORTED)


def test_successful_run_shows_article_summary_and_goodbye(orchestrator) -> None:
    result = run_cli(OPTIONS, "N\n")

    assert result.exit_code == 0, result.output
    assert "A programming language." in result.output
    assert "Resumen" in result.output
    assert "Mi trabajo aquí ha terminado" in result.output


def test_empty_topic_is_asked_again(orchestrator, summary) -> None:
    result = run_cli(["--idioma", "inglés"], "\n   \nPython\nN\n")

    assert result.exit_code == 0, result.output
    assert result.output.count(EMPTY_TEXT_ERROR) == 2
    orchestrator.fetch_article.assert_called_once_with("Python")


def test_empty_language_is_asked_again(orchestrator, summary) -> None:
    result = run_cli(["--tema", "Python"], "\ninglés\nN\n")

    assert result.exit_code == 0, result.output
    assert EMPTY_TEXT_ERROR in result.output
    summary.assert_called_once_with("Python", "inglés", cli.NOT_EXPORTED)


def test_empty_or_invalid_export_answers_are_asked_again(orchestrator, summary) -> None:
    result = run_cli(OPTIONS, "\nX\nN\n")

    assert result.exit_code == 0, result.output
    assert "No has escrito nada. Escribe Y o N." in result.output
    assert "'X' no es una opción válida. Escribe Y o N." in result.output
    summary.assert_called_once_with("Python", "inglés", cli.NOT_EXPORTED)


@pytest.mark.parametrize(("answer", "export_format"), [("P", "PDF"), ("t", "TXT")])
def test_chosen_export_format_reaches_the_summary(
    orchestrator, summary, answer, export_format
) -> None:
    result = run_cli(OPTIONS, f"Y\n{answer}\n")

    assert result.exit_code == 0, result.output
    summary.assert_called_once_with("Python", "inglés", export_format)


def test_unknown_topic_asks_for_a_new_one(orchestrator, summary) -> None:
    orchestrator.fetch_article.side_effect = [ResourceNotFoundError("missing"), ARTICLE]

    result = run_cli(["--tema", "zzzxxyy", "--idioma", "inglés"], "Python\nN\n")

    assert result.exit_code == 0, result.output
    assert "No he encontrado nada sobre 'zzzxxyy' en Wikipedia" in result.output
    calls = [call.args for call in orchestrator.fetch_article.call_args_list]
    assert calls == [("zzzxxyy",), ("Python",)]
    summary.assert_called_once_with("Python", "inglés", cli.NOT_EXPORTED)


@pytest.mark.parametrize(
    "error", [WikiEnrichmentError("offline"), ProviderTimeoutError("slow")]
)
def test_provider_errors_exit_with_code_1(orchestrator, summary, error) -> None:
    orchestrator.fetch_article.side_effect = error

    result = run_cli(OPTIONS)

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert NETWORK_ERROR in result.output
    summary.assert_not_called()


def test_network_failure_with_real_adapters_exits_with_code_1() -> None:
    with patch(GET, side_effect=requests.ConnectionError("no internet")):
        result = run_cli(OPTIONS)

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert NETWORK_ERROR in result.output


def test_full_flow_with_real_adapters_searches_spanish_wikipedia(summary) -> None:
    responses = [
        make_response(json_data={"query": {"search": [{"title": "Python"}]}}),
        make_response(text='<div id="mw-content-text"><p>Un lenguaje.</p></div>'),
    ]

    with patch(GET, side_effect=responses) as mock_get:
        result = run_cli(OPTIONS, "N\n")

    assert result.exit_code == 0, result.output
    assert "Un lenguaje." in result.output
    assert mock_get.call_args_list[0].args[0].startswith("https://es.wikipedia.org")
    summary.assert_called_once_with("Python", "inglés", cli.NOT_EXPORTED)
