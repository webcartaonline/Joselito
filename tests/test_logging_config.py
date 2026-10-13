"""Unit tests for the central logging configuration."""

import logging
import re
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from wiki_enrichment.infrastructure.logging_config import (
    LOGGER_NAME,
    REDACTION_PLACEHOLDER,
    SensitiveDataFilter,
    UtcFormatter,
    configure_logging,
    redact_sensitive_data,
    resolve_log_level,
)

LOG_FILE = Path("logs") / "app.log"

HUGGING_FACE_TOKEN = "hf_abcdefghijklmnop"

SECRET_SAMPLES = (
    (f"Loading model with token {HUGGING_FACE_TOKEN}", HUGGING_FACE_TOKEN),
    (f"Configuration HF_TOKEN={HUGGING_FACE_TOKEN}", HUGGING_FACE_TOKEN),
)


@pytest.fixture(autouse=True)
def log_workspace(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[Path]:
    """Run each test in a temporary directory with a clean logger."""

    logger = logging.getLogger(LOGGER_NAME)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    yield tmp_path
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


def test_configure_logging_creates_log_directory(log_workspace: Path) -> None:
    """Configuring logging creates the logs folder."""
    configure_logging()

    assert (log_workspace / "logs").is_dir()


def test_configure_logging_writes_to_log_file(log_workspace: Path) -> None:
    """A logged message ends up in the app.log file."""
    logger = configure_logging()

    logger.info("App started")

    assert "App started" in (log_workspace / LOG_FILE).read_text(encoding="utf-8")


def test_log_line_contains_utc_timestamp_and_level(log_workspace: Path) -> None:
    """Each line has a timestamp and a severity level."""
    logger = configure_logging()

    logger.error("Something failed")

    content = (log_workspace / LOG_FILE).read_text(encoding="utf-8")
    pattern = (
        r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \| ERROR \| "
        r"wiki_enrichment \| Something failed"
    )
    assert re.search(pattern, content)


def test_formatter_renders_timestamps_in_utc() -> None:
    """The formatter uses UTC instead of local time."""
    assert UtcFormatter.converter is time.gmtime


def test_level_filters_lower_severity_records(log_workspace: Path) -> None:
    """Records below the configured level are not stored."""
    logger = configure_logging("WARNING")

    logger.info("hidden")
    logger.warning("visible")

    content = (log_workspace / LOG_FILE).read_text(encoding="utf-8")
    assert "hidden" not in content
    assert "visible" in content


def test_configure_logging_does_not_duplicate_handlers() -> None:
    """Configuring twice keeps a single handler."""
    logger = configure_logging()
    configure_logging()

    assert len(logger.handlers) == 1


def test_resolve_log_level_defaults_to_info() -> None:
    """Without an override the default level is INFO."""
    assert resolve_log_level() == logging.INFO


def test_resolve_log_level_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """The LOG_LEVEL variable overrides the default."""
    monkeypatch.setenv("LOG_LEVEL", "debug")

    assert resolve_log_level() == logging.DEBUG


def test_resolve_log_level_falls_back_on_unknown_level(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unknown level name falls back to the default."""
    monkeypatch.setenv("LOG_LEVEL", "nonsense")

    assert resolve_log_level() == logging.INFO


def test_resolve_log_level_prefers_explicit_argument(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicit level wins over the environment."""
    monkeypatch.setenv("LOG_LEVEL", "info")

    assert resolve_log_level("WARNING") == logging.WARNING


@pytest.mark.parametrize(("message", "secret"), SECRET_SAMPLES)
def test_sensitive_values_are_redacted_in_log_file(
    log_workspace: Path, message: str, secret: str
) -> None:
    """Known secrets never reach the log file."""
    logger = configure_logging()

    logger.info(message)

    content = (log_workspace / LOG_FILE).read_text(encoding="utf-8")
    assert secret not in content
    assert REDACTION_PLACEHOLDER in content


@pytest.mark.parametrize(("message", "secret"), SECRET_SAMPLES)
def test_redact_sensitive_data_replaces_secrets(message: str, secret: str) -> None:
    """Every known secret pattern is replaced."""
    redacted = redact_sensitive_data(message)

    assert secret not in redacted
    assert REDACTION_PLACEHOLDER in redacted


def test_redact_sensitive_data_keeps_normal_text() -> None:
    """Plain messages are left untouched."""
    assert redact_sensitive_data("App started") == "App started"


def test_redact_sensitive_data_ignores_other_keys() -> None:
    """Only the Hugging Face token is redacted."""
    assert redact_sensitive_data("key sk-abcdefghijklmnop") == "key sk-abcdefghijklmnop"


def test_sensitive_data_filter_redacts_record_message() -> None:
    """The filter rewrites the record message with the token removed."""
    record = logging.LogRecord(
        LOGGER_NAME,
        logging.INFO,
        __file__,
        1,
        f"token {HUGGING_FACE_TOKEN}",
        None,
        None,
    )

    allowed = SensitiveDataFilter().filter(record)

    assert allowed is True
    assert HUGGING_FACE_TOKEN not in record.getMessage()
