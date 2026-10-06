"""Domain-level exceptions shared across adapters and use cases."""


class WikiEnrichmentError(Exception):
    """Base exception for expected wiki enrichment failures."""


class ResourceNotFoundError(WikiEnrichmentError):
    """Raised when a requested article or resource cannot be found."""


class ProviderTimeoutError(WikiEnrichmentError):
    """Raised when an external provider exceeds its configured timeout."""


class EnrichmentError(WikiEnrichmentError):
    """Raised when the AI provider fails to generate an enrichment."""