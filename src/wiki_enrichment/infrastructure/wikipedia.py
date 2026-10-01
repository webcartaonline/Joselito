"""Wikipedia source adapter: searches a topic and scrapes the article."""

import requests
from bs4 import BeautifulSoup

from wiki_enrichment.domain.exceptions import (
    ProviderTimeoutError,
    ResourceNotFoundError,
    WikiEnrichmentError,
)
from wiki_enrichment.domain.models import ArticleContent

MAX_PARAGRAPHS = 5
REQUEST_TIMEOUT_SECONDS = 10
HEADERS = {"User-Agent": "WikiEnrichmentBot/1.0 (bootcamp project)"}


class WikipediaSourceAdapter:
    """Fetches the title and first paragraphs of a Wikipedia article."""

    def __init__(self, language: str = "en") -> None:
        self._base_url = f"https://{language}.wikipedia.org"

    def fetch_article(self, topic: str) -> ArticleContent:
        """Search the topic on Wikipedia and return its scraped content."""
        try:
            title = self._search_title(topic)
            html = self._download_article(title)
        except requests.Timeout as exc:
            raise ProviderTimeoutError("Wikipedia took too long to respond") from exc
        except requests.RequestException as exc:
            raise WikiEnrichmentError(f"Could not reach Wikipedia: {exc}") from exc

        paragraphs = self._extract_paragraphs(html)
        if not paragraphs:
            raise ResourceNotFoundError(f"No content found for '{topic}'")

        return ArticleContent(title=title, paragraphs=paragraphs)

    def _search_title(self, topic: str) -> str:
        response = requests.get(
            f"{self._base_url}/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": topic,
                "srlimit": 1,
                "format": "json",
            },
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        results = response.json()["query"]["search"]
        if not results:
            raise ResourceNotFoundError(f"No Wikipedia results for '{topic}'")
        return results[0]["title"]

    def _download_article(self, title: str) -> str:
        response = requests.get(
            f"{self._base_url}/wiki/{title.replace(' ', '_')}",
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        if response.status_code == 404:
            raise ResourceNotFoundError(f"Article '{title}' not found")
        response.raise_for_status()
        return response.text

    @staticmethod
    def _extract_paragraphs(html: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        content = soup.find("div", id="mw-content-text")
        if content is None:
            return []
        paragraphs = [p.get_text(" ", strip=True) for p in content.find_all("p")]
        return [p for p in paragraphs if p][:MAX_PARAGRAPHS]
