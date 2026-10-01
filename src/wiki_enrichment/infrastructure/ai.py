"""AI content enrichment adapter placeholder."""

from wiki_enrichment.domain.models import ArticleContent, EnrichedContent


class AIContentEnricher:
    """Placeholder adapter for a future AI summarization provider."""

    def enrich(self, article: ArticleContent) -> EnrichedContent:
        """Enrich an article once a concrete AI provider is configured."""

        raise NotImplementedError("AI enrichment is not implemented yet")

