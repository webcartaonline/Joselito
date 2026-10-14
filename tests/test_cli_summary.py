"""Tests for the brief summary flow of the command-line interface."""

from unittest.mock import create_autospec, patch

import pytest
from rich.console import Console
from typer.testing import CliRunner

import cli
from wiki_enrichment.application.use_cases import WikiEnrichmentOrchestrator
from wiki_enrichment.domain.exceptions import (
    EnrichmentError,
    ProviderTimeoutError,
    SummarizationError,
)
from wiki_enrichment.domain.models import ArticleContent, BriefSummary, EnrichedContent

ARTICLE = ArticleContent("Python", ["A programming language."])
CONTENT = EnrichedContent(original_article=ARTICLE, ai_summary="Enriched text.")
SUMMARY = BriefSummary(title="Python", text="Brief.", translated_text="Breve.")
OPTIONS = ["--tema", "Python", "--idioma", "inglés"]

runner = CliRunner()


@pytest.fixture(autouse=True)
def fast_plain_console(monkeypatch):
    monkeypatch.setattr(cli, "PENDING_STEP_SECONDS", 0)
    monkeypatch.setattr(
        cli,
        "console",
        Console(force_terminal=False, color_system=None, highlight=False, width=120),
    )


@pytest.fixture(autouse=True)
def no_real_ai_token(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)


@pytest.fixture
def orchestrator():
    fake = create_autospec(WikiEnrichmentOrchestrator, instance=True)
    fake.fetch_article.return_value = ARTICLE
    fake.enrich_article.return_value = CONTENT
    fake.summarize.return_value = SUMMARY
    with patch("cli.build_orchestrator", return_value=fake):
        yield fake


def answer_with(monkeypatch, *replies) -> None:
    """Make ask_option return the given answers, in order."""
    remaining = iter(replies)
    monkeypatch.setattr(cli, "ask_option", lambda question, options: next(remaining))


def make_flow() -> tuple[cli.BriefSummaryFlow, object]:
    fake = create_autospec(WikiEnrichmentOrchestrator, instance=True)
    fake.summarize.return_value = SUMMARY
    return cli.BriefSummaryFlow(fake), fake


def test_request_returns_none_when_the_user_declines(monkeypatch) -> None:
    answer_with(monkeypatch, cli.NO)
    flow, fake = make_flow()

    assert flow.request(CONTENT, "inglés") is None
    fake.summarize.assert_not_called()


def test_request_generates_and_shows_the_summary(monkeypatch, capsys) -> None:
    answer_with(monkeypatch, cli.YES)
    flow, fake = make_flow()

    result = flow.request(CONTENT, "inglés")

    assert result == SUMMARY
    fake.summarize.assert_called_once_with(CONTENT, "inglés")
    assert "Brief." in capsys.readouterr().out


@pytest.mark.parametrize(
    "error", [SummarizationError("no token"), ProviderTimeoutError("slow")]
)
def test_request_shows_a_message_when_the_summary_fails(monkeypatch, capsys, error) -> None:
    answer_with(monkeypatch, cli.YES)
    flow, fake = make_flow()
    fake.summarize.side_effect = error

    assert flow.request(CONTENT, "inglés") is None
    assert "No he podido generar el resumen breve" in capsys.readouterr().out


def test_ask_format_returns_the_chosen_format(monkeypatch) -> None:
    answer_with(monkeypatch, "T")

    assert cli.BriefSummaryFlow.ask_format() == "TXT"


@pytest.mark.parametrize(
    ("path", "summary_format", "expected"),
    [
        ("output/apuntes.pdf", "TXT", "output/apuntes_summary.txt"),
        ("output/notas.pdf.txt", "PDF", "output/notas.pdf_summary.pdf"),
    ],
)
def test_summary_path_is_next_to_the_enriched_file(path, summary_format, expected) -> None:
    assert cli.summary_path(path, summary_format) == expected


def test_export_research_exports_the_summary_in_its_own_format(monkeypatch) -> None:
    answer_with(monkeypatch, cli.YES, "P", "T")
    monkeypatch.setattr(cli, "prompt_user", lambda question: "apuntes")
    fake = create_autospec(WikiEnrichmentOrchestrator, instance=True)

    result = cli.export_research(fake, CONTENT, SUMMARY)

    assert result == ("PDF", "output/apuntes.pdf")
    fake.export_document.assert_called_once_with(CONTENT, "PDF", "output/apuntes.pdf")
    fake.export_summary.assert_called_once_with(SUMMARY, "TXT", "output/apuntes_summary.txt")


def test_export_research_without_summary_exports_only_the_text(monkeypatch) -> None:
    answer_with(monkeypatch, cli.YES, "T")
    monkeypatch.setattr(cli, "prompt_user", lambda question: "apuntes")
    fake = create_autospec(WikiEnrichmentOrchestrator, instance=True)

    result = cli.export_research(fake, CONTENT)

    assert result == ("TXT", "output/apuntes.txt")
    fake.export_summary.assert_not_called()


def test_export_research_saves_nothing_when_the_user_declines(monkeypatch) -> None:
    answer_with(monkeypatch, cli.NO)
    fake = create_autospec(WikiEnrichmentOrchestrator, instance=True)

    result = cli.export_research(fake, CONTENT, SUMMARY)

    assert result == (cli.NOT_EXPORTED, cli.NO_FILE)
    fake.export_document.assert_not_called()
    fake.export_summary.assert_not_called()


def test_full_flow_exports_the_text_and_the_summary(orchestrator) -> None:
    result = runner.invoke(cli.app, OPTIONS, input="Y\nY\nP\napuntes\nT\n")

    assert result.exit_code == 0, result.output
    orchestrator.summarize.assert_called_once_with(CONTENT, "inglés")
    orchestrator.export_document.assert_called_once_with(CONTENT, "PDF", "output/apuntes.pdf")
    orchestrator.export_summary.assert_called_once_with(SUMMARY, "TXT", "output/apuntes_summary.txt")


def test_full_flow_without_summary_skips_it(orchestrator) -> None:
    result = runner.invoke(cli.app, OPTIONS, input="N\nN\n")

    assert result.exit_code == 0, result.output
    orchestrator.summarize.assert_not_called()
    orchestrator.export_summary.assert_not_called()


def test_full_flow_keeps_going_when_the_summary_fails(orchestrator) -> None:
    orchestrator.summarize.side_effect = SummarizationError("no token")

    result = runner.invoke(cli.app, OPTIONS, input="Y\nN\n")

    assert result.exit_code == 0, result.output
    assert "No he podido generar el resumen breve" in result.output
    orchestrator.export_summary.assert_not_called()


def test_full_flow_does_not_offer_a_summary_without_enriched_text(orchestrator) -> None:
    orchestrator.enrich_article.side_effect = EnrichmentError("no token")

    result = runner.invoke(cli.app, OPTIONS, input="N\n")

    assert result.exit_code == 0, result.output
    assert cli.SUMMARY_QUESTION not in result.output
    orchestrator.summarize.assert_not_called()