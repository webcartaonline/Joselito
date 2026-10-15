"""Central logging configuration for the wiki enrichment application."""

import logging
import os
import re
import time
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType
from uuid import uuid4

LOGGER_NAME = "wiki_enrichment"
LOG_DIRECTORY = Path("logs")
LOG_FILE_PREFIX = "app"
LOG_FILE_EXTENSION = ".log"
LOG_FILE_NAME = f"{LOG_FILE_PREFIX}{LOG_FILE_EXTENSION}"
LOG_LEVEL_VARIABLE = "LOG_LEVEL"
DEFAULT_LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(run_id)s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_MAX_BYTES = 1_000_000
LOG_BACKUP_COUNT = 5
LOG_ENCODING = "utf-8"

RUN_ID_FIELD = "run_id"
DEFAULT_RUN_ID = "-"
RUN_ID_LENGTH = 8
_current_run_id: ContextVar[str] = ContextVar(RUN_ID_FIELD, default=DEFAULT_RUN_ID)

REDACTION_PLACEHOLDER = "***"
HUGGING_FACE_TOKEN_PATTERN = re.compile(r"hf_[A-Za-z0-9]{8,}")


class UtcFormatter(logging.Formatter):
    """Formatter that renders UTC timestamps and redacts exception text."""

    converter = time.gmtime

    def formatException(
        self, exc_info: tuple[type[BaseException], BaseException, TracebackType | None]
    ) -> str:
        """Return the traceback with sensitive values removed."""

        return redact_sensitive_data(super().formatException(exc_info))


def generate_run_id() -> str:
    """Return a short unique identifier for one application run."""

    return uuid4().hex[:RUN_ID_LENGTH]


def set_run_id(run_id: str) -> None:
    """Set the identifier attached to the log records of the current run.

    Args:
        run_id: Identifier to attach to the following log records.
    """

    _current_run_id.set(run_id)


def current_run_id() -> str:
    """Return the identifier attached to the log records of the current run."""

    return _current_run_id.get()


def log_file_name(run_id: str | None = None) -> str:
    """Return the log file name for a run, including its identifier.

    Args:
        run_id: Identifier of the run. When omitted, the current one is used.

    Returns:
        ``app_<run_id>.log``, or the shared ``app.log`` when no identifier
        is set, so each execution can be told apart by its file name.
    """

    run_id = current_run_id() if run_id is None else run_id
    if run_id == DEFAULT_RUN_ID:
        return LOG_FILE_NAME
    return f"{LOG_FILE_PREFIX}_{run_id}{LOG_FILE_EXTENSION}"


def log_file_path(run_id: str | None = None) -> Path:
    """Return the path to the log file of a run, including its identifier.

    Args:
        run_id: Identifier of the run. When omitted, the current one is used.

    Returns:
        The path inside ``LOG_DIRECTORY`` for the given or current run.
    """

    return LOG_DIRECTORY / log_file_name(run_id)


class RunIdFilter(logging.Filter):
    """Filter that attaches the current run identifier to every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add the run identifier to the record and let it through.

        Args:
            record: The log record about to be formatted.

        Returns:
            Always ``True`` so the record is never dropped.
        """

        record.run_id = current_run_id()
        return True


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
        A handler writing UTF-8 lines with UTC timestamps, the run
        identifier and the Hugging Face token removed.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        path,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding=LOG_ENCODING,
    )
    formatter = UtcFormatter(
        LOG_FORMAT, LOG_DATE_FORMAT, defaults={RUN_ID_FIELD: DEFAULT_RUN_ID}
    )
    handler.setFormatter(formatter)
    handler.addFilter(RunIdFilter())
    handler.addFilter(SensitiveDataFilter())
    return handler


def configure_logging(
    level: str | None = None, run_id: str | None = None
) -> logging.Logger:
    """Configure and return the application logger.

    Sets up a single rotating file handler writing to
    ``logs/app_<run_id>.log`` (``logs/app.log`` when no identifier is
    set), so every run keeps its own file. Calling it again replaces the
    previous handler instead of adding duplicates.

    Args:
        level: Optional level name overriding ``LOG_LEVEL``.
        run_id: Optional run identifier. When given, it becomes the current
            identifier and names the log file.

    Returns:
        The configured ``wiki_enrichment`` logger.
    """

    if run_id is not None:
        set_run_id(run_id)
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(resolve_log_level(level))
    logger.propagate = False
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    logger.addHandler(build_file_handler(log_file_path()))
    return logger
