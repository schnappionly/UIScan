"""Harmony scanner: coordinates page finding, code analysis, and dialog scanning."""

from pathlib import Path
from typing import Dict, List

from ui_scanner.models import ModuleInfo, Page, Platform
from ui_scanner.utils.file_utils import find_files, read_file_lines
from ui_scanner.harmony.page_finder import find_pages
from ui_scanner.harmony.code_analyzer import scan_code
from ui_scanner.harmony.dialog_scanner import scan_dialogs


def scan_harmony(
    root_path: str,
    verbose: bool = False,
) -> List[ModuleInfo]:
    """Scan a Harmony (ArkTS/ArkUI) project and return grouped results."""
    root = Path(root_path).resolve()

    # Find .ets source files
    ets_files = list(find_files(str(root), ('.ets',)))

    if verbose:
        print(f"  [Harmony] Found {len(ets_files)} .ets files")

    # Find pages and components
    pages = find_pages(ets_files)
    if verbose:
        print(f"    Found {len(pages)} pages/components")

    # Scan code for each page
    for page in pages:
        lines = read_file_lines(page.source_file)
        if lines:
            code_elements = scan_code(lines)
            page.elements.extend(code_elements)
            page.dialogs = scan_dialogs(lines)
            if verbose and (code_elements or page.dialogs):
                print(f"      {page.name}: {len(code_elements)} elements, {len(page.dialogs)} dialogs")

    # Group by directory
    modules = _group_by_directory(pages, root)
    if verbose:
        print(f"    Grouped into {len(modules)} modules")

    return modules


def _group_by_directory(pages: List[Page], root: Path) -> List[ModuleInfo]:
    """Group pages by their source directory."""
    groups: Dict[str, List[Page]] = {}

    for page in pages:
        if page.source_file:
            try:
                rel = Path(page.source_file).relative_to(root)
                parts = rel.parts
                # Use first 2 parts as module name
                module_name = '/'.join(parts[:2]) if len(parts) > 2 else parts[0] if parts else 'unknown'
            except ValueError:
                module_name = 'unknown'
        else:
            module_name = 'unknown'

        groups.setdefault(module_name, []).append(page)

    modules = []
    for name, pages in groups.items():
        modules.append(ModuleInfo(
            name=name,
            platform=Platform.HARMONY,
            pages=pages,
        ))
    return modules
