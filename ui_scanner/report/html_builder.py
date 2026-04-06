"""Generate interactive HTML report from scan results."""

import html
import json
import time
from io import StringIO
from typing import List

from ui_scanner.models import (
    ScanResult, ModuleInfo, Page, UIElement, DialogInfo,
    ElementType, Platform,
)


CSS = """\
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f7fa; color: #2c3e50; }
.header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px 40px; }
.header h1 { font-size: 24px; font-weight: 600; margin-bottom: 6px; }
.header .meta { font-size: 13px; opacity: 0.85; }
.stats { display: flex; gap: 20px; padding: 20px 40px; background: white; border-bottom: 1px solid #e1e4e8; flex-wrap: wrap; }
.stat-card { background: #f8f9fa; border-radius: 10px; padding: 16px 24px; min-width: 150px; }
.stat-card .num { font-size: 28px; font-weight: 700; color: #2c3e50; }
.stat-card .label { font-size: 12px; color: #7f8c8d; margin-top: 2px; }
.controls { padding: 16px 40px; background: white; border-bottom: 1px solid #e1e4e8; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.controls input[type="text"] { padding: 8px 14px; border: 1px solid #d1d5da; border-radius: 6px; font-size: 14px; width: 280px; outline: none; }
.controls input[type="text"]:focus { border-color: #667eea; box-shadow: 0 0 0 3px rgba(102,126,234,0.15); }
.controls select { padding: 8px 12px; border: 1px solid #d1d5da; border-radius: 6px; font-size: 13px; background: white; outline: none; }
.btn { padding: 7px 14px; border: 1px solid #d1d5da; border-radius: 6px; background: white; cursor: pointer; font-size: 13px; }
.btn:hover { background: #f0f0f0; }
.search-info { font-size: 12px; color: #7f8c8d; padding: 4px 0; }
.content { padding: 20px 40px; }
.platform-section { margin-bottom: 24px; }
.platform-header { display: flex; align-items: center; gap: 10px; padding: 12px 0; cursor: pointer; }
.platform-header h2 { font-size: 18px; }
.platform-icon { font-size: 22px; }
.module-section { margin-left: 16px; margin-bottom: 12px; }
.module-header { font-size: 15px; font-weight: 600; color: #34495e; padding: 8px 12px; background: #eef1f5; border-radius: 6px; cursor: pointer; }
.page-section { margin-left: 16px; margin-bottom: 8px; }
.page-header { font-size: 14px; font-weight: 500; padding: 6px 10px; border-left: 3px solid #667eea; background: #fafbfc; border-radius: 0 4px 4px 0; cursor: pointer; }
.page-type-badge { display: inline-block; font-size: 11px; padding: 1px 6px; border-radius: 3px; margin-left: 8px; font-weight: normal; }
.badge-activity { background: #dbeafe; color: #1e40af; }
.badge-fragment { background: #fce7f3; color: #9d174d; }
.badge-vc { background: #d1fae5; color: #065f46; }
.badge-view { background: #fef3c7; color: #92400e; }
.badge-page { background: #e0e7ff; color: #3730a3; }
.badge-component { background: #fce7f3; color: #9d174d; }
.category-section { margin-left: 20px; margin-top: 4px; }
.category-header { font-size: 13px; font-weight: 500; padding: 4px 8px; border-radius: 4px; display: inline-block; margin: 2px 0; cursor: pointer; }
.cat-clickable { background: #dbeafe; color: #1e40af; }
.cat-display { background: #d1fae5; color: #065f46; }
.cat-animation { background: #fef3c7; color: #92400e; }
.cat-input { background: #ede9fe; color: #5b21b6; }
.cat-container { background: #f1f5f9; color: #475569; }
.element-item { margin-left: 24px; padding: 4px 0; font-size: 13px; color: #555; display: flex; gap: 8px; align-items: baseline; flex-wrap: wrap; }
.element-id { font-family: 'SF Mono', 'Fira Code', monospace; color: #e11d48; font-size: 12px; }
.element-type { color: #7c3aed; font-size: 12px; }
.element-props { color: #94a3b8; font-size: 12px; }
.element-line { color: #94a3b8; font-size: 11px; font-family: 'SF Mono', monospace; background: #f1f5f9; padding: 1px 5px; border-radius: 3px; }
.element-comment { color: #6b7280; font-size: 12px; font-style: italic; }
.dialog-section { margin-left: 20px; margin-top: 4px; }
.dialog-header { background: #fff7ed; color: #9a3412; }
.dialog-item { margin-left: 24px; padding: 4px 0; font-size: 13px; }
.dialog-type { color: #7c3aed; font-size: 12px; }
.dialog-scenario { display: inline-block; font-size: 11px; padding: 1px 6px; border-radius: 3px; background: #fef3c7; color: #92400e; margin-left: 6px; }
details summary { list-style: none; }
details summary::-webkit-details-marker { display: none; }
details summary::before { content: '▶ '; font-size: 10px; display: inline-block; transition: transform 0.15s; }
details[open] summary::before { transform: rotate(90deg); }
.hidden { display: none !important; }
.no-results { padding: 40px; text-align: center; color: #94a3b8; font-size: 15px; }
mark { background: #ffe066; padding: 0 2px; border-radius: 2px; }
.search-match { background: #fffbeb; border-left: 3px solid #f59e0b; padding-left: 4px; }
"""

JS = """\
let filterPlatform = 'all';
let filterCategory = 'all';
let searchText = '';
let originalContents = new WeakMap();

// Save original textContent for all searchable elements
function initSearch() {
    document.querySelectorAll('[data-searchable]').forEach(el => {
        originalContents.set(el, el.innerHTML);
    });
}

function removeHighlights() {
    document.querySelectorAll('[data-searchable]').forEach(el => {
        const orig = originalContents.get(el);
        if (orig !== undefined) {
            el.innerHTML = orig;
        }
        el.classList.remove('search-match');
    });
}

function highlightText(textNode, query) {
    const text = textNode.textContent;
    const lower = text.toLowerCase();
    const idx = lower.indexOf(query.toLowerCase());
    if (idx === -1) return false;

    const before = text.substring(0, idx);
    const match = text.substring(idx, idx + query.length);
    const after = text.substring(idx + query.length);

    const span = document.createElement('span');
    span.innerHTML = escapeHtml(before) + '<mark>' + escapeHtml(match) + '</mark>' + escapeHtml(after);
    textNode.parentNode.replaceChild(span, textNode);
    return true;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function expandParents(el) {
    let parent = el.parentElement;
    while (parent) {
        if (parent.tagName === 'DETAILS') {
            parent.open = true;
        }
        parent = parent.parentElement;
    }
}

function applyFilters() {
    let matchCount = 0;
    let firstMatch = null;

    // First remove existing highlights
    removeHighlights();

    // Iterate over all searchable items
    const items = document.querySelectorAll('[data-searchable]');
    items.forEach(el => {
        const plat = el.dataset.platform || '';
        const cat = el.dataset.category || '';
        const text = el.dataset.text || '';
        let show = true;
        if (filterPlatform !== 'all' && plat !== filterPlatform) show = false;
        if (filterCategory !== 'all' && !el.classList.contains('element-item') && !el.classList.contains('dialog-item')) {
            if (cat !== filterCategory) show = false;
        }
        if (searchText) {
            const lowerText = text.toLowerCase();
            const lowerQuery = searchText.toLowerCase();
            if (!lowerText.includes(lowerQuery)) {
                show = false;
            }
        }

        el.classList.toggle('hidden', !show);

        if (show && searchText) {
            // Highlight matching text in child text nodes
            let highlighted = false;
            const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null, false);
            const textNodes = [];
            while (walker.nextNode()) {
                textNodes.push(walker.currentNode);
            }
            for (const node of textNodes) {
                if (highlightText(node, searchText)) {
                    highlighted = true;
                    break; // One highlight per element is enough
                }
            }
            if (highlighted) {
                el.classList.add('search-match');
                matchCount++;
                if (!firstMatch) firstMatch = el;
                expandParents(el);
            }
        }
    });

    // Update match count display
    const infoEl = document.getElementById('searchInfo');
    if (searchText) {
        infoEl.textContent = matchCount > 0 ? '找到 ' + matchCount + ' 个匹配' : '无匹配结果';
        infoEl.classList.remove('hidden');
    } else {
        infoEl.classList.add('hidden');
    }

    // Check if anything is visible
    const visibleItems = document.querySelectorAll('[data-searchable]:not(.hidden)');
    document.getElementById('noResults').classList.toggle('hidden', visibleItems.length > 0);

    // Auto-scroll to first match
    if (firstMatch) {
        firstMatch.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}

document.getElementById('search').addEventListener('input', e => {
    searchText = e.target.value.trim();
    applyFilters();
});
document.getElementById('platformFilter').addEventListener('change', e => {
    filterPlatform = e.target.value;
    applyFilters();
});
document.getElementById('categoryFilter').addEventListener('change', e => {
    filterCategory = e.target.value;
    applyFilters();
});
function expandAll() {
    document.querySelectorAll('details').forEach(d => d.open = true);
}
function collapseAll() {
    document.querySelectorAll('details').forEach(d => d.open = false);
}

// Initialize search on load
initSearch();
"""


class HTMLBuilder:
    """Build an interactive HTML report from ScanResult."""

    def __init__(self, result: ScanResult):
        self.result = result

    def build(self) -> str:
        """Generate the complete HTML string."""
        buf = StringIO()
        buf.write('<!DOCTYPE html>\n<html lang="zh-CN"><head><meta charset="utf-8">')
        buf.write('<meta name="viewport" content="width=device-width, initial-scale=1">')
        buf.write('<title>UI Scanner Report</title>')
        buf.write(f'<style>{CSS}</style></head><body>')

        self._build_header(buf)
        self._build_stats(buf)
        self._build_controls(buf)
        self._build_content(buf)

        buf.write('<div id="noResults" class="no-results hidden">没有找到匹配的结果</div>')
        buf.write('</div>')  # close .content

        # Embed data for JS filtering
        scan_data = json.dumps(self._build_filter_data(), ensure_ascii=False)
        buf.write(f'<script>const __SCAN_DATA__ = {scan_data};</script>')
        buf.write(f'<script>{JS}</script>')
        buf.write('</body></html>')
        return buf.getvalue()

    def _build_header(self, buf: StringIO):
        buf.write('<div class="header">')
        buf.write('<h1>UI Scanner Report</h1>')
        buf.write(f'<div class="meta">Generated {time.strftime("%Y-%m-%d %H:%M")} | ')
        buf.write(f'Scan time: {self.result.scan_time:.2f}s</div>')
        buf.write('</div>')

    def _build_stats(self, buf: StringIO):
        r = self.result
        android_el = sum(len(p.elements) for m in r.android_modules for p in m.pages)
        ios_el = sum(len(p.elements) for m in r.ios_modules for p in m.pages)
        harmony_el = sum(len(p.elements) for m in r.harmony_modules for p in m.pages)
        buf.write('<div class="stats">')
        self._stat_card(buf, r.total_pages, '页面总数')
        self._stat_card(buf, r.total_elements, 'UI 元素')
        self._stat_card(buf, r.total_dialogs, '弹框')
        self._stat_card(buf, len(r.android_modules), 'Android 模块')
        self._stat_card(buf, len(r.ios_modules), 'iOS 模块')
        self._stat_card(buf, len(r.harmony_modules), 'Harmony 模块')
        buf.write('</div>')

    def _stat_card(self, buf: StringIO, num: int, label: str):
        buf.write(f'<div class="stat-card"><div class="num">{num}</div><div class="label">{label}</div></div>')

    def _build_controls(self, buf: StringIO):
        buf.write('<div class="controls">')
        buf.write('<input type="text" id="search" placeholder="搜索元素名称、类型、ID、注释...">')
        buf.write('<span id="searchInfo" class="search-info hidden"></span>')
        buf.write('<select id="platformFilter">')
        buf.write('<option value="all">所有平台</option>')
        buf.write('<option value="Android">Android</option>')
        buf.write('<option value="iOS">iOS</option>')
        buf.write('<option value="Harmony">Harmony</option>')
        buf.write('</select>')
        buf.write('<select id="categoryFilter">')
        buf.write('<option value="all">所有分类</option>')
        for et in ElementType:
            buf.write(f'<option value="{et.value}">{et.value}</option>')
        buf.write('</select>')
        buf.write('<button class="btn" onclick="expandAll()">全部展开</button>')
        buf.write('<button class="btn" onclick="collapseAll()">全部收起</button>')
        buf.write('</div>')

    def _build_content(self, buf: StringIO):
        buf.write('<div class="content">')
        for platform in [Platform.ANDROID, Platform.IOS, Platform.HARMONY]:
            if platform == Platform.ANDROID:
                modules = self.result.android_modules
            elif platform == Platform.IOS:
                modules = self.result.ios_modules
            else:
                modules = self.result.harmony_modules

            if not modules:
                continue
            plat_label = platform.value
            icons = {Platform.ANDROID: '🤖', Platform.IOS: '🍎', Platform.HARMONY: '🔵'}
            icon = icons.get(platform, '📱')
            buf.write(f'<div class="platform-section" data-platform="{plat_label}">')
            buf.write(f'<div class="platform-header"><span class="platform-icon">{icon}</span>')
            buf.write(f'<h2>{plat_label} ({len(modules)} modules, ')
            total_el = sum(len(p.elements) for m in modules for p in m.pages)
            buf.write(f'{total_el} elements)</h2></div>')

            for module in modules:
                self._build_module(buf, module, plat_label)

            buf.write('</div>')
        buf.write('</div>')

    def _build_module(self, buf: StringIO, module: ModuleInfo, platform: str):
        buf.write(f'<details class="module-section" data-platform="{platform}" data-searchable data-text="{_esc_attr(module.name)}">')
        buf.write(f'<summary class="module-header">{_esc(module.name)} ')
        buf.write(f'({len(module.pages)} pages)</summary>')

        for page in module.pages:
            self._build_page(buf, page, platform)

        buf.write('</details>')

    def _build_page(self, buf: StringIO, page: Page, platform: str):
        badge_class = {
            'Activity': 'badge-activity',
            'Fragment': 'badge-fragment',
            'ViewController': 'badge-vc',
            'View': 'badge-view',
            'Page': 'badge-page',
            'Component': 'badge-component',
        }.get(page.page_type.value, 'badge-view')

        search_text = f'{page.name} {page.page_type.value}'
        if page.comment:
            search_text += f' {page.comment}'

        buf.write(f'<details class="page-section" data-platform="{platform}" ')
        buf.write(f'data-searchable data-text="{_esc_attr(search_text)}">')
        buf.write(f'<summary class="page-header">{_esc(page.name)} ')
        buf.write(f'<span class="page-type-badge {badge_class}">{page.page_type.value}</span>')
        buf.write(f' <small>({len(page.elements)} elements')
        if page.dialogs:
            buf.write(f', {len(page.dialogs)} dialogs')
        buf.write(')</small>')
        if page.comment:
            buf.write(f' <span class="element-comment">— {_esc(page.comment)}</span>')
        buf.write('</summary>')

        # Group elements by category
        categories = {}
        for elem in page.elements:
            categories.setdefault(elem.category, []).append(elem)

        for cat_type in [ElementType.CLICKABLE, ElementType.DISPLAY, ElementType.ANIMATION,
                         ElementType.INPUT, ElementType.CONTAINER]:
            elems = categories.get(cat_type, [])
            if not elems:
                continue
            cat_class = f'cat-{cat_type.name.lower()}'
            buf.write(f'<details class="category-section" data-platform="{platform}" ')
            buf.write(f'data-category="{cat_type.value}" data-searchable data-text="{_esc_attr(search_text)}">')
            buf.write(f'<summary class="category-header {cat_class}">')
            buf.write(f'{cat_type.value} ({len(elems)})</summary>')

            for elem in elems:
                self._build_element(buf, elem, platform)

            buf.write('</details>')

        # Dialogs
        if page.dialogs:
            dialog_text = ' '.join(d.name + d.scenario + (d.comment or '') for d in page.dialogs)
            buf.write(f'<details class="dialog-section" data-platform="{platform}" ')
            buf.write(f'data-searchable data-text="{_esc_attr(search_text + " dialog " + dialog_text)}">')
            buf.write(f'<summary class="category-header dialog-header">弹框 ({len(page.dialogs)})</summary>')
            for dialog in page.dialogs:
                self._build_dialog(buf, dialog, platform)
            buf.write('</details>')

        buf.write('</details>')

    def _build_element(self, buf: StringIO, elem: UIElement, platform: str = ''):
        # Build searchable text
        search_parts = [elem.name, elem.element_type]
        if elem.element_id:
            search_parts.append(elem.element_id)
        if elem.text_content:
            search_parts.append(elem.text_content)
        if elem.comment:
            search_parts.append(elem.comment)
        for v in elem.properties.values():
            search_parts.append(v)
        search_text = ' '.join(search_parts)

        buf.write(f'<div class="element-item" data-platform="{platform}" data-searchable ')
        buf.write(f'data-text="{_esc_attr(search_text)}">')
        buf.write(f'<span>{_esc(elem.name)}</span>')
        if elem.element_id:
            buf.write(f'<span class="element-id">#{_esc(elem.element_id)}</span>')
        buf.write(f'<span class="element-type">[{_esc(elem.element_type)}]</span>')
        if elem.properties:
            props_str = ' | '.join(f'{k}={v}' for k, v in list(elem.properties.items())[:3])
            buf.write(f'<span class="element-props">{_esc(props_str)}</span>')
        if elem.line_number:
            buf.write(f'<span class="element-line">L{elem.line_number}</span>')
        if elem.comment:
            buf.write(f'<span class="element-comment">— {_esc(elem.comment)}</span>')
        buf.write('</div>')

    def _build_dialog(self, buf: StringIO, dialog: DialogInfo, platform: str = ''):
        # Build searchable text
        search_parts = [dialog.name, dialog.dialog_type, dialog.scenario]
        if dialog.message_hint:
            search_parts.append(dialog.message_hint)
        if dialog.comment:
            search_parts.append(dialog.comment)
        search_text = ' '.join(search_parts)

        buf.write(f'<div class="dialog-item" data-platform="{platform}" data-searchable ')
        buf.write(f'data-text="{_esc_attr(search_text)}">')
        buf.write(f'<span>{_esc(dialog.name)}</span>')
        buf.write(f'<span class="dialog-type">[{_esc(dialog.dialog_type)}]</span>')
        buf.write(f'<span class="dialog-scenario">{_esc(dialog.scenario)}</span>')
        if dialog.message_hint:
            hint = dialog.message_hint[:80]
            buf.write(f'<span class="element-props">{_esc(hint)}</span>')
        if dialog.line_number:
            buf.write(f'<span class="element-line">L{dialog.line_number}</span>')
        if dialog.comment:
            buf.write(f'<span class="element-comment">— {_esc(dialog.comment)}</span>')
        buf.write('</div>')

    def _build_filter_data(self) -> dict:
        """Build lightweight data structure for JS filtering."""
        return {
            'totalPages': self.result.total_pages,
            'totalElements': self.result.total_elements,
            'totalDialogs': self.result.total_dialogs,
        }


def _esc(text: str) -> str:
    return html.escape(str(text), quote=False)


def _esc_attr(text: str) -> str:
    return html.escape(str(text), quote=True)
