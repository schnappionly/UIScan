"""Data models for UI Scanner."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional


class ElementType(str, Enum):
    CLICKABLE = "可点击"
    DISPLAY = "展示数据"
    ANIMATION = "动画"
    CONTAINER = "容器布局"
    INPUT = "输入"


class Platform(str, Enum):
    ANDROID = "Android"
    IOS = "iOS"


class PageType(str, Enum):
    ACTIVITY = "Activity"
    FRAGMENT = "Fragment"
    VIEW_CONTROLLER = "ViewController"
    VIEW = "View"


@dataclass
class UIElement:
    """A single UI element found in a page."""
    name: str
    element_type: str
    category: ElementType
    element_id: str = ""
    text_content: str = ""
    properties: Dict[str, str] = field(default_factory=dict)
    source_file: str = ""
    line_number: int = 0

    @property
    def category_label(self) -> str:
        return self.category.value


@dataclass
class DialogInfo:
    """A dialog/popup found in a page."""
    name: str
    dialog_type: str
    scenario: str  # e.g., "确认", "错误提示", "输入", "加载中", "权限请求", "删除警告"
    message_hint: str = ""
    source_file: str = ""
    line_number: int = 0
    properties: Dict[str, str] = field(default_factory=dict)


@dataclass
class Page:
    """A page (Activity/Fragment/ViewController) with its UI elements."""
    name: str
    page_type: PageType
    platform: Platform
    source_file: str = ""
    layout_file: str = ""
    package_name: str = ""
    parent_class: str = ""
    elements: List[UIElement] = field(default_factory=list)
    dialogs: List[DialogInfo] = field(default_factory=list)

    @property
    def clickable_elements(self) -> List[UIElement]:
        return [e for e in self.elements if e.category == ElementType.CLICKABLE]

    @property
    def display_elements(self) -> List[UIElement]:
        return [e for e in self.elements if e.category == ElementType.DISPLAY]

    @property
    def animation_elements(self) -> List[UIElement]:
        return [e for e in self.elements if e.category == ElementType.ANIMATION]

    @property
    def input_elements(self) -> List[UIElement]:
        return [e for e in self.elements if e.category == ElementType.INPUT]

    @property
    def container_elements(self) -> List[UIElement]:
        return [e for e in self.elements if e.category == ElementType.CONTAINER]


@dataclass
class ModuleInfo:
    """A module/package grouping of pages."""
    name: str
    platform: Platform
    pages: List[Page] = field(default_factory=list)


@dataclass
class ScanResult:
    """Complete scan result for all scanned projects."""
    modules: List[ModuleInfo] = field(default_factory=list)
    total_pages: int = 0
    total_elements: int = 0
    total_dialogs: int = 0
    scan_time: float = 0.0
    errors: List[str] = field(default_factory=list)

    def add_module(self, module: ModuleInfo):
        self.modules.append(module)
        self._recalculate()

    def _recalculate(self):
        self.total_pages = sum(len(m.pages) for m in self.modules)
        self.total_elements = sum(
            len(p.elements) for m in self.modules for p in m.pages
        )
        self.total_dialogs = sum(
            len(p.dialogs) for m in self.modules for p in m.pages
        )

    @property
    def android_modules(self) -> List[ModuleInfo]:
        return [m for m in self.modules if m.platform == Platform.ANDROID]

    @property
    def ios_modules(self) -> List[ModuleInfo]:
        return [m for m in self.modules if m.platform == Platform.IOS]
