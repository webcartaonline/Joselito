"""Unit tests for the Hugging Face summarizer with a mocked client."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from wiki_enrichment.domain.exceptions import (
    ProviderTimeoutError,
    SummarizationError,
)
from wiki_enrichment.infrastructure.huggingface_summarizer import (
    HuggingFaceSummarizer,
)

MODEL = "test/model"
TEXT = "A long enriched text about Python."
CLIENT_TARGET = (
    "wiki_enrichment.infrastructure.huggingface_summarizer.InferenceClient"
)


def make_client(content: str | None = "A brief summary.") -> MagicMock:
    """Build a fake inference client returning the given message content."""
    client = MagicMock()
    client.chat_completion.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )
    return client


def test_summarize_returns_summary() -> None:
    """Return the generated summary."""
    result = HuggingFaceSummarizer(model=MODEL, client=make_client()).summarize(TEXT)

    assert result == "A brief summary."


def test_summarize_strips_whitespace_from_summary() -> None:
    """Remove surrounding whitespace from the generated summary."""
    client = make_client("   A brief summary.   ")

    result = HuggingFaceSummarizer(model=MODEL, client=client).summarize(TEXT)

    assert result == "A brief summary."


def test_summarize_sends_model_limits_and_text() -> None:
    """Call the provider with the model, token limit and given text."""
    client = make_client()

    HuggingFaceSummarizer(model=MODEL, max_tokens=99, client=client).summarize(TEXT)

    kwargs = client.chat_completion.call_args.kwargs
    assert kwargs["model"] == MODEL
    assert kwargs["max_tokens"] == 99
    assert kwargs["messages"][0]["role"] == "system"
    assert kwargs["messages"][1]["role"] == "user"
    assert TEXT in kwargs["messages"][1]["content"]


@pytest.mark.parametrize("text", ["", "   "])
def test_summarize_raises_error_on_empty_text(text) -> None:
    """Reject empty text before calling the provider."""
    client = make_client()
    summarizer = HuggingFaceSummarizer(model=MODEL, client=client)

    with pytest.raises(SummarizationError):
        summarizer.summarize(text)

    client.chat_completion.assert_not_called()


@pytest.mark.parametrize("content", ["", "   ", None])
def test_summarize_raises_error_on_empty_summary(content) -> None:
    """Raise a summarization error when the provider returns no text."""
    summarizer = HuggingFaceSummarizer(model=MODEL, client=make_client(content))

    with pytest.raises(SummarizationError):
        summarizer.summarize(TEXT)


def test_summarize_maps_timeout_to_provider_timeout_error() -> None:
    """Map a provider timeout to the domain timeout error."""
    client = make_client()
    client.chat_completion.side_effect = TimeoutError()

    with pytest.raises(ProviderTimeoutError):
        HuggingFaceSummarizer(model=MODEL, client=client).summarize(TEXT)


def test_summarize_wraps_provider_errors() -> None:
    """Map unexpected provider failures to the summarization error."""
    client = make_client()
    client.chat_completion.side_effect = RuntimeError("provider down")

    with pytest.raises(SummarizationError, match="provider down"):
        HuggingFaceSummarizer(model=MODEL, client=client).summarize(TEXT)


def test_init_raises_error_when_token_is_missing(monkeypatch) -> None:
    """Raise a summarization error when no token is configured."""
    monkeypatch.delenv("HF_TOKEN", raising=False)

    with pytest.raises(SummarizationError):
        HuggingFaceSummarizer(model=MODEL)


@patch(CLIENT_TARGET)
def test_init_builds_client_with_token_and_timeout(mock_client_class) -> None:
    """Create the inference client with the given token and timeout."""
    HuggingFaceSummarizer(model=MODEL, token="hf_fake_token", timeout=5.0)

    mock_client_class.assert_called_once_with(api_key="hf_fake_token", timeout=5.0)


@patch(CLIENT_TARGET)
def test_init_reads_token_from_environment(mock_client_class, monkeypatch) -> None:
    """Fall back to the HF_TOKEN environment variable."""
    monkeypatch.setenv("HF_TOKEN", "hf_env_token")

    HuggingFaceSummarizer(model=MODEL)

    assert mock_client_class.call_args.kwargs["api_key"] == "hf_env_token"