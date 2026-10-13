"""Unit tests for the central logging configuration."""

import logging
import re
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from wiki_enrichment.infrastructure.logging_config import (
    LOGGER_NAME,
    UtcFormatter,
    configure_logging,
    resolve_log_level,
)

LOG_FILE = Path("logs") / "app.log"


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
