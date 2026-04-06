"""Fast file traversal and parallel processing utilities."""

import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Callable, Generator, List, Tuple, Any, Optional

DEFAULT_EXCLUDE_DIRS = {
    'build', '.gradle', '.idea', '.git', '.svn',
    'Pods', 'DerivedData', '.build', 'node_modules',
    '.venv', 'venv', '__pycache__', '.cache',
    'bin', 'gen', 'out', 'target', '.mvn',
}


def find_files(
    root: str,
    extensions: Tuple[str, ...],
    exclude_dirs: Optional[set] = None,
) -> Generator[Path, None, None]:
    """Yield file paths matching given extensions, excluding certain directories."""
    exclude = exclude_dirs or DEFAULT_EXCLUDE_DIRS
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in exclude]
        for fname in filenames:
            if fname.endswith(extensions):
                yield Path(dirpath) / fname


def read_file_text(path: str) -> Optional[str]:
    """Read file text with encoding fallback (UTF-8 -> Latin-1)."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        try:
            with open(path, 'r', encoding='latin-1') as f:
                return f.read()
        except Exception:
            return None
    except Exception:
        return None


def read_file_lines(path: str) -> Optional[List[str]]:
    """Read file lines with encoding fallback."""
    text = read_file_text(path)
    if text is None:
        return None
    return text.splitlines()


def quick_contains(path: str, *keywords: str) -> bool:
    """Fast check if file contains any of the keywords (binary-safe)."""
    try:
        with open(path, 'rb') as f:
            chunk = f.read(65536)  # Read first 64KB
            text = chunk.decode('utf-8', errors='ignore')
            return any(kw in text for kw in keywords)
    except Exception:
        return False


def parallel_process(
    files: List[Path],
    processor: Callable,
    workers: int = 4,
    verbose: bool = False,
) -> List[Any]:
    """Process files in parallel using ProcessPoolExecutor."""
    results = []
    if not files:
        return results

    effective_workers = min(workers, len(files), os.cpu_count() or 4)

    with ProcessPoolExecutor(max_workers=effective_workers) as executor:
        futures = {executor.submit(processor, f): f for f in files}
        for future in futures:
            try:
                result = future.result(timeout=30)
                if result:
                    if isinstance(result, list):
                        results.extend(result)
                    else:
                        results.append(result)
            except Exception as e:
                if verbose:
                    f = futures[future]
                    print(f"  [WARN] Error processing {f}: {e}")
    return results


def find_dirs_with_file(root: str, filename: str) -> List[Path]:
    """Find all directories containing a specific file (e.g., build.gradle)."""
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        if filename in filenames:
            found.append(Path(dirpath))
    return found
