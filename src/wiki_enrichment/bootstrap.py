"""Composition root: the only place where concrete adapters are created."""

import os
from pathlib import Path

from dotenv import load_dotenv

from wiki_enrichment.application.use_cases import WikiEnrichmentOrchestrator
from wiki_enrichment.domain.exceptions import EnrichmentError, SummarizationError
from wiki_enrichment.domain.ports import ContentEnricher, ContentSummarizer
from wiki_enrichment.infrastructure.ai import AIContentEnricher, AIContentSummarizer
from wiki_enrichment.infrastructure.deepseek_enricher import (
    BASE_URL_VARIABLE as DEEPSEEK_BASE_URL_VARIABLE,
)
from wiki_enrichment.infrastructure.deepseek_enricher import (
    DEFAULT_BASE_URL as DEEPSEEK_DEFAULT_BASE_URL,
)
from wiki_enrichment.infrastructure.deepseek_enricher import (
    DEFAULT_MODEL as DEEPSEEK_DEFAULT_MODEL,
)
from wiki_enrichment.infrastructure.deepseek_enricher import (
    MODEL_VARIABLE as DEEPSEEK_MODEL_VARIABLE,
)
from wiki_enrichment.infrastructure.deepseek_enricher import DeepSeekEnricher
from wiki_enrichment.infrastructure.deepseek_summarizer import (
    BASE_URL_VARIABLE as DEEPSEEK_SUMMARIZER_BASE_URL_VARIABLE,
)
from wiki_enrichment.infrastructure.deepseek_summarizer import (
    DEFAULT_BASE_URL as DEEPSEEK_SUMMARIZER_DEFAULT_BASE_URL,
)
from wiki_enrichment.infrastructure.deepseek_summarizer import (
    DEFAULT_MODEL as DEEPSEEK_SUMMARIZER_DEFAULT_MODEL,
)
from wiki_enrichment.infrastructure.deepseek_summarizer import (
    FALLBACK_MODEL_VARIABLE as DEEPSEEK_SUMMARIZER_FALLBACK_VARIABLE,
)
from wiki_enrichment.infrastructure.deepseek_summarizer import (
    MODEL_VARIABLE as DEEPSEEK_SUMMARIZER_MODEL_VARIABLE,
)
from wiki_enrichment.infrastructure.deepseek_summarizer import DeepSeekSummarizer
from wiki_enrichment.infrastructure.exporters import DocumentExporterAdapter
from wiki_enrichment.infrastructure.translation import TranslationAdapter
from wiki_enrichment.infrastructure.wikipedia import WikipediaSourceAdapter

# Cargar el .env lo antes posible: no sobrescribe variables ya existentes
# en el entorno (Windows, PyCharm, VS Code), que tienen prioridad.
load_dotenv()


def build_content_enricher() -> ContentEnricher:
    """Return the DeepSeek enricher, or a fallback if it cannot be configured.

    The model can be changed with DEEPSEEK_MODEL and the endpoint with
    DEEPSEEK_BASE_URL in the .env file.
    """

    try:
        return DeepSeekEnricher(
            model=os.getenv(DEEPSEEK_MODEL_VARIABLE) or DEEPSEEK_DEFAULT_MODEL,
            base_url=os.getenv(DEEPSEEK_BASE_URL_VARIABLE)
            or DEEPSEEK_DEFAULT_BASE_URL,
        )
    except EnrichmentError as error:
        return AIContentEnricher(reason=str(error))


def build_content_summarizer() -> ContentSummarizer:
    """Return the DeepSeek summarizer, or a fallback if it cannot be configured.

    It uses DEEPSEEK_SUMMARIZER_MODEL, then DEEPSEEK_MODEL, then the default.
    The model must support chat completion.
    """

    try:
        return DeepSeekSummarizer(
            model=os.getenv(DEEPSEEK_SUMMARIZER_MODEL_VARIABLE)
            or os.getenv(DEEPSEEK_SUMMARIZER_FALLBACK_VARIABLE)
            or DEEPSEEK_SUMMARIZER_DEFAULT_MODEL,
            base_url=os.getenv(DEEPSEEK_SUMMARIZER_BASE_URL_VARIABLE)
            or DEEPSEEK_SUMMARIZER_DEFAULT_BASE_URL,
        )
    except SummarizationError as error:
        return AIContentSummarizer(reason=str(error))
def _load_local_env_file() -> None:
    """Load a project-root `.env` file without overriding existing variables."""

    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def build_orchestrator(wikipedia_language: str = "es") -> WikiEnrichmentOrchestrator:
    """Wire the concrete adapters into the application use case."""

    _load_local_env_file()

    return WikiEnrichmentOrchestrator(
        wikipedia_source=WikipediaSourceAdapter(language=wikipedia_language),
        content_enricher=build_content_enricher(),
        translator=TranslationAdapter(),
        document_exporter=DocumentExporterAdapter(),
        content_summarizer=build_content_summarizer(),
    )
