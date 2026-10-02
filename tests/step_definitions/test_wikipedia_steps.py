from unittest.mock import MagicMock, patch

import pytest
from pytest_bdd import given, scenarios, then, when

import requests

from wiki_enrichment.domain.exceptions import (
    ProviderTimeoutError,
    ResourceNotFoundError,
    WikiEnrichmentError,
)
from wiki_enrichment.infrastructure.wikipedia import WikipediaSourceAdapter


scenarios("../features/wikipedia_scraping.feature")


SEARCH_OK = {
    "query": {
        "search": [
            {"title": "Python (programming language)"}
        ]
    }
}

HTML_OK = (
    '<div id="mw-content-text">'
    + "".join(f"<p>Paragraph {i}</p>" for i in range(1, 8))
    + "</div>"
)

GET = "wiki_enrichment.infrastructure.wikipedia.requests.get"


def make_response(json_data=None, text="", status_code=200):
    response = MagicMock()
    response.json.return_value = json_data
    response.text = text
    response.status_code = status_code
    response.raise_for_status.return_value = None
    return response


@pytest.fixture
def context():
    return {}


@given('Wikipedia has an article about "Python"')
def wikipedia_has_python_article(context):
    context["mock_get"] = patch(GET)
    mock_get = context["mock_get"].start()

    mock_get.side_effect = [
        make_response(json_data=SEARCH_OK),
        make_response(text=HTML_OK),
    ]


@given('Wikipedia has no results for "zzzxxyy"')
def wikipedia_has_no_results(context):
    context["mock_get"] = patch(GET)
    mock_get = context["mock_get"].start()

    mock_get.return_value = make_response(
        json_data={"query": {"search": []}}
    )


@given("Wikipedia exceeds the configured timeout")
def wikipedia_timeout(context):
    context["mock_get"] = patch(GET)
    mock_get = context["mock_get"].start()

    mock_get.side_effect = requests.Timeout()


@given("there is no network connection")
def no_network_connection(context):
    context["mock_get"] = patch(GET)
    mock_get = context["mock_get"].start()

    mock_get.side_effect = requests.ConnectionError("no internet")


@when('I fetch the article for the topic "Python"', target_fixture="context")
def fetch_python_article(context):
    try:
        context["article"] = WikipediaSourceAdapter().fetch_article("Python")
    except Exception as exc:
        context["exception"] = exc

    context["mock_get"].stop()

    return context


@when('I fetch the article for the topic "zzzxxyy"', target_fixture="context")
def fetch_unknown_article(context):
    try:
        context["article"] = WikipediaSourceAdapter().fetch_article("zzzxxyy")
    except Exception as exc:
        context["exception"] = exc

    context["mock_get"].stop()

    return context


@then("I receive the article title")
def receive_article_title(context):
    assert context["article"].title == "Python (programming language)"


@then("I receive at most 5 paragraphs")
def receive_at_most_five_paragraphs(context):
    assert len(context["article"].paragraphs) <= 5


@then("a ResourceNotFoundError is raised")
def resource_not_found_is_raised(context):
    assert isinstance(context["exception"], ResourceNotFoundError)


@then("a ProviderTimeoutError is raised")
def provider_timeout_is_raised(context):
    assert isinstance(context["exception"], ProviderTimeoutError)


@then("a WikiEnrichmentError is raised")
def wiki_enrichment_error_is_raised(context):
    assert isinstance(context["exception"], WikiEnrichmentError)