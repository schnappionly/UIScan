"""Parse iOS storyboard and XIB files for UI elements."""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ui_scanner.models import Page, PageType, Platform, UIElement, ElementType

# Storyboard element classification
STORYBOARD_CLICKABLE = {
    'button', 'segmentedControl', 'pageControl', 'stepper',
    'slider', 'switch', 'barButtonItem', 'collectionViewCell',
    'tableViewCell', 'tapGestureRecognizer', 'pinchGestureRecognizer',
    'swipeGestureRecognizer', 'panGestureRecognizer',
    'longPressGestureRecognizer',
}

STORYBOARD_DISPLAY = {
    'label', 'imageView', 'tableView', 'collectionView',
    'textView', 'scrollView', 'mapView', 'progressView',
    'activityIndicatorView', 'visualEffectView', 'stackView',
    'wkWebView', 'datePicker', 'pickerView', 'calendarView',
}

STORYBOARD_INPUT = {
    'textField', 'searchBar', 'textView',
}

STORYBOARD_CONTAINER = {
    'view', 'containerView', 'navigationController', 'tabBarController',
    'splitViewController', 'pageViewController', 'popoverController',
}


def parse_storyboard(path: str) -> Tuple[List[Page], Dict[str, List[UIElement]]]:
    """Parse a storyboard file, returning VCs and their elements.

    Returns:
        Tuple of (list of Page objects, dict mapping VC class name -> elements)
    """
    try:
        tree = ET.parse(path)
    except ET.ParseError:
        return [], {}
    root = tree.getroot()

    pages = []
    vc_elements = {}  # class_name -> [UIElement]

    # Find all scenes
    for scene in root.iter('scene'):
        vc_info = _extract_vc_from_scene(scene)
        if vc_info:
            class_name, page_type = vc_info
            elements = _extract_elements_from_scene(scene)
            pages.append(Page(
                name=class_name,
                page_type=page_type,
                platform=Platform.IOS,
                source_file=str(path),
                layout_file=str(path),
            ))
            vc_elements[class_name] = elements

    return pages, vc_elements


def parse_xib(path: str) -> Tuple[List[Page], Dict[str, List[UIElement]]]:
    """Parse a XIB file."""
    try:
        tree = ET.parse(path)
    except ET.ParseError:
        return [], {}
    root = tree.getroot()

    pages = []
    vc_elements = {}

    # XIB files may have File's Owner as a VC
    for obj in root:
        class_name = obj.get('customClass', '')
        if not class_name:
            continue

        # Check if it's a VC type
        if _is_vc_class(class_name):
            elements = _walk_xib_elements(obj)
            pages.append(Page(
                name=class_name,
                page_type=PageType.VIEW_CONTROLLER,
                platform=Platform.IOS,
                source_file=str(path),
                layout_file=str(path),
            ))
            vc_elements[class_name] = elements
            break  # Usually one VC per XIB

    # If no VC found, treat as a View
    if not pages:
        elements = _walk_xib_elements(root)
        if elements:
            xib_name = Path(path).stem
            pages.append(Page(
                name=xib_name,
                page_type=PageType.VIEW,
                platform=Platform.IOS,
                source_file=str(path),
                layout_file=str(path),
            ))
            vc_elements[xib_name] = elements

    return pages, vc_elements


def _extract_vc_from_scene(scene: ET.Element) -> Optional[Tuple[str, PageType]]:
    """Extract ViewController info from a storyboard scene."""
    # Look for VC-like objects in the scene
    vc_tags = [
        'viewController', 'tableViewController', 'collectionViewController',
        'navigationController', 'tabBarController', 'splitViewController',
        'pageViewController', 'abstractViewController',
    ]

    for obj in scene.iter():
        tag = obj.tag
        if tag in vc_tags or tag.endswith('ViewController'):
            custom_class = obj.get('customClass', '')
            storyboard_id = obj.get('storyboardIdentifier', obj.get('id', ''))
            if custom_class:
                page_type = PageType.VIEW_CONTROLLER
                return custom_class, page_type
            # Use tag as fallback name with storyboard ID
            if storyboard_id:
                return f'{tag}_{storyboard_id[:20]}', PageType.VIEW_CONTROLLER
    return None


def _extract_elements_from_scene(scene: ET.Element) -> List[UIElement]:
    """Extract all UI elements from a storyboard scene."""
    elements = []
    seen_ids = set()

    for elem in scene.iter():
        tag = elem.tag
        if tag in ('scene', 'objects') or tag.endswith('ViewController') or 'Controller' in tag:
            continue

        category = _classify_storyboard_element(tag, elem)
        if category is None:
            continue

        elem_id = elem.get('userLabel', '') or elem.get(' RestorationIdentifier', '') or ''
        properties = {}
        for attr in ['text', 'title', 'placeholder', 'image', 'enabled', 'hidden', 'tag']:
            val = elem.get(attr, '')
            if val:
                properties[attr] = val

        # Check for action connections (clickable indicator)
        for conn in elem.iter('action'):
            properties['hasAction'] = 'true'
            category = ElementType.CLICKABLE

        key = f'{tag}:{elem_id}'
        if key not in seen_ids:
            seen_ids.add(key)
            elements.append(UIElement(
                name=elem.get('userLabel', '') or tag,
                element_type=tag,
                category=category,
                element_id=elem_id,
                properties=properties,
            ))

    return elements


def _walk_xib_elements(root: ET.Element) -> List[UIElement]:
    """Walk a XIB tree to find UI elements."""
    elements = []
    seen_ids = set()

    for elem in root.iter():
        tag = elem.tag
        category = _classify_storyboard_element(tag, elem)
        if category is None:
            continue

        elem_id = elem.get('userLabel', '')
        key = f'{tag}:{elem_id}'
        if key not in seen_ids:
            seen_ids.add(key)
            elements.append(UIElement(
                name=elem_id or tag,
                element_type=tag,
                category=category,
                element_id=elem_id,
            ))

    return elements


def _classify_storyboard_element(tag: str, elem: ET.Element) -> Optional[ElementType]:
    """Classify a storyboard/XIB element."""
    if tag in STORYBOARD_CLICKABLE:
        return ElementType.CLICKABLE
    if tag in STORYBOARD_INPUT:
        return ElementType.INPUT
    if tag in STORYBOARD_DISPLAY:
        return ElementType.DISPLAY
    if tag in STORYBOARD_CONTAINER:
        return ElementType.CONTAINER
    # Check for custom class suggesting a view
    custom = elem.get('customClass', '')
    if custom:
        return ElementType.DISPLAY
    return None


def _is_vc_class(class_name: str) -> bool:
    """Check if a class name suggests a ViewController."""
    cn = class_name.lower()
    return cn.endswith('viewcontroller') or cn.endswith('vc') or cn.endswith('controller')
