from anecbot.utils.text import ZERO_WIDTH_SPACE, with_blank_lines


def test_with_blank_lines_wraps_text_with_zero_width_space_lines():
    """The text is wrapped with a zero-width-space line before and after."""
    result = with_blank_lines("hello")
    assert result == f"{ZERO_WIDTH_SPACE}\nhello\n{ZERO_WIDTH_SPACE}"


def test_with_blank_lines_preserves_internal_newlines():
    """Multi-line text keeps its internal structure, only wrapped at the edges."""
    result = with_blank_lines("line one\nline two")
    assert result == f"{ZERO_WIDTH_SPACE}\nline one\nline two\n{ZERO_WIDTH_SPACE}"
