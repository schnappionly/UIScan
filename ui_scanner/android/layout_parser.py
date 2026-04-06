"""Parse Android XML layout files and classify UI elements."""

import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Set

from ui_scanner.models import UIElement, ElementType

ANDROID_NS = 'http://schemas.android.com/apk/res/android'

# Element classification sets
CLICKABLE_TAGS: Set[str] = {
    'Button', 'ImageButton', 'FloatingActionButton', 'MaterialButton',
    'CheckedTextView', 'CheckBox', 'RadioButton', 'Switch', 'SwitchCompat',
    'Spinner', 'ToggleButton', 'Chip', 'ChipView',
}

DISPLAY_TAGS: Set[str] = {
    'TextView', 'ImageView', 'RecyclerView', 'ListView', 'GridView',
    'ScrollView', 'HorizontalScrollView', 'WebView', 'ProgressBar',
    'RatingBar', 'SeekBar', 'MapView', 'TextureView', 'SurfaceView',
    'VideoView', 'ExpandableListView', 'AdapterView', 'Gallery',
    'ImageSwitcher', 'TextSwitcher', 'ViewFlipper', 'Chronometer',
    'DigitalClock', 'AnalogClock', 'BottomNavigationView', 'TabLayout',
}

CONTAINER_TAGS: Set[str] = {
    'ConstraintLayout', 'LinearLayout', 'FrameLayout', 'RelativeLayout',
    'CoordinatorLayout', 'GridLayout', 'TableLayout', 'TableRow',
    'NavigationViewSet', 'ViewPager', 'ViewPager2', 'CardView',
    'NestedScrollView', 'SwipeRefreshLayout', 'TextInputLayout',
    'ChipGroup', 'FlowLayout', 'MotionLayout', 'Guideline', 'Barrier',
    'include', 'merge', 'ViewStub',
}

INPUT_TAGS: Set[str] = {
    'EditText', 'TextInputEditText', 'AutoCompleteTextView',
    'MultiAutoCompleteTextView', 'SearchView', 'EditText',
}

# All known tags for stripping package prefix (e.g., android.widget.Button -> Button)
KNOWN_WIDGETS = CLICKABLE_TAGS | DISPLAY_TAGS | CONTAINER_TAGS | INPUT_TAGS


def parse_layout(
    layout_path: str,
    resource_dir: str = '',
    visited: Optional[Set[str]] = None,
) -> List[UIElement]:
    """Parse a layout XML file and return classified UI elements."""
    if visited is None:
        visited = set()

    layout_name = Path(layout_path).stem
    if layout_name in visited:
        return []
    visited.add(layout_name)

    try:
        tree = ET.parse(layout_path)
    except ET.ParseError:
        return []
    except FileNotFoundError:
        return []

    root = tree.getroot()
    elements: List[UIElement] = []
    _walk_element(root, elements, resource_dir, visited)
    return elements


def _walk_element(
    elem: ET.Element,
    elements: List[UIElement],
    resource_dir: str,
    visited: Set[str],
) -> None:
    """Recursively walk XML elements, collecting UI elements."""
    tag = _strip_tag(elem.tag)

    # Handle <include> by resolving to referenced layout
    if tag == 'include':
        layout_ref = _get_attr(elem, 'layout')
        if layout_ref and layout_ref.startswith('@layout/'):
            layout_name = layout_ref[8:]
            included_path = _resolve_layout_path(layout_name, resource_dir)
            if included_path:
                included_elements = parse_layout(included_path, resource_dir, visited)
                elements.extend(included_elements)
        return

    # Skip merge and ViewStub
    if tag in ('merge', 'ViewStub', 'requestFocus'):
        for child in elem:
            _walk_element(child, elements, resource_dir, visited)
        return

    # Classify the element
    element = _classify_element(tag, elem)
    if element:
        elements.append(element)

    # Recurse into children
    for child in elem:
        _walk_element(child, elements, resource_dir, visited)


def _classify_element(tag: str, elem: ET.Element) -> Optional[UIElement]:
    """Classify a single XML element into an ElementType."""
    # Determine the clean tag name
    clean_tag = tag
    if '.' in tag:
        # Handle fully qualified names like android.widget.Button
        short = tag.rsplit('.', 1)[-1]
        if short in KNOWN_WIDGETS:
            clean_tag = short
        else:
            clean_tag = short

    element_id = _get_attr(elem, 'id')
    if element_id and element_id.startswith('@+id/'):
        element_id = element_id[5:]
    elif element_id and element_id.startswith('@id/'):
        element_id = element_id[4:]

    text_content = _get_attr(elem, 'text') or ''
    if text_content.startswith('@string/'):
        text_content = text_content  # Keep reference; will be resolved later

    # Determine category
    category = _get_category(clean_tag, elem)
    if category is None:
        return None

    # Collect useful properties
    properties = {}
    for attr_key in ['hint', 'src', 'background', 'visibility', 'enabled',
                     'onClick', 'clickable', 'focusable', 'inputType', 'maxLines']:
        val = _get_attr(elem, attr_key)
        if val:
            properties[attr_key] = val

    return UIElement(
        name=clean_tag,
        element_type=clean_tag,
        category=category,
        element_id=element_id,
        text_content=text_content,
        properties=properties,
    )


def _get_category(tag: str, elem: ET.Element) -> Optional[ElementType]:
    """Determine the category of an element."""
    # Clickable: explicit tag or onClick attribute or clickable=true
    if tag in CLICKABLE_TAGS:
        return ElementType.CLICKABLE

    if _get_attr(elem, 'onClick'):
        return ElementType.CLICKABLE

    if _get_attr(elem, 'clickable') == 'true':
        return ElementType.CLICKABLE

    # Input elements
    if tag in INPUT_TAGS:
        return ElementType.INPUT

    # Display elements
    if tag in DISPLAY_TAGS:
        return ElementType.DISPLAY

    # Container elements
    if tag in CONTAINER_TAGS:
        return ElementType.CONTAINER

    # Unknown tags with id are treated as display
    if _get_attr(elem, 'id'):
        return ElementType.DISPLAY

    return None


def _get_attr(elem: ET.Element, name: str) -> str:
    """Get an Android namespaced attribute value."""
    # Try namespaced form first
    val = elem.get(f'{{{ANDROID_NS}}}{name}', '')
    if val:
        return val
    # Try without namespace
    return elem.get(name, '')


def _strip_tag(tag: str) -> str:
    """Strip namespace from XML tag."""
    if tag.startswith('{'):
        return tag.split('}', 1)[-1]
    return tag


def _resolve_layout_path(layout_name: str, resource_dir: str) -> Optional[str]:
    """Resolve a layout resource name to its file path."""
    if not resource_dir:
        return None
    layout_dir = os.path.join(resource_dir, 'layout')
    candidate = os.path.join(layout_dir, f'{layout_name}.xml')
    if os.path.isfile(candidate):
        return candidate
    return None
