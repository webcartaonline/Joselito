"""Wikipedia source adapter placeholder.

This module intentionally contains no network client. A future task can add
the provider-specific implementation while preserving the domain port.
"""

from wiki_enrichment.domain.models import ArticleContent


class WikipediaSourceAdapter:
    """Placeholder adapter for a future Wikipedia integration."""

    def fetch_article(self, topic: str) -> ArticleContent:
        """Fetch an article once a concrete provider is configured."""

        raise NotImplementedError("Wikipedia integration is not implemented yet")

