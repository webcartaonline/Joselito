"""Domain-level exceptions shared across adapters and use cases."""


class WikiEnrichmentError(Exception):
    """Base exception for expected wiki enrichment failures."""


class ResourceNotFoundError(WikiEnrichmentError):
    """Raised when a requested article or resource cannot be found."""


class ProviderTimeoutError(WikiEnrichmentError):
    """Raised when an external provider exceeds its configured timeout."""


class RateLimitError(WikiEnrichmentError):
    """Raised when a provider receives too many requests and asks to wait."""

    def __init__(self, message: str, retry_after_seconds: int | None = None) -> None:
        """Keep how many seconds the provider asked to wait, if it said so."""
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class EnrichmentError(WikiEnrichmentError):
    """Raised when the AI provider fails to generate an enrichment."""


class ExportError(WikiEnrichmentError):
    """Raised when a document cannot be saved."""


class SummarizationError(EnrichmentError):
    """Raised when the brief summary cannot be generated."""