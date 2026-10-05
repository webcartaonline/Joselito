"""Shared HTTP mocks for Wikipedia adapter tests."""

from typing import Any
from unittest.mock import MagicMock

import requests

REQUEST_TARGET = "wiki_enrichment.infrastructure.wikipedia.requests.get"
DEFAULT_SEARCH_TITLE = "Python (programming language)"
EXTRA_PARAGRAPH_COUNT = 7


def build_search_payload(title: str = DEFAULT_SEARCH_TITLE) -> dict[str, Any]:
    """Build a Wikipedia search API payload with a single result.

    Args:
        title: Article title returned as the first search result.

    Returns:
        A JSON-serializable payload shaped as the search API response.
    """
    return {"query": {"search": [{"title": title}]}}


def build_article_html(paragraphs: list[str]) -> str:
    """Build a minimal Wikipedia article body from paragraphs.

    Args:
        paragraphs: Paragraph texts to embed in the content div.

    Returns:
        An HTML fragment with the given paragraphs.
    """
    body = "".join(f"<p>{text}</p>" for text in paragraphs)
    return f'<div id="mw-content-text">{body}</div>'


def default_article_html() -> str:
    """Build the default article body with more paragraphs than allowed.

    Returns:
        An HTML fragment with EXTRA_PARAGRAPH_COUNT paragraphs.
    """
    paragraphs = [f"Paragraph {index}" for index in range(1, EXTRA_PARAGRAPH_COUNT + 1)]
    return build_article_html(paragraphs)


def make_response(
    json_data: Any = None, text: str = "", status_code: int = 200
) -> MagicMock:
    """Build a fake ``requests`` response without performing I/O.

    Args:
        json_data: Value returned by ``response.json()``.
        text: Value exposed as ``response.text``.
        status_code: HTTP status code exposed by the response.

    Returns:
        A mocked response with a no-op ``raise_for_status``.
    """
    response = MagicMock()
    response.json.return_value = json_data
    response.text = text
    response.status_code = status_code
    response.raise_for_status.return_value = None
    return response


def make_search_response(title: str = DEFAULT_SEARCH_TITLE) -> MagicMock:
    """Build a successful search-API response for a title.

    Args:
        title: Article title returned as the first search result.

    Returns:
        A mocked response carrying the search payload.
    """
    return make_response(json_data=build_search_payload(title))


def make_article_response(html: str | None = None) -> MagicMock:
    """Build a successful article-download response.

    Args:
        html: Article HTML body. Defaults to the standard test article.

    Returns:
        A mocked response carrying the article HTML.
    """
    return make_response(text=html if html is not None else default_article_html())


def make_http_error_response(status_code: int) -> MagicMock:
    """Build a response whose ``raise_for_status`` raises an HTTP error.

    Args:
        status_code: HTTP status code exposed by the response.

    Returns:
        A mocked response raising ``requests.HTTPError`` on status check.
    """
    response = make_response(status_code=status_code)
    response.raise_for_status.side_effect = requests.HTTPError(
        f"HTTP {status_code}"
    )
    return response


def make_invalid_payload_response() -> MagicMock:
    """Build a search response with an unexpected JSON shape.

    Returns:
        A mocked response whose JSON lacks the search result list.
    """
    return make_response(json_data={"invalid": True})
