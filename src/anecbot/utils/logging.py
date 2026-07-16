import logging
import logging.handlers
from pathlib import Path

MAX_LOG_FILE_BYTES = 5_000_000
LOG_FILE_BACKUP_COUNT = 3

SCOPE_MAP = {
    "anecbot.bot": "BOT",
    "anecbot.models": "DB",
}

LEVEL_COLORS = {
    logging.DEBUG: "\033[36m",
    logging.INFO: "\033[32m",
    logging.WARNING: "\033[33m",
    logging.ERROR: "\033[31m",
    logging.CRITICAL: "\033[1;31m",
}

SCOPE_COLORS = {
    "BOT": "\033[35m",
    "DB": "\033[34m",
}

RESET = "\033[0m"


class ScopedFormatter(logging.Formatter):
    """Formatter that adds a short scope tag derived from logger name."""

    def __init__(self, fmt: str, use_color: bool = True) -> None:
        """Initialize the formatter, optionally disabling ANSI color codes."""
        super().__init__(fmt)
        self.use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with scope tag."""
        scope = next(
            (
                tag
                for prefix, tag in SCOPE_MAP.items()
                if record.name.startswith(prefix)
            ),
            record.name,
        )
        if self.use_color:
            level_color = LEVEL_COLORS.get(record.levelno, "")
            scope_color = SCOPE_COLORS.get(scope, "")
            record.scope = f"{scope_color}{scope}{RESET}"  # type: ignore[attr-defined]
            record.levelname = f"{level_color}{record.levelname}{RESET}"
        else:
            record.scope = scope  # type: ignore[attr-defined]
        return super().format(record)


def _resolve_level(level: int | str) -> int:
    """Resolve a log level given as an int or a level name (e.g. from an env var)."""
    if isinstance(level, int):
        return level
    return getattr(logging, level.upper(), logging.INFO)


def setup_logging(level: int | str = logging.INFO, log_file: str | None = None) -> None:
    """Configure logging with a scoped console handler and an optional rotating file handler."""
    resolved_level = _resolve_level(level)
    fmt = "%(levelname)s [%(scope)s] - %(message)s"

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ScopedFormatter(fmt))
    handlers: list[logging.Handler] = [console_handler]

    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=MAX_LOG_FILE_BYTES,
            backupCount=LOG_FILE_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(ScopedFormatter(fmt, use_color=False))
        handlers.append(file_handler)

    logging.basicConfig(level=resolved_level, handlers=handlers, force=True)
