"""Scan Swift/ObjC code for programmatic UI, gestures, and animations."""

import re
from typing import List

from ui_scanner.models import UIElement, ElementType

# Swift programmatic view patterns
SWIFT_VIEW_PATTERNS = [
    (re.compile(r'let\s+(\w+)\s*[=:]\s*UIButton'), 'UIButton'),
    (re.compile(r'let\s+(\w+)\s*[=:]\s*UILabel'), 'UILabel'),
    (re.compile(r'let\s+(\w+)\s*[=:]\s*UIImageView'), 'UIImageView'),
    (re.compile(r'let\s+(\w+)\s*[=:]\s*UITableView'), 'UITableView'),
    (re.compile(r'let\s+(\w+)\s*[=:]\s*UICollectionView'), 'UICollectionView'),
    (re.compile(r'let\s+(\w+)\s*[=:]\s*UITextField'), 'UITextField'),
    (re.compile(r'let\s+(\w+)\s*[=:]\s*UITextView'), 'UITextView'),
    (re.compile(r'let\s+(\w+)\s*[=:]\s*UIScrollView'), 'UIScrollView'),
    (re.compile(r'let\s+(\w+)\s*[=:]\s*UIStackView'), 'UIStackView'),
    (re.compile(r'let\s+(\w+)\s*[=:]\s*UIProgressView'), 'UIProgressView'),
    (re.compile(r'let\s+(\w+)\s*[=:]\s*UISlider'), 'UISlider'),
    (re.compile(r'let\s+(\w+)\s*[=:]\s*UISwitch'), 'UISwitch'),
    (re.compile(r'let\s+(\w+)\s*[=:]\s*UIStepper'), 'UIStepper'),
]

# ObjC programmatic view patterns
OBJC_VIEW_PATTERNS = [
    (re.compile(r'\[\s*UIButton\s+buttonWithType:'), 'UIButton'),
    (re.compile(r'\[\s*\[\s*UILabel\s+alloc\]\s+init\]'), 'UILabel'),
    (re.compile(r'\[\s*\[\s*UIImageView\s+alloc\]\s+init\]'), 'UIImageView'),
    (re.compile(r'\[\s*\[\s*UITextField\s+alloc\]\s+init\]'), 'UITextField'),
    (re.compile(r'\[\s*\[\s*UIScrollView\s+alloc\]\s+init\]'), 'UIScrollView'),
]

# Gesture recognizers
GESTURE_PATTERNS = [
    re.compile(r'UITapGestureRecognizer'),
    re.compile(r'UIPinchGestureRecognizer'),
    re.compile(r'UISwipeGestureRecognizer'),
    re.compile(r'UIPanGestureRecognizer'),
    re.compile(r'UILongPressGestureRecognizer'),
    re.compile(r'UIRotationGestureRecognizer'),
    re.compile(r'UIscreenEdgePanGestureRecognizer'),
]

# Animation patterns
ANIMATION_PATTERNS = [
    (re.compile(r'UIView\.animate'), 'UIView.animate'),
    (re.compile(r'UIViewPropertyAnimator'), 'UIViewPropertyAnimator'),
    (re.compile(r'CABasicAnimation'), 'CABasicAnimation'),
    (re.compile(r'CAKeyframeAnimation'), 'CAKeyframeAnimation'),
    (re.compile(r'CAAnimationGroup'), 'CAAnimationGroup'),
    (re.compile(r'CATransition'), 'CATransition'),
    (re.compile(r'CASpringAnimation'), 'CASpringAnimation'),
    (re.compile(r'TransitionCoordinator'), 'TransitionCoordinator'),
    (re.compile(r'LottieAnimationView|Lottie\.'), 'Lottie'),
]

# addSubview pattern
ADD_SUBVIEW_RE = re.compile(r'(?:addSubview|\.addSubview)\s*\(\s*(\w+)')


def scan_code(lines: List[str], is_swift: bool = True) -> List[UIElement]:
    """Scan source code for programmatic UI, gestures, and animations."""
    elements = []
    elements.extend(_find_programmatic_views(lines, is_swift))
    elements.extend(_find_gestures(lines))
    elements.extend(_find_animations(lines))
    return elements


def _find_programmatic_views(lines: List[str], is_swift: bool) -> List[UIElement]:
    """Find programmatic view creation."""
    elements = []
    patterns = SWIFT_VIEW_PATTERNS if is_swift else OBJC_VIEW_PATTERNS

    for i, line in enumerate(lines):
        for pattern, view_type in patterns:
            m = pattern.search(line)
            if m:
                var_name = m.group(1) if m.lastindex else view_type
                elements.append(UIElement(
                    name=f'{var_name} ({view_type})',
                    element_type=view_type,
                    category=_classify_ios_view(view_type),
                    element_id=var_name,
                    line_number=i + 1,
                    properties={'creation': 'programmatic'},
                ))
                break
    return elements


def _find_gestures(lines: List[str]) -> List[UIElement]:
    """Find gesture recognizer usage."""
    elements = []
    for i, line in enumerate(lines):
        for pattern in GESTURE_PATTERNS:
            if pattern.search(line):
                gesture_name = pattern.pattern
                elements.append(UIElement(
                    name=gesture_name,
                    element_type=gesture_name,
                    category=ElementType.CLICKABLE,
                    line_number=i + 1,
                    properties={'type': 'gesture'},
                ))
                break
    return elements


def _find_animations(lines: List[str]) -> List[UIElement]:
    """Find animation usage."""
    elements = []
    for i, line in enumerate(lines):
        for pattern, anim_type in ANIMATION_PATTERNS:
            if pattern.search(line):
                elements.append(UIElement(
                    name=anim_type,
                    element_type=anim_type,
                    category=ElementType.ANIMATION,
                    line_number=i + 1,
                    properties={'source': line.strip()[:200]},
                ))
                break
    return elements


def _classify_ios_view(view_type: str) -> ElementType:
    """Classify an iOS view type."""
    clickable = {'UIButton', 'UISwitch', 'UISlider', 'UIStepper'}
    input_types = {'UITextField', 'UITextView', 'UISearchBar'}
    if view_type in clickable:
        return ElementType.CLICKABLE
    if view_type in input_types:
        return ElementType.INPUT
    return ElementType.DISPLAY
