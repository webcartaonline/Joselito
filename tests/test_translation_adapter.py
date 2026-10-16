"""Tests for the Google Cloud Translation adapter without external API calls."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from domain.exceptions import ProviderTimeoutError, WikiEnrichmentError
from infrastructure import translation
from infrastructure.translation import (
    MAX_RETRIES,
    REQUEST_TIMEOUT_SECONDS,
    TRANSLATE_URL,
    TranslationAdapter,
)

POST_TARGET = "infrastructure.translation.requests.post"
SLEEP_TARGET = "infrastructure.translation.time.sleep"
API_KEY = "test-key"


def make_response(json_data=None, status_code=200, headers=None, json_error=None):
    response = MagicMock()
    response.status_code = status_code
    response.headers = headers or {}
    if json_error is not None:
        response.json.side_effect = json_error
    else:
        response.json.return_value = json_data
    return response


def ok(text: str) -> MagicMock:
    return make_response({"data": {"translations": [{"translatedText": text}]}})


def google_error(status: int, message: str, status_name: str, reason: str) -> MagicMock:
    return make_response(
        {
            "error": {
                "code": status,
                "message": message,
                "errors": [{"message": message, "domain": "global", "reason": reason}],
                "status": status_name,
            }
        },
        status_code=status,
    )


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    monkeypatch.setenv("GOOGLE_TRANSLATE_API_KEY", API_KEY)


@pytest.fixture
def sleep():
    with patch(SLEEP_TARGET) as mock_sleep:
        yield mock_sleep


def test_translate_posts_to_google_with_header_key(sleep) -> None:
    with patch(POST_TARGET, return_value=ok("Hello world")) as post:
        result = TranslationAdapter().translate("Hola mundo", "inglés")

    assert result == "Hello world"
    post.assert_called_once_with(
        TRANSLATE_URL,
        json={"q": "Hola mundo", "source": "es", "target": "en", "format": "text"},
        headers={
            "x-goog-api-key": API_KEY,
            "Content-Type": "application/json; charset=utf-8",
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    assert TRANSLATE_URL == "https://translation.googleapis.com/language/translate/v2"
    assert API_KEY not in post.call_args.args[0]
    assert "params" not in post.call_args.kwargs
    sleep.assert_not_called()


def test_translate_accepts_language_code() -> None:
    with patch(POST_TARGET, return_value=ok("Bonjour")) as post:
        assert TranslationAdapter().translate("Hola", "fr") == "Bonjour"

    assert post.call_args.kwargs["json"]["target"] == "fr"


@pytest.mark.parametrize("value", [None, "", "   "])
def test_translate_requires_api_key(monkeypatch, value) -> None:
    if value is None:
        monkeypatch.delenv("GOOGLE_TRANSLATE_API_KEY", raising=False)
    else:
        monkeypatch.setenv("GOOGLE_TRANSLATE_API_KEY", value)

    with patch(POST_TARGET) as post:
        with pytest.raises(WikiEnrichmentError, match="GOOGLE_TRANSLATE_API_KEY"):
            TranslationAdapter().translate("Hola", "en")
    post.assert_not_called()


def test_translate_returns_blank_text_without_calling_the_api() -> None:
    with patch(POST_TARGET) as post:
        assert TranslationAdapter().translate("  \n ", "en") == "  \n "
    post.assert_not_called()


def test_translate_converts_timeout_to_domain_error() -> None:
    with patch(POST_TARGET, side_effect=requests.Timeout):
        with pytest.raises(ProviderTimeoutError, match="Google Translate"):
            TranslationAdapter().translate("Hola", "en")


def test_translate_converts_request_failure_to_domain_error() -> None:
    with patch(POST_TARGET, side_effect=requests.ConnectionError):
        with pytest.raises(WikiEnrichmentError, match="Could not reach Google Translate"):
            TranslationAdapter().translate("Hola", "en")


def test_translate_reports_403_with_hint_and_redacted_details(monkeypatch, sleep) -> None:
    secret = "AIza-secret-value"
    monkeypatch.setenv("GOOGLE_TRANSLATE_API_KEY", secret)
    response = google_error(
        403,
        f"Requests are blocked for {secret}; token=private-value",
        "PERMISSION_DENIED",
        "forbidden",
    )

    with patch(POST_TARGET, return_value=response) as post:
        with pytest.raises(WikiEnrichmentError) as error:
            TranslationAdapter().translate("Hola", "en")

    message = str(error.value)
    assert message.startswith("Google Translate returned HTTP 403 (permission denied")
    assert "Cloud Translation API is enabled" in message
    assert "[REDACTED]" in message
    assert "token=[REDACTED]" in message
    assert "[PERMISSION_DENIED; forbidden]" in message
    assert secret not in message
    assert "private-value" not in message
    post.assert_called_once()
    sleep.assert_not_called()


def test_translate_reports_invalid_key_reason_from_details(sleep) -> None:
    response = make_response(
        {
            "error": {
                "code": 400,
                "message": "API key not valid. Please pass a valid API key.",
                "status": "INVALID_ARGUMENT",
                "details": [{"reason": "API_KEY_INVALID"}, "ignored"],
            }
        },
        status_code=400,
    )

    with patch(POST_TARGET, return_value=response) as post:
        with pytest.raises(WikiEnrichmentError) as error:
            TranslationAdapter().translate("Hola", "en")

    assert str(error.value) == (
        "Google Translate returned HTTP 400 (bad request): API key not valid. "
        "Please pass a valid API key. [INVALID_ARGUMENT; API_KEY_INVALID]"
    )
    post.assert_called_once()
    sleep.assert_not_called()


@pytest.mark.parametrize("status", [429, 500, 503])
def test_translate_retries_transient_errors_then_succeeds(sleep, status) -> None:
    responses = [make_response(status_code=status, json_error=ValueError()), ok("Hello")]

    with patch(POST_TARGET, side_effect=responses) as post:
        assert TranslationAdapter().translate("Hola", "en") == "Hello"

    assert post.call_count == 2
    sleep.assert_called_once_with(translation.RETRY_BACKOFF_SECONDS)


def test_translate_honours_capped_retry_after_header(sleep) -> None:
    responses = [
        make_response(status_code=429, headers={"Retry-After": "3"}, json_error=ValueError()),
        make_response(status_code=429, headers={"Retry-After": "999"}, json_error=ValueError()),
        ok("Hello"),
    ]

    with patch(POST_TARGET, side_effect=responses):
        assert TranslationAdapter().translate("Hola", "en") == "Hello"

    assert [call.args[0] for call in sleep.call_args_list] == [
        3.0,
        translation.MAX_RETRY_DELAY_SECONDS,
    ]


def test_translate_gives_up_after_max_retries_on_429(sleep) -> None:
    response = google_error(
        429, "Quota exceeded for quota metric", "RESOURCE_EXHAUSTED", "rateLimitExceeded"
    )

    with patch(POST_TARGET, return_value=response) as post:
        with pytest.raises(WikiEnrichmentError) as error:
            TranslationAdapter().translate("Hola", "en")

    assert str(error.value).startswith(
        "Google Translate returned HTTP 429 (quota or rate limit exceeded"
    )
    assert "Quota exceeded" in str(error.value)
    assert post.call_count == MAX_RETRIES + 1
    assert sleep.call_count == MAX_RETRIES


def test_translate_reports_5xx_as_service_unavailable(sleep) -> None:
    response = make_response(status_code=502, json_error=ValueError("html page"))

    with patch(POST_TARGET, return_value=response):
        with pytest.raises(WikiEnrichmentError) as error:
            TranslationAdapter().translate("Hola", "en")

    assert str(error.value) == (
        "Google Translate returned HTTP 502 (service unavailable; try again later)"
    )


def test_translate_reports_unmapped_status_without_hint(sleep) -> None:
    response = make_response({"error": "Not Found"}, status_code=404)

    with patch(POST_TARGET, return_value=response):
        with pytest.raises(WikiEnrichmentError) as error:
            TranslationAdapter().translate("Hola", "en")

    assert str(error.value) == "Google Translate returned HTTP 404: Not Found"


@pytest.mark.parametrize("payload", [["not", "a", "dict"], {"error": 7}])
def test_translate_reports_status_when_error_body_is_unexpected(sleep, payload) -> None:
    with patch(POST_TARGET, return_value=make_response(payload, status_code=400)):
        with pytest.raises(WikiEnrichmentError) as error:
            TranslationAdapter().translate("Hola", "en")

    assert str(error.value) == "Google Translate returned HTTP 400 (bad request)"


def test_translate_surfaces_provider_error_in_successful_http_response() -> None:
    response = make_response(
        {"error": {"code": 400, "message": "Invalid Value", "status": "INVALID_ARGUMENT"}}
    )

    with patch(POST_TARGET, return_value=response):
        with pytest.raises(WikiEnrichmentError) as error:
            TranslationAdapter().translate("Hola", "en")

    assert str(error.value) == (
        "Google Translate rejected the request: Invalid Value [INVALID_ARGUMENT] (code 400)"
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"data": {"translations": []}},
        {"data": {"translations": {"translatedText": "Hello"}}},
        {"data": {"translations": [{"translatedText": "A"}, {"translatedText": "B"}]}},
        {"data": {"translations": [{"translatedText": ""}]}},
        {"data": {"translations": [{"translatedText": None}]}},
        {"data": {"translations": ["Hello"]}},
        {"data": None},
        {},
        None,
        ["Hello"],
    ],
)
def test_translate_rejects_invalid_response(payload) -> None:
    with patch(POST_TARGET, return_value=make_response(payload)):
        with pytest.raises(WikiEnrichmentError, match="Invalid Google Translate response"):
            TranslationAdapter().translate("Hola", "en")


def test_translate_rejects_non_json_response() -> None:
    response = make_response(json_error=ValueError("not json"))

    with patch(POST_TARGET, return_value=response):
        with pytest.raises(WikiEnrichmentError, match="Invalid Google Translate response"):
            TranslationAdapter().translate("Hola", "en")


def test_translate_splits_long_text_and_preserves_separators(monkeypatch) -> None:
    monkeypatch.setattr(translation, "MAX_CHARS_PER_REQUEST", 20)
    text = "Uno dos tres.\n\nCuatro cinco seis.\nSiete."
    sent: list[str] = []

    def fake_post(url, json, **kwargs):
        sent.append(json["q"])
        return ok(json["q"].upper())

    with patch(POST_TARGET, side_effect=fake_post):
        result = TranslationAdapter().translate(text, "en")

    assert sent == ["Uno dos tres.", "Cuatro cinco seis.", "Siete."]
    assert result == "UNO DOS TRES.\n\nCUATRO CINCO SEIS.\nSIETE."


def test_translate_keeps_whitespace_only_chunks_without_calling_the_api(monkeypatch) -> None:
    monkeypatch.setattr(translation, "MAX_CHARS_PER_REQUEST", 4)

    with patch(POST_TARGET, return_value=ok("Hi")) as post:
        assert TranslationAdapter().translate("\n\nHola", "en") == "\n\nHi"

    post.assert_called_once()
    assert post.call_args.kwargs["json"]["q"] == "Hola"


def test_chunk_text_reassembles_exactly_and_respects_limit() -> None:
    paragraph = "Primera frase larga aquí. Segunda frase también larga! " * 3
    word = "x" * 45
    text = f"Corto.\n\n{paragraph}\n{word}\nFin."

    chunks = translation._chunk_text(text, 40)

    assert "".join(chunks) == text
    assert all(len(chunk) <= 40 for chunk in chunks)
    assert len(chunks) > 3


def test_chunk_text_keeps_short_text_in_one_chunk() -> None:
    text = "Hola.\nAdiós."
    assert translation._chunk_text(text, translation.MAX_CHARS_PER_REQUEST) == [text]
