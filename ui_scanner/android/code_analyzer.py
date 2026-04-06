"""Scan Java code for animations, programmatic UI, and click listeners."""

import re
from typing import List

from ui_scanner.models import UIElement, ElementType
from ui_scanner.utils.comment_utils import extract_comment

# Animation patterns
ANIMATION_PATTERNS = [
    (re.compile(r'ObjectAnimator\.of\w+\('), 'ObjectAnimator'),
    (re.compile(r'ValueAnimator\.of\w+\('), 'ValueAnimator'),
    (re.compile(r'\.\s*animate\(\)'), 'ViewPropertyAnimator'),
    (re.compile(r'AnimatorSet\s*[\(\w]'), 'AnimatorSet'),
    (re.compile(r'AnimationUtils\.loadAnimation\('), 'AnimationUtils'),
    (re.compile(r'LottieComposition|LottieDrawable|app:lottie_'), 'Lottie'),
    (re.compile(r'TransitionManager|TransitionSet|ChangeTransform|ChangeBounds|Fade\(|Slide\('), 'Transition'),
    (re.compile(r'MotionLayout'), 'MotionLayout'),
    (re.compile(r'overridePendingTransition\('), 'PageTransition'),
]

# Clickable listener patterns
CLICK_LISTENER_PATTERNS = [
    re.compile(r'\.setOnClickListener\s*\('),
    re.compile(r'\.setOnItemClickListener\s*\('),
    re.compile(r'\.setOnItemSelectedListener\s*\('),
    re.compile(r'\.setOnCheckedChangeListener\s*\('),
    re.compile(r'\.setOnLongClickListener\s*\('),
    re.compile(r'\.setOnTouchListener\s*\('),
]

# Programmatic view creation patterns
PROG_VIEW_PATTERN = re.compile(
    r'new\s+(Button|ImageButton|TextView|ImageView|EditText|'
    r'RecyclerView|ListView|CheckBox|RadioButton|Switch|'
    r'Spinner|ProgressBar|SeekBar|ScrollView|WebView|'
    r'ViewPager|VideoView|MapView)\s*\('
)
PROG_VIEW_VAR = re.compile(r'(Button|ImageButton|TextView|ImageView|EditText)\s+(\w+)\s*=')


def scan_code(lines: List[str], file_ext: str = '.java') -> List[UIElement]:
    """Scan Java code for animations, click listeners, and programmatic views."""
    elements = []
    elements.extend(_find_animations(lines, file_ext))
    elements.extend(_find_click_listeners(lines, file_ext))
    elements.extend(_find_programmatic_views(lines, file_ext))
    return elements


def _find_animations(lines: List[str], file_ext: str = '.java') -> List[UIElement]:
    """Find animation usage in code."""
    elements = []
    for i, line in enumerate(lines):
        for pattern, anim_type in ANIMATION_PATTERNS:
            if pattern.search(line):
                elements.append(UIElement(
                    name=anim_type,
                    element_type=anim_type,
                    category=ElementType.ANIMATION,
                    line_number=i + 1,
                    comment=extract_comment(lines, i + 1, file_ext),
                    properties={'source': line.strip()[:200]},
                ))
                break  # One match per line is enough
    return elements


def _find_click_listeners(lines: List[str], file_ext: str = '.java') -> List[UIElement]:
    """Find click/event listener registrations."""
    elements = []
    for i, line in enumerate(lines):
        for pattern in CLICK_LISTENER_PATTERNS:
            m = pattern.search(line)
            if m:
                # Try to extract the view variable name
                view_name = line.strip().split('.')[0].strip() if '.' in line else ''
                listener_type = m.group(0).replace('(', '').replace('.', '').strip()
                elements.append(UIElement(
                    name=f'{view_name}.{listener_type}' if view_name else listener_type,
                    element_type=listener_type,
                    category=ElementType.CLICKABLE,
                    line_number=i + 1,
                    comment=extract_comment(lines, i + 1, file_ext),
                    properties={'listener': listener_type, 'view': view_name},
                ))
                break
    return elements


def _find_programmatic_views(lines: List[str], file_ext: str = '.java') -> List[UIElement]:
    """Find views created programmatically."""
    elements = []
    for i, line in enumerate(lines):
        m = PROG_VIEW_PATTERN.search(line)
        if m:
            view_type = m.group(1)
            elements.append(UIElement(
                name=f'{view_type} (code)',
                element_type=view_type,
                category=_classify_prog_view(view_type),
                line_number=i + 1,
                comment=extract_comment(lines, i + 1, file_ext),
                properties={'creation': 'programmatic'},
            ))
            continue

        m = PROG_VIEW_VAR.search(line)
        if m:
            view_type = m.group(1)
            var_name = m.group(2)
            elements.append(UIElement(
                name=f'{var_name} ({view_type})',
                element_type=view_type,
                category=_classify_prog_view(view_type),
                element_id=var_name,
                line_number=i + 1,
                comment=extract_comment(lines, i + 1, file_ext),
                properties={'creation': 'programmatic'},
            ))
    return elements


def _classify_prog_view(view_type: str) -> ElementType:
    """Classify a programmatic view type."""
    clickable_types = {'Button', 'ImageButton', 'CheckBox', 'RadioButton', 'Switch', 'Spinner'}
    input_types = {'EditText'}
    if view_type in clickable_types:
        return ElementType.CLICKABLE
    if view_type in input_types:
        return ElementType.INPUT
    return ElementType.DISPLAY
