"""Scan iOS Swift/ObjC code for dialogs and alerts."""

import re
from typing import List, Optional

from ui_scanner.models import DialogInfo
from ui_scanner.android.dialog_scanner import infer_scenario

# iOS dialog patterns
IOS_DIALOG_PATTERNS = [
    (re.compile(r'UIAlertController'), 'UIAlertController'),
    (re.compile(r'UIAlertView'), 'UIAlertView'),
    (re.compile(r'UIActionSheet'), 'UIActionSheet'),
    (re.compile(r'popoverPresentationController'), 'Popover'),
    (re.compile(r'UIPopoverController'), 'UIPopoverController'),
    (re.compile(r'SFSafariViewController'), 'SFSafariViewController'),
    (re.compile(r'WKWebView'), 'WKWebView Popup'),
]

# Context extraction patterns
_SWIFT_TITLE_RE = re.compile(r'title\s*:\s*"([^"]*)"')
_SWIFT_MSG_RE = re.compile(r'message\s*:\s*"([^"]*)"')
_OBJC_TITLE_RE = re.compile(r'@"([^"]*)"')
_SWIFT_STYLE_RE = re.compile(r'preferredStyle\s*:\s*\.(\w+)')


def scan_dialogs(lines: List[str], is_swift: bool = True) -> List[DialogInfo]:
    """Scan source code for dialog/alert usage."""
    dialogs = []
    for i, line in enumerate(lines):
        for pattern, dialog_type in IOS_DIALOG_PATTERNS:
            if pattern.search(line):
                context = _extract_context(lines, i, is_swift)
                scenario = infer_scenario(context)

                # Determine alert style
                style = 'alert'
                m = _SWIFT_STYLE_RE.search(line)
                if m:
                    style = m.group(1)
                elif 'actionSheet' in line.lower():
                    style = 'actionSheet'

                dialogs.append(DialogInfo(
                    name=f'{dialog_type}',
                    dialog_type=dialog_type,
                    scenario=scenario,
                    message_hint=context[:200],
                    line_number=i + 1,
                    properties={'style': style, 'context': context[:500]},
                ))
                break
    return dialogs


def _extract_context(lines: List[str], match_line: int, is_swift: bool) -> str:
    """Extract surrounding context for dialog scenario inference."""
    start = max(0, match_line - 2)
    end = min(len(lines), match_line + 15)
    context_parts = []

    for line_no in range(start, end):
        line = lines[line_no]
        if is_swift:
            for pattern in [_SWIFT_TITLE_RE, _SWIFT_MSG_RE]:
                m = pattern.search(line)
                if m:
                    context_parts.append(m.group(1))
        else:
            for m in _OBJC_TITLE_RE.finditer(line):
                context_parts.append(m.group(1))

    return ' '.join(context_parts)
