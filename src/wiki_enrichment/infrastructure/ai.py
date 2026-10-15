"""Fallback content enricher used when no AI provider can be configured."""

from wiki_enrichment.domain.exceptions import EnrichmentError
from wiki_enrichment.domain.models import ArticleContent, EnrichedContent

NO_PROVIDER_REASON = "No AI provider is configured."


class AIContentEnricher:
    """Enricher that always fails with a clear reason (for example, a missing token).

    It lets the app start without AI and show a friendly message instead of crashing.
    """

    def __init__(self, reason: str = NO_PROVIDER_REASON) -> None:
        """Store why the AI provider is not available."""

        self._reason = reason

    def enrich(self, article: ArticleContent) -> EnrichedContent:
        """Raise an EnrichmentError explaining why AI is not available."""

        raise EnrichmentError(self._reason)
