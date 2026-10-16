"""Wikipedia source adapter: searches a topic and scrapes the article."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from domain.exceptions import (
    ProviderTimeoutError,
    RateLimitError,
    ResourceNotFoundError,
    WikiEnrichmentError,
)
from domain.models import ArticleContent, SearchResult
from infrastructure.logging_config import LOGGER_NAME

MAX_PARAGRAPHS = 5
REQUEST_TIMEOUT_SECONDS = 10
HEADERS = {"User-Agent": "WikiEnrichmentBot/1.0 (bootcamp project)"}
SEARCH_RESULTS_LIMIT = 6  # The first result plus 5 more for the user to choose from.
SUMMARY_SENTENCES = 2
INVALID_RESPONSE = "Invalid Wikipedia response"
INVISIBLE_SPACE = "\u200b"  # Wikipedia leaves it where its references were.
TOO_MANY_REQUESTS = 429


def parse_retry_after(value: object) -> int | None:
    """Return the seconds Wikipedia asks to wait, or None if it does not say."""
    try:
        seconds = int(str(value))
    except ValueError:
        return None
    return seconds if seconds > 0 else None


def check_status(response: requests.Response) -> None:
    """Raise RateLimitError for too many requests, or the usual HTTP error."""
    if response.status_code == TOO_MANY_REQUESTS:
        raise RateLimitError(
            "Wikipedia received too many requests",
            retry_after_seconds=parse_retry_after(response.headers.get("Retry-After")),
        )
    response.raise_for_status()


@contextmanager
def domain_errors() -> Iterator[None]:
    """Turn network problems into the app's own errors."""
    try:
        yield
    except requests.Timeout as exc:
        raise ProviderTimeoutError("Wikipedia took too long to respond") from exc
    except requests.RequestException as exc:
        raise WikiEnrichmentError(f"Could not reach Wikipedia: {exc}") from exc

logger = logging.getLogger(f"{LOGGER_NAME}.{__name__}")


class WikipediaSourceAdapter:
    """Fetch the title and first paragraphs of a Wikipedia article."""

    def __init__(self, language: str = "en") -> None:
        self._language = language
        self._base_url = f"https://{language}.wikipedia.org"

    def fetch_article(self, topic: str) -> ArticleContent:
        logger.info(
            "Searching Wikipedia: topic=%s language=%s", topic, self._language
        )
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
        logger.info("Article ready: title=%s paragraphs=%d", title, len(paragraphs))

        return ArticleContent(title=title, paragraphs=paragraphs)

    def search(self, topic: str) -> list[SearchResult]:
        """Return up to SEARCH_RESULTS_LIMIT results, each with a short summary.

        If Wikipedia suggests another spelling ("¿Quisiste decir...?"), the
        results for the suggestion go first, then those for the original topic.

        Raises:
            ResourceNotFoundError: If nothing is found.
        """
        with domain_errors():
            results, suggestion = self._search_with_summaries(topic)
        if suggestion and suggestion.lower() != topic.lower():
            results = self._add_suggested_results(results, suggestion)
        if not results:
            raise ResourceNotFoundError(f"No Wikipedia results for '{topic}'")
        return results[:SEARCH_RESULTS_LIMIT]

    def _add_suggested_results(
        self, results: list[SearchResult], suggestion: str
    ) -> list[SearchResult]:
        """Put the suggestion's results first, without repeating any title.

        If the search for the suggestion fails, the original results are kept:
        the user still gets an answer and it does not count as a failure.
        """
        try:
            with domain_errors():
                suggested, _ = self._search_with_summaries(suggestion)
        except WikiEnrichmentError:
            return results
        suggested_titles = {result.title for result in suggested}
        return suggested + [result for result in results if result.title not in suggested_titles]

    def fetch_article_by_title(self, title: str) -> ArticleContent:
        """Download the article with this exact title (one chosen by the user)."""
        with domain_errors():
            html = self._download_article(title)
        paragraphs = self._extract_paragraphs(html)
        if not paragraphs:
            raise ResourceNotFoundError(f"No content found for '{title}'")
        return ArticleContent(title=title, paragraphs=paragraphs)

    def _search_with_summaries(self, topic: str) -> tuple[list[SearchResult], str]:
        """Ask Wikipedia, in one request, for the results, their summaries and a suggestion."""
        response = requests.get(
            f"{self._base_url}/w/api.php",
            params={
                "action": "query",
                "format": "json",
                "formatversion": 2,
                "generator": "search",
                "gsrsearch": topic,
                "gsrlimit": SEARCH_RESULTS_LIMIT,
                "gsrinfo": "suggestion",
                "prop": "extracts",
                "exintro": 1,
                "explaintext": 1,
                "exsentences": SUMMARY_SENTENCES,
                "exlimit": SEARCH_RESULTS_LIMIT,
            },
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        check_status(response)
        try:
            payload = response.json()
        except ValueError as exc:
            raise WikiEnrichmentError(INVALID_RESPONSE) from exc
        return self._parse_search_results(payload)

    @staticmethod
    def _parse_search_results(payload: object) -> tuple[list[SearchResult], str]:
        """Return the results in Wikipedia's order and its suggestion ("" if none).

        Wikipedia leaves out "query" when there are no results, and "extract"
        when a page has no summary.
        """
        if not isinstance(payload, dict) or "error" in payload:
            raise WikiEnrichmentError(INVALID_RESPONSE)
        query = payload.get("query", {})
        try:
            pages = sorted(query.get("pages", []), key=lambda page: page["index"])
            results = [
                SearchResult(page["title"], page.get("extract", "").replace(INVISIBLE_SPACE, "").strip())
                for page in pages
            ]
            suggestion = query.get("searchinfo", {}).get("suggestion", "")
        except (AttributeError, KeyError, TypeError) as exc:
            raise WikiEnrichmentError(INVALID_RESPONSE) from exc
        return results, suggestion

    def _search_title(self, topic: str) -> str:
        """Search Wikipedia and return the first matching article title."""
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
        logger.debug(
            "Search request finished: topic=%s status=%d",
            topic,
            response.status_code,
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise WikiEnrichmentError("Invalid Wikipedia response") from exc
        return self._parse_search_title(payload, topic)

    @staticmethod
    def _parse_search_title(payload: object, topic: str) -> str:
        """Extract the first article title from a search payload."""
        try:
            results = payload["query"]["search"]  # type: ignore[index]
        except (KeyError, TypeError) as exc:
            raise WikiEnrichmentError("Invalid Wikipedia response") from exc
        if not results:
            raise ResourceNotFoundError(f"No Wikipedia results for '{topic}'")
        try:
            title = results[0]["title"]
        except (KeyError, TypeError, IndexError) as exc:
            raise WikiEnrichmentError("Invalid Wikipedia response") from exc
        if not isinstance(title, str) or not title:
            raise WikiEnrichmentError("Invalid Wikipedia response")
        logger.debug("Article selected: title=%s", title)
        return title

    def _download_article(self, title: str) -> str:
        logger.debug("Downloading article: title=%s", title)
        slug = quote(title.replace(" ", "_"), safe="()")
        response = requests.get(
            f"{self._base_url}/wiki/{slug}",
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        if response.status_code == 404:
            raise ResourceNotFoundError(f"Article '{title}' not found")
        check_status(response)
        logger.debug(
            "Article downloaded: title=%s status=%d bytes=%d",
            title,
            response.status_code,
            len(response.text),
        )
        return response.text

    @staticmethod
    def _extract_paragraphs(html: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        content = soup.find("div", id="mw-content-text")
        if content is None:
            return []
        paragraphs = [p.get_text(" ", strip=True) for p in content.find_all("p")]
        return [p for p in paragraphs if p][:MAX_PARAGRAPHS]
