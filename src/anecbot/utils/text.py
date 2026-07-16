ZERO_WIDTH_SPACE = "​"


def with_blank_lines(text: str) -> str:
    """Wrap text with a blank line before and after that survives Discord's whitespace trimming."""
    return f"{ZERO_WIDTH_SPACE}\n{text}\n{ZERO_WIDTH_SPACE}"
