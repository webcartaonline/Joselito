"""Unit tests for the DeepSeek summarizer with a mocked HTTP layer."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from domain.exceptions import (
    ProviderTimeoutError,
    SummarizationError,
)
from infrastructure.deepseek_summarizer import DeepSeekSummarizer

POST_TARGET = "infrastructure.deepseek_summarizer.requests.post"


def make_response(content="A brief summary."):
    response = MagicMock()
    response.json.return_value = {"choices": [{"message": {"content": content}}]}
    response.raise_for_status.return_value = None
    return response


def test_summarize_returns_brief_text() -> None:
    with patch(POST_TARGET, return_value=make_response()) as mock_post:
        result = DeepSeekSummarizer(api_key="sk_fake").summarize("Some long text.")

    assert result == "A brief summary."
    assert mock_post.call_args.args[0].endswith("/chat/completions")


def test_summarize_sends_bearer_auth_and_model() -> None:
    with patch(POST_TARGET, return_value=make_response()) as mock_post:
        DeepSeekSummarizer(api_key="sk_fake", model="deepseek-chat").summarize("Text.")

    kwargs = mock_post.call_args.kwargs
    assert kwargs["headers"] == {"Authorization": "Bearer sk_fake"}
    assert kwargs["json"]["model"] == "deepseek-chat"
    assert kwargs["json"]["max_tokens"] == 200


def test_init_raises_error_when_key_is_missing(monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(SummarizationError, match="DEEPSEEK_API_KEY"):
        DeepSeekSummarizer()


def test_summarize_rejects_empty_text() -> None:
    with patch(POST_TARGET) as mock_post:
        with pytest.raises(SummarizationError):
            DeepSeekSummarizer(api_key="sk_fake").summarize("   ")

    mock_post.assert_not_called()


def test_summarize_maps_timeout_to_provider_timeout_error() -> None:
    with patch(POST_TARGET, side_effect=requests.Timeout()):
        with pytest.raises(ProviderTimeoutError):
            DeepSeekSummarizer(api_key="sk_fake").summarize("Text.")


def test_summarize_wraps_http_errors() -> None:
    response = make_response()
    response.raise_for_status.side_effect = requests.HTTPError("401 bad key")

    with patch(POST_TARGET, return_value=response):
        with pytest.raises(SummarizationError, match="401 bad key"):
            DeepSeekSummarizer(api_key="sk_fake").summarize("Text.")


@pytest.mark.parametrize("content", ["", "   ", None])
def test_summarize_raises_error_on_empty_summary(content) -> None:
    with patch(POST_TARGET, return_value=make_response(content)):
        with pytest.raises(SummarizationError):
            DeepSeekSummarizer(api_key="sk_fake").summarize("Text.")
