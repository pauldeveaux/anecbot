import logging
import logging.handlers
import re
from pathlib import Path

import pytest

from anecbot.utils.logging import ScopedFormatter, setup_logging


@pytest.fixture(autouse=True)
def _restore_root_logger():
    """Snapshot and restore the root logger's handlers/level around each test.

    setup_logging() calls logging.basicConfig(), which mutates global state - without this,
    a test here would leak handlers/level into every other test in the suite.
    """
    root = logging.getLogger()
    handlers = list(root.handlers)
    level = root.level
    yield
    root.handlers = handlers
    root.setLevel(level)


def _make_record(name: str = "anecbot.bot") -> logging.LogRecord:
    """Build a bare INFO log record for the given logger name."""
    return logging.LogRecord(name, logging.INFO, "test", 0, "hello", None, None)


def test_scoped_formatter_with_color_includes_ansi_codes():
    """The default (colored) formatter wraps level/scope in ANSI escape sequences."""
    formatter = ScopedFormatter("%(levelname)s [%(scope)s] - %(message)s")
    output = formatter.format(_make_record())
    assert "\033[" in output


def test_scoped_formatter_without_color_has_no_ansi_codes():
    """use_color=False produces plain text, suitable for a log file."""
    formatter = ScopedFormatter(
        "%(levelname)s [%(scope)s] - %(message)s", use_color=False
    )
    output = formatter.format(_make_record())
    assert "\033[" not in output
    assert output == "INFO [BOT] - hello"


def test_scoped_formatter_includes_timestamp_with_given_datefmt():
    """A datefmt passed to the formatter produces a leading timestamp in that format."""
    formatter = ScopedFormatter(
        "%(asctime)s %(levelname)s [%(scope)s] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        use_color=False,
    )
    output = formatter.format(_make_record())
    assert re.match(
        r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} INFO \[BOT\] - hello$", output
    )


def test_setup_logging_resolves_string_level():
    """A level name (as env vars provide) resolves to the matching logging constant."""
    setup_logging(level="DEBUG")
    assert logging.getLogger().getEffectiveLevel() == logging.DEBUG


def test_setup_logging_unknown_level_falls_back_to_info():
    """An unrecognized level name falls back to INFO instead of raising."""
    setup_logging(level="NOT_A_LEVEL")
    assert logging.getLogger().getEffectiveLevel() == logging.INFO


def test_setup_logging_without_log_file_has_only_console_handler():
    """No log_file means only the console handler is attached."""
    setup_logging()
    assert len(logging.getLogger().handlers) == 1


def test_setup_logging_console_handler_includes_timestamp():
    """The console handler set up by setup_logging() prefixes log lines with a timestamp."""
    setup_logging()
    handler = logging.getLogger().handlers[0]
    output = handler.formatter.format(_make_record())  # type: ignore[union-attr]
    assert re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} ", output)


def test_setup_logging_with_log_file_creates_parent_dir_and_file_handler(tmp_path):
    """A log_file path attaches a RotatingFileHandler and creates missing parent directories."""
    log_file = tmp_path / "nested" / "anecbot.log"
    setup_logging(log_file=str(log_file))

    assert log_file.parent.is_dir()
    handlers = logging.getLogger().handlers
    assert len(handlers) == 2
    file_handlers = [
        h for h in handlers if isinstance(h, logging.handlers.RotatingFileHandler)
    ]
    assert len(file_handlers) == 1
    assert Path(file_handlers[0].baseFilename) == log_file
