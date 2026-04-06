"""Discover Harmony pages (@Entry) and components (@Component) from .ets files."""

import re
from pathlib import Path
from typing import List

from ui_scanner.models import Page, PageType, Platform
from ui_scanner.utils.file_utils import read_file_lines, quick_contains
from ui_scanner.utils.comment_utils import extract_comment

# @Entry or @Component followed by struct declaration
_ENTRY_RE = re.compile(
    r'@Entry\s*\n\s*(?:export\s+)?(?:default\s+)?struct\s+(\w+)', re.MULTILINE
)
_COMPONENT_RE = re.compile(
    r'@Component\s*\n\s*(?:export\s+)?(?:default\s+)?struct\s+(\w+)', re.MULTILINE
)

# Also handle single-line form: @Entry struct Foo
_ENTRY_INLINE_RE = re.compile(
    r'@Entry\s+(?:export\s+)?(?:default\s+)?struct\s+(\w+)'
)
_COMPONENT_INLINE_RE = re.compile(
    r'@Component\s+(?:export\s+)?(?:default\s+)?struct\s+(\w+)'
)


def find_pages(ets_files: list) -> List[Page]:
    """Find all @Entry pages and @Component components from .ets files."""
    pages = []
    for fpath in ets_files:
        fpath = Path(fpath) if not isinstance(fpath, Path) else fpath
        if not quick_contains(str(fpath), 'struct', '@Entry', '@Component'):
            continue
        pages.extend(_parse_file(fpath))
    return pages


def _parse_file(fpath: Path) -> List[Page]:
    """Parse a single .ets file for pages and components."""
    lines = read_file_lines(str(fpath))
    if not lines:
        return []

    text = '\n'.join(lines)
    results = []

    # Find @Entry pages
    for m in _ENTRY_RE.finditer(text):
        name = m.group(1)
        line_no = text[:m.start()].count('\n') + 1
        comment = extract_comment(lines, line_no, '.ets')
        results.append(Page(
            name=name,
            page_type=PageType.PAGE,
            platform=Platform.HARMONY,
            source_file=str(fpath),
            line_number=line_no,
            comment=comment,
        ))

    for m in _ENTRY_INLINE_RE.finditer(text):
        name = m.group(1)
        line_no = text[:m.start()].count('\n') + 1
        # Skip if already found by multiline pattern
        if any(p.name == name and p.page_type == PageType.PAGE for p in results):
            continue
        comment = extract_comment(lines, line_no, '.ets')
        results.append(Page(
            name=name,
            page_type=PageType.PAGE,
            platform=Platform.HARMONY,
            source_file=str(fpath),
            line_number=line_no,
            comment=comment,
        ))

    # Find @Component components
    for m in _COMPONENT_RE.finditer(text):
        name = m.group(1)
        line_no = text[:m.start()].count('\n') + 1
        if any(p.name == name for p in results):
            continue
        comment = extract_comment(lines, line_no, '.ets')
        results.append(Page(
            name=name,
            page_type=PageType.COMPONENT,
            platform=Platform.HARMONY,
            source_file=str(fpath),
            line_number=line_no,
            comment=comment,
        ))

    for m in _COMPONENT_INLINE_RE.finditer(text):
        name = m.group(1)
        line_no = text[:m.start()].count('\n') + 1
        if any(p.name == name for p in results):
            continue
        comment = extract_comment(lines, line_no, '.ets')
        results.append(Page(
            name=name,
            page_type=PageType.COMPONENT,
            platform=Platform.HARMONY,
            source_file=str(fpath),
            line_number=line_no,
            comment=comment,
        ))

    return results
