"""Detect Harmony dialogs and infer scenarios."""

import re
from typing import List, Tuple

from ui_scanner.models import DialogInfo
from ui_scanner.utils.comment_utils import extract_comment
from ui_scanner.android.dialog_scanner import infer_scenario

# Harmony dialog patterns: (regex, type_label)
DIALOG_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r'\bAlertDialog\b'), 'AlertDialog'),
    (re.compile(r'\bActionSheet\b'), 'ActionSheet'),
    (re.compile(r'\bToast\b'), 'Toast'),
    (re.compile(r'\bCustomDialogController\b'), 'CustomDialog'),
    (re.compile(r'\bCustomDialog\b'), 'CustomDialog'),
    (re.compile(r'\bDatePickerDialog\b'), 'DatePickerDialog'),
    (re.compile(r'\bTimePickerDialog\b'), 'TimePickerDialog'),
    (re.compile(r'\bTextPickerDialog\b'), 'TextPickerDialog'),
    (re.compile(r'\bpromptAction\b'), 'promptAction'),
    (re.compile(r'\bshowDialog\b'), 'showDialog'),
]

# Context extraction: look for string literals in nearby lines
_STRING_RE = re.compile(r'["\']([^"\']{2,})["\']')


def scan_dialogs(lines: list) -> List[DialogInfo]:
    """Scan ArkTS code for dialog usage."""
    dialogs = []

    for i, line in enumerate(lines):
        line_num = i + 1
        stripped = line.strip()
        if not stripped or stripped.startswith('//'):
            continue

        for pattern, label in DIALOG_PATTERNS:
            if pattern.search(stripped):
                context = _extract_context(lines, i)
                scenario = infer_scenario(context)
                comment = extract_comment(lines, line_num, '.ets')

                dialogs.append(DialogInfo(
                    name=label,
                    dialog_type=label,
                    scenario=scenario,
                    message_hint=context[:200],
                    line_number=line_num,
                    comment=comment,
                    properties={'context': context[:500]},
                ))
                break  # One dialog per line

    return dialogs


def _extract_context(lines: list, match_idx: int) -> str:
    """Extract surrounding text for scenario inference."""
    start = max(0, match_idx - 2)
    end = min(len(lines), match_idx + 16)
    texts = []
    for i in range(start, end):
        for m in _STRING_RE.finditer(lines[i]):
            val = m.group(1)
            # Skip short strings and common non-text values
            if len(val) >= 2 and not val.startswith(('0x', 'http', '$r(')):
                texts.append(val)
    return ' '.join(texts)
