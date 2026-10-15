"""Immutable domain models used by the wiki enrichment workflow."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ArticleContent:
    """An article retrieved from a content source."""

    title: str
    paragraphs: list[str]

    @property
    def full_text(self) -> str:
        """Return the article paragraphs as a readable block of text."""

        return "\n\n".join(self.paragraphs)


@dataclass(frozen=True, slots=True)
class SearchResult:
    """A Wikipedia search result: just enough to let the user choose an article.

    Only the title and a short summary are kept, never the whole article,
    so a list of results takes very little memory.
    """

    title: str
    summary: str = ""


@dataclass(frozen=True)
class EnrichedContent:
    """An article together with its generated and translated summaries."""

    original_article: ArticleContent
    ai_summary: str
    translated_summary: str = ""


@dataclass(frozen=True)
class BriefSummary:
    """A short summary of enriched content, with its translation."""

    title: str
    text: str
    translated_text: str = ""