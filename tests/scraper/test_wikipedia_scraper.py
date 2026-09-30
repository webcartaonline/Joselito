from unittest.mock import Mock, patch

import pytest
import requests

from src.scraper.wikipedia_scraper import ScraperError, WikipediaScraper

FAKE_HTML = """
<h1 id="firstHeading">Python</h1>
<div class="mw-parser-output">
  <section><p>Paragraph 1[1]</p><p></p><p>Paragraph 2</p></section>
</div>
"""


@patch("src.scraper.wikipedia_scraper.requests.get")
def test_get_content_success(mock_get):
    mock_get.return_value = Mock(text=FAKE_HTML, raise_for_status=lambda: None)
    result = WikipediaScraper().get_content("Python")
    assert result["title"] == "Python"
    assert result["paragraphs"] == ["Paragraph 1", "Paragraph 2"]


@patch("src.scraper.wikipedia_scraper.requests.get")
def test_get_content_network_error(mock_get):
    mock_get.side_effect = requests.ConnectionError("no connection")
    with pytest.raises(ScraperError):
        WikipediaScraper().get_content("Python")


@patch("src.scraper.wikipedia_scraper.requests.get")
def test_get_content_missing_title(mock_get):
    mock_get.return_value = Mock(text="<p>no title</p>", raise_for_status=lambda: None)
    with pytest.raises(ScraperError):
        WikipediaScraper().get_content("Python")