import re

import requests
from bs4 import BeautifulSoup


class ScraperError(Exception):
    """Raised when the page cannot be fetched or parsed."""


class WikipediaScraper:
    HEADERS = {"User-Agent": "ContentEnricher/1.0 (bootcamp project)"}

    def __init__(self, language: str = "es", max_paragraphs: int = 5):
        self.language = language
        self.max_paragraphs = max_paragraphs

    def _build_url(self, topic: str) -> str:
        return f"https://{self.language}.wikipedia.org/wiki/{topic.strip().replace(' ', '_')}"

    def _download_html(self, url: str) -> str:
        try:
            response = requests.get(url, headers=self.HEADERS, timeout=10)
            response.raise_for_status()
        except requests.RequestException as error:
            raise ScraperError(f"Could not access {url}: {error}") from error
        return response.text

    @staticmethod
    def _clean_text(text: str) -> str:
        return re.sub(r"\[\d+\]", "", text).strip()

    def get_content(self, topic: str) -> dict:
        html = self._download_html(self._build_url(topic))
        soup = BeautifulSoup(html, "html.parser")

        title = soup.find(id="firstHeading")
        if title is None:
            raise ScraperError("Page title not found")

        paragraphs = [
            self._clean_text(p.get_text())
            for p in soup.select("div.mw-parser-output p")
            if self._clean_text(p.get_text())
        ][: self.max_paragraphs]

        return {"title": title.get_text(strip=True), "paragraphs": paragraphs}