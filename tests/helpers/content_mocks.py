"""Contract data builders for enrichment content tests."""

from wiki_enrichment.domain.models import ArticleContent, EnrichedContent

DEFAULT_TITLE = "Python"
DEFAULT_PARAGRAPHS = ["A programming language.", "It is widely used."]
DEFAULT_SUMMARY = "A concise summary."
DEFAULT_TRANSLATION = "Un résumé concis."
DEFAULT_TOPIC = "Python"
DEFAULT_TARGET_LANG = "fr"
DEFAULT_EXPORT_BASE = "output/article"


def make_article(
    title: str = DEFAULT_TITLE, paragraphs: list[str] | None = None
) -> ArticleContent:
    """Build an article with deterministic test content.

    Args:
        title: Article title.
        paragraphs: Article paragraphs. Defaults to DEFAULT_PARAGRAPHS.

    Returns:
        An article carrying the given title and paragraphs.
    """
    return ArticleContent(
        title=title,
        paragraphs=list(paragraphs) if paragraphs is not None else list(DEFAULT_PARAGRAPHS),
    )


def make_enriched(
    article: ArticleContent | None = None,
    ai_summary: str = DEFAULT_SUMMARY,
    translated_summary: str = "",
) -> EnrichedContent:
    """Build enriched content around a test article.

    Args:
        article: Original article. Defaults to a default test article.
        ai_summary: Enrichment summary attached to the article.
        translated_summary: Translated summary attached to the content.

    Returns:
        Enriched content combining the article with both summaries.
    """
    return EnrichedContent(
        original_article=article if article is not None else make_article(),
        ai_summary=ai_summary,
        translated_summary=translated_summary,
    )


def default_article() -> ArticleContent:
    """Build the default test article.

    Returns:
        An article with the default title and paragraphs.
    """
    return make_article()


def default_enriched() -> EnrichedContent:
    """Build the default enriched content without translation.

    Returns:
        Enriched content with the default article and summary.
    """
    return make_enriched()
