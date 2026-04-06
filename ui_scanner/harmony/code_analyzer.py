"""Analyze ArkTS/ArkUI code for UI elements, animations, and gestures."""

import re
from typing import List, Tuple

from ui_scanner.models import UIElement, ElementType
from ui_scanner.utils.comment_utils import extract_comment

# ── Component classification sets ──

CLICKABLE_COMPONENTS = {
    'Button', 'Toggle', 'Checkbox', 'Radio', 'Rating',
    'Stepper', 'StepperItem', 'SwipeAction', 'SelectOption',
}
DISPLAY_COMPONENTS = {
    'Text', 'Image', 'List', 'ListItem', 'Grid', 'GridItem',
    'WaterFlow', 'FlowItem', 'Progress', 'LoadingProgress',
    'Gauge', 'Marquee', 'QRCode', 'RichText', 'DataPanel',
    'Scroll', 'TabContent', 'Web', 'Video', 'Canvas',
    'Shape', 'Clock', 'Calendar', 'TextClock', 'AlphabetIndexer',
    'Blank', 'Divider',
}
CONTAINER_COMPONENTS = {
    'Column', 'Row', 'Stack', 'Flex', 'RelativeContainer',
    'GridRow', 'GridCol', 'Navigation', 'NavRouter', 'NavDestination',
    'Tabs', 'TabBar', 'TabContent', 'List', 'Grid', 'Swiper',
    'Panel', 'SideBarContainer', 'Counter', 'Refresh', 'LazyForEach',
}
INPUT_COMPONENTS = {
    'TextInput', 'TextArea', 'Search', 'RichEditor',
    'PatternLock', 'Select', 'TimePicker', 'DatePicker',
    'TextPicker',
}
ANIMATION_APIS = {
    'animateTo', 'animation', 'Animator', 'AnimatorResult',
}
ALL_COMPONENTS = CLICKABLE_COMPONENTS | DISPLAY_COMPONENTS | CONTAINER_COMPONENTS | INPUT_COMPONENTS

# Component regex — matches declarative UI calls like Button(...) or Text("...")
_COMPONENT_RE = re.compile(r'\b(' + '|'.join(sorted(ALL_COMPONENTS, key=len, reverse=True)) + r')\s*[\(\{]')

# Animation patterns
_ANIMATION_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r'\banimateTo\s*\('), 'animateTo'),
    (re.compile(r'\bAnimator\b'), 'Animator'),
    (re.compile(r'\.animation\s*\('), 'animation'),
    (re.compile(r'@AnimatableExtend'), '@AnimatableExtend'),
    (re.compile(r'\bAnimatorResult\b'), 'AnimatorResult'),
    (re.compile(r'\bSpring\s*\('), 'SpringAnimation'),
    (re.compile(r'\bCurves\.'), 'Curves'),
]

# Gesture patterns
_GESTURE_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r'\bTapGesture\b'), 'TapGesture'),
    (re.compile(r'\bLongPressGesture\b'), 'LongPressGesture'),
    (re.compile(r'\bPinchGesture\b'), 'PinchGesture'),
    (re.compile(r'\bRotationGesture\b'), 'RotationGesture'),
    (re.compile(r'\bSwipeGesture\b'), 'SwipeGesture'),
    (re.compile(r'\bPanGesture\b'), 'PanGesture'),
    (re.compile(r'\.gesture\s*\('), 'gesture'),
]

# Property extraction patterns
_ID_RE = re.compile(r'\.id\s*\(\s*["\']?(\w+)["\']?\s*\)')
_TEXT_RE = re.compile(r'(?:Text|Button)\s*\(\s*["\']([^"\']*)["\']')
_PLACEHOLDER_RE = re.compile(r'\.placeholder\s*\(\s*["\']([^"\']*)["\']')


def scan_code(lines: list) -> List[UIElement]:
    """Scan ArkTS code lines for UI elements, animations, and gestures."""
    elements = []
    seen = set()  # Deduplicate by (name, line_number)

    for i, line in enumerate(lines):
        line_num = i + 1
        stripped = line.strip()

        # Skip comments and empty lines
        if not stripped or stripped.startswith('//') or stripped.startswith('/*'):
            continue

        # UI components
        for m in _COMPONENT_RE.finditer(stripped):
            comp_name = m.group(1)
            elem = _make_element(comp_name, stripped, lines, line_num, '.ets')
            key = (elem.name, elem.line_number)
            if key not in seen:
                seen.add(key)
                elements.append(elem)
            break  # One component match per line

        # Animations
        for pattern, label in _ANIMATION_PATTERNS:
            if pattern.search(stripped):
                key = (label, line_num)
                if key not in seen:
                    seen.add(key)
                    comment = extract_comment(lines, line_num, '.ets')
                    elements.append(UIElement(
                        name=label,
                        element_type=label,
                        category=ElementType.ANIMATION,
                        line_number=line_num,
                        comment=comment,
                        properties={'source': stripped[:200]},
                    ))
                break

        # Gestures
        for pattern, label in _GESTURE_PATTERNS:
            if pattern.search(stripped):
                key = (label, line_num)
                if key not in seen:
                    seen.add(key)
                    comment = extract_comment(lines, line_num, '.ets')
                    elements.append(UIElement(
                        name=label,
                        element_type=label,
                        category=ElementType.CLICKABLE,
                        line_number=line_num,
                        comment=comment,
                        properties={'type': 'gesture'},
                    ))
                break

    return elements


def _make_element(
    comp_name: str,
    line: str,
    all_lines: list,
    line_num: int,
    file_ext: str,
) -> UIElement:
    """Create a UIElement from a component match."""
    category = _classify_component(comp_name)

    # Extract properties from the same line
    props = {}
    text_content = ''

    m = _TEXT_RE.search(line)
    if m:
        text_content = m.group(1)

    m = _ID_RE.search(line)
    if m:
        props['id'] = m.group(1)

    comment = extract_comment(all_lines, line_num, file_ext)

    # Element name: use text content if available, else component name
    name = text_content if text_content else comp_name

    return UIElement(
        name=name,
        element_type=comp_name,
        category=category,
        text_content=text_content,
        line_number=line_num,
        comment=comment,
        properties=props,
    )


def _classify_component(comp_name: str) -> ElementType:
    """Classify a Harmony component into an element category."""
    if comp_name in CLICKABLE_COMPONENTS:
        return ElementType.CLICKABLE
    if comp_name in INPUT_COMPONENTS:
        return ElementType.INPUT
    if comp_name in DISPLAY_COMPONENTS:
        return ElementType.DISPLAY
    if comp_name in CONTAINER_COMPONENTS:
        return ElementType.CONTAINER
    return ElementType.DISPLAY  # Default fallback
