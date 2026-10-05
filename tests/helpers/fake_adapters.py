"""In-memory fakes implementing the domain ports without I/O."""

from tests.helpers.content_mocks import make_article
from wiki_enrichment.domain.exceptions import WikiEnrichmentError
from wiki_enrichment.domain.models import ArticleContent, EnrichedContent


class FakeWikipediaSource:
    """Fake article source returning a fixed article without network calls."""

    def __init__(
        self,
        article: ArticleContent | None = None,
        failure: WikiEnrichmentError | None = None,
    ) -> None:
        """Configure the article to return or the failure to raise."""
        self._article = article if article is not None else make_article()
        self._failure = failure
        self.requested_topics: list[str] = []

    def fetch_article(self, topic: str) -> ArticleContent:
        """Record the topic and return the fixed article."""
        self.requested_topics.append(topic)
        if self._failure is not None:
            raise self._failure
        return self._article


class FakeContentEnricher:
    """Fake enricher attaching a fixed summary without calling any AI."""

    def __init__(
        self,
        ai_summary: str = "A concise summary.",
        failure: WikiEnrichmentError | None = None,
    ) -> None:
        """Configure the summary to attach or the failure to raise."""
        self._ai_summary = ai_summary
        self._failure = failure
        self.received_articles: list[ArticleContent] = []

    def enrich(self, article: ArticleContent) -> EnrichedContent:
        """Record the article and return it with the fixed summary."""
        self.received_articles.append(article)
        if self._failure is not None:
            raise self._failure
        return EnrichedContent(original_article=article, ai_summary=self._ai_summary)


class FakeTranslator:
    """Fake translator rendering a deterministic output without any API."""

    def __init__(self, failure: WikiEnrichmentError | None = None) -> None:
        """Configure the optional failure to raise."""
        self._failure = failure
        self.received_calls: list[tuple[str, str]] = []

    def translate(self, text: str, target_lang: str) -> str:
        """Record the call and return the text tagged with the language."""
        self.received_calls.append((text, target_lang))
        if self._failure is not None:
            raise self._failure
        return f"{text} [{target_lang}]"


class FakeDocumentExporter:
    """Fake exporter recording exports without touching the filesystem."""

    def __init__(self, failure: WikiEnrichmentError | None = None) -> None:
        """Configure the optional failure to raise."""
        self._failure = failure
        self.saved_txt: list[tuple[EnrichedContent, str]] = []
        self.saved_pdf: list[tuple[EnrichedContent, str]] = []

    def export_txt(self, content: EnrichedContent, path: str) -> None:
        """Record a plain-text export."""
        if self._failure is not None:
            raise self._failure
        self.saved_txt.append((content, path))

    def export_pdf(self, content: EnrichedContent, path: str) -> None:
        """Record a PDF export."""
        if self._failure is not None:
            raise self._failure
        self.saved_pdf.append((content, path))
