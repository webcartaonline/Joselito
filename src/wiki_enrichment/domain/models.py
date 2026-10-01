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


@dataclass(frozen=True)
class EnrichedContent:
    """An article together with its generated and translated summaries."""

    original_article: ArticleContent
    ai_summary: str
    translated_summary: str = ""

