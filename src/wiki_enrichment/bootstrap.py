"""Composition root: the only place where concrete adapters are created."""

from wiki_enrichment.application.use_cases import WikiEnrichmentOrchestrator
from wiki_enrichment.infrastructure.ai import AIContentEnricher
from wiki_enrichment.infrastructure.exporters import DocumentExporterAdapter
from wiki_enrichment.infrastructure.translation import TranslationAdapter
from wiki_enrichment.infrastructure.wikipedia import WikipediaSourceAdapter


def build_orchestrator(wikipedia_language: str = "es") -> WikiEnrichmentOrchestrator:
    """Wire the concrete adapters into the application use case."""

    return WikiEnrichmentOrchestrator(
        wikipedia_source=WikipediaSourceAdapter(language=wikipedia_language),
        content_enricher=AIContentEnricher(),
        translator=TranslationAdapter(),
        document_exporter=DocumentExporterAdapter(),
    )
