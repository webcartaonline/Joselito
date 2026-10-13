"""Hugging Face adapter implementing the ContentSummarizer port."""

import os

from dotenv import load_dotenv
from huggingface_hub import InferenceClient

from wiki_enrichment.domain.exceptions import (
    ProviderTimeoutError,
    SummarizationError,
)

load_dotenv()

SYSTEM_PROMPT = (
    "You write very brief summaries. Use three or four sentences, write in "
    "the same language as the text, stay faithful to it and do not invent "
    "facts."
)


class HuggingFaceSummarizer:
    """Generate a brief summary of a text using Hugging Face."""

    def __init__(
        self,
        model: str,
        token: str | None = None,
        timeout: float = 60.0,
        max_tokens: int = 200,
        client: InferenceClient | None = None,
    ) -> None:
        self._model = model
        self._max_tokens = max_tokens
        if client is not None:
            self._client = client
            return
        api_key = token or os.getenv("HF_TOKEN")
        if not api_key:
            raise SummarizationError("HF_TOKEN is not set. Add it to your .env file.")
        self._client = InferenceClient(api_key=api_key, timeout=timeout)

    def summarize(self, text: str) -> str:
        """Generate a brief summary for the given text."""

        if not text.strip():
            raise SummarizationError("Cannot summarize an empty text.")

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Summarize this text briefly: {text}"},
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
            raise SummarizationError(f"AI summarization failed: {error}") from error

        summary = (response.choices[0].message.content or "").strip()
        if not summary:
            raise SummarizationError("The AI provider returned an empty summary.")

        return summary