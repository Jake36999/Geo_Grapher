"""Map constant IDs to their comment-block and assignment lines."""

from collections import defaultdict
from typing import Iterable


def constant_comment_lines(text: str, constants: Iterable[tuple[str, int, int]]) -> dict[int, set[str]]:
    """Map each line number to the canonical IDs of constants it belongs to.

    Includes assignment lines and preceding contiguous full-line '#' comments
    at the same indentation level. Stops at gaps, non-comments, or different indentation.
    """
    lines = text.splitlines()
    result: dict[int, set[str]] = defaultdict(set)

    # Process each constant's line span
    for const_id, start_line, end_line in constants:
        # Add the assignment lines themselves
        for line_num in range(start_line, end_line + 1):
            result[line_num].add(const_id)

        # Now find the comment block above the assignment
        if start_line < 1:
            continue  # Invalid line number

        first_line_index = start_line - 1  # Convert to 0-based index
        if first_line_index >= len(lines):
            continue

        first_line = lines[first_line_index]
        indent = _get_indent(first_line)

        # Scan upward from the line just before the assignment
        for i in range(first_line_index - 1, -1, -1):
            line = lines[i]
            stripped = line.lstrip()
            # Stop conditions:
            # - Blank line
            # - Non-comment line
            # - Comment with different indentation
            # - Inline comment (starts with non-'#' after strip)
            if not stripped:
                break
            if not stripped.startswith('#'):
                break
            if _get_indent(line) != indent:
                break
            # It's a valid comment line in the block
            result[i + 1].add(const_id)  # Convert back to 1-based line number

    return {line_num: result[line_num] for line_num in sorted(result)}


def _get_indent(line: str) -> str:
    """Extract leading whitespace from a line."""
    return line[:len(line) - len(line.lstrip())]
