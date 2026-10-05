"""Unit tests for the Wikipedia source adapter with mocked HTTP."""

from unittest.mock import patch

import pytest
import requests

from tests.helpers.wikipedia_mocks import (
    DEFAULT_SEARCH_TITLE,
    REQUEST_TARGET,
    build_article_html,
    make_article_response,
    make_http_error_response,
    make_invalid_payload_response,
    make_response,
    make_search_response,
)
from wiki_enrichment.domain.exceptions import (
    ProviderTimeoutError,
    ResourceNotFoundError,
    WikiEnrichmentError,
)
from wiki_enrichment.infrastructure.wikipedia import (
    HEADERS,
    MAX_PARAGRAPHS,
    REQUEST_TIMEOUT_SECONDS,
    WikipediaSourceAdapter,
)


@patch(REQUEST_TARGET)
def test_fetch_article_returns_title_and_first_five_paragraphs(
    mock_get,
) -> None:
    """Return the title and at most MAX_PARAGRAPHS paragraphs on success."""
    mock_get.side_effect = [make_search_response(), make_article_response()]

    article = WikipediaSourceAdapter().fetch_article("python")

    assert article.title == DEFAULT_SEARCH_TITLE
    assert len(article.paragraphs) == MAX_PARAGRAPHS
    assert article.paragraphs[0] == "Paragraph 1"


@patch(REQUEST_TARGET)
def test_fetch_article_raises_not_found_when_no_results(mock_get) -> None:
    """Raise not found when the search API returns no matches."""
    mock_get.return_value = make_response(json_data={"query": {"search": []}})

    with pytest.raises(ResourceNotFoundError):
        WikipediaSourceAdapter().fetch_article("zzzxxyy")


@patch(REQUEST_TARGET)
def test_fetch_article_raises_timeout_error(mock_get) -> None:
    """Map a search timeout to a provider timeout error."""
    mock_get.side_effect = requests.Timeout()

    with pytest.raises(ProviderTimeoutError):
        WikipediaSourceAdapter().fetch_article("python")


@patch(REQUEST_TARGET)
def test_fetch_article_raises_timeout_on_download(mock_get) -> None:
    """Map an article download timeout to a provider timeout error."""
    mock_get.side_effect = [make_search_response(), requests.Timeout()]

    with pytest.raises(ProviderTimeoutError):
        WikipediaSourceAdapter().fetch_article("python")


@patch(REQUEST_TARGET)
def test_fetch_article_wraps_network_errors(mock_get) -> None:
    """Map connection failures to the base domain error."""
    mock_get.side_effect = requests.ConnectionError("no internet")

    with pytest.raises(WikiEnrichmentError):
        WikipediaSourceAdapter().fetch_article("python")


@patch(REQUEST_TARGET)
def test_fetch_article_wraps_search_http_error(mock_get) -> None:
    """Map search HTTP failures to the base domain error."""
    mock_get.return_value = make_http_error_response(500)

    with pytest.raises(WikiEnrichmentError):
        WikipediaSourceAdapter().fetch_article("python")


@patch(REQUEST_TARGET)
def test_fetch_article_wraps_download_http_error(mock_get) -> None:
    """Map article download HTTP failures to the base domain error."""
    mock_get.side_effect = [make_search_response(), make_http_error_response(500)]

    with pytest.raises(WikiEnrichmentError):
        WikipediaSourceAdapter().fetch_article("python")


@patch(REQUEST_TARGET)
def test_fetch_article_raises_domain_error_on_invalid_payload(
    mock_get,
) -> None:
    """Map malformed search payloads to the base domain error."""
    mock_get.return_value = make_invalid_payload_response()

    with pytest.raises(WikiEnrichmentError):
        WikipediaSourceAdapter().fetch_article("python")


@patch(REQUEST_TARGET)
def test_fetch_article_raises_domain_error_on_invalid_json(mock_get) -> None:
    """Map undecodable search bodies to the base domain error."""
    broken_response = make_search_response()
    broken_response.json.side_effect = ValueError("No JSON")
    mock_get.return_value = broken_response

    with pytest.raises(WikiEnrichmentError):
        WikipediaSourceAdapter().fetch_article("python")


@patch(REQUEST_TARGET)
def test_fetch_article_raises_domain_error_on_missing_title(
    mock_get,
) -> None:
    """Map search results without a title to the base domain error."""
    mock_get.return_value = make_response(
        json_data={"query": {"search": [{"missing": "title"}]}}
    )

    with pytest.raises(WikiEnrichmentError):
        WikipediaSourceAdapter().fetch_article("python")


@patch(REQUEST_TARGET)
def test_fetch_article_raises_domain_error_on_empty_title(mock_get) -> None:
    """Map empty search titles to the base domain error."""
    mock_get.return_value = make_response(
        json_data={"query": {"search": [{"title": ""}]}}
    )

    with pytest.raises(WikiEnrichmentError):
        WikipediaSourceAdapter().fetch_article("python")


@patch(REQUEST_TARGET)
def test_fetch_article_raises_not_found_on_404(mock_get) -> None:
    """Raise not found when the article page returns 404."""
    mock_get.side_effect = [
        make_search_response(),
        make_response(status_code=404),
    ]

    with pytest.raises(ResourceNotFoundError):
        WikipediaSourceAdapter().fetch_article("python")


@patch(REQUEST_TARGET)
def test_fetch_article_raises_not_found_when_page_has_no_content(
    mock_get,
) -> None:
    """Raise not found when the page has no content container."""
    mock_get.side_effect = [
        make_search_response(),
        make_response(text="<html><body></body></html>"),
    ]

    with pytest.raises(ResourceNotFoundError):
        WikipediaSourceAdapter().fetch_article("python")


@patch(REQUEST_TARGET)
def test_fetch_article_raises_not_found_when_page_has_no_paragraphs(
    mock_get,
) -> None:
    """Raise not found when the page has only empty paragraphs."""
    mock_get.side_effect = [
        make_search_response(),
        make_response(text='<div id="mw-content-text"><p>  </p></div>'),
    ]

    with pytest.raises(ResourceNotFoundError):
        WikipediaSourceAdapter().fetch_article("python")


@patch(REQUEST_TARGET)
def test_fetch_article_skips_empty_paragraphs(mock_get) -> None:
    """Skip empty paragraphs while keeping the article order."""
    html = build_article_html(["", "First paragraph", "  ", "Second paragraph"])
    mock_get.side_effect = [make_search_response(), make_article_response(html)]

    article = WikipediaSourceAdapter().fetch_article("python")

    assert article.paragraphs == ["First paragraph", "Second paragraph"]


@patch(REQUEST_TARGET)
def test_fetch_article_sends_expected_request_params(mock_get) -> None:
    """Call search and download endpoints with headers and timeout."""
    mock_get.side_effect = [make_search_response(), make_article_response()]

    WikipediaSourceAdapter().fetch_article("python")

    search_call, download_call = mock_get.call_args_list
    assert search_call.args[0].endswith("/w/api.php")
    assert search_call.kwargs["params"]["srsearch"] == "python"
    assert search_call.kwargs["headers"] == HEADERS
    assert search_call.kwargs["timeout"] == REQUEST_TIMEOUT_SECONDS
    assert download_call.args[0].endswith("/wiki/Python_(programming_language)")
    assert download_call.kwargs["headers"] == HEADERS
    assert download_call.kwargs["timeout"] == REQUEST_TIMEOUT_SECONDS


def test_fetch_article_uses_configured_language(mock_http_get) -> None:
    """Build request URLs from the configured Wikipedia language."""
    mock_http_get.side_effect = [
        make_search_response("Agujero negro"),
        make_article_response(build_article_html(["Un párrafo."])),
    ]

    article = WikipediaSourceAdapter(language="es").fetch_article("agujero negro")

    assert article.title == "Agujero negro"
    assert mock_http_get.call_args_list[0].args[0].startswith(
        "https://es.wikipedia.org"
    )
