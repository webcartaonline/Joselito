"""Unit tests for the central logging configuration."""

import logging
import re
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from infrastructure.logging_config import (
    DEFAULT_RUN_ID,
    LOGGER_NAME,
    REDACTION_PLACEHOLDER,
    RUN_ID_LENGTH,
    RunIdFilter,
    SensitiveDataFilter,
    UtcFormatter,
    configure_logging,
    current_run_id,
    generate_run_id,
    log_file_name,
    redact_sensitive_data,
    resolve_log_level,
    set_run_id,
)

LOG_FILE = Path("logs") / "app.log"

HUGGING_FACE_TOKEN = "hf_abcdefghijklmnop"
DEEPSEEK_API_KEY = "sk-abcdefghijklmnop"

SECRET_SAMPLES = (
    (f"Loading model with token {HUGGING_FACE_TOKEN}", HUGGING_FACE_TOKEN),
    (f"Configuration HF_TOKEN={HUGGING_FACE_TOKEN}", HUGGING_FACE_TOKEN),
    (f"Calling DeepSeek with key {DEEPSEEK_API_KEY}", DEEPSEEK_API_KEY),
    (f"Authorization: Bearer {DEEPSEEK_API_KEY}", DEEPSEEK_API_KEY),
)


@pytest.fixture(autouse=True)
def log_workspace(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[Path]:
    """Run each test in a temporary directory with a clean logger."""

    logger = logging.getLogger(LOGGER_NAME)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    set_run_id(DEFAULT_RUN_ID)
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
        r"- \| wiki_enrichment \| Something failed"
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


def test_redact_sensitive_data_removes_deepseek_key() -> None:
    """DeepSeek API keys are redacted as well."""
    redacted = redact_sensitive_data(f"key {DEEPSEEK_API_KEY}")

    assert DEEPSEEK_API_KEY not in redacted
    assert REDACTION_PLACEHOLDER in redacted


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


def test_configure_logging_writes_the_run_id(log_workspace: Path) -> None:
    """Each line includes the identifier of the current run."""
    logger = configure_logging()
    run_id = "abc12345"
    set_run_id(run_id)

    logger.info("App started")

    content = (log_workspace / LOG_FILE).read_text(encoding="utf-8")
    assert f"| {run_id} |" in content


def test_default_run_id_is_used_without_setting(log_workspace: Path) -> None:
    """Without setting an identifier the default one is written."""
    logger = configure_logging()

    logger.info("App started")

    content = (log_workspace / LOG_FILE).read_text(encoding="utf-8")
    assert f"| {DEFAULT_RUN_ID} |" in content


def test_generate_run_id_returns_unique_identifiers() -> None:
    """Two generated identifiers differ and have the expected length."""
    first = generate_run_id()
    second = generate_run_id()

    assert first != second
    assert len(first) == RUN_ID_LENGTH


def test_set_run_id_updates_the_current_identifier() -> None:
    """Setting the identifier updates the value read back."""
    set_run_id("run-42")

    assert current_run_id() == "run-42"


def test_run_id_filter_attaches_the_current_identifier() -> None:
    """The filter adds the current run identifier to the record."""
    set_run_id("run-99")
    record = logging.LogRecord(
        LOGGER_NAME, logging.INFO, __file__, 1, "message", None, None
    )

    allowed = RunIdFilter().filter(record)

    assert allowed is True
    assert record.run_id == "run-99"


def test_log_file_name_includes_the_run_id() -> None:
    """The log file name carries the identifier of the run."""
    assert log_file_name("abc12345") == "app_abc12345.log"


def test_log_file_name_without_run_id_keeps_the_shared_file() -> None:
    """Without an identifier the shared app.log name is kept."""
    set_run_id(DEFAULT_RUN_ID)

    assert log_file_name() == "app.log"


def test_configure_logging_creates_one_file_per_run(log_workspace: Path) -> None:
    """A run writes to its own log file, named after its identifier."""
    logger = configure_logging(run_id="abc12345")

    logger.info("App started")

    content = (log_workspace / "logs" / "app_abc12345.log").read_text(
        encoding="utf-8"
    )
    assert "App started" in content
    assert "| abc12345 |" in content


def test_each_run_gets_its_own_log_file(log_workspace: Path) -> None:
    """Two runs with different identifiers keep separate files."""
    first = configure_logging(run_id="aaaa1111")
    first.info("First run")
    second = configure_logging(run_id="bbbb2222")
    second.info("Second run")

    first_log = (log_workspace / "logs" / "app_aaaa1111.log").read_text(
        encoding="utf-8"
    )
    second_log = (log_workspace / "logs" / "app_bbbb2222.log").read_text(
        encoding="utf-8"
    )
    assert "First run" in first_log
    assert "First run" not in second_log
    assert "Second run" in second_log
