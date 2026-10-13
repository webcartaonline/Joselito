"""DeepTranslate adapter for translating application text."""

import os

import requests

from wiki_enrichment.domain.exceptions import ProviderTimeoutError, WikiEnrichmentError

TRANSLATE_URL = "https://deep-translate1.p.rapidapi.com/language/translate/v2"
RAPIDAPI_HOST = "deep-translate1.p.rapidapi.com"
REQUEST_TIMEOUT_SECONDS = 15

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
        except requests.RequestException as exc:
            raise WikiEnrichmentError("Could not reach DeepTranslate") from exc

        try:
            translated_text = response.json()["data"]["translations"]["translatedText"]
        except (ValueError, KeyError, TypeError) as exc:
            raise WikiEnrichmentError("Invalid DeepTranslate response") from exc
        if not isinstance(translated_text, str) or not translated_text:
            raise WikiEnrichmentError("Invalid DeepTranslate response")
        return translated_text
