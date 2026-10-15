"""Tests for the composition root that chooses the concrete adapters."""

from unittest.mock import patch

import pytest

from tests.helpers.content_mocks import make_article
from wiki_enrichment import bootstrap
from wiki_enrichment.domain.exceptions import EnrichmentError
from wiki_enrichment.infrastructure.ai import NO_PROVIDER_REASON, AIContentEnricher
from wiki_enrichment.infrastructure.huggingface_enricher import HuggingFaceEnricher

CLIENT_TARGET = "wiki_enrichment.infrastructure.huggingface_enricher.InferenceClient"


@patch(CLIENT_TARGET)
def test_uses_hugging_face_with_the_default_model_when_there_is_a_token(
    _client, monkeypatch
) -> None:
    monkeypatch.setenv("HF_TOKEN", "hf_fake_token")
    monkeypatch.delenv(bootstrap.HF_MODEL_VARIABLE, raising=False)

    enricher = bootstrap.build_content_enricher()

    assert isinstance(enricher, HuggingFaceEnricher)
    assert enricher._model == bootstrap.DEFAULT_HF_MODEL


@patch(CLIENT_TARGET)
def test_model_can_be_changed_from_the_environment(_client, monkeypatch) -> None:
    monkeypatch.setenv("HF_TOKEN", "hf_fake_token")
    monkeypatch.setenv(bootstrap.HF_MODEL_VARIABLE, "another/model")

    enricher = bootstrap.build_content_enricher()

    assert enricher._model == "another/model"


def test_without_token_the_fallback_explains_the_problem(monkeypatch) -> None:
    monkeypatch.delenv("HF_TOKEN", raising=False)

    enricher = bootstrap.build_content_enricher()

    assert isinstance(enricher, AIContentEnricher)
    with pytest.raises(EnrichmentError, match="HF_TOKEN"):
        enricher.enrich(make_article())


def test_fallback_enricher_has_a_default_reason() -> None:
    with pytest.raises(EnrichmentError, match=NO_PROVIDER_REASON):
        AIContentEnricher().enrich(make_article())
