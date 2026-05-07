"""
Android 组件 ID 命名规则定义模块
定义组件缩写映射、页面名提取、合规判断、建议 ID 生成
"""

import re
from typing import Optional

# Android 组件 → 缩写映射（按标签名匹配）
COMPONENT_ABBR = {
    # 基础组件
    "TextView": "tv",
    "EditText": "et",
    "AutoCompleteTextView": "actv",
    "MultiAutoCompleteTextView": "mactv",
    "Button": "btn",
    "ImageButton": "ib",
    "ImageView": "iv",
    "ProgressBar": "pb",
    "SeekBar": "sb",
    "RatingBar": "rb",
    "CheckBox": "cb",
    "RadioButton": "rb",
    "RadioGroup": "rg",
    "Switch": "sw",
    "SwitchCompat": "sw",
    "ToggleButton": "tb",
    "Spinner": "sp",
    "VideoView": "vv",
    "SurfaceView": "surface",
    "CalendarView": "cal",
    "DatePicker": "dp",
    "TimePicker": "tp",
    "SearchView": "search",
    "Chronometer": "chrono",
    "TextureView": "texture",
    # 容器组件
    "ScrollView": "sv",
    "HorizontalScrollView": "hsv",
    "NestedScrollView": "nsv",
    "RecyclerView": "rv",
    "ListView": "lv",
    "GridView": "gv",
    "ViewPager": "vp",
    "ViewPager2": "vp",
    "WebView": "wv",
    "FrameLayout": "fl",
    "LinearLayout": "ll",
    "RelativeLayout": "rl",
    "ConstraintLayout": "cl",
    "TableLayout": "tl",
    "TableRow": "tr",
    "GridLayout": "gl",
    # Material / AndroidX 组件
    "CardView": "cv",
    "MaterialCardView": "cv",
    "FloatingActionButton": "fab",
    "ExtendedFloatingActionButton": "efab",
    "BottomNavigationView": "bnv",
    "NavigationRailView": "nrv",
    "TabLayout": "tl",
    "TabItem": "ti",
    "Toolbar": "tb",
    "MaterialToolbar": "tb",
    "TextInputLayout": "til",
    "TextInputEditText": "tiet",
    "Chip": "chip",
    "ChipGroup": "cg",
    "Slider": "slider",
    "Snackbar": "snackbar",
    "AppBarLayout": "abl",
    "CollapsingToolbarLayout": "ctl",
    "CoordinatorLayout": "col",
    "DrawerLayout": "dl",
    "SwipeRefreshLayout": "srl",
    "RefreshLayout": "srl",
    "RefreshLayout": "srl",
    "BottomSheetBehavior": "bsb",
    "BottomSheetDialog": "bsd",
    "NavigationView": "nv",
    "RefreshLayout": "srl",
    "FlowLayout": "fl",
    "FlexboxLayout": "fbl",
    "MotionLayout": "ml",
    # 常见自定义 View 标记（include 标签）
    "include": "include",
    "View": "view",
    "ViewStub": "vs",
    "Space": "space",
    "merge": "merge",
}

# 反向映射：缩写 → 组件类型列表
ABBR_TO_COMPONENTS = {}
for comp, abbr in COMPONENT_ABBR.items():
    ABBR_TO_COMPONENTS.setdefault(abbr, []).append(comp)

# 所有已知缩写集合
KNOWN_ABBRS = set(COMPONENT_ABBR.values())

# 布局文件名前缀（提取页面名时去掉）
LAYOUT_PREFIXES = [
    "activity_",
    "fragment_",
    "dialog_",
    "layout_",
    "view_",
]

# 合规 ID 正则：至少3段，全小写字母数字+下划线
COMPLIANT_PATTERN = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+){2,}$")

# ID 提取正则
ID_PATTERN = re.compile(r"@\\+?id/(.+?)(?:\"|\'|\s|<)")


def extract_page_name(layout_filename: str) -> str:
    """从布局文件名提取页面名。
    activity_login.xml -> login
    fragment_home.xml -> home
    dialog_confirm.xml -> confirm
    item_product.xml -> item_product  (item 布局保留 item_ 前缀)
    """
    name = layout_filename
    if name.endswith(".xml"):
        name = name[:-4]

    # item 布局保留 item_ 前缀
    if name.startswith("item_"):
        return name

    # 去掉已知前缀
    for prefix in LAYOUT_PREFIXES:
        if name.startswith(prefix):
            name = name[len(prefix):]
            break

    return name


def get_component_abbr(tag_name: str) -> Optional[str]:
    """获取 XML 标签对应的组件缩写。处理带包名的情况。"""
    # 去掉包名前缀，如 android.widget.TextView -> TextView
    simple_name = tag_name.split(".")[-1]
    return COMPONENT_ABBR.get(simple_name)


def _split_id_parts(id_name: str, page_name: str) -> tuple[str, Optional[str], str]:
    """智能拆分 ID 为 (页面名部分, 组件缩写, 功能描述)。

    处理页面名本身包含下划线的情况（如 item_product）。
    """
    parts = id_name.split("_")

    # 尝试匹配页面名前缀（page_name 可能包含下划线）
    page_parts = page_name.split("_") if page_name else []

    # 尝试从 ID 开头匹配页面名
    matched_page_len = 0
    if page_parts and len(parts) >= len(page_parts):
        # 完全匹配
        if parts[:len(page_parts)] == page_parts:
            matched_page_len = len(page_parts)

    if matched_page_len == 0 and page_name and parts and parts[0] == page_name:
        matched_page_len = 1

    # 剩余部分：缩写 + 描述
    remaining = parts[matched_page_len:] if matched_page_len > 0 else parts

    abbr = None
    desc_parts = []

    if remaining:
        # 第一段是否是已知缩写
        if remaining[0] in KNOWN_ABBRS:
            abbr = remaining[0]
            desc_parts = remaining[1:]
        else:
            desc_parts = remaining
    else:
        desc_parts = []

    description = "_".join(desc_parts) if desc_parts else ""
    matched_page = "_".join(parts[:matched_page_len]) if matched_page_len > 0 else ""

    return matched_page, abbr, description


def is_id_compliant(
    id_name: str,
    page_name: str,
    component_tag: Optional[str] = None,
) -> tuple[bool, list[str]]:
    """检查 ID 是否合规。返回 (是否合规, 原因列表)。"""
    reasons = []

    if not id_name:
        reasons.append("ID 为空")
        return False, reasons

    # 检查是否全小写
    if id_name != id_name.lower():
        reasons.append("包含大写字母，应全部小写")

    # 智能拆分
    matched_page, abbr, description = _split_id_parts(id_name, page_name)

    parts = id_name.split("_")

    # 检查页面名前缀
    if not matched_page:
        reasons.append(f"页面名不匹配：期望以 '{page_name}' 开头")

    # 检查组件缩写
    if not abbr:
        reasons.append("缺少组件缩写段")
    else:
        # 验证缩写是否与实际组件匹配
        if component_tag:
            expected_abbr = get_component_abbr(component_tag)
            if expected_abbr and abbr != expected_abbr:
                reasons.append(
                    f"组件缩写不匹配：标签 '{component_tag}' 期望缩写 '{expected_abbr}'，实际为 '{abbr}'"
                )

    # 检查功能描述
    if not description:
        reasons.append("缺少功能描述段")

    is_ok = len(reasons) == 0
    return is_ok, reasons


def generate_suggested_id(
    id_name: str,
    page_name: str,
    component_tag: Optional[str] = None,
) -> str:
    """为不合规的 ID 生成建议的新 ID。

    核心逻辑：从原 ID 中提取功能语义，组装为 {page}_{abbr}_{desc}。
    """
    # 处理驼峰：loginBtn -> login_btn, textView1 -> text_view1
    id_snake = camel_to_snake(id_name).lower()
    # 去掉数字后缀（自动生成的 textView1 等）
    id_clean = re.sub(r"\d+$", "", id_snake).rstrip("_")

    parts = id_clean.split("_") if id_clean else []
    expected_abbr = get_component_abbr(component_tag) if component_tag else None

    # 去掉页面名各段、去掉所有已知缩写、去掉纯数字，收集剩余有意义的词
    page_part_set = set(page_name.split("_")) if page_name else set()
    meaningful = [p for p in parts if p and p not in page_part_set and p not in KNOWN_ABBRS and not p.isdigit()]

    # 如果没提取到有意义的词，尝试从驼峰拆分的各段中宽松匹配：
    # 只去掉已知缩写，不去掉页面名（此时页面名本身就是功能描述）
    if not meaningful:
        meaningful = [p for p in parts if p and p not in KNOWN_ABBRS and not p.isdigit() and len(p) > 1]

    # 如果还没有，尝试从原始 ID 全词中再提取
    if not meaningful:
        raw_parts = id_name.lower().split("_")
        meaningful = [p for p in raw_parts if p and p not in KNOWN_ABBRS and not p.isdigit() and len(p) > 1]

    if meaningful:
        description = "_".join(meaningful)
    else:
        # 最终兜底：基于组件标签推一个通用描述
        if expected_abbr == "btn":
            description = "submit"
        elif expected_abbr == "tv":
            description = "text"
        elif expected_abbr == "et":
            description = "input"
        elif expected_abbr == "iv":
            description = "image"
        elif expected_abbr == "rv":
            description = "list"
        elif expected_abbr == "fab":
            description = "add"
        else:
            description = "view"

    # 去掉非法字符
    description = re.sub(r"[^a-z0-9_]", "", description)
    if not description:
        description = "view"

    abbr = expected_abbr or "view"
    return f"{page_name}_{abbr}_{description}"


def snake_to_camel(snake_str: str) -> str:
    """下划线转小驼峰（用于 ViewBinding 字段名转换）。
    login_tv_title -> loginTvTitle
    """
    components = snake_str.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


def camel_to_snake(camel_str: str) -> str:
    """小驼峰转下划线。
    loginTvTitle -> login_tv_title
    """
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", camel_str)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
