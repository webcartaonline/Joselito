"""DeepSeek adapter implementing the ContentSummarizer port.

Calls the OpenAI-compatible chat API (default ``https://api.deepseek.com/v1``)
so brief summaries work without Hugging Face credits.
"""

import os

import requests
from dotenv import load_dotenv

from wiki_enrichment.domain.exceptions import (
    ProviderTimeoutError,
    SummarizationError,
)

load_dotenv()

SYSTEM_PROMPT = (
    "Escribes resumenes muy breves. Usa tres o cuatro frases, responde "
    "siempre en espanol, se fiel al texto y no inventes datos."
)

API_KEY_VARIABLE = "DEEPSEEK_API_KEY"
MODEL_VARIABLE = "DEEPSEEK_SUMMARIZER_MODEL"
FALLBACK_MODEL_VARIABLE = "DEEPSEEK_MODEL"
BASE_URL_VARIABLE = "DEEPSEEK_BASE_URL"
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_BASE_URL = "https://api.deepseek.com/v1"


class DeepSeekSummarizer:
    """Generate a brief summary of a text using the DeepSeek API."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 60.0,
        max_tokens: int = 200,
    ) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_tokens = max_tokens
        key = api_key or os.getenv(API_KEY_VARIABLE)
        if not key:
            raise SummarizationError(
                f"{API_KEY_VARIABLE} is not set. Add it to your .env file."
            )
        self._api_key = key

    def summarize(self, text: str) -> str:
        """Generate a brief summary for the given text."""

        if not text.strip():
            raise SummarizationError("Cannot summarize an empty text.")

        try:
            response = requests.post(
                f"{self._base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": f"Resume brevemente este texto en espanol: {text}",
                        },
                    ],
                    "max_tokens": self._max_tokens,
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
            summary = (
                response.json()["choices"][0]["message"].get("content") or ""
            ).strip()
        except (requests.Timeout, TimeoutError) as error:
            raise ProviderTimeoutError("DeepSeek request timed out.") from error
        except SummarizationError:
            raise
        except Exception as error:
            raise SummarizationError(f"AI summarization failed: {error}") from error

        if not summary:
            raise SummarizationError("The AI provider returned an empty summary.")

        return summary
