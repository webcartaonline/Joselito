"""Unit tests for the fallback summarizer used without an AI provider."""

import pytest

from wiki_enrichment.domain.exceptions import SummarizationError
from wiki_enrichment.infrastructure.ai import NO_PROVIDER_REASON, AIContentSummarizer


def test_summarizer_fails_with_the_default_reason() -> None:
    """Without a provider the summarizer explains why it cannot work."""

    with pytest.raises(SummarizationError, match=NO_PROVIDER_REASON):
        AIContentSummarizer().summarize("Any text.")


def test_summarizer_fails_with_a_custom_reason() -> None:
    """The reason given at creation is the one shown to the user."""

    with pytest.raises(SummarizationError, match="HF_TOKEN is not set"):
        AIContentSummarizer("HF_TOKEN is not set").summarize("Any text.")