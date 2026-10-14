"""DeepTranslate adapter for translating application text."""

import os
import re

import requests

from wiki_enrichment.domain.exceptions import ProviderTimeoutError, WikiEnrichmentError

TRANSLATE_URL = "https://deep-translate1.p.rapidapi.com/language/translate/v2"
RAPIDAPI_HOST = "deep-translate1.p.rapidapi.com"
REQUEST_TIMEOUT_SECONDS = 15
MAX_ERROR_DETAIL_LENGTH = 300


def _safe_error_detail(response: requests.Response, api_key: str) -> str:
    """Extract a short provider message without exposing credential-like data."""

    try:
        body = response.json()
    except (ValueError, requests.RequestException):
        return ""

    candidates = []

    def collect(value: object) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key.casefold() in {"message", "error", "detail", "description"}:
                    collect(item)
        elif isinstance(value, (str, int, float)):
            candidates.append(str(value))

    collect(body)
    detail = "; ".join(candidates)
    if api_key:
        detail = detail.replace(api_key, "[REDACTED]")
    detail = re.sub(
        r"(?i)\b(bearer\s+)\S+|\b(api[_-]?key|token|secret|password)\s*[:=]\s*\S+",
        lambda match: f"{match.group(1) or match.group(2) + '='}[REDACTED]",
        detail,
    )
    return detail[:MAX_ERROR_DETAIL_LENGTH]


def _extract_translated_text(body: object) -> str:
    """Return translated text from a Deep Translate v2 JSON body."""

    if not isinstance(body, dict):
        raise WikiEnrichmentError("Invalid DeepTranslate response")

    if "error" in body:
        detail = _safe_error_detail_from_body(body)
        message = "DeepTranslate rejected the request"
        if detail:
            message += f": {detail}"
        raise WikiEnrichmentError(message)

    try:
        translations = body["data"]["translations"]
    except (KeyError, TypeError) as exc:
        raise WikiEnrichmentError("Invalid DeepTranslate response") from exc

    if isinstance(translations, list):
        if not translations:
            raise WikiEnrichmentError("Invalid DeepTranslate response")
        first = translations[0]
        if not isinstance(first, dict):
            raise WikiEnrichmentError("Invalid DeepTranslate response")
        translated_text = first.get("translatedText")
    elif isinstance(translations, dict):
        translated_text = translations.get("translatedText")
    else:
        raise WikiEnrichmentError("Invalid DeepTranslate response")

    if not isinstance(translated_text, str) or not translated_text:
        raise WikiEnrichmentError("Invalid DeepTranslate response")
    return translated_text


def _safe_error_detail_from_body(body: dict) -> str:
    """Collect a short error message from a provider JSON error object."""

    candidates: list[str] = []

    def collect(value: object) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key.casefold() in {"message", "error", "detail", "description"}:
                    collect(item)
        elif isinstance(value, (str, int, float)):
            candidates.append(str(value))

    collect(body.get("error", body))
    return "; ".join(candidates)[:MAX_ERROR_DETAIL_LENGTH]


LANGUAGE_CODES = {
    "alemán": "de",
    "aleman": "de",
    "catalán": "ca",
    "catalan": "ca",
    "español": "es",
    "espanol": "es",
    "francés": "fr",
    "frances": "fr",
    "inglés": "en",
    "ingles": "en",
    "italiano": "it",
    "japonés": "ja",
    "japones": "ja",
    "portugués": "pt",
    "portugues": "pt",
}


class TranslationAdapter:
    """Translate text through the project's DeepTranslate RapidAPI provider."""

    def translate(self, text: str, target_lang: str) -> str:
        """Translate text into the requested language or raise a domain error."""

        api_key = os.getenv("RAPIDAPI_KEY")
        if not api_key:
            raise WikiEnrichmentError(
                "DeepTranslate is not configured. Set the RAPIDAPI_KEY environment variable."
            )

        target_code = LANGUAGE_CODES.get(target_lang.strip().casefold(), target_lang.strip())
        headers = {
            "x-rapidapi-key": api_key,
            "x-rapidapi-host": RAPIDAPI_HOST,
            "Content-Type": "application/json",
        }
        payload = {"q": text, "source": "es", "target": target_code}

        try:
            response = requests.post(
                TRANSLATE_URL,
                json=payload,
                headers=headers,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.Timeout as exc:
            raise ProviderTimeoutError("DeepTranslate took too long to respond") from exc
        except requests.HTTPError as exc:
            failed_response = exc.response
            status = failed_response.status_code if failed_response is not None else "unknown"
            detail = (
                _safe_error_detail(failed_response, api_key)
                if failed_response is not None
                else ""
            )
            message = f"DeepTranslate returned HTTP {status}"
            if detail:
                message += f": {detail}"
            raise WikiEnrichmentError(message) from exc
        except requests.RequestException as exc:
            raise WikiEnrichmentError("Could not reach DeepTranslate") from exc

        try:
            body = response.json()
        except ValueError as exc:
            raise WikiEnrichmentError("Invalid DeepTranslate response") from exc

        return _extract_translated_text(body)
