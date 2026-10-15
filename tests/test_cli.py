"""Tests for the interactive command-line interface."""

import logging
import re
from unittest.mock import MagicMock, create_autospec, patch

import pytest
import requests
from rich.console import Console
from typer.testing import CliRunner

import cli
from tests.helpers.document_readers import read_document
from tests.helpers.fake_adapters import (
    FakeContentEnricher,
    FakeTranslator,
    FakeWikipediaSource,
)
from wiki_enrichment.application.use_cases import WikiEnrichmentOrchestrator
from wiki_enrichment.domain.exceptions import (
    EnrichmentError,
    ExportError,
    ProviderTimeoutError,
    ResourceNotFoundError,
    WikiEnrichmentError,
)
from wiki_enrichment.domain.models import ArticleContent, EnrichedContent, SearchResult
from wiki_enrichment.domain.ports import ContentSummarizer
from wiki_enrichment.infrastructure.exporters import EMPTY_SECTION_TEXT, DocumentExporterAdapter
from wiki_enrichment.infrastructure.logging_config import LOGGER_NAME

ARTICLE = ArticleContent("Python", ["A programming language."])
RESULTS = [SearchResult("Python", "Un lenguaje de programación.")]
TREE_RESULTS = [
    SearchResult("Árbol", "Una planta de tallo leñoso."),
    SearchResult("Árboles del Paraíso", "Un árbol del Edén."),
    SearchResult("Dos Árboles de Valinor", "Árboles de Tolkien."),
    SearchResult("Árbol genealógico", "Un esquema familiar."),
    SearchResult("Árbol de decisión", ""),
    SearchResult("Árbol (informática)", "Un tipo de datos."),
]
TREE = ArticleContent("Árbol", ["Una planta."])
SEARCH_PAYLOAD = {
    "query": {"pages": [{"title": "Python", "index": 1, "extract": "Un lenguaje."}]}
}
AI_TEXT = "Python es un lenguaje muy usado para aprender a programar."
TRANSLATED = "Un lenguaje de programación."
ENRICHED = EnrichedContent(original_article=ARTICLE, ai_summary=AI_TEXT)
CONTENT = EnrichedContent(
    original_article=ARTICLE,
    ai_summary=AI_TEXT,
    translated_summary=TRANSLATED,
)
GET = "wiki_enrichment.infrastructure.wikipedia.requests.get"
TRANSLATION_POST = "wiki_enrichment.infrastructure.translation.requests.post"
OPTIONS = ["--tema", "Python", "--idioma", "inglés"]
EMPTY_TEXT_ERROR = "No has escrito nada. Inténtalo de nuevo."
NETWORK_ERROR = "No he podido conectar con Wikipedia"
WIKIPEDIA_SLOW = "Wikipedia está tardando demasiado"
AI_SLOW = "La IA está tardando demasiado en responder"
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


@pytest.fixture(autouse=True)
def no_real_ai_token(monkeypatch):
    """Never call the real AI from tests, even if a .env file has a key."""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

@pytest.fixture(autouse=True)
def skip_summary_question(monkeypatch):
    """The summary question is tested in test_cli_summary.py, so these tests skip it."""
    monkeypatch.setattr(cli.BriefSummaryFlow, "request", lambda self, content, language: None)

@pytest.fixture(autouse=True)
def isolated_logs(monkeypatch, tmp_path):
    """Send application logs to a temporary folder and clean them up."""
    logger = logging.getLogger(LOGGER_NAME)
    monkeypatch.chdir(tmp_path)
    yield
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


def read_log(workspace) -> str:
    """Return the contents of the run's log file."""
    [log_file] = (workspace / "logs").glob("app_*.log")
    return log_file.read_text(encoding="utf-8")


@pytest.fixture
def orchestrator():
    fake = create_autospec(WikiEnrichmentOrchestrator, instance=True)
    fake.search_articles.return_value = RESULTS
    fake.fetch_article_by_title.return_value = ARTICLE
    fake.enrich_article.return_value = ENRICHED
    fake.translate_article.return_value = TRANSLATED
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
    orchestrator.search_articles.assert_not_called()


def test_options_skip_the_topic_and_language_questions(orchestrator, summary) -> None:
    result = run_cli(OPTIONS, "Y\nN\n")

    assert result.exit_code == 0, result.output
    assert cli.TOPIC_QUESTION not in result.output
    assert cli.LANGUAGE_QUESTION not in result.output
    orchestrator.search_articles.assert_called_once_with("Python")
    orchestrator.fetch_article_by_title.assert_called_once_with("Python")
    orchestrator.translate_article.assert_called_once_with(ARTICLE, "inglés")
    summary.assert_called_once_with("Python", "inglés", cli.NOT_EXPORTED, cli.NO_FILE)


def test_missing_options_are_asked_interactively(orchestrator, summary) -> None:
    result = run_cli(user_input="Python\ninglés\nY\nN\n")

    assert result.exit_code == 0, result.output
    assert cli.TOPIC_QUESTION in result.output
    assert cli.LANGUAGE_QUESTION in result.output
    orchestrator.search_articles.assert_called_once_with("Python")
    summary.assert_called_once_with("Python", "inglés", cli.NOT_EXPORTED, cli.NO_FILE)


def test_first_result_is_shown_with_its_summary_and_confirmed(orchestrator, summary) -> None:
    result = run_cli(OPTIONS, "Y\nN\n")

    assert result.exit_code == 0, result.output
    assert "Primer resultado: Python" in result.output
    assert "Un lenguaje de programación." in result.output
    assert cli.CONFIRM_QUESTION in result.output


def test_confirmed_first_result_is_not_downloaded_twice(orchestrator, summary) -> None:
    result = run_cli(OPTIONS, "Y\nN\n")

    assert result.exit_code == 0, result.output
    orchestrator.fetch_article_by_title.assert_called_once_with("Python")


def test_nothing_is_enriched_before_the_user_confirms(orchestrator, summary) -> None:
    orchestrator.search_articles.return_value = TREE_RESULTS

    result = run_cli(OPTIONS, "N\n")

    assert result.exit_code == 1
    orchestrator.enrich_article.assert_not_called()


def test_result_without_summary_says_so(orchestrator, summary) -> None:
    orchestrator.search_articles.return_value = [SearchResult("Python")]

    result = run_cli(OPTIONS, "Y\nN\n")

    assert result.exit_code == 0, result.output
    assert "Primer resultado: Python" in result.output
    assert cli.NO_DESCRIPTION in result.output


def test_invalid_confirmation_is_asked_again(orchestrator, summary) -> None:
    result = run_cli(OPTIONS, "\nX\nY\nN\n")

    assert result.exit_code == 0, result.output
    assert "No has escrito nada. Escribe Y o N." in result.output
    assert "'X' no es una opción válida. Escribe Y o N." in result.output


def test_rejected_result_shows_the_other_results_numbered(orchestrator, summary) -> None:
    orchestrator.search_articles.return_value = TREE_RESULTS
    orchestrator.fetch_article_by_title.side_effect = [TREE, ARTICLE]

    result = run_cli(OPTIONS, "N\n3\nN\n")

    assert result.exit_code == 0, result.output
    assert "Otros resultados" in result.output
    for number, tree in enumerate(TREE_RESULTS[1:], start=1):
        assert re.search(rf"{number}\. {re.escape(tree.title)}", result.output)
    assert re.search(rf"6\. {cli.RETYPE_OPTION}", result.output)
    assert "Un árbol del Edén." in result.output
    assert cli.NO_DESCRIPTION in result.output
    titles = [call.args[0] for call in orchestrator.fetch_article_by_title.call_args_list]
    assert titles == ["Árbol", "Árbol genealógico"]


def test_invalid_number_is_asked_again(orchestrator, summary) -> None:
    orchestrator.search_articles.return_value = TREE_RESULTS

    result = run_cli(OPTIONS, "N\n7\ndos\n\n1\nN\n")

    assert result.exit_code == 0, result.output
    assert "'7' no es una opción válida." in result.output
    assert "'DOS' no es una opción válida." in result.output
    assert "No has escrito nada." in result.output
    orchestrator.fetch_article_by_title.assert_called_with("Árboles del Paraíso")


def test_retype_option_asks_for_the_topic_again(orchestrator, summary) -> None:
    orchestrator.search_articles.side_effect = [TREE_RESULTS, RESULTS]

    result = run_cli(["--tema", "Alboles", "--idioma", "inglés"], "N\n6\nPython\nY\nN\n")

    assert result.exit_code == 0, result.output
    assert cli.TOPIC_QUESTION in result.output
    calls = [call.args for call in orchestrator.search_articles.call_args_list]
    assert calls == [("Alboles",), ("Python",)]


def test_with_a_single_result_only_the_retype_option_is_offered(orchestrator, summary) -> None:
    orchestrator.search_articles.side_effect = [[SearchResult("Molisol", "Un suelo.")], RESULTS]

    result = run_cli(["--tema", "Alboles", "--idioma", "inglés"], "N\n1\nPython\nY\nN\n")

    assert result.exit_code == 0, result.output
    assert re.search(rf"1\. {cli.RETYPE_OPTION}", result.output)


def test_failed_prefetch_downloads_after_the_yes(orchestrator, summary) -> None:
    orchestrator.fetch_article_by_title.side_effect = [WikiEnrichmentError("offline"), ARTICLE]

    result = run_cli(OPTIONS, "Y\nN\n")

    assert result.exit_code == 0, result.output
    assert orchestrator.fetch_article_by_title.call_count == 2
    assert "A programming language." in result.output


def test_article_that_cannot_be_opened_sends_back_to_the_list(orchestrator, summary) -> None:
    orchestrator.search_articles.return_value = TREE_RESULTS
    orchestrator.fetch_article_by_title.side_effect = [
        TREE, ResourceNotFoundError("missing"), ARTICLE,
    ]

    result = run_cli(OPTIONS, "N\n2\n4\nN\n")

    assert result.exit_code == 0, result.output
    assert "No he podido abrir el artículo 'Dos Árboles de Valinor'" in result.output
    assert result.output.count("Otros resultados") == 2


def test_confirmed_article_that_cannot_be_opened_offers_the_list(orchestrator, summary) -> None:
    orchestrator.search_articles.return_value = TREE_RESULTS
    orchestrator.fetch_article_by_title.side_effect = [
        WikiEnrichmentError("offline"), ResourceNotFoundError("missing"), ARTICLE,
    ]

    result = run_cli(OPTIONS, "Y\n1\nN\n")

    assert result.exit_code == 0, result.output
    assert "Otros resultados" in result.output


def test_successful_run_shows_article_summary_and_goodbye(orchestrator) -> None:
    result = run_cli(OPTIONS, "Y\nN\n")

    assert result.exit_code == 0, result.output
    assert "A programming language." in result.output
    assert TRANSLATED in result.output
    assert "Resumen" in result.output
    assert "Mi trabajo aquí ha terminado" in result.output


def test_translator_timeout_is_reported_and_exits(orchestrator, summary) -> None:
    orchestrator.translate_article.side_effect = ProviderTimeoutError("slow")

    result = run_cli(OPTIONS, "Y\nN\n")

    assert result.exit_code == 1
    assert "Google Translate ha tardado demasiado" in result.output
    summary.assert_not_called()


def test_translation_failure_is_reported_and_exits(orchestrator, summary) -> None:
    orchestrator.translate_article.side_effect = WikiEnrichmentError("provider unavailable")

    result = run_cli(OPTIONS, "Y\nN\n")

    assert result.exit_code == 1
    assert "No he podido traducir el contenido con Google Translate" in result.output
    assert "provider unavailable" in result.output
    summary.assert_not_called()


def test_empty_topic_is_asked_again(orchestrator, summary) -> None:
    result = run_cli(["--idioma", "inglés"], "\n   \nPython\nY\nN\n")

    assert result.exit_code == 0, result.output
    assert result.output.count(EMPTY_TEXT_ERROR) == 2
    orchestrator.search_articles.assert_called_once_with("Python")


def test_empty_language_is_asked_again(orchestrator, summary) -> None:
    result = run_cli(["--tema", "Python"], "\ninglés\nY\nN\n")

    assert result.exit_code == 0, result.output
    assert EMPTY_TEXT_ERROR in result.output
    summary.assert_called_once_with("Python", "inglés", cli.NOT_EXPORTED, cli.NO_FILE)


def test_too_long_topic_is_asked_again(orchestrator, summary) -> None:
    long_topic = "x" * (cli.MAX_TOPIC_LENGTH + 1)

    result = run_cli(["--tema", long_topic, "--idioma", "inglés"], "Python\nY\nN\n")

    assert result.exit_code == 0, result.output
    assert "El tema es demasiado largo" in result.output
    orchestrator.search_articles.assert_called_once_with("Python")


def test_invalid_language_is_asked_again(orchestrator, summary) -> None:
    result = run_cli(["--tema", "Python"], "123\ninglés\nY\nN\n")

    assert result.exit_code == 0, result.output
    assert "'123' no es un idioma válido" in result.output
    summary.assert_called_once_with("Python", "inglés", cli.NOT_EXPORTED, cli.NO_FILE)


@pytest.mark.parametrize("topic", ["", "x" * 301])
def test_topic_error_rejects_invalid_topics(topic) -> None:
    assert cli.topic_error(topic) is not None


@pytest.mark.parametrize("topic", ["Python", "Agujero negro", "C++", "x" * 300])
def test_topic_error_accepts_valid_topics(topic) -> None:
    assert cli.topic_error(topic) is None


@pytest.mark.parametrize("language", ["", "123", "inglés!", "en-US"])
def test_language_error_rejects_invalid_languages(language) -> None:
    assert cli.language_error(language) is not None


@pytest.mark.parametrize("language", ["inglés", "francés", "chino mandarín", "EN"])
def test_language_error_accepts_valid_languages(language) -> None:
    assert cli.language_error(language) is None
@pytest.mark.parametrize("negative", ["N", "n", "NO", "No", "no", "  no  "])
def test_export_declined_with_common_negative_answers(
    orchestrator, summary, negative
) -> None:
    result = run_cli(OPTIONS, f"Y\n{negative}\n")

    assert result.exit_code == 0, result.output
    summary.assert_called_once_with("Python", "inglés", cli.NOT_EXPORTED, cli.NO_FILE)
    orchestrator.export_document.assert_not_called()


@pytest.mark.parametrize("affirmative", ["Y", "yes", "YES", "Sí", "si", "  Si  "])
def test_export_accepted_with_common_affirmative_answers(
    orchestrator, summary, affirmative
) -> None:
    result = run_cli(OPTIONS, f"Y\n{affirmative}\nT\napuntes\n")

    assert result.exit_code == 0, result.output
    orchestrator.export_document.assert_called_once_with(CONTENT, "TXT", "output/apuntes.txt")


def test_empty_or_invalid_export_answers_are_asked_again(orchestrator, summary) -> None:
    result = run_cli(OPTIONS, "Y\n\nX\nN\n")

    assert result.exit_code == 0, result.output
    assert "No has escrito nada. Escribe Y o N." in result.output
    assert "'X' no es una opción válida. Escribe Y o N." in result.output
    assert result.output.count(cli.EXPORT_QUESTION) >= 3
    summary.assert_called_once_with("Python", "inglés", cli.NOT_EXPORTED, cli.NO_FILE)


def test_invalid_export_answer_then_no_is_not_reused_as_yes(orchestrator, summary) -> None:
    result = run_cli(OPTIONS, "Y\nBielarusia\nn\n")

    assert result.exit_code == 0, result.output
    assert "'BIELARUSIA' no es una opción válida. Escribe Y o N." in result.output
    orchestrator.export_document.assert_not_called()
    summary.assert_called_once_with("Python", "inglés", cli.NOT_EXPORTED, cli.NO_FILE)


@pytest.mark.parametrize(
    ("answers", "export_format", "file_name"),
    [
        ("P\napuntes", "PDF", "output/apuntes.pdf"),
        ("t\nmis apuntes", "TXT", "output/mis apuntes.txt"),
        ("P\nresumen.PDF", "PDF", "output/resumen.pdf"),
        ("T\nnotas.pdf", "TXT", "output/notas.pdf.txt"),
    ],
)
def test_chosen_format_and_file_name_are_exported(
    orchestrator, summary, answers, export_format, file_name
) -> None:
    result = run_cli(OPTIONS, f"Y\nY\n{answers}\n")

    assert result.exit_code == 0, result.output
    assert cli.FILE_NAME_QUESTION in result.output
    orchestrator.export_document.assert_called_once_with(CONTENT, export_format, file_name)
    summary.assert_called_once_with("Python", "inglés", export_format, file_name)


def test_no_export_does_not_ask_for_a_file_name(orchestrator, summary) -> None:
    result = run_cli(OPTIONS, "Y\nN\n")

    assert result.exit_code == 0, result.output
    assert cli.FILE_NAME_QUESTION not in result.output
    orchestrator.export_document.assert_not_called()


def test_export_failure_shows_a_message(orchestrator, summary) -> None:
    orchestrator.export_document.side_effect = ExportError("disk full")

    result = run_cli(OPTIONS, "Y\nY\nT\napuntes\n")

    assert result.exit_code == 0, result.output
    assert "No he podido guardar el archivo." in result.output
    summary.assert_called_once_with("Python", "inglés", cli.NOT_EXPORTED, cli.NO_FILE)


def test_invalid_file_names_are_asked_again(orchestrator, summary) -> None:
    result = run_cli(OPTIONS, "Y\nY\nP\n\nnotas?\ncon\nnotas.\nnotas\n")

    assert result.exit_code == 0, result.output
    assert EMPTY_TEXT_ERROR in result.output
    assert "no puede llevar estos símbolos: ?" in result.output
    assert "'con' es un nombre reservado" in result.output
    assert "no puede terminar en punto" in result.output
    summary.assert_called_once_with("Python", "inglés", "PDF", "output/notas.pdf")


@pytest.mark.parametrize(
    "name", ["", "a/b", "a\\b", "a:b", "a*b", "a?b", 'a"b', "a<b", "a>b", "a|b",
             "fin.", "CON", "nul", "COM1", "lpt9", "x" * 101],
)
def test_file_name_error_rejects_invalid_names(name) -> None:
    assert cli.file_name_error(name) is not None


@pytest.mark.parametrize(
    "name", ["apuntes", "mis apuntes", "Tema_1-final", "versión.2", "x" * 100, "CONSOLA"],
)
def test_file_name_error_accepts_valid_names(name) -> None:
    assert cli.file_name_error(name) is None


def test_unknown_topic_asks_for_a_new_one(orchestrator, summary) -> None:
    orchestrator.search_articles.side_effect = [ResourceNotFoundError("missing"), RESULTS]

    result = run_cli(["--tema", "zzzxxyy", "--idioma", "inglés"], "Python\nY\nN\n")

    assert result.exit_code == 0, result.output
    assert "No he encontrado nada sobre 'zzzxxyy' en Wikipedia" in result.output
    calls = [call.args for call in orchestrator.search_articles.call_args_list]
    assert calls == [("zzzxxyy",), ("Python",)]
    summary.assert_called_once_with("Python", "inglés", cli.NOT_EXPORTED, cli.NO_FILE)


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (WikiEnrichmentError("offline"), NETWORK_ERROR),
        (ProviderTimeoutError("slow"), WIKIPEDIA_SLOW),
    ],
)
def test_provider_errors_exit_with_code_1(orchestrator, summary, error, message) -> None:
    orchestrator.search_articles.side_effect = error

    result = run_cli(OPTIONS)

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert message in result.output
    summary.assert_not_called()


def test_unexpected_error_shows_a_message_instead_of_crashing(orchestrator, summary) -> None:
    orchestrator.search_articles.side_effect = ZeroDivisionError("division by zero")

    result = run_cli(OPTIONS)

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "Ha ocurrido un error inesperado" in result.output
    assert "division by zero" not in result.output
    summary.assert_not_called()


@pytest.mark.parametrize("cancel", [KeyboardInterrupt(), EOFError()])
def test_cancelling_shows_a_message_instead_of_crashing(orchestrator, summary, cancel) -> None:
    orchestrator.search_articles.side_effect = cancel

    result = run_cli(OPTIONS)

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "Has cancelado la investigación" in result.output
    summary.assert_not_called()


def test_closing_the_input_while_asking_shows_a_message(orchestrator, summary) -> None:
    result = run_cli(user_input="")

    assert result.exit_code == 1
    assert "Has cancelado la investigación" in result.output
    orchestrator.search_articles.assert_not_called()


def test_network_failure_with_real_adapters_exits_with_code_1() -> None:
    with patch(GET, side_effect=requests.ConnectionError("no internet")):
        result = run_cli(OPTIONS)

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert NETWORK_ERROR in result.output


def test_slow_wikipedia_with_real_adapters_exits_with_code_1() -> None:
    with patch(GET, side_effect=requests.Timeout("read timed out")):
        result = run_cli(OPTIONS)

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert WIKIPEDIA_SLOW in result.output
    assert "read timed out" not in result.output


def test_full_flow_with_adapters_translates_after_searching_spanish_wikipedia(
    summary, monkeypatch
) -> None:
    responses = [
        make_response(json_data=SEARCH_PAYLOAD),
        make_response(text='<div id="mw-content-text"><p>Un lenguaje.</p></div>'),
    ]
    translation_response = make_response(
        json_data={"data": {"translations": [{"translatedText": "A language."}]}}
    )
    monkeypatch.setenv("GOOGLE_TRANSLATE_API_KEY", "test-key")

    with patch(GET, side_effect=responses) as mock_get:
        with patch(TRANSLATION_POST, return_value=translation_response) as mock_post:
            result = run_cli(OPTIONS, "Y\nN\n")

    assert result.exit_code == 0, result.output
    assert "Un lenguaje." in result.output
    assert "A language." in result.output
    assert mock_get.call_args_list[0].args[0].startswith("https://es.wikipedia.org")
    assert mock_post.call_args.kwargs["json"] == {
        "q": "Un lenguaje.",
        "source": "es",
        "target": "en",
        "format": "text",
    }
    assert mock_post.call_args.kwargs["headers"]["x-goog-api-key"] == "test-key"
    summary.assert_called_once_with("Python", "inglés", cli.NOT_EXPORTED, cli.NO_FILE)


@pytest.mark.parametrize(("answer", "file_name"), [("T", "apuntes.txt"), ("P", "apuntes.pdf")])
def test_full_flow_creates_a_real_file_with_simulated_data(
    tmp_path, monkeypatch, answer, file_name
) -> None:
    """From the questions to the saved file, with fakes instead of real services."""
    orchestrator = WikiEnrichmentOrchestrator(
        FakeWikipediaSource(article=ARTICLE),
        FakeContentEnricher(),
        FakeTranslator(),
        DocumentExporterAdapter(),
        create_autospec(ContentSummarizer, instance=True),
    )
    monkeypatch.setattr(cli, "EXPORT_FOLDER", str(tmp_path))

    with patch("cli.build_orchestrator", return_value=orchestrator):
        result = run_cli(OPTIONS, f"Y\nY\n{answer}\napuntes\n")

    assert result.exit_code == 0, result.output
    text = read_document(tmp_path / file_name)
    assert "Python" in text
    assert "A programming language." in text
    assert "A concise summary." in text
    assert "A programming language. [inglés]" in text
    assert text.count(EMPTY_SECTION_TEXT) == 0


def test_enriched_text_is_shown_and_exported(orchestrator, summary) -> None:
    result = run_cli(OPTIONS, "Y\nY\nT\napuntes\n")

    assert result.exit_code == 0, result.output
    assert "Texto enriquecido con IA" in result.output
    assert AI_TEXT in result.output
    orchestrator.enrich_article.assert_called_once_with(ARTICLE)
    exported_content = orchestrator.export_document.call_args.args[0]
    assert exported_content.ai_summary == AI_TEXT
    assert exported_content.translated_summary == TRANSLATED


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (EnrichmentError("no token"), "No he podido enriquecer el texto con IA"),
        (ProviderTimeoutError("slow"), AI_SLOW),
    ],
)
def test_ai_failure_shows_a_message_and_keeps_going(orchestrator, summary, error, message) -> None:
    orchestrator.enrich_article.side_effect = error

    result = run_cli(OPTIONS, "Y\nY\nT\napuntes\n")

    assert result.exit_code == 0, result.output
    assert message in result.output
    assert "Texto enriquecido con IA" not in result.output
    exported_content = orchestrator.export_document.call_args.args[0]
    assert exported_content.ai_summary == ""
    summary.assert_called_once_with("Python", "inglés", "TXT", "output/apuntes.txt")


def test_real_adapters_without_token_still_export_the_original(tmp_path, monkeypatch, summary) -> None:
    """Without DEEPSEEK_API_KEY the app warns about the AI and still saves the file."""
    responses = [
        make_response(json_data=SEARCH_PAYLOAD),
        make_response(text='<div id="mw-content-text"><p>Un lenguaje.</p></div>'),
    ]
    translation_response = make_response(
        json_data={"data": {"translations": [{"translatedText": "A language."}]}}
    )
    monkeypatch.setenv("GOOGLE_TRANSLATE_API_KEY", "test-key")
    monkeypatch.setattr(cli, "EXPORT_FOLDER", str(tmp_path))

    with patch(GET, side_effect=responses):
        with patch(TRANSLATION_POST, return_value=translation_response):
            result = run_cli(OPTIONS, "Y\nY\nT\napuntes\n")

    assert result.exit_code == 0, result.output
    assert "No he podido enriquecer el texto con IA" in result.output
    assert "Un lenguaje." in read_document(tmp_path / "apuntes.txt")
    assert "A language." in read_document(tmp_path / "apuntes.txt")


RUN_ID_LINE = re.compile(
    r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \| INFO \| [0-9a-f]{8} \|"
)
LOG_FILE_NAME_PATTERN = re.compile(r"^app_[0-9a-f]{8}\.log$")


def test_application_start_and_finish_are_logged(tmp_path, orchestrator) -> None:
    result = run_cli(OPTIONS, "Y\nN\n")

    assert result.exit_code == 0, result.output
    content = read_log(tmp_path)
    assert "Application started" in content
    assert "Application finished" in content


def test_selected_topic_and_language_are_logged(tmp_path, orchestrator) -> None:
    run_cli(OPTIONS, "Y\nN\n")

    content = read_log(tmp_path)
    assert "Topic selected: Python" in content
    assert "Target language selected: inglés" in content


def test_each_log_line_contains_a_run_id(tmp_path, orchestrator) -> None:
    run_cli(OPTIONS, "Y\nN\n")

    assert RUN_ID_LINE.search(read_log(tmp_path))


def test_log_file_is_named_after_the_run(tmp_path, orchestrator) -> None:
    result = run_cli(OPTIONS, "Y\nN\n")

    assert result.exit_code == 0, result.output
    [log_file] = (tmp_path / "logs").glob("app_*.log")
    assert LOG_FILE_NAME_PATTERN.match(log_file.name)
    run_id = log_file.name.removeprefix("app_").removesuffix(".log")
    assert f"| {run_id} |" in log_file.read_text(encoding="utf-8")


def test_unexpected_error_is_logged_as_critical(tmp_path, orchestrator) -> None:
    orchestrator.search_articles.side_effect = RuntimeError("boom")

    result = run_cli(OPTIONS, "N\n")

    assert result.exit_code == 1
    content = read_log(tmp_path)
    assert "| CRITICAL |" in content
    assert "Unexpected error" in content


def test_confirmation_question_and_answer_are_logged(tmp_path, orchestrator) -> None:
    result = run_cli(OPTIONS, "Y\nN\n")

    assert result.exit_code == 0, result.output
    content = read_log(tmp_path)
    assert "Confirming the first result: title=Python" in content
    assert "First result confirmed: title=Python" in content


def test_rejected_result_options_and_new_topic_are_logged(tmp_path, orchestrator) -> None:
    orchestrator.search_articles.side_effect = [TREE_RESULTS, RESULTS]

    result = run_cli(
        ["--tema", "Alboles", "--idioma", "inglés"], "N\n6\nPython\nY\nN\n"
    )

    assert result.exit_code == 0, result.output
    content = read_log(tmp_path)
    assert "First result rejected: title=Árbol" in content
    assert "Showing other results: count=5" in content
    assert "The user wants to write the topic again" in content
    assert "Topic selected: Python" in content


def test_chosen_result_from_the_list_is_logged(tmp_path, orchestrator) -> None:
    orchestrator.search_articles.return_value = TREE_RESULTS
    orchestrator.fetch_article_by_title.side_effect = [TREE, ARTICLE]

    result = run_cli(OPTIONS, "N\n3\nN\n")

    assert result.exit_code == 0, result.output
    assert "Result chosen from the list: title=Árbol genealógico" in read_log(tmp_path)
