"""BDD step definitions for Wikipedia scraping with mocked HTTP."""

from unittest.mock import MagicMock, patch

import pytest
import requests
from pytest_bdd import given, scenarios, then, when

from tests.helpers.wikipedia_mocks import (
    DEFAULT_SEARCH_TITLE,
    REQUEST_TARGET,
    make_article_response,
    make_response,
    make_search_response,
)
from wiki_enrichment.domain.exceptions import (
    ProviderTimeoutError,
    ResourceNotFoundError,
    WikiEnrichmentError,
)
from wiki_enrichment.infrastructure.wikipedia import WikipediaSourceAdapter

scenarios("../features/wikipedia_scraping.feature")


@pytest.fixture
def context():
    """Return a fresh scenario context dictionary."""
    return {}


def start_http_mock(context) -> MagicMock:
    """Patch HTTP where the adapter uses it and store the patcher."""
    patcher = patch(REQUEST_TARGET)
    mocked_get = patcher.start()
    context["mock_get"] = patcher
    return mocked_get


@given('Wikipedia has an article about "Python"')
def wikipedia_has_python_article(context) -> None:
    """Mock a successful search followed by an article download."""
    mocked_get = start_http_mock(context)
    mocked_get.side_effect = [make_search_response(), make_article_response()]


@given('Wikipedia has no results for "zzzxxyy"')
def wikipedia_has_no_results(context) -> None:
    """Mock an empty search result list."""
    mocked_get = start_http_mock(context)
    mocked_get.return_value = make_response(json_data={"query": {"search": []}})


@given("Wikipedia exceeds the configured timeout")
def wikipedia_timeout(context) -> None:
    """Mock a timeout on the Wikipedia request."""
    mocked_get = start_http_mock(context)
    mocked_get.side_effect = requests.Timeout()


@given("there is no network connection")
def no_network_connection(context) -> None:
    """Mock a connection failure on the Wikipedia request."""
    mocked_get = start_http_mock(context)
    mocked_get.side_effect = requests.ConnectionError("no internet")


def fetch_article(context, topic: str) -> dict:
    """Fetch an article while recording the result or the raised error."""
    try:
        context["article"] = WikipediaSourceAdapter().fetch_article(topic)
    except Exception as exc:
        context["exception"] = exc
    context["mock_get"].stop()
    return context


@when('I fetch the article for the topic "Python"', target_fixture="context")
def fetch_python_article(context) -> dict:
    """Fetch the mocked Python article."""
    return fetch_article(context, "Python")


@when('I fetch the article for the topic "zzzxxyy"', target_fixture="context")
def fetch_unknown_article(context) -> dict:
    """Fetch a mocked unknown topic."""
    return fetch_article(context, "zzzxxyy")


@then("I receive the article title")
def receive_article_title(context) -> None:
    """Check the mocked article title."""
    assert context["article"].title == DEFAULT_SEARCH_TITLE


@then("I receive at most 5 paragraphs")
def receive_at_most_five_paragraphs(context) -> None:
    """Check the mocked article keeps at most five paragraphs."""
    assert len(context["article"].paragraphs) <= 5


@then("a ResourceNotFoundError is raised")
def resource_not_found_is_raised(context) -> None:
    """Check a missing article maps to a not-found error."""
    assert isinstance(context["exception"], ResourceNotFoundError)


@then("a ProviderTimeoutError is raised")
def provider_timeout_is_raised(context) -> None:
    """Check a timeout maps to a provider timeout error."""
    assert isinstance(context["exception"], ProviderTimeoutError)


@then("a WikiEnrichmentError is raised")
def wiki_enrichment_error_is_raised(context) -> None:
    """Check a network failure maps to the base domain error."""
    assert isinstance(context["exception"], WikiEnrichmentError)
