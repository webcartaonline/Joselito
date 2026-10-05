"""Shared pytest fixtures for contract-level test doubles."""

from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest

from tests.helpers.content_mocks import default_article, default_enriched
from tests.helpers.fake_adapters import (
    FakeContentEnricher,
    FakeDocumentExporter,
    FakeTranslator,
    FakeWikipediaSource,
)
from tests.helpers.wikipedia_mocks import (
    DEFAULT_SEARCH_TITLE,
    REQUEST_TARGET,
    build_article_html,
    build_search_payload,
    default_article_html,
)
from wiki_enrichment.domain.models import ArticleContent, EnrichedContent


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


@pytest.fixture
def sample_article() -> ArticleContent:
    """Return the default contract test article."""
    return default_article()


@pytest.fixture
def sample_enriched() -> EnrichedContent:
    """Return the default contract enriched content."""
    return default_enriched()


@pytest.fixture
def fake_source(sample_article: ArticleContent) -> FakeWikipediaSource:
    """Return a fake source serving the sample article."""
    return FakeWikipediaSource(article=sample_article)


@pytest.fixture
def fake_enricher() -> FakeContentEnricher:
    """Return a fake enricher with the default summary."""
    return FakeContentEnricher()


@pytest.fixture
def fake_translator() -> FakeTranslator:
    """Return a fake translator without external calls."""
    return FakeTranslator()


@pytest.fixture
def fake_exporter() -> FakeDocumentExporter:
    """Return a fake exporter recording without filesystem writes."""
    return FakeDocumentExporter()
