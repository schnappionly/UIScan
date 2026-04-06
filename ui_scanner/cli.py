"""CLI entry point for UI Scanner."""

import argparse
import sys

from ui_scanner.scanner import ScanRunner
from ui_scanner.report.html_builder import HTMLBuilder


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='UI Scanner - Scan Android/iOS/Harmony projects for UI elements',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python3 -m ui_scanner.cli --android /path/to/android-project -o report.html
  python3 -m ui_scanner.cli --ios /path/to/ios-project -o report.html
  python3 -m ui_scanner.cli --harmony /path/to/harmony-project -o report.html
  python3 -m ui_scanner.cli --android /path/to/android --harmony /path/to/harmony -o report.html
""",
    )
    parser.add_argument('--android', metavar='PATH',
                        help='Path to Android project root')
    parser.add_argument('--ios', metavar='PATH',
                        help='Path to iOS project root')
    parser.add_argument('--harmony', metavar='PATH',
                        help='Path to Harmony (ArkTS) project root')
    parser.add_argument('--output', '-o', metavar='FILE', default='ui_report.html',
                        help='Output HTML file path (default: ui_report.html)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Print progress details')
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    if not args.android and not args.ios and not args.harmony:
        print("Error: Must specify at least one of --android, --ios, or --harmony", file=sys.stderr)
        return 1

    runner = ScanRunner(
        android_path=args.android,
        ios_path=args.ios,
        harmony_path=args.harmony,
        verbose=args.verbose,
    )

    result = runner.run()

    # Generate HTML report
    builder = HTMLBuilder(result)
    html_content = builder.build()

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"\nReport saved to: {args.output}")
    print(f"  Pages: {result.total_pages} | Elements: {result.total_elements} | Dialogs: {result.total_dialogs}")
    print(f"  Scan time: {result.scan_time:.2f}s")

    if result.errors:
        print(f"\nWarnings/Errors ({len(result.errors)}):")
        for err in result.errors:
            print(f"  - {err}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
