"""Google Cloud Translation (Basic v2) adapter for translating application text."""

import os
import re
import time

import requests

from wiki_enrichment.domain.exceptions import ProviderTimeoutError, WikiEnrichmentError

TRANSLATE_URL = "https://translation.googleapis.com/language/translate/v2"
API_KEY_ENV_VAR = "GOOGLE_TRANSLATE_API_KEY"
PROVIDER_NAME = "Google Translate"
SOURCE_LANGUAGE = "es"
REQUEST_TIMEOUT_SECONDS = (5, 30)
MAX_CHARS_PER_REQUEST = 5000
MAX_RETRIES = 2
RETRY_BACKOFF_SECONDS = 1.0
MAX_RETRY_DELAY_SECONDS = 10.0
MAX_ERROR_DETAIL_LENGTH = 300

STATUS_HINTS = {
    400: "bad request",
    401: "unauthenticated: check the API key",
    403: (
        "permission denied: check the API key, its restrictions, and that the "
        "Cloud Translation API is enabled"
    ),
    429: "quota or rate limit exceeded; try again later",
}
SERVER_ERROR_HINT = "service unavailable; try again later"

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


def _redact(detail: str, api_key: str) -> str:
    """Remove credential-like data from a provider message and shorten it."""

    if api_key:
        detail = detail.replace(api_key, "[REDACTED]")
    detail = re.sub(
        r"(?i)\b(bearer\s+)\S+|\b(api[_-]?key|token|secret|password)\s*[:=]\s*\S+",
        lambda match: f"{match.group(1) or match.group(2) + '='}[REDACTED]",
        detail,
    )
    return detail[:MAX_ERROR_DETAIL_LENGTH]


def _google_error_detail(body: object, api_key: str) -> str:
    """Summarize a Google API error object as `message [STATUS; REASON]`."""

    if not isinstance(body, dict):
        return ""
    error = body.get("error")
    if isinstance(error, str):
        return _redact(error, api_key)
    if not isinstance(error, dict):
        return ""

    message = error.get("message")
    tags: list[str] = []
    status = error.get("status")
    if isinstance(status, str) and status:
        tags.append(status)
    for key in ("errors", "details"):
        items = error.get(key)
        if isinstance(items, list):
            for item in items:
                reason = item.get("reason") if isinstance(item, dict) else None
                if isinstance(reason, str) and reason and reason not in tags:
                    tags.append(reason)

    detail = message if isinstance(message, str) else ""
    if tags:
        detail = f"{detail} [{'; '.join(tags)}]".strip()
    return _redact(detail, api_key)


def _response_error_detail(response: requests.Response, api_key: str) -> str:
    try:
        body = response.json()
    except (ValueError, requests.RequestException):
        return ""
    return _google_error_detail(body, api_key)


def _http_error(response: requests.Response, api_key: str) -> WikiEnrichmentError:
    status = response.status_code
    hint = SERVER_ERROR_HINT if status >= 500 else STATUS_HINTS.get(status)
    message = f"{PROVIDER_NAME} returned HTTP {status}"
    if hint:
        message += f" ({hint})"
    detail = _response_error_detail(response, api_key)
    if detail:
        message += f": {detail}"
    return WikiEnrichmentError(message)


def _is_retryable(status: int) -> bool:
    return status == 429 or status >= 500


def _retry_delay(response: requests.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After") if response.headers else None
    if isinstance(retry_after, str) and retry_after.strip().isdigit():
        return min(float(retry_after.strip()), MAX_RETRY_DELAY_SECONDS)
    return min(RETRY_BACKOFF_SECONDS * 2**attempt, MAX_RETRY_DELAY_SECONDS)


def _extract_translated_text(body: object, api_key: str) -> str:
    """Return translated text from a Google Translation v2 JSON body."""

    if not isinstance(body, dict):
        raise WikiEnrichmentError(f"Invalid {PROVIDER_NAME} response")

    if "error" in body:
        message = f"{PROVIDER_NAME} rejected the request"
        detail = _google_error_detail(body, api_key)
        if detail:
            message += f": {detail}"
        error = body["error"]
        code = error.get("code") if isinstance(error, dict) else None
        if isinstance(code, int):
            message += f" (code {code})"
        raise WikiEnrichmentError(message)

    data = body.get("data")
    translations = data.get("translations") if isinstance(data, dict) else None
    if not isinstance(translations, list) or len(translations) != 1:
        raise WikiEnrichmentError(f"Invalid {PROVIDER_NAME} response")
    first = translations[0]
    translated_text = first.get("translatedText") if isinstance(first, dict) else None
    if not isinstance(translated_text, str) or not translated_text.strip():
        raise WikiEnrichmentError(f"Invalid {PROVIDER_NAME} response")
    return translated_text


def _hard_split(token: str, limit: int) -> list[str]:
    """Cut an oversized token into slices, preferring whitespace boundaries."""

    pieces = []
    while len(token) > limit:
        cut = token.rfind(" ", 0, limit)
        if cut <= 0:
            cut = limit
        pieces.append(token[:cut])
        token = token[cut:]
    if token:
        pieces.append(token)
    return pieces


def _chunk_text(text: str, limit: int) -> list[str]:
    """Split text into chunks of at most `limit` characters.

    Concatenating the chunks reproduces the original text exactly. Breaks are
    made on line breaks first, then sentence ends, then whitespace.
    """

    tokens: list[str] = []
    for paragraph in re.split(r"(\n+)", text):
        if len(paragraph) <= limit:
            tokens.append(paragraph)
            continue
        for sentence in re.split(r"(?<=[.!?])(\s+)", paragraph):
            tokens.extend(_hard_split(sentence, limit))

    chunks: list[str] = []
    current = ""
    for token in tokens:
        if not token:
            continue
        if len(current) + len(token) > limit and current:
            chunks.append(current)
            current = ""
        current += token
    if current:
        chunks.append(current)
    return chunks


class TranslationAdapter:
    """Translate text through Google Cloud Translation Basic (v2)."""

    def translate(self, text: str, target_lang: str) -> str:
        """Translate text into the requested language or raise a domain error."""

        api_key = os.getenv(API_KEY_ENV_VAR, "").strip()
        if not api_key:
            raise WikiEnrichmentError(
                f"{PROVIDER_NAME} is not configured. "
                f"Set the {API_KEY_ENV_VAR} environment variable."
            )

        target_code = LANGUAGE_CODES.get(target_lang.strip().casefold(), target_lang.strip())

        if not text.strip():
            return text

        return "".join(
            self._translate_chunk(chunk, target_code, api_key)
            for chunk in _chunk_text(text, MAX_CHARS_PER_REQUEST)
        )

    def _translate_chunk(self, chunk: str, target_code: str, api_key: str) -> str:
        core = chunk.strip()
        if not core:
            return chunk
        leading = chunk[: len(chunk) - len(chunk.lstrip())]
        trailing = chunk[len(chunk.rstrip()) :]
        return leading + self._request_translation(core, target_code, api_key) + trailing

    def _request_translation(self, text: str, target_code: str, api_key: str) -> str:
        headers = {
            "x-goog-api-key": api_key,
            "Content-Type": "application/json; charset=utf-8",
        }
        payload = {
            "q": text,
            "source": SOURCE_LANGUAGE,
            "target": target_code,
            "format": "text",
        }

        for attempt in range(MAX_RETRIES + 1):
            try:
                response = requests.post(
                    TRANSLATE_URL,
                    json=payload,
                    headers=headers,
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
            except requests.Timeout as exc:
                raise ProviderTimeoutError(f"{PROVIDER_NAME} took too long to respond") from exc
            except requests.RequestException as exc:
                raise WikiEnrichmentError(f"Could not reach {PROVIDER_NAME}") from exc

            status = response.status_code
            if status < 400:
                break
            if _is_retryable(status) and attempt < MAX_RETRIES:
                time.sleep(_retry_delay(response, attempt))
                continue
            raise _http_error(response, api_key)

        try:
            body = response.json()
        except ValueError as exc:
            raise WikiEnrichmentError(f"Invalid {PROVIDER_NAME} response") from exc

        return _extract_translated_text(body, api_key)
