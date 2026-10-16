"""Unit tests for searching Wikipedia with summaries, with mocked HTTP."""

from unittest.mock import patch

import pytest
import requests

from tests.helpers.wikipedia_mocks import (
    REQUEST_TARGET,
    build_article_html,
    make_article_response,
    make_http_error_response,
    make_response,
    make_results_response,
)
from domain.exceptions import (
    ProviderTimeoutError,
    RateLimitError,
    ResourceNotFoundError,
    WikiEnrichmentError,
)
from domain.models import SearchResult
from infrastructure.wikipedia import (
    HEADERS,
    REQUEST_TIMEOUT_SECONDS,
    SEARCH_RESULTS_LIMIT,
    SUMMARY_SENTENCES,
    WikipediaSourceAdapter,
)

TREE_PAGES = [("Árbol", "Un árbol es una planta."), ("Árbol genealógico", "Un esquema.")]
TYPO_PAGES = [("Molisol", "Un tipo de suelo.")]


@patch(REQUEST_TARGET)
def test_search_returns_results_in_wikipedia_order(mock_get) -> None:
    """Pages come unordered and are sorted by Wikipedia's index."""
    mock_get.return_value = make_results_response(TREE_PAGES)

    results = WikipediaSourceAdapter().search("arboles")

    assert results == [SearchResult(title, summary) for title, summary in TREE_PAGES]
    assert mock_get.call_count == 1


@patch(REQUEST_TARGET)
def test_search_puts_the_suggestion_results_first(mock_get) -> None:
    """With "¿Quisiste decir...?", the suggested results go first and are not repeated."""
    mock_get.side_effect = [
        make_results_response(TYPO_PAGES + [TREE_PAGES[0]], suggestion="arboles"),
        make_results_response(TREE_PAGES),
    ]

    results = WikipediaSourceAdapter().search("Alboles")

    assert [result.title for result in results] == ["Árbol", "Árbol genealógico", "Molisol"]
    assert mock_get.call_args_list[1].kwargs["params"]["gsrsearch"] == "arboles"


@patch(REQUEST_TARGET)
def test_search_ignores_a_suggestion_equal_to_the_topic(mock_get) -> None:
    """Do not search twice for the same words."""
    mock_get.return_value = make_results_response(TREE_PAGES, suggestion="arboles")

    WikipediaSourceAdapter().search("Arboles")

    assert mock_get.call_count == 1


@patch(REQUEST_TARGET)
def test_search_returns_at_most_the_limit(mock_get) -> None:
    """Keep only the first result plus the ones the user can choose from."""
    pages = [(f"Page {number}", "Summary.") for number in range(SEARCH_RESULTS_LIMIT)]
    mock_get.side_effect = [
        make_results_response(pages, suggestion="other"),
        make_results_response([("Extra", "Summary.")]),
    ]

    results = WikipediaSourceAdapter().search("page")

    assert len(results) == SEARCH_RESULTS_LIMIT
    assert results[0].title == "Extra"


@patch(REQUEST_TARGET)
def test_search_leaves_the_summary_empty_when_wikipedia_has_none(mock_get) -> None:
    """A page without summary keeps an empty one instead of failing."""
    mock_get.return_value = make_results_response([("Árbol", None)])

    assert WikipediaSourceAdapter().search("arboles") == [SearchResult("Árbol", "")]


@patch(REQUEST_TARGET)
def test_search_removes_invisible_spaces_from_summaries(mock_get) -> None:
    """Wikipedia leaves invisible spaces where references were; remove them."""
    mock_get.return_value = make_results_response([("Árbol", "Una planta.\u200b Leñosa.")])

    assert WikipediaSourceAdapter().search("arboles")[0].summary == "Una planta. Leñosa."


@patch(REQUEST_TARGET)
def test_search_sends_one_request_with_results_summaries_and_suggestion(mock_get) -> None:
    """Ask for everything in a single request, with headers and timeout."""
    mock_get.return_value = make_results_response(TREE_PAGES)

    WikipediaSourceAdapter(language="es").search("arboles")

    call = mock_get.call_args
    assert call.args[0] == "https://es.wikipedia.org/w/api.php"
    assert call.kwargs["params"]["gsrsearch"] == "arboles"
    assert call.kwargs["params"]["gsrlimit"] == SEARCH_RESULTS_LIMIT
    assert call.kwargs["params"]["gsrinfo"] == "suggestion"
    assert call.kwargs["params"]["exsentences"] == SUMMARY_SENTENCES
    assert call.kwargs["headers"] == HEADERS
    assert call.kwargs["timeout"] == REQUEST_TIMEOUT_SECONDS


@pytest.mark.parametrize("suggestion", ["", "zzzxxy"])
@patch(REQUEST_TARGET)
def test_search_raises_not_found_without_results(mock_get, suggestion) -> None:
    """Raise not found when neither the topic nor the suggestion find anything."""
    mock_get.side_effect = [
        make_results_response([], suggestion=suggestion),
        make_results_response([]),
    ]

    with pytest.raises(ResourceNotFoundError):
        WikipediaSourceAdapter().search("zzzxxyy")


@pytest.mark.parametrize(
    "payload",
    [
        ["not", "a", "dict"],
        {"error": {"code": "cirrussearch-query-too-long"}},
        {"query": "not a dict"},
        {"query": {"pages": [{"title": "No index"}]}},
        {"query": {"pages": [{"index": 1}]}},
    ],
)
@patch(REQUEST_TARGET)
def test_search_raises_domain_error_on_invalid_payload(mock_get, payload) -> None:
    """Unexpected answers become the app's own error."""
    mock_get.return_value = make_response(json_data=payload)

    with pytest.raises(WikiEnrichmentError):
        WikipediaSourceAdapter().search("python")


@patch(REQUEST_TARGET)
def test_search_raises_domain_error_on_invalid_json(mock_get) -> None:
    """A response that is not JSON becomes the app's own error."""
    response = make_response()
    response.json.side_effect = ValueError("not json")
    mock_get.return_value = response

    with pytest.raises(WikiEnrichmentError):
        WikipediaSourceAdapter().search("python")


@pytest.mark.parametrize(
    ("failure", "error"),
    [
        (requests.Timeout(), ProviderTimeoutError),
        (requests.ConnectionError(), WikiEnrichmentError),
    ],
)
@patch(REQUEST_TARGET)
def test_search_maps_network_errors(mock_get, failure, error) -> None:
    """Network problems become the app's own errors."""
    mock_get.side_effect = failure

    with pytest.raises(error):
        WikipediaSourceAdapter().search("python")


@patch(REQUEST_TARGET)
def test_search_wraps_http_errors(mock_get) -> None:
    """An HTTP error such as 503 (service unavailable) becomes a domain error."""
    mock_get.return_value = make_http_error_response(503)

    with pytest.raises(WikiEnrichmentError):
        WikipediaSourceAdapter().search("python")


@pytest.mark.parametrize(
    ("retry_after", "seconds"), [("30", 30), (None, None), ("0", None), ("soon", None)]
)
@patch(REQUEST_TARGET)
def test_too_many_requests_raises_rate_limit_with_the_wait(mock_get, retry_after, seconds) -> None:
    """A 429 answer becomes RateLimitError with the seconds Wikipedia asks to wait."""
    response = make_response(status_code=429)
    response.headers = {"Retry-After": retry_after} if retry_after is not None else {}
    mock_get.return_value = response

    with pytest.raises(RateLimitError) as error:
        WikipediaSourceAdapter().search("python")

    assert error.value.retry_after_seconds == seconds


@patch(REQUEST_TARGET)
def test_download_too_many_requests_raises_rate_limit(mock_get) -> None:
    """Downloading the chosen article can also be rate limited."""
    response = make_response(status_code=429)
    response.headers = {"Retry-After": "12"}
    mock_get.return_value = response

    with pytest.raises(RateLimitError) as error:
        WikipediaSourceAdapter().fetch_article_by_title("Árbol")

    assert error.value.retry_after_seconds == 12


@pytest.mark.parametrize(
    "failure", [requests.Timeout(), requests.ConnectionError(), make_http_error_response(503)]
)
@patch(REQUEST_TARGET)
def test_search_keeps_original_results_if_the_suggestion_search_fails(mock_get, failure) -> None:
    """A failed second search does not lose the results of the first one."""
    mock_get.side_effect = [
        make_results_response(TYPO_PAGES, suggestion="arboles"),
        failure,
    ]

    results = WikipediaSourceAdapter().search("Alboles")

    assert [result.title for result in results] == ["Molisol"]


@patch(REQUEST_TARGET)
def test_fetch_article_by_title_downloads_only_that_article(mock_get) -> None:
    """Download the chosen title directly, without searching again."""
    mock_get.return_value = make_article_response(build_article_html(["Una planta."]))

    article = WikipediaSourceAdapter(language="es").fetch_article_by_title("Árbol")

    assert article.title == "Árbol"
    assert article.paragraphs == ["Una planta."]
    assert mock_get.call_count == 1
    assert mock_get.call_args.args[0] == "https://es.wikipedia.org/wiki/%C3%81rbol"


@pytest.mark.parametrize(
    "response",
    [make_response(status_code=404), make_article_response(build_article_html([]))],
)
@patch(REQUEST_TARGET)
def test_fetch_article_by_title_raises_not_found(mock_get, response) -> None:
    """A missing or empty article raises not found."""
    mock_get.return_value = response

    with pytest.raises(ResourceNotFoundError):
        WikipediaSourceAdapter().fetch_article_by_title("Árbol")


@patch(REQUEST_TARGET)
def test_fetch_article_by_title_maps_timeouts(mock_get) -> None:
    """A slow download becomes a provider timeout error."""
    mock_get.side_effect = requests.Timeout()

    with pytest.raises(ProviderTimeoutError):
        WikipediaSourceAdapter().fetch_article_by_title("Árbol")
