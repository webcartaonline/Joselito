"""Unit tests for the DeepSeek content enricher with a mocked HTTP layer."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from domain.exceptions import (
    EnrichmentError,
    ProviderTimeoutError,
)
from domain.models import ArticleContent
from infrastructure.deepseek_enricher import DeepSeekEnricher

POST_TARGET = "infrastructure.deepseek_enricher.requests.post"


def make_article(paragraphs=None) -> ArticleContent:
    if paragraphs is None:
        paragraphs = ["First paragraph.", "Second paragraph."]
    return ArticleContent(title="Python", paragraphs=paragraphs)


def make_response(content="A summary."):
    response = MagicMock()
    response.json.return_value = {"choices": [{"message": {"content": content}}]}
    response.raise_for_status.return_value = None
    return response


def test_enrich_returns_summary_and_keeps_original_article() -> None:
    article = make_article()

    with patch(POST_TARGET, return_value=make_response()) as mock_post:
        result = DeepSeekEnricher(api_key="sk_fake").enrich(article)

    assert result.original_article == article
    assert result.ai_summary == "A summary."
    assert result.translated_summary == ""
    assert mock_post.call_args.args[0].endswith("/chat/completions")


def test_enrich_sends_bearer_auth_model_and_truncated_text() -> None:
    long_text = "x" * 5000
    article = make_article(paragraphs=[long_text])

    with patch(POST_TARGET, return_value=make_response()) as mock_post:
        DeepSeekEnricher(api_key="sk_fake", model="deepseek-chat").enrich(article)

    kwargs = mock_post.call_args.kwargs
    assert kwargs["headers"] == {"Authorization": "Bearer sk_fake"}
    assert kwargs["json"]["model"] == "deepseek-chat"
    sent = kwargs["json"]["messages"][1]["content"]
    assert len(sent) < len(long_text) + 500
    assert "Python" in sent


def test_init_raises_error_when_key_is_missing(monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(EnrichmentError, match="DEEPSEEK_API_KEY"):
        DeepSeekEnricher()


def test_enrich_maps_timeout_to_provider_timeout_error() -> None:
    with patch(POST_TARGET, side_effect=requests.Timeout()):
        with pytest.raises(ProviderTimeoutError):
            DeepSeekEnricher(api_key="sk_fake").enrich(make_article())


@pytest.mark.parametrize("content", ["", "   ", None])
def test_enrich_raises_error_on_empty_summary(content) -> None:
    with patch(POST_TARGET, return_value=make_response(content)):
        with pytest.raises(EnrichmentError):
            DeepSeekEnricher(api_key="sk_fake").enrich(make_article())


def test_enrich_rejects_article_without_text() -> None:
    """An article without text is rejected before calling the provider."""
    with patch(POST_TARGET) as mock_post:
        with pytest.raises(EnrichmentError):
            DeepSeekEnricher(api_key="sk_fake").enrich(make_article(paragraphs=["  "]))

    mock_post.assert_not_called()


def test_enrich_wraps_http_errors() -> None:
    response = make_response()
    response.raise_for_status.side_effect = requests.HTTPError("401 bad key")

    with patch(POST_TARGET, return_value=response):
        with pytest.raises(EnrichmentError, match="401 bad key"):
            DeepSeekEnricher(api_key="sk_fake").enrich(make_article())
