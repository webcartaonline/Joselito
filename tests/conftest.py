"""Shared pytest fixtures for Wikipedia HTTP mocking."""

from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest

from tests.helpers.wikipedia_mocks import (
    DEFAULT_SEARCH_TITLE,
    REQUEST_TARGET,
    build_article_html,
    build_search_payload,
    default_article_html,
)


@pytest.fixture
def search_title() -> str:
    """Return the default mocked article title."""
    return DEFAULT_SEARCH_TITLE


@pytest.fixture
def search_payload() -> dict:
    """Return the default mocked search API payload."""
    return build_search_payload()


@pytest.fixture
def article_html() -> str:
    """Return the default mocked article HTML body."""
    return default_article_html()


@pytest.fixture
def mixed_article_html() -> str:
    """Return article HTML mixing empty and valid paragraphs."""
    return build_article_html(
        ["", "First paragraph", "  ", "Second paragraph", "Third paragraph"]
    )


@pytest.fixture
def mock_http_get() -> Iterator[MagicMock]:
    """Patch ``requests.get`` where the adapter uses it.

    Yields:
        The mocked ``requests.get`` function with no real I/O.
    """
    with patch(REQUEST_TARGET) as mocked_get:
        yield mocked_get
