"""Tests for the DeepTranslate HTTP adapter without external API calls."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from wiki_enrichment.domain.exceptions import ProviderTimeoutError, WikiEnrichmentError
from wiki_enrichment.infrastructure.translation import (
    REQUEST_TIMEOUT_SECONDS,
    TRANSLATE_URL,
    TranslationAdapter,
)

POST_TARGET = "wiki_enrichment.infrastructure.translation.requests.post"


def test_translate_posts_to_deeptranslate_and_returns_translation(monkeypatch) -> None:
    monkeypatch.setenv("RAPIDAPI_KEY", "test-key")
    response = MagicMock()
    response.json.return_value = {
        "data": {"translations": {"translatedText": "Hello world"}}
    }

    with patch(POST_TARGET, return_value=response) as post:
        result = TranslationAdapter().translate("Hola mundo", "inglés")

    assert result == "Hello world"
    post.assert_called_once_with(
        TRANSLATE_URL,
        json={"q": "Hola mundo", "source": "es", "target": "en"},
        headers={
            "x-rapidapi-key": "test-key",
            "x-rapidapi-host": "deep-translate1.p.rapidapi.com",
            "Content-Type": "application/json",
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status.assert_called_once_with()


def test_translate_accepts_language_code(monkeypatch) -> None:
    monkeypatch.setenv("RAPIDAPI_KEY", "test-key")
    response = MagicMock()
    response.json.return_value = {
        "data": {"translations": {"translatedText": "Bonjour"}}
    }

    with patch(POST_TARGET, return_value=response) as post:
        assert TranslationAdapter().translate("Hola", "fr") == "Bonjour"

    assert post.call_args.kwargs["json"]["target"] == "fr"


def test_translate_requires_rapidapi_key(monkeypatch) -> None:
    monkeypatch.delenv("RAPIDAPI_KEY", raising=False)

    with pytest.raises(WikiEnrichmentError, match="RAPIDAPI_KEY"):
        TranslationAdapter().translate("Hola", "en")


def test_translate_converts_timeout_to_domain_error(monkeypatch) -> None:
    monkeypatch.setenv("RAPIDAPI_KEY", "test-key")

    with patch(POST_TARGET, side_effect=requests.Timeout):
        with pytest.raises(ProviderTimeoutError, match="DeepTranslate"):
            TranslationAdapter().translate("Hola", "en")


def test_translate_converts_request_failure_to_domain_error(monkeypatch) -> None:
    monkeypatch.setenv("RAPIDAPI_KEY", "test-key")

    with patch(POST_TARGET, side_effect=requests.ConnectionError):
        with pytest.raises(WikiEnrichmentError, match="Could not reach DeepTranslate"):
            TranslationAdapter().translate("Hola", "en")


@pytest.mark.parametrize(
    "payload",
    [
        {"data": {"translations": {}}},
        {"data": {"translations": {"translatedText": ""}}},
        {"data": {"translations": {"translatedText": None}}},
        None,
    ],
)
def test_translate_rejects_invalid_response(monkeypatch, payload) -> None:
    monkeypatch.setenv("RAPIDAPI_KEY", "test-key")
    response = MagicMock()
    response.json.return_value = payload

    with patch(POST_TARGET, return_value=response):
        with pytest.raises(WikiEnrichmentError, match="Invalid DeepTranslate response"):
            TranslationAdapter().translate("Hola", "en")


def test_translate_rejects_non_json_response(monkeypatch) -> None:
    monkeypatch.setenv("RAPIDAPI_KEY", "test-key")
    response = MagicMock()
    response.json.side_effect = ValueError("not json")

    with patch(POST_TARGET, return_value=response):
        with pytest.raises(WikiEnrichmentError, match="Invalid DeepTranslate response"):
            TranslationAdapter().translate("Hola", "en")
