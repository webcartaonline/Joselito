"""DeepTranslate adapter for translating application text."""

import os
import re

import requests

from wiki_enrichment.domain.exceptions import ProviderTimeoutError, WikiEnrichmentError

TRANSLATE_URL = "https://deep-translate1.p.rapidapi.com/language/translate/v2"
RAPIDAPI_HOST = "deep-translate1.p.rapidapi.com"
TRANSLATE_URL_V4 = "https://deep-translate4.p.rapidapi.com/v3/translate"
RAPIDAPI_HOST_V4 = "deep-translate4.p.rapidapi.com"
SOURCE_LANGUAGE = "es"
REQUEST_TIMEOUT_SECONDS = 15
MAX_ERROR_DETAIL_LENGTH = 300
DEEP_TRANSLATE1_OUTAGE_CODES = {520}


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


def _provider_error_code(body: dict) -> int | None:
    """Return a numeric provider error code when the payload includes one."""

    error = body.get("error")
    if not isinstance(error, dict):
        return None
    code = error.get("code")
    return code if isinstance(code, int) else None


def _format_provider_rejection(body: dict) -> WikiEnrichmentError:
    """Build a domain error for a provider JSON error object."""

    detail = _safe_error_detail_from_body(body)
    message = "DeepTranslate rejected the request"
    if detail:
        message += f": {detail}"
    code = _provider_error_code(body)
    if code is not None:
        message += f" (code {code})"
    return WikiEnrichmentError(message)


def _extract_translated_text(body: object) -> str:
    """Return translated text from a Deep Translate v2 JSON body."""

    if not isinstance(body, dict):
        raise WikiEnrichmentError("Invalid DeepTranslate response")

    if "error" in body:
        raise _format_provider_rejection(body)

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


def _extract_deep_translate4_text(body: object) -> str:
    """Return translated text from a Deep Translate 4 JSON body."""

    if isinstance(body, list):
        if len(body) >= 2 and isinstance(body[0], int):
            if body[0] >= 400:
                detail = body[1] if isinstance(body[1], str) else str(body[1])
                raise WikiEnrichmentError(
                    f"DeepTranslate rejected the request: {detail} (code {body[0]})"
                )
            if body[0] == 200 and isinstance(body[1], str) and body[1].strip():
                return body[1]
        try:
            nested = body[0][0][0]
        except (IndexError, TypeError) as exc:
            raise WikiEnrichmentError("Invalid DeepTranslate response") from exc
        if isinstance(nested, str) and nested.strip():
            return nested
        raise WikiEnrichmentError("Invalid DeepTranslate response")

    if isinstance(body, dict):
        status = body.get("status")
        if isinstance(status, int) and status >= 400:
            detail = body.get("message")
            message = "DeepTranslate rejected the request"
            if isinstance(detail, str) and detail:
                message += f": {detail}"
            message += f" (code {status})"
            raise WikiEnrichmentError(message)
        for key in ("translatedText", "translation", "result", "text", "data"):
            value = body.get(key)
            if isinstance(value, str) and value.strip():
                return value

    raise WikiEnrichmentError("Invalid DeepTranslate response")


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


def _should_fallback_to_deep_translate4(error: WikiEnrichmentError) -> bool:
    """Return True when Deep Translate 1 failed due to a recoverable provider outage."""

    message = str(error)
    if "(code 520)" in message or "Service Error" in message:
        return True
    for code in DEEP_TRANSLATE1_OUTAGE_CODES:
        if f"(code {code})" in message:
            return True
    return False


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

        try:
            return self._translate_deep_translate1(text, target_code, api_key)
        except WikiEnrichmentError as exc:
            if _should_fallback_to_deep_translate4(exc):
                return self._translate_deep_translate4(text, target_code, api_key)
            raise

    def _translate_deep_translate1(self, text: str, target_code: str, api_key: str) -> str:
        headers = {
            "x-rapidapi-key": api_key,
            "x-rapidapi-host": RAPIDAPI_HOST,
            "Content-Type": "application/json",
        }
        payload = {
            "q": text,
            "source": SOURCE_LANGUAGE,
            "target": target_code,
            "format": "text",
        }

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

    def _translate_deep_translate4(self, text: str, target_code: str, api_key: str) -> str:
        headers = {
            "x-rapidapi-key": api_key,
            "x-rapidapi-host": RAPIDAPI_HOST_V4,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        payload = {
            "sl": SOURCE_LANGUAGE,
            "tl": target_code,
            "text": text,
        }

        try:
            response = requests.post(
                TRANSLATE_URL_V4,
                data=payload,
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

        return _extract_deep_translate4_text(body)
