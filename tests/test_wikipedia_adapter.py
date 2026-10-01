"""Unit tests for the Wikipedia source adapter."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from wiki_enrichment.domain.exceptions import (
    ProviderTimeoutError,
    ResourceNotFoundError,
    WikiEnrichmentError,
)
from wiki_enrichment.infrastructure.wikipedia import WikipediaSourceAdapter

SEARCH_OK = {"query": {"search": [{"title": "Python (programming language)"}]}}
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


@patch(GET)
def test_fetch_article_returns_title_and_first_five_paragraphs(mock_get) -> None:
    """A valid topic returns the title and at most five paragraphs."""
    mock_get.side_effect = [
        make_response(json_data=SEARCH_OK),
        make_response(text=HTML_OK),
    ]

    article = WikipediaSourceAdapter().fetch_article("python")

    assert article.title == "Python (programming language)"
    assert len(article.paragraphs) == 5
    assert article.paragraphs[0] == "Paragraph 1"


@patch(GET)
def test_fetch_article_raises_not_found_when_no_results(mock_get) -> None:
    """A topic without search results raises ResourceNotFoundError."""
    mock_get.return_value = make_response(json_data={"query": {"search": []}})

    with pytest.raises(ResourceNotFoundError):
        WikipediaSourceAdapter().fetch_article("zzzxxyy")


@patch(GET)
def test_fetch_article_raises_timeout_error(mock_get) -> None:
    """A request timeout raises ProviderTimeoutError."""
    mock_get.side_effect = requests.Timeout()

    with pytest.raises(ProviderTimeoutError):
        WikipediaSourceAdapter().fetch_article("python")


@patch(GET)
def test_fetch_article_wraps_network_errors(mock_get) -> None:
    """Other network failures raise the base WikiEnrichmentError."""
    mock_get.side_effect = requests.ConnectionError("no internet")

    with pytest.raises(WikiEnrichmentError):
        WikipediaSourceAdapter().fetch_article("python")

@patch(GET)
def test_fetch_article_raises_not_found_on_404(mock_get) -> None:
    """A 404 when downloading the article raises ResourceNotFoundError."""
    mock_get.side_effect = [
        make_response(json_data=SEARCH_OK),
        make_response(status_code=404),
    ]

    with pytest.raises(ResourceNotFoundError):
        WikipediaSourceAdapter().fetch_article("python")


@patch(GET)
def test_fetch_article_raises_not_found_when_page_has_no_content(mock_get) -> None:
    """A page without the content container raises ResourceNotFoundError."""
    mock_get.side_effect = [
        make_response(json_data=SEARCH_OK),
        make_response(text="<html><body></body></html>"),
    ]

    with pytest.raises(ResourceNotFoundError):
        WikipediaSourceAdapter().fetch_article("python")

@patch(GET)
def test_fetch_article_raises_not_found_when_page_has_no_paragraphs(mock_get) -> None:
    """A content container with only empty paragraphs raises ResourceNotFoundError."""
    mock_get.side_effect = [
        make_response(json_data=SEARCH_OK),
        make_response(text='<div id="mw-content-text"><p>  </p></div>'),
    ]

    with pytest.raises(ResourceNotFoundError):
        WikipediaSourceAdapter().fetch_article("python")