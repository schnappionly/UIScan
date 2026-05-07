"""
公共工具函数模块
文件遍历、XML 解析、颜色输出等
"""

import os
import re
import glob
import xml.etree.ElementTree as ET
from typing import Generator


# ============================================================
# 颜色输出
# ============================================================

class Colors:
    RESET = "\033[0m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    BOLD = "\033[1m"


def cprint(text: str, color: str = Colors.RESET) -> None:
    print(f"{color}{text}{Colors.RESET}")


def print_success(text: str) -> None:
    cprint(f"  [OK] {text}", Colors.GREEN)


def print_error(text: str) -> None:
    cprint(f"  [ERROR] {text}", Colors.RED)


def print_warning(text: str) -> None:
    cprint(f"  [WARN] {text}", Colors.YELLOW)


def print_info(text: str) -> None:
    cprint(f"  [INFO] {text}", Colors.CYAN)


# ============================================================
# 文件遍历
# ============================================================

def find_files(
    root_dir: str,
    extensions: list[str] = None,
    patterns: list[str] = None,
) -> Generator[str, None, None]:
    """递归查找文件。支持按扩展名或 glob 模式过滤。"""
    if patterns:
        for pattern in patterns:
            full_pattern = os.path.join(root_dir, pattern)
            # 支持 ** glob
            matches = glob.glob(full_pattern, recursive=True)
            for match in matches:
                if os.path.isfile(match):
                    yield os.path.abspath(match)
    elif extensions:
        for dirpath, _, filenames in os.walk(root_dir):
            for filename in filenames:
                if any(filename.endswith(ext) for ext in extensions):
                    yield os.path.abspath(os.path.join(dirpath, filename))
    else:
        for dirpath, _, filenames in os.walk(root_dir):
            for filename in filenames:
                yield os.path.abspath(os.path.join(dirpath, filename))


def find_layout_files(project_dir: str, layout_patterns: list[str]) -> list[str]:
    """查找所有布局 XML 文件。"""
    files = []
    for f in find_files(project_dir, patterns=layout_patterns):
        files.append(f)
    return sorted(files)


def find_source_files(
    project_dir: str,
    source_dirs: list[str],
) -> dict[str, list[str]]:
    """按类型查找源文件。返回 {类型: [文件路径列表]}。"""
    result = {
        "kotlin": [],
        "java": [],
        "xml": [],
    }
    for src_dir in source_dirs:
        full_dir = os.path.join(project_dir, src_dir)
        if not os.path.exists(full_dir):
            continue
        for dirpath, _, filenames in os.walk(full_dir):
            for fn in filenames:
                fp = os.path.abspath(os.path.join(dirpath, fn))
                if fn.endswith((".kt", ".kts")):
                    result["kotlin"].append(fp)
                elif fn.endswith(".java"):
                    result["java"].append(fp)
                elif fn.endswith(".xml"):
                    result["xml"].append(fp)
    return result


# ============================================================
# XML 解析工具
# ============================================================

# Android XML namespace
ANDROID_NS = "http://schemas.android.com/apk/res/android"
TOOLS_NS = "http://schemas.android.com/tools"

# android:id 属性的各种形式
ID_DECLARE_PATTERN = re.compile(r'android:id\s*=\s*"@\+id/([^"]+)"')
ID_REF_PATTERN = re.compile(r'@id/([a-zA-Z0-9_]+)')
ID_DECLARE_CAPTURE = re.compile(r"@\\+id/([a-zA-Z0-9_]+)")


def parse_layout_xml(filepath: str) -> list[dict]:
    """解析布局 XML 文件，提取所有组件及其 ID 信息。
    返回 [{"tag": "...", "id": "...", "line": N, "has_id": bool}, ...]
    """
    elements = []
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
        _walk_xml_tree(root, elements)
    except ET.ParseError as e:
        print_warning(f"XML 解析错误 {filepath}: {e}")
        # 回退到正则方式提取
        elements = _parse_xml_by_regex(filepath)
    return elements


def _walk_xml_tree(element: ET.Element, result: list, depth: int = 0) -> None:
    """递归遍历 XML 树。"""
    tag = element.tag
    # 去掉 namespace
    if "}" in tag:
        tag = tag.split("}")[1]

    # 获取 android:id
    id_value = None
    has_id = False
    for attr_name, attr_value in element.attrib.items():
        clean_attr = attr_name
        if "}" in clean_attr:
            clean_attr = clean_attr.split("}")[1]
        if clean_attr == "id":
            has_id = True
            if attr_value.startswith("@+id/"):
                id_value = attr_value[5:]
            elif attr_value.startswith("@id/"):
                id_value = attr_value[4:]

    result.append({
        "tag": tag,
        "id": id_value,
        "has_id": has_id,
        "depth": depth,
    })

    for child in element:
        _walk_xml_tree(child, result, depth + 1)


def _parse_xml_by_regex(filepath: str) -> list[dict]:
    """正则回退方式提取 ID。"""
    elements = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # 提取所有标签及其 android:id
        tag_pattern = re.compile(r"<([a-zA-Z0-9_.]+)[^>]*?android:id\s*=\s*\"@\+id/([^\"]+)\"[^>]*>", re.DOTALL)
        for match in tag_pattern.finditer(content):
            elements.append({
                "tag": match.group(1).split(".")[-1],
                "id": match.group(2),
                "has_id": True,
                "depth": 0,
            })
    except Exception as e:
        print_warning(f"正则解析也失败 {filepath}: {e}")

    return elements


# ============================================================
# 文件读写工具
# ============================================================

def read_file(filepath: str) -> str:
    """读取文件内容。"""
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def write_file(filepath: str, content: str) -> None:
    """写入文件内容。"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)


def backup_file(filepath: str) -> str:
    """创建文件备份，返回备份路径。"""
    backup_path = filepath + ".bak"
    import shutil
    shutil.copy2(filepath, backup_path)
    return backup_path
