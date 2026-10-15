"""Hugging Face adapter implementing the ContentEnricher port."""

import os

from dotenv import load_dotenv
from huggingface_hub import InferenceClient

from wiki_enrichment.domain.exceptions import (
    EnrichmentError,
    ProviderTimeoutError,
)
from wiki_enrichment.domain.models import ArticleContent, EnrichedContent

load_dotenv()

SYSTEM_PROMPT = (
    "You summarize and enrich encyclopedia articles. "
    "Write in the same language as the article, stay faithful to its content "
    "and do not invent facts."
)


class HuggingFaceEnricher:
    """Enrich an article with an AI-generated summary using Hugging Face."""

    def __init__(
        self,
        model: str,
        token: str | None = None,
        timeout: float = 60.0,
        max_tokens: int = 600,
        client: InferenceClient | None = None,
    ) -> None:
        self._model = model
        self._max_tokens = max_tokens
        if client is not None:
            self._client = client
            return
        api_key = token or os.getenv("HF_TOKEN")
        if not api_key:
            raise EnrichmentError("HF_TOKEN is not set. Add it to your .env file.")
        self._client = InferenceClient(api_key=api_key, timeout=timeout)

    def enrich(self, article: ArticleContent) -> EnrichedContent:
        """Generate an AI summary for the given article."""

        if not article.full_text.strip():
            raise EnrichmentError("Cannot enrich an article without text.")

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Title: {article.title}\n\n"
                    f"Write a clear, enriched summary of this article:\n\n"
                    f"{article.full_text}"
                ),
            },
        ]

        try:
            response = self._client.chat_completion(
                messages=messages,
                model=self._model,
                max_tokens=self._max_tokens,
            )
        except TimeoutError as error:
            raise ProviderTimeoutError("Hugging Face request timed out.") from error
        except Exception as error:
            raise EnrichmentError(f"AI enrichment failed: {error}") from error

        summary = (response.choices[0].message.content or "").strip()
        if not summary:
            raise EnrichmentError("The AI provider returned an empty summary.")

        return EnrichedContent(original_article=article, ai_summary=summary)