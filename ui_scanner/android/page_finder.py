"""Discover Android Activity and Fragment classes from Java source files."""

import re
from pathlib import Path
from typing import List, Optional

from ui_scanner.models import Page, PageType, Platform
from ui_scanner.utils.file_utils import read_file_lines, quick_contains

# Known Activity superclasses
ACTIVITY_SUPERS = {
    'Activity', 'AppCompatActivity', 'FragmentActivity', 'ActionBarActivity',
    'ListActivity', 'LauncherActivity', 'BaseActivity', 'MvpActivity',
    'MviActivity', 'AndroidActivityResult', 'ComponentActivity',
}

# Known Fragment superclasses
FRAGMENT_SUPERS = {
    'Fragment', 'DialogFragment', 'BottomSheetDialogFragment', 'ListFragment',
    'SupportFragment', 'MvpFragment', 'MviFragment', 'PreferenceFragment',
    'PreferenceFragmentCompat', 'BaseFragment',
}

# Regex: class declaration with optional extends/implements
_CLASS_RE = re.compile(
    r'(?:public\s+|abstract\s+|final\s+)*class\s+(\w+)\s+'
    r'(?:extends\s+(\w+))?\s*(?:implements\s+[\w,\s]+)?\s*\{'
)

# Layout reference patterns
_LAYOUT_PATTERNS = [
    re.compile(r'setContentView\s*\(\s*R\.layout\.(\w+)'),
    re.compile(r'inflater\.inflate\s*\(\s*R\.layout\.(\w+)'),
    re.compile(r'LayoutInflater.*?inflate\s*\(\s*R\.layout\.(\w+)'),
    re.compile(r'DataBindingUtil\.inflate.*?R\.layout\.(\w+)'),
    re.compile(r'@Layout\s*\(\s*R\.layout\.(\w+)\s*\)'),
    re.compile(r'\.setContent\s*\(\s*R\.layout\.(\w+)'),
]

_PACKAGE_RE = re.compile(r'package\s+([\w.]+)\s*;')

# Quick-filter keywords
_KEYWORDS = ('Activity', 'Fragment', 'activity', 'fragment', 'Controller')


def find_pages(java_files: List[Path]) -> List[Page]:
    """Find all Activity/Fragment classes from Java files."""
    pages = []
    for fpath in java_files:
        # Quick filter: skip files unlikely to contain Activity/Fragment
        if not quick_contains(str(fpath), *_KEYWORDS):
            continue
        found = _parse_file(fpath)
        pages.extend(found)
    return pages


def _parse_file(path: Path) -> List[Page]:
    """Parse a single Java file for Activity/Fragment classes."""
    lines = read_file_lines(str(path))
    if not lines:
        return []

    package = ''
    pages = []
    class_info = {}  # class_name -> superclass

    # Build class map
    for i, line in enumerate(lines):
        # Package
        m = _PACKAGE_RE.search(line)
        if m:
            package = m.group(1)

        # Class declaration
        m = _CLASS_RE.search(line)
        if m:
            class_name = m.group(1)
            superclass = m.group(2) or ''
            class_info[class_name] = superclass

    if not class_info:
        return []

    # Resolve inheritance: if superclass is also in this file or follows naming convention
    for class_name, superclass in class_info.items():
        page_type = _determine_page_type(class_name, superclass, class_info)
        if page_type is None:
            continue

        layout = _find_layout_reference(lines)
        pages.append(Page(
            name=class_name,
            page_type=page_type,
            platform=Platform.ANDROID,
            source_file=str(path),
            layout_file=layout,
            package_name=package,
            parent_class=superclass,
        ))

    return pages


def _determine_page_type(class_name: str, superclass: str, class_info: dict) -> Optional[PageType]:
    """Determine if a class is an Activity or Fragment."""
    # Direct superclass match
    if superclass in ACTIVITY_SUPERS:
        return PageType.ACTIVITY
    if superclass in FRAGMENT_SUPERS:
        return PageType.FRAGMENT
    # Check if superclass ends with Activity/Fragment (custom base class convention)
    if superclass:
        if superclass.endswith('Activity'):
            return PageType.ACTIVITY
        if superclass.endswith('Fragment'):
            return PageType.FRAGMENT
    # Fallback: naming convention
    if class_name.endswith('Activity'):
        return PageType.ACTIVITY
    if class_name.endswith('Fragment'):
        return PageType.FRAGMENT
    return None


def _find_layout_reference(lines: List[str]) -> str:
    """Find the layout resource name referenced in the code."""
    for line in lines:
        for pattern in _LAYOUT_PATTERNS:
            m = pattern.search(line)
            if m:
                return m.group(1)
    return ''
