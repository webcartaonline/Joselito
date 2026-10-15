"""BDD step definitions for confirming the Wikipedia result, with fake services."""

import re
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
from wiki_enrichment.application.use_cases import WikiEnrichmentOrchestrator
from wiki_enrichment.domain.models import SearchResult
from wiki_enrichment.domain.ports import ContentSummarizer

LANGUAGE = "inglés"
NO_EXPORT = "N\n"
TREE_RESULTS = [
    SearchResult("Árbol", "Una planta de tallo leñoso."),
    SearchResult("Árboles del Paraíso", "Un árbol del Edén."),
    SearchResult("Dos Árboles de Valinor", "Árboles de Tolkien."),
    SearchResult("Árbol genealógico", "Un esquema familiar."),
    SearchResult("Árbol de decisión", "Un modelo de predicción."),
    SearchResult("Árbol (informática)", "Un tipo de datos."),
]

scenarios("../features/search_confirmation.feature")

runner = CliRunner()


@pytest.fixture(autouse=True)
def plain_console(monkeypatch, tmp_path):
    """Print without colors, skip the summary question and save files in a temp folder."""
    monkeypatch.setattr(cli, "PENDING_STEP_SECONDS", 0)
    monkeypatch.setattr(cli, "EXPORT_FOLDER", str(tmp_path))
    monkeypatch.setattr(cli.BriefSummaryFlow, "request", lambda self, content, language: None)
    monkeypatch.setattr(
        cli,
        "console",
        Console(force_terminal=False, color_system=None, highlight=False, width=120),
    )


@pytest.fixture
def context():
    """Return a fresh scenario context with an enricher that records its work."""
    return {"enricher": FakeContentEnricher()}


@given(parsers.parse('Wikipedia finds "{title}" with the summary "{summary}"'))
def results_with_summary(context, title: str, summary: str) -> None:
    """Simulate a search whose first result has a summary."""
    context["wikipedia"] = FakeWikipediaSource(results=[SearchResult(title, summary)])


@given(parsers.parse('Wikipedia finds "{title}" without a summary'))
def results_without_summary(context, title: str) -> None:
    """Simulate a search whose first result has no summary."""
    context["wikipedia"] = FakeWikipediaSource(results=[SearchResult(title)])


@given("Wikipedia finds 6 results about trees")
def tree_results(context) -> None:
    """Simulate a search with the first result plus 5 more."""
    context["wikipedia"] = FakeWikipediaSource(results=TREE_RESULTS)


@when(parsers.parse('I search "{topic}" and answer "{answers}"'))
def search_and_answer(context, topic: str, answers: str) -> None:
    """Run the app and type the answers, separated by spaces."""
    orchestrator = WikiEnrichmentOrchestrator(
        context["wikipedia"],
        context["enricher"],
        FakeTranslator(),
        FakeDocumentExporter(),
        create_autospec(ContentSummarizer, instance=True),
    )
    user_input = "".join(f"{answer}\n" for answer in answers.split())
    with patch("cli.build_orchestrator", return_value=orchestrator):
        context["result"] = runner.invoke(
            cli.app, ["--tema", topic, "--idioma", LANGUAGE], input=user_input + NO_EXPORT
        )


@then(parsers.parse('I see the first result "{title}"'))
def first_result_is_shown(context, title: str) -> None:
    """The first result and the confirmation question are on screen."""
    output = context["result"].output
    assert f"Primer resultado: {title}" in output
    assert cli.CONFIRM_QUESTION in output


@then(parsers.parse('I see the summary "{summary}"'))
def summary_is_shown(context, summary: str) -> None:
    """The summary from Wikipedia, or the note that there is none, is on screen."""
    assert summary in context["result"].output


@then(parsers.parse('the article "{title}" is downloaded only once'))
def downloaded_once(context, title: str) -> None:
    """The chosen article is downloaded a single time and the app finishes."""
    titles = context["wikipedia"].requested_titles
    assert titles.count(title) == 1
    assert titles[-1] == title
    assert context["result"].exit_code == 0, context["result"].output


@then("nothing is enriched")
def nothing_is_enriched(context) -> None:
    """The AI is never called before the user confirms a result."""
    assert context["enricher"].received_articles == []


@then("only the chosen article is enriched")
def only_chosen_is_enriched(context) -> None:
    """The AI works once, after the user chose."""
    assert len(context["enricher"].received_articles) == 1


@then("I see the other 5 results numbered from 1 to 5")
def other_results_are_numbered(context) -> None:
    """Each of the other results appears with its number and summary."""
    output = context["result"].output
    for number, result in enumerate(TREE_RESULTS[1:], start=1):
        assert re.search(rf"{number}\. {re.escape(result.title)}", output)
        assert result.summary in output
    assert cli.CHOOSE_QUESTION in output


@then("I see the option 6 to write the topic again")
def retype_option_is_shown(context) -> None:
    """The last option lets the user write the topic again."""
    assert re.search(rf"6\. {cli.RETYPE_OPTION}", context["result"].output)


@then(parsers.parse('Wikipedia is searched for "{first}" and then for "{second}"'))
def searched_twice(context, first: str, second: str) -> None:
    """The new topic starts a brand-new search."""
    assert context["wikipedia"].requested_topics == [first, second]
