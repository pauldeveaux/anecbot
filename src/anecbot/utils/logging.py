import logging

SCOPE_MAP = {
    "anecbot.bot": "BOT",
    "anecbot.models": "DB",
    "anecbot.features": "FEATURES",
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
    "FEATURES": "\033[32m",
}

RESET = "\033[0m"


class ScopedFormatter(logging.Formatter):
    """Formatter that adds a short scope tag derived from logger name."""

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
        level_color = LEVEL_COLORS.get(record.levelno, "")
        scope_color = SCOPE_COLORS.get(scope, "")
        record.scope = f"{scope_color}{scope}{RESET}"  # type: ignore[attr-defined]
        record.levelname = f"{level_color}{record.levelname}{RESET}"
        return super().format(record)


def setup_logging(level: int = logging.INFO) -> None:
    """Configure logging with scoped formatter."""
    handler = logging.StreamHandler()
    handler.setFormatter(ScopedFormatter("%(levelname)s [%(scope)s] - %(message)s"))
    logging.basicConfig(level=level, handlers=[handler])
