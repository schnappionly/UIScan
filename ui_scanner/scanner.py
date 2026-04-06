"""Top-level scanner orchestrator."""

import time
from typing import List, Optional

from ui_scanner.models import ScanResult, ModuleInfo


class ScanRunner:
    """Orchestrates Android and iOS scanning."""

    def __init__(
        self,
        android_path: Optional[str] = None,
        ios_path: Optional[str] = None,
        harmony_path: Optional[str] = None,
        verbose: bool = False,
    ):
        self.android_path = android_path
        self.ios_path = ios_path
        self.harmony_path = harmony_path
        self.verbose = verbose

    def run(self) -> ScanResult:
        """Run the scan and return results."""
        result = ScanResult()
        start = time.time()

        if self.android_path:
            self._log("Scanning Android project...")
            try:
                from ui_scanner.android.android_scanner import scan_android
                modules = scan_android(self.android_path, verbose=self.verbose)
                for m in modules:
                    result.add_module(m)
                self._log(f"  Android: {len(modules)} modules found")
            except Exception as e:
                result.errors.append(f"Android scan error: {e}")
                self._log(f"  Android error: {e}")

        if self.ios_path:
            self._log("Scanning iOS project...")
            try:
                from ui_scanner.ios.ios_scanner import scan_ios
                modules = scan_ios(self.ios_path, verbose=self.verbose)
                for m in modules:
                    result.add_module(m)
                self._log(f"  iOS: {len(modules)} modules found")
            except Exception as e:
                result.errors.append(f"iOS scan error: {e}")
                self._log(f"  iOS error: {e}")

        if self.harmony_path:
            self._log("Scanning Harmony project...")
            try:
                from ui_scanner.harmony.harmony_scanner import scan_harmony
                modules = scan_harmony(self.harmony_path, verbose=self.verbose)
                for m in modules:
                    result.add_module(m)
                self._log(f"  Harmony: {len(modules)} modules found")
            except Exception as e:
                result.errors.append(f"Harmony scan error: {e}")
                self._log(f"  Harmony error: {e}")

        result.scan_time = time.time() - start
        self._log(f"Scan complete in {result.scan_time:.2f}s")
        self._log(f"  Total: {result.total_pages} pages, {result.total_elements} elements, {result.total_dialogs} dialogs")

        if result.errors:
            self._log(f"  Errors: {len(result.errors)}")
            for err in result.errors:
                self._log(f"    - {err}")

        return result

    def _log(self, msg: str):
        if self.verbose:
            print(msg)
