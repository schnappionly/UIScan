"""Scan Android Java code for dialogs and popups."""

import re
from typing import Dict, List, Optional

from ui_scanner.models import DialogInfo

# Dialog detection patterns
DIALOG_PATTERNS = [
    (re.compile(r'AlertDialog\.\s*Builder\s*\(|new\s+AlertDialog\b'), 'AlertDialog'),
    (re.compile(r'DialogFragment\b|extends\s+\w*Dialog\s'), 'DialogFragment'),
    (re.compile(r'BottomSheetDialog(?:Fragment)?\b'), 'BottomSheetDialog'),
    (re.compile(r'MaterialAlertDialogBuilder\b|MaterialDialog\b'), 'MaterialDialog'),
    (re.compile(r'ProgressDialog\b'), 'ProgressDialog'),
    (re.compile(r'DatePickerDialog\b'), 'DatePickerDialog'),
    (re.compile(r'TimePickerDialog\b'), 'TimePickerDialog'),
    (re.compile(r'Toast\.\s*makeText\b'), 'Toast'),
    (re.compile(r'Snackbar\.\s*make\b'), 'Snackbar'),
    (re.compile(r'PopupWindow\b'), 'PopupWindow'),
    (re.compile(r'LoadingDialog\b|LoadingView\b|ProgressView\b'), 'LoadingDialog'),
    (re.compile(r'TipDialog\b|HintDialog\b'), 'TipDialog'),
]

# Patterns to extract dialog context (title, message)
_TITLE_RE = re.compile(r'\.setTitle\s*\(\s*(?:R\.string\.(\w+)|"([^"]*)")')
_MESSAGE_RE = re.compile(r'\.setMessage\s*\(\s*(?:R\.string\.(\w+)|"([^"]*)")')
_POSITIVE_RE = re.compile(r'\.setPositiveButton\s*\(\s*(?:R\.string\.(\w+)|"([^"]*)")')
_NEGATIVE_RE = re.compile(r'\.setNegativeButton\s*\(\s*(?:R\.string\.(\w+)|"([^"]*)")')

# Scenario inference keywords (Chinese + English)
SCENARIO_KEYWORDS = {
    '删除确认': ['delete', '删除', 'remove', '移除', '移入', 'trash'],
    '网络错误': ['network', '网络', 'connection', '连接', 'timeout', '超时', 'offline'],
    '登录提示': ['login', '登录', 'signin', 'sign_in', '登录', '密码', 'password', '账号'],
    '权限请求': ['permission', '权限', 'authorize', '授权', 'access'],
    '加载中': ['loading', '加载', 'progress', '等待', 'please wait', 'loading'],
    '操作确认': ['confirm', '确认', 'sure', '确定', '是否'],
    '错误提示': ['error', '错误', 'fail', '失败', 'exception', '异常', 'wrong'],
    '成功提示': ['success', '成功', 'complete', '完成', 'done'],
    '退出确认': ['exit', '退出', 'logout', '登出', 'quit', '退出登录'],
    '更新提示': ['update', '更新', 'upgrade', '升级', 'version', '版本'],
    '保存确认': ['save', '保存', 'store', '存储'],
    '支付相关': ['pay', '支付', 'purchase', '购买', 'order', '订单', 'price', '价格'],
    '分享': ['share', '分享', 'forward', '转发'],
    '评价': ['rate', '评价', 'review', '评分', 'comment', '评论'],
    '注册': ['register', '注册', 'signup', 'sign_up', '注册'],
    '数据同步': ['sync', '同步', 'backup', '备份', 'restore', '恢复'],
}


def scan_dialogs(
    lines: List[str],
    strings_map: Optional[Dict[str, str]] = None,
) -> List[DialogInfo]:
    """Scan Java code for dialog/popup usage."""
    if strings_map is None:
        strings_map = {}

    dialogs = []
    for i, line in enumerate(lines):
        for pattern, dialog_type in DIALOG_PATTERNS:
            if pattern.search(line):
                context = _extract_context(lines, i, strings_map)
                scenario = infer_scenario(context)
                dialogs.append(DialogInfo(
                    name=f'{dialog_type}',
                    dialog_type=dialog_type,
                    scenario=scenario,
                    message_hint=context[:200],
                    line_number=i + 1,
                    properties={'context': context[:500]},
                ))
                break  # One dialog per line
    return dialogs


def _extract_context(
    lines: List[str],
    match_line: int,
    strings_map: Dict[str, str],
) -> str:
    """Extract surrounding context text for a dialog match."""
    start = max(0, match_line - 2)
    end = min(len(lines), match_line + 20)
    context_parts = []

    for line_no in range(start, end):
        line = lines[line_no]
        # Title
        m = _TITLE_RE.search(line)
        if m:
            text = m.group(2) or strings_map.get(m.group(1), m.group(1))
            context_parts.append(text)
        # Message
        m = _MESSAGE_RE.search(line)
        if m:
            text = m.group(2) or strings_map.get(m.group(1), m.group(1))
            context_parts.append(text)
        # Positive button
        m = _POSITIVE_RE.search(line)
        if m:
            text = m.group(2) or strings_map.get(m.group(1), m.group(1))
            context_parts.append(text)
        # Negative button
        m = _NEGATIVE_RE.search(line)
        if m:
            text = m.group(2) or strings_map.get(m.group(1), m.group(1))
            context_parts.append(text)

    return ' '.join(context_parts)


def infer_scenario(text: str) -> str:
    """Infer dialog scenario from text content."""
    if not text:
        return '未知'
    text_lower = text.lower()
    for scenario, keywords in SCENARIO_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return scenario
    return '通用弹框'
