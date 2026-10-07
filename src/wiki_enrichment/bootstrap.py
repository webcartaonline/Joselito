"""Composition root: the only place where concrete adapters are created."""

import os

from wiki_enrichment.application.use_cases import WikiEnrichmentOrchestrator
from wiki_enrichment.domain.exceptions import EnrichmentError
from wiki_enrichment.domain.ports import ContentEnricher
from wiki_enrichment.infrastructure.ai import AIContentEnricher
from wiki_enrichment.infrastructure.exporters import DocumentExporterAdapter
from wiki_enrichment.infrastructure.huggingface_enricher import HuggingFaceEnricher
from wiki_enrichment.infrastructure.translation import TranslationAdapter
from wiki_enrichment.infrastructure.wikipedia import WikipediaSourceAdapter

HF_MODEL_VARIABLE = "HF_MODEL"
DEFAULT_HF_MODEL = "openai/gpt-oss-120b"


def build_content_enricher() -> ContentEnricher:
    """Return the Hugging Face enricher, or a fallback if it cannot be configured.

    The model can be changed with the HF_MODEL variable in the .env file.
    """

    model = os.getenv(HF_MODEL_VARIABLE) or DEFAULT_HF_MODEL
    try:
        return HuggingFaceEnricher(model=model)
    except EnrichmentError as error:
        return AIContentEnricher(reason=str(error))


def build_orchestrator(wikipedia_language: str = "es") -> WikiEnrichmentOrchestrator:
    """Wire the concrete adapters into the application use case."""

    return WikiEnrichmentOrchestrator(
        wikipedia_source=WikipediaSourceAdapter(language=wikipedia_language),
        content_enricher=build_content_enricher(),
        translator=TranslationAdapter(),
        document_exporter=DocumentExporterAdapter(),
    )
