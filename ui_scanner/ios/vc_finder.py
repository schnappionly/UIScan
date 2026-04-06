"""Discover iOS ViewController classes from ObjC and Swift source files."""

import re
from pathlib import Path
from typing import List, Optional, Set

from ui_scanner.models import Page, PageType, Platform
from ui_scanner.utils.file_utils import read_file_lines, quick_contains

# ObjC: @interface ClassName : SuperClass
_OBJC_IFACE_RE = re.compile(r'@interface\s+(\w+)\s*:\s*(\w+)')

# ObjC: @implementation ClassName
_OBJC_IMPL_RE = re.compile(r'@implementation\s+(\w+)')

# Swift: class ClassName : SuperClass, Protocol1, Protocol2 {
_SWIFT_CLASS_RE = re.compile(
    r'class\s+(\w+)\s*(?::\s*([^{]+?))?\s*\{'
)

# Known VC superclasses
VC_SUPERCLASSES = {
    'UIViewController', 'UITableViewController', 'UICollectionViewController',
    'UINavigationController', 'UITabBarController', 'UISplitViewController',
    'UIPageViewController', 'UIImagePickerController', 'GLKViewController',
}

# Quick-filter keywords
_KEYWORDS = ('ViewController', 'Controller', 'UIViewController', 'VC')


def find_view_controllers(source_files: List[Path]) -> List[Page]:
    """Find all ViewController classes from source files."""
    pages = []
    for fpath in source_files:
        if not quick_contains(str(fpath), *_KEYWORDS):
            continue
        ext = fpath.suffix
        if ext in ('.m', '.h'):
            found = _parse_objc(fpath)
        elif ext == '.swift':
            found = _parse_swift(fpath)
        else:
            continue
        pages.extend(found)
    return pages


def _parse_objc(path: Path) -> List[Page]:
    """Parse ObjC file for ViewController classes."""
    lines = read_file_lines(str(path))
    if not lines:
        return []

    pages = []
    # First pass: collect interfaces with superclass
    classes = {}  # name -> superclass
    for line in lines:
        m = _OBJC_IFACE_RE.search(line)
        if m:
            classes[m.group(1)] = m.group(2)

    for class_name, superclass in classes.items():
        page_type = _classify_vc(class_name, superclass)
        if page_type:
            pages.append(Page(
                name=class_name,
                page_type=page_type,
                platform=Platform.IOS,
                source_file=str(path),
                parent_class=superclass,
            ))

    return pages


def _parse_swift(path: Path) -> List[Page]:
    """Parse Swift file for ViewController classes."""
    lines = read_file_lines(str(path))
    if not lines:
        return []

    pages = []
    for i, line in enumerate(lines):
        m = _SWIFT_CLASS_RE.search(line)
        if m:
            class_name = m.group(1)
            inheritance = m.group(2) or ''
            # Check if any parent is a VC
            parents = [p.strip() for p in inheritance.split(',')]
            superclass = parents[0] if parents else ''
            page_type = _classify_vc(class_name, superclass)
            if page_type:
                pages.append(Page(
                    name=class_name,
                    page_type=page_type,
                    platform=Platform.IOS,
                    source_file=str(path),
                    parent_class=superclass,
                ))

    return pages


def _classify_vc(class_name: str, superclass: str) -> Optional[PageType]:
    """Determine if a class is a ViewController."""
    if superclass in VC_SUPERCLASSES:
        return PageType.VIEW_CONTROLLER
    # Check naming convention
    name_lower = class_name.lower()
    if name_lower.endswith('viewcontroller') or name_lower.endswith('vc'):
        return PageType.VIEW_CONTROLLER
    if name_lower.endswith('controller') and 'view' in name_lower:
        return PageType.VIEW_CONTROLLER
    # Check if superclass follows convention
    super_lower = superclass.lower()
    if super_lower.endswith('viewcontroller') or super_lower.endswith('vc'):
        return PageType.VIEW_CONTROLLER
    return None
