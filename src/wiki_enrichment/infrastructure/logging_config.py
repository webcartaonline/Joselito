"""Central logging configuration for the wiki enrichment application."""

import logging
import os
import re
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOGGER_NAME = "wiki_enrichment"
LOG_DIRECTORY = Path("logs")
LOG_FILE_NAME = "app.log"
LOG_LEVEL_VARIABLE = "LOG_LEVEL"
DEFAULT_LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_MAX_BYTES = 1_000_000
LOG_BACKUP_COUNT = 5
LOG_ENCODING = "utf-8"

REDACTION_PLACEHOLDER = "***"
HUGGING_FACE_TOKEN_PATTERN = re.compile(r"hf_[A-Za-z0-9]{8,}")


class UtcFormatter(logging.Formatter):
    """Formatter that renders timestamps in UTC instead of local time."""

    converter = time.gmtime


def redact_sensitive_data(text: str) -> str:
    """Replace the Hugging Face token found in a text with a placeholder.

    Args:
        text: Text that may contain the Hugging Face token.

    Returns:
        The text with every detected token replaced by
        ``REDACTION_PLACEHOLDER``.
    """

    return HUGGING_FACE_TOKEN_PATTERN.sub(REDACTION_PLACEHOLDER, text)


class SensitiveDataFilter(logging.Filter):
    """Filter that removes the Hugging Face token from every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact the record message and let it through.

        Args:
            record: The log record about to be formatted.

        Returns:
            Always ``True`` so the record is never dropped.
        """

        record.msg = redact_sensitive_data(record.getMessage())
        record.args = ()
        return True


def resolve_log_level(level: str | None = None) -> int:
    """Return the numeric log level from an argument, the environment or a default.

    Args:
        level: Optional explicit level name. When omitted, the ``LOG_LEVEL``
            environment variable is used.

    Returns:
        A valid :mod:`logging` level. Unknown names fall back to
        ``DEFAULT_LOG_LEVEL``.
    """

    name = (level or os.getenv(LOG_LEVEL_VARIABLE) or DEFAULT_LOG_LEVEL).upper()
    levels = logging.getLevelNamesMapping()
    return levels.get(name, levels[DEFAULT_LOG_LEVEL])


def build_file_handler(path: Path) -> RotatingFileHandler:
    """Create the rotating file handler that stores the application log.

    Args:
        path: Destination of the log file. Missing folders are created.

    Returns:
        A handler writing UTF-8 lines with UTC timestamps and the Hugging
        Face token removed.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        path,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding=LOG_ENCODING,
    )
    handler.setFormatter(UtcFormatter(LOG_FORMAT, LOG_DATE_FORMAT))
    handler.addFilter(SensitiveDataFilter())
    return handler


def configure_logging(level: str | None = None) -> logging.Logger:
    """Configure and return the application logger.

    Sets up a single rotating file handler writing to ``logs/app.log``.
    Calling it again replaces the previous handler instead of adding
    duplicates.

    Args:
        level: Optional level name overriding ``LOG_LEVEL``.

    Returns:
        The configured ``wiki_enrichment`` logger.
    """

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(resolve_log_level(level))
    logger.propagate = False
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    logger.addHandler(build_file_handler(LOG_DIRECTORY / LOG_FILE_NAME))
    return logger
