"""Comment extraction utilities for source code files."""

import re
from typing import Optional


def extract_comment(
    lines: list,
    line_number: int,
    file_ext: str = '',
) -> str:
    """Extract comments near a given line.

    Checks 2 lines before and 2 lines after the target line for comments.

    Args:
        lines: All lines of the file (0-indexed).
        line_number: 1-based line number of the target.
        file_ext: File extension (.java, .kt, .swift, .ets, .xml, etc.)

    Returns:
        Extracted comment text, or empty string if no comment found.
    """
    if line_number <= 0:
        return ''

    idx = line_number - 1  # Convert to 0-based
    window_start = max(0, idx - 2)
    window_end = min(len(lines), idx + 3)  # +3 to include 2 lines after

    comments = []
    ext = file_ext.lower()

    if ext in ('.xml', '.storyboard', '.xib'):
        for i in range(window_start, window_end):
            line = lines[i].strip()
            m = re.search(r'<!--\s*(.*?)\s*-->', line)
            if m:
                comments.append(m.group(1))
    else:
        # Java, Kotlin, Swift, ArkTS, ObjC — all use // and /* */
        for i in range(window_start, window_end):
            line = lines[i].strip()
            # Single-line comment
            if '//' in line:
                m = re.search(r'//\s*(.*)', line)
                if m:
                    text = m.group(1).strip()
                    if text:
                        comments.append(text)
            # Inline block comment
            elif '/*' in line:
                m = re.search(r'/\*\s*(.*?)\s*\*/', line)
                if m:
                    text = m.group(1).strip()
                    if text:
                        comments.append(text)

    return ' '.join(comments)
