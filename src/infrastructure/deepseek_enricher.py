"""DeepSeek adapter implementing the ContentEnricher port.

Calls the OpenAI-compatible chat API (default ``https://api.deepseek.com/v1``)
so a DeepSeek API key (``sk-...``) can be used for enrichment without
Hugging Face credits.
"""

import os

import requests
from dotenv import load_dotenv

from domain.exceptions import (
    EnrichmentError,
    ProviderTimeoutError,
)
from domain.models import ArticleContent, EnrichedContent

load_dotenv()

SYSTEM_PROMPT = (
    "Resumes y enriqueces articulos de enciclopedia. "
    "Responde siempre en espanol, se fiel al contenido del articulo "
    "y no inventes datos."
)

API_KEY_VARIABLE = "DEEPSEEK_API_KEY"
MODEL_VARIABLE = "DEEPSEEK_MODEL"
BASE_URL_VARIABLE = "DEEPSEEK_BASE_URL"
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_BASE_URL = "https://api.deepseek.com/v1"

# Same cap as the Hugging Face enricher: full Wikipedia articles would
# waste money/time on every call.
MAX_ARTICLE_CHARS = 4000


class DeepSeekEnricher:
    """Enrich an article with an AI-generated summary using the DeepSeek API."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 60.0,
        max_tokens: int = 600,
    ) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_tokens = max_tokens
        key = api_key or os.getenv(API_KEY_VARIABLE)
        if not key:
            raise EnrichmentError(
                f"{API_KEY_VARIABLE} is not set. Add it to your .env file."
            )
        self._api_key = key

    def enrich(self, article: ArticleContent) -> EnrichedContent:
        """Generate an AI summary for the given article."""

        if not article.full_text.strip():
            raise EnrichmentError("Cannot enrich an article without text.")

        text = article.full_text.strip()
        if len(text) > MAX_ARTICLE_CHARS:
            text = text[:MAX_ARTICLE_CHARS] + "\n\n[Texto truncado para ahorrar coste de IA.]"

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
                            "content": (
                                f"Titulo: {article.title}\n\n"
                                f"Escribe en espanol un resumen claro y enriquecido "
                                f"de este articulo:\n\n"
                                f"{text}"
                            ),
                        },
                    ],
                    "max_tokens": self._max_tokens,
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
            content = (
                response.json()["choices"][0]["message"].get("content") or ""
            ).strip()
        except (requests.Timeout, TimeoutError) as error:
            raise ProviderTimeoutError("DeepSeek request timed out.") from error
        except Exception as error:
            raise EnrichmentError(f"AI enrichment failed: {error}") from error

        if not content:
            raise EnrichmentError("The AI provider returned an empty summary.")

        return EnrichedContent(original_article=article, ai_summary=content)
