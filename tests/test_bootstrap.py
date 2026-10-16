"""Tests for the composition root that chooses the concrete adapters."""

import pytest

from tests.helpers.content_mocks import make_article
import bootstrap
from domain.exceptions import EnrichmentError, SummarizationError
from infrastructure.ai import (
    NO_PROVIDER_REASON,
    AIContentEnricher,
    AIContentSummarizer,
)
from infrastructure.deepseek_enricher import DeepSeekEnricher
from infrastructure.deepseek_summarizer import DeepSeekSummarizer


def test_uses_deepseek_with_the_default_model_when_there_is_a_key(
    monkeypatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk_fake_key")
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)

    enricher = bootstrap.build_content_enricher()

    assert isinstance(enricher, DeepSeekEnricher)
    assert enricher._model == "deepseek-chat"


def test_enricher_model_can_be_changed_from_the_environment(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk_fake_key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-reasoner")

    enricher = bootstrap.build_content_enricher()

    assert isinstance(enricher, DeepSeekEnricher)
    assert enricher._model == "deepseek-reasoner"


def test_without_key_the_fallback_explains_the_problem(monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    enricher = bootstrap.build_content_enricher()

    assert isinstance(enricher, AIContentEnricher)
    with pytest.raises(EnrichmentError, match="DEEPSEEK_API_KEY"):
        enricher.enrich(make_article())


def test_fallback_enricher_has_a_default_reason() -> None:
    with pytest.raises(EnrichmentError, match=NO_PROVIDER_REASON):
        AIContentEnricher().enrich(make_article())


def test_summarizer_uses_the_default_model_when_there_is_a_key(
    monkeypatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk_fake_key")
    monkeypatch.delenv("DEEPSEEK_SUMMARIZER_MODEL", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)

    summarizer = bootstrap.build_content_summarizer()

    assert isinstance(summarizer, DeepSeekSummarizer)
    assert summarizer._model == "deepseek-chat"


def test_summarizer_follows_the_enricher_model_from_the_environment(
    monkeypatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk_fake_key")
    monkeypatch.delenv("DEEPSEEK_SUMMARIZER_MODEL", raising=False)
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-reasoner")

    summarizer = bootstrap.build_content_summarizer()

    assert isinstance(summarizer, DeepSeekSummarizer)
    assert summarizer._model == "deepseek-reasoner"


def test_summarizer_model_can_be_changed_from_the_environment(
    monkeypatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk_fake_key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat")
    monkeypatch.setenv("DEEPSEEK_SUMMARIZER_MODEL", "deepseek-reasoner")

    summarizer = bootstrap.build_content_summarizer()

    assert isinstance(summarizer, DeepSeekSummarizer)
    assert summarizer._model == "deepseek-reasoner"


def test_without_key_the_summarizer_fallback_explains_the_problem(
    monkeypatch,
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    summarizer = bootstrap.build_content_summarizer()

    assert isinstance(summarizer, AIContentSummarizer)
    with pytest.raises(SummarizationError, match="DEEPSEEK_API_KEY"):
        summarizer.summarize("Any text.")
