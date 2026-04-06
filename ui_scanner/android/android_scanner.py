"""Android scanner: coordinates page finding, layout parsing, code analysis, dialog scanning."""

import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional

from ui_scanner.models import ModuleInfo, Page, Platform
from ui_scanner.utils.file_utils import (
    find_files, read_file_lines, read_file_text, find_dirs_with_file,
)
from ui_scanner.android.page_finder import find_pages
from ui_scanner.android.layout_parser import parse_layout
from ui_scanner.android.code_analyzer import scan_code
from ui_scanner.android.dialog_scanner import scan_dialogs


def scan_android(
    root_path: str,
    verbose: bool = False,
) -> List[ModuleInfo]:
    """Scan an Android project and return grouped results."""
    root = Path(root_path).resolve()

    # Find modules (directories with build.gradle)
    gradle_files = list(root.rglob('build.gradle')) + list(root.rglob('build.gradle.kts'))
    if gradle_files:
        module_dirs = list(set(g.parent for g in gradle_files))
    else:
        module_dirs = [root]

    modules = []
    for mod_dir in module_dirs:
        mod_name = mod_dir.relative_to(root).as_posix() if mod_dir != root else 'app'
        if verbose:
            print(f"  [Android] Scanning module: {mod_name}")

        pages = _scan_module(mod_dir, verbose)
        if pages:
            modules.append(ModuleInfo(
                name=mod_name,
                platform=Platform.ANDROID,
                pages=pages,
            ))

    return modules


def _scan_module(module_dir: Path, verbose: bool) -> List[Page]:
    """Scan a single Android module."""
    # Find source directories
    src_dirs = list(module_dir.rglob('src/main/java')) + list(module_dir.rglob('src/main/kotlin'))
    if not src_dirs:
        src_dirs = [module_dir / 'src' / 'main'] if (module_dir / 'src/main').exists() else [module_dir]

    # Find resource dir
    res_dir = _find_res_dir(module_dir)

    # Build strings map for dialog scenario inference
    strings_map = _build_strings_map(res_dir) if res_dir else {}

    # Find Java/Kotlin files
    java_files = []
    for src in src_dirs:
        java_files.extend(find_files(str(src), ('.java', '.kt')))
    if not java_files:
        # Try broader search
        java_files = list(find_files(str(module_dir), ('.java', '.kt')))

    if verbose:
        print(f"    Found {len(java_files)} source files")

    # Find Activity/Fragment pages
    pages = find_pages(java_files)
    if verbose:
        print(f"    Found {len(pages)} pages")

    # For each page, parse layout and analyze code
    for page in pages:
        # Parse layout XML
        if page.layout_file and res_dir:
            layout_path = _resolve_layout(page.layout_file, res_dir)
            if layout_path:
                page.layout_file = str(layout_path)
                elements = parse_layout(layout_path, str(res_dir))
                page.elements.extend(elements)
                if verbose:
                    print(f"      {page.name}: {len(elements)} elements from layout")

        # Scan code for animations, click listeners, programmatic views
        lines = read_file_lines(page.source_file)
        if lines:
            code_elements = scan_code(lines)
            page.elements.extend(code_elements)
            page.dialogs = scan_dialogs(lines, strings_map)
            if verbose and page.dialogs:
                print(f"      {page.name}: {len(page.dialogs)} dialogs")

    return pages


def _find_res_dir(module_dir: Path) -> Optional[Path]:
    """Find the res/ directory for a module."""
    candidates = [
        module_dir / 'src' / 'main' / 'res',
        module_dir / 'res',
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return None


def _resolve_layout(layout_name: str, res_dir: Path) -> Optional[str]:
    """Resolve layout name to file path."""
    layout_dir = res_dir / 'layout'
    candidate = layout_dir / f'{layout_name}.xml'
    if candidate.is_file():
        return str(candidate)
    return None


def _build_strings_map(res_dir: Path) -> Dict[str, str]:
    """Build a map of string resource names to values."""
    strings_map = {}
    values_dir = res_dir / 'values'
    if not values_dir.is_dir():
        return strings_map

    strings_file = values_dir / 'strings.xml'
    if not strings_file.is_file():
        return strings_map

    try:
        tree = ET.parse(str(strings_file))
        root = tree.getroot()
        for elem in root.iter('string'):
            name = elem.get('name', '')
            value = elem.text or ''
            if name:
                strings_map[name] = value
    except ET.ParseError:
        pass

    return strings_map
