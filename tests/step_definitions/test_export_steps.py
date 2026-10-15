"""BDD step definitions for exporting documents with simulated content."""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

import cli
from tests.helpers.content_mocks import make_article, make_enriched
from tests.helpers.document_readers import read_document
from tests.helpers.fake_adapters import (
    FakeContentEnricher,
    FakeTranslator,
    FakeWikipediaSource,
)
from wiki_enrichment.application.use_cases import WikiEnrichmentOrchestrator
from wiki_enrichment.domain.exceptions import ExportError
from wiki_enrichment.infrastructure.exporters import (
    EMPTY_SECTION_TEXT,
    ENRICHED_HEADING,
    ORIGINAL_HEADING,
    TRANSLATED_HEADING,
    DocumentExporterAdapter,
)

ORIGINAL_TEXT = "Un agujero negro es una región del espacio."
ENRICHED_TEXT = "Texto simulado ampliado por la IA."
TRANSLATED_TEXT = "Simulated text translated into English."
MISSING_SECTIONS = 2

scenarios("../features/export.feature")


@pytest.fixture
def context(tmp_path):
    """Return a scenario context with a real exporter writing to a temp folder."""
    orchestrator = WikiEnrichmentOrchestrator(
        FakeWikipediaSource(),
        FakeContentEnricher(),
        FakeTranslator(),
        DocumentExporterAdapter(),
    )
    return {"folder": tmp_path, "orchestrator": orchestrator}


@given(parsers.parse('an article about "{title}" with enriched and translated content'))
def complete_content(context, title: str) -> None:
    """Simulate the three contents without calling any real service."""
    article = make_article(title, [ORIGINAL_TEXT])
    context["content"] = make_enriched(article, ENRICHED_TEXT, TRANSLATED_TEXT)


@given(parsers.parse('an article about "{title}" without enriched or translated content'))
def only_original_content(context, title: str) -> None:
    """Simulate an article whose AI and translation steps produced nothing."""
    context["content"] = make_enriched(make_article(title, [ORIGINAL_TEXT]), "", "")


@given("the destination cannot be written")
def destination_is_a_folder(context) -> None:
    """Block the destination by creating a folder with the file's name."""
    (context["folder"] / "apuntes.pdf").mkdir()


@when(parsers.parse('I export it as "{export_format}" with the name "{name}"'))
def export_document(context, export_format: str, name: str) -> None:
    """Export through the use case into the temporary folder."""
    path = context["folder"] / f"{name}{cli.EXTENSIONS[export_format]}"
    context["orchestrator"].export_document(context["content"], export_format, str(path))
    context["path"] = path


@when(parsers.parse('I try to export it as "{export_format}" with the name "{name}"'))
def try_to_export_document(context, export_format: str, name: str) -> None:
    """Export and keep the error, if any, for the next step."""
    path = context["folder"] / f"{name}.{export_format.lower()}"
    try:
        context["orchestrator"].export_document(context["content"], export_format, str(path))
        context["error"] = None
    except (ExportError, ValueError) as error:
        context["error"] = error


@when(parsers.parse('the user types the file name "{name}"'))
def type_file_name(context, name: str) -> None:
    """Validate the name exactly as the CLI does."""
    context["name_error"] = cli.file_name_error(name)


@then(parsers.parse('the file "{file_name}" is created'))
def file_is_created(context, file_name: str) -> None:
    assert (context["folder"] / file_name).is_file()


@then("the file can be opened and contains the three contents")
def file_contains_three_contents(context) -> None:
    text = read_document(context["path"])
    expected_order = [
        "Agujero negro",
        ORIGINAL_HEADING, ORIGINAL_TEXT,
        ENRICHED_HEADING, ENRICHED_TEXT,
        TRANSLATED_HEADING, TRANSLATED_TEXT,
    ]
    positions = [text.index(part) for part in expected_order]
    assert positions == sorted(positions)


@then("the missing contents are marked as not available")
def missing_contents_are_marked(context) -> None:
    assert read_document(context["path"]).count(EMPTY_SECTION_TEXT) == MISSING_SECTIONS


@then("an ExportError is raised")
def export_error_is_raised(context) -> None:
    assert isinstance(context["error"], ExportError)


@then("a ValueError is raised")
def value_error_is_raised(context) -> None:
    assert isinstance(context["error"], ValueError)


@then("the file name is rejected")
def file_name_is_rejected(context) -> None:
    assert context["name_error"] is not None
