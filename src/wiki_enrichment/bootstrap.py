"""Composition root: the only place where concrete adapters are created."""

import os
from pathlib import Path

from wiki_enrichment.application.use_cases import WikiEnrichmentOrchestrator
from wiki_enrichment.infrastructure.ai import AIContentEnricher
from wiki_enrichment.infrastructure.exporters import DocumentExporterAdapter
from wiki_enrichment.infrastructure.translation import TranslationAdapter
from wiki_enrichment.infrastructure.wikipedia import WikipediaSourceAdapter


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
        content_enricher=AIContentEnricher(),
        translator=TranslationAdapter(),
        document_exporter=DocumentExporterAdapter(),
    )
