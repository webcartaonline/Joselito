"""Unit tests for the Hugging Face content enricher with a mocked client."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from wiki_enrichment.domain.exceptions import (
    EnrichmentError,
    ProviderTimeoutError,
)
from wiki_enrichment.domain.models import ArticleContent
from wiki_enrichment.infrastructure.huggingface_enricher import (
    HuggingFaceEnricher,
)

MODEL = "test/model"
CLIENT_TARGET = "wiki_enrichment.infrastructure.huggingface_enricher.InferenceClient"


def make_article(paragraphs: list[str] | None = None) -> ArticleContent:
    """Build an article with sensible default paragraphs."""
    if paragraphs is None:
        paragraphs = ["First paragraph.", "Second paragraph."]
    return ArticleContent(title="Python", paragraphs=paragraphs)


def make_client(content: str | None = "A summary.") -> MagicMock:
    """Build a fake inference client returning the given message content."""
    client = MagicMock()
    client.chat_completion.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )
    return client


def test_enrich_returns_summary_and_keeps_original_article() -> None:
    """Return the AI summary together with the original article."""
    article = make_article()

    result = HuggingFaceEnricher(model=MODEL, client=make_client()).enrich(article)

    assert result.original_article == article
    assert result.ai_summary == "A summary."
    assert result.translated_summary == ""


def test_enrich_strips_whitespace_from_summary() -> None:
    """Remove surrounding whitespace from the generated summary."""
    client = make_client("  A summary.  \n")

    result = HuggingFaceEnricher(model=MODEL, client=client).enrich(make_article())

    assert result.ai_summary == "A summary."


def test_enrich_sends_model_limits_and_article_text() -> None:
    """Call the provider with the model, token limit and article text."""
    client = make_client()
    article = make_article()

    HuggingFaceEnricher(model=MODEL, max_tokens=123, client=client).enrich(article)

    kwargs = client.chat_completion.call_args.kwargs
    assert kwargs["model"] == MODEL
    assert kwargs["max_tokens"] == 123
    assert kwargs["messages"][0]["role"] == "system"
    assert kwargs["messages"][1]["role"] == "user"
    assert "Python" in kwargs["messages"][1]["content"]
    assert article.full_text in kwargs["messages"][1]["content"]


def test_enrich_raises_error_when_article_has_no_text() -> None:
    """Reject articles without text before calling the provider."""
    client = make_client()
    enricher = HuggingFaceEnricher(model=MODEL, client=client)

    with pytest.raises(EnrichmentError):
        enricher.enrich(make_article(paragraphs=["  "]))

    client.chat_completion.assert_not_called()


@pytest.mark.parametrize("content", ["", "   ", None])
def test_enrich_raises_error_on_empty_summary(content) -> None:
    """Raise an enrichment error when the provider returns no text."""
    enricher = HuggingFaceEnricher(model=MODEL, client=make_client(content))

    with pytest.raises(EnrichmentError):
        enricher.enrich(make_article())


def test_enrich_maps_timeout_to_provider_timeout_error() -> None:
    """Map a provider timeout to the domain timeout error."""
    client = make_client()
    client.chat_completion.side_effect = TimeoutError()

    with pytest.raises(ProviderTimeoutError):
        HuggingFaceEnricher(model=MODEL, client=client).enrich(make_article())


def test_enrich_wraps_provider_errors() -> None:
    """Map unexpected provider failures to the enrichment error."""
    client = make_client()
    client.chat_completion.side_effect = RuntimeError("provider down")

    with pytest.raises(EnrichmentError, match="provider down"):
        HuggingFaceEnricher(model=MODEL, client=client).enrich(make_article())


def test_init_raises_error_when_token_is_missing(monkeypatch) -> None:
    """Raise an enrichment error when no token is configured."""
    monkeypatch.delenv("HF_TOKEN", raising=False)

    with pytest.raises(EnrichmentError):
        HuggingFaceEnricher(model=MODEL)


@patch(CLIENT_TARGET)
def test_init_builds_client_with_token_and_timeout(mock_client_class) -> None:
    """Create the inference client with the given token and timeout."""
    HuggingFaceEnricher(model=MODEL, token="hf_fake_token", timeout=5.0)

    mock_client_class.assert_called_once_with(api_key="hf_fake_token", timeout=5.0)


@patch(CLIENT_TARGET)
def test_init_reads_token_from_environment(mock_client_class, monkeypatch) -> None:
    """Fall back to the HF_TOKEN environment variable."""
    monkeypatch.setenv("HF_TOKEN", "hf_env_token")

    HuggingFaceEnricher(model=MODEL)

    assert mock_client_class.call_args.kwargs["api_key"] == "hf_env_token"