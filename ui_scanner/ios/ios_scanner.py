"""iOS scanner: coordinates VC finding, storyboard parsing, code analysis, dialog scanning."""

from pathlib import Path
from typing import Dict, List, Optional

from ui_scanner.models import ModuleInfo, Page, Platform, UIElement
from ui_scanner.utils.file_utils import find_files, read_file_lines
from ui_scanner.ios.vc_finder import find_view_controllers
from ui_scanner.ios.storyboard_parser import parse_storyboard, parse_xib
from ui_scanner.ios.code_analyzer import scan_code
from ui_scanner.ios.dialog_scanner import scan_dialogs


def scan_ios(
    root_path: str,
    verbose: bool = False,
) -> List[ModuleInfo]:
    """Scan an iOS project and return grouped results."""
    root = Path(root_path).resolve()

    # Find source files
    source_files = list(find_files(
        str(root), ('.swift', '.m', '.h'),
    ))

    if verbose:
        print(f"  [iOS] Found {len(source_files)} source files")

    # Parse storyboards and XIBs
    storyboard_elements: Dict[str, List[UIElement]] = {}
    storyboard_pages = []

    for sb_path in find_files(str(root), ('.storyboard',)):
        pages, vc_elems = parse_storyboard(str(sb_path))
        storyboard_pages.extend(pages)
        storyboard_elements.update(vc_elems)
        if verbose:
            print(f"    Storyboard {sb_path.name}: {len(pages)} VCs")

    for xib_path in find_files(str(root), ('.xib',)):
        pages, vc_elems = parse_xib(str(xib_path))
        storyboard_pages.extend(pages)
        storyboard_elements.update(vc_elems)

    # Find VCs from code
    code_pages = find_view_controllers(source_files)
    if verbose:
        print(f"    Found {len(code_pages)} VCs from code")

    # Merge: code pages get storyboard elements where class names match
    all_pages = _merge_pages(code_pages, storyboard_pages, storyboard_elements)

    # Scan code for each VC page
    for page in all_pages:
        lines = read_file_lines(page.source_file)
        if lines:
            is_swift = page.source_file.endswith('.swift')
            code_elements = scan_code(lines, is_swift)
            page.elements.extend(code_elements)
            page.dialogs = scan_dialogs(lines, is_swift)

    # Group by directory
    modules = _group_by_directory(all_pages, root)
    if verbose:
        print(f"    Grouped into {len(modules)} modules")

    return modules


def _merge_pages(
    code_pages: List[Page],
    storyboard_pages: List[Page],
    storyboard_elements: Dict[str, List[UIElement]],
) -> List[Page]:
    """Merge code-discovered VCs with storyboard data."""
    # Index storyboard pages by name
    sb_by_name = {p.name: p for p in storyboard_pages}

    merged = []
    seen_names = set()

    # Start with code pages, enrich with storyboard elements
    for page in code_pages:
        if page.name in storyboard_elements:
            page.elements.extend(storyboard_elements[page.name])
        seen_names.add(page.name)
        merged.append(page)

    # Add storyboard-only pages (no corresponding code file found)
    for sb_page in storyboard_pages:
        if sb_page.name not in seen_names:
            if sb_page.name in storyboard_elements:
                sb_page.elements.extend(storyboard_elements[sb_page.name])
            merged.append(sb_page)
            seen_names.add(sb_page.name)

    return merged


def _group_by_directory(pages: List[Page], root: Path) -> List[ModuleInfo]:
    """Group pages by their source directory."""
    groups: Dict[str, List[Page]] = {}

    for page in pages:
        if page.source_file:
            page_path = Path(page.source_file)
            try:
                rel = page_path.relative_to(root)
                # Use first 2 parts as module name
                parts = rel.parts
                module_name = '/'.join(parts[:2]) if len(parts) > 2 else parts[0] if parts else 'unknown'
            except ValueError:
                module_name = 'unknown'
        else:
            module_name = 'storyboard'

        groups.setdefault(module_name, []).append(page)

    modules = []
    for name, pages in groups.items():
        modules.append(ModuleInfo(
            name=name,
            platform=Platform.IOS,
            pages=pages,
        ))
    return modules
