# UIScan - 移动应用 UI 元素静态扫描工具

UIScan 是一个面向 Android 和 iOS 移动应用（harmony待补充）的 **静态代码分析工具**，能够自动扫描源码和布局文件，发现、分类并报告所有 UI 元素，最终生成一份可交互的 HTML 扫描报告。

## 功能特性

### Android 扫描

- **页面发现**：自动识别 `Activity` 和 `Fragment` 类
- **布局解析**：解析 XML 布局文件（`layout/*.xml`），提取所有 UI 控件
- **代码分析**：扫描 Java/Kotlin 源码，检测动画（ObjectAnimator、Lottie 等）、点击监听器、编程式创建的视图
- **弹窗检测**：识别 AlertDialog、Toast、Snackbar、BottomSheetDialog 等，并智能推断弹窗场景（删除确认、网络错误、权限请求、登录提示、加载中等）
- **多模块支持**：按 Gradle 模块（`build.gradle` / `build.gradle.kts`）自动分组
- **字符串资源解析**：读取 `strings.xml`，解析弹窗标题/消息中的字符串引用，提升场景推断准确度

### iOS 扫描

- **页面发现**：自动识别 `ViewController` 类（Swift / Objective-C）
- **布局解析**：解析 `.storyboard` 和 `.xib` 文件中的 UI 元素
- **代码分析**：扫描源码，检测编程式 UI、手势识别器（Tap、Pinch、Swipe 等）、动画
- **弹窗检测**：识别 UIAlertController、UIAlertView、Action Sheet、Popover
- **智能合并**：自动合并代码文件与 Storyboard 中的 ViewController 数据

### UI 元素分类

所有发现的元素会被自动归类为以下五大类别：

| 类别 | 说明 | 典型元素 |
|------|------|----------|
| 可点击 | 可交互的控件 | Button、Switch、OnClickListener、手势识别 |
| 展示数据 | 展示信息的控件 | TextView、ImageView、RecyclerView、ProgressBar |
| 动画 | 动画相关元素 | ObjectAnimator、Lottie、UIView.animate |
| 容器布局 | 布局容器 | ConstraintLayout、LinearLayout、StackView |
| 输入 | 用户输入控件 | EditText、UITextField、SearchView |

### HTML 报告

生成一份自包含的交互式 HTML 报告，支持：

- 树形结构展示：平台 → 模块 → 页面 → 元素类别 → 具体元素
- 关键词搜索过滤
- 平台筛选（Android / iOS）
- 类别筛选
- 一键展开 / 折叠所有节点
- 页面类型标签（Activity / Fragment / ViewController / View）
- 扫描统计信息（页面数、元素数、弹窗数、扫描耗时）

## 项目结构

```
UIScan/
├── ui_scanner/
│   ├── __init__.py                      # 包初始化，版本号
│   ├── scanner.py                       # ScanRunner 扫描编排器
│   ├── models.py                        # 数据模型定义
│   ├── cli.py                           # 命令行参数解析
│   ├── utils/
│   │   └── file_utils.py               # 文件遍历、并行处理工具
│   ├── android/
│   │   ├── android_scanner.py           # Android 扫描协调器
│   │   ├── page_finder.py               # Activity/Fragment 发现
│   │   ├── layout_parser.py             # Android XML 布局解析
│   │   ├── code_analyzer.py             # Java/Kotlin 代码分析
│   │   └── dialog_scanner.py            # 弹窗检测与场景推断
│   ├── ios/
│   │   ├── ios_scanner.py               # iOS 扫描协调器
│   │   ├── vc_finder.py                 # ViewController 发现
│   │   ├── storyboard_parser.py         # Storyboard/XIB 解析
│   │   ├── code_analyzer.py             # Swift/ObjC 代码分析
│   │   └── dialog_scanner.py            # 弹窗检测
│   └── report/
│       └── html_builder.py              # HTML 报告生成器
```

## 环境要求

- **Python 3.10+**（使用了 `match` 语法、`dataclass`、类型注解等特性）
- **无第三方依赖** — 仅使用 Python 标准库

## 快速开始

### 安装

```bash
git clone <repo-url>
cd UIScan/UIScan
```

无需安装任何依赖，直接运行即可。

### 使用方法

```bash
# 扫描 Android 项目
python3 -m ui_scanner.cli --android /path/to/android-project -o report.html

# 扫描 iOS 项目
python3 -m ui_scanner.cli --ios /path/to/ios-project -o report.html

# 同时扫描 Android 和 iOS 项目
python3 -m ui_scanner.cli --android /path/to/android --ios /path/to/ios -o report.html

# 开启详细日志输出
python3 -m ui_scanner.cli --android /path/to/android-project -v
```

### 命令行参数

| 参数 | 缩写 | 说明 | 默认值 |
|------|------|------|--------|
| `--android PATH` | — | Android 项目根目录路径 | — |
| `--ios PATH` | — | iOS 项目根目录路径 | — |
| `--output FILE` | `-o` | 输出 HTML 报告文件路径 | `ui_report.html` |
| `--verbose` | `-v` | 打印详细扫描进度 | `false` |

> 至少需要指定 `--android` 或 `--ios` 中的一个参数。

## 工作原理

### 整体流程

```
命令行参数解析 (cli.py, 运行方式: python3 -m ui_scanner.cli)
  └─→ ScanRunner (scanner.py)
        ├─→ Android 扫描 (android/android_scanner.py)
        │     ├─ 定位 Gradle 模块目录
        │     ├─ PageFinder: 正则匹配 Activity/Fragment 类
        │     ├─ LayoutParser: 解析 XML 布局文件
        │     ├─ CodeAnalyzer: 正则匹配动画、监听器、编程式视图
        │     └─ DialogScanner: 正则匹配弹窗 + 关键词场景推断
        ├─→ iOS 扫描 (ios/ios_scanner.py)
        │     ├─ VCFinder: 正则匹配 ViewController 类
        │     ├─ StoryboardParser: 解析 Storyboard/XIB XML
        │     ├─ CodeAnalyzer: 正则匹配编程式 UI、手势、动画
        │     └─ DialogScanner: 正则匹配弹窗类型
        └─→ HTMLBuilder (report/html_builder.py)
              └─ 生成自包含交互式 HTML 报告
```

### 弹窗场景推断

工具通过中英文关键词匹配，将检测到的弹窗自动归类到以下场景：

- 删除确认 / 删除警告
- 网络错误 / 错误提示
- 登录提示
- 权限请求
- 加载中
- 输入 / 表单
- 确认操作
- 退出确认
- 其他

### 并行处理

文件扫描阶段使用 `ProcessPoolExecutor` 进行并行处理，充分利用多核 CPU 加速大型项目扫描。

## 数据模型

核心数据结构定义在 `models.py` 中：

```
ScanResult                     # 完整扫描结果
 └─ ModuleInfo[]               # 模块/包分组
     └─ Page[]                 # 页面 (Activity/Fragment/ViewController)
         ├─ UIElement[]        # UI 元素
         │    ├─ name          # 元素名称
         │    ├─ element_type  # 元素类型
         │    ├─ category      # 分类 (可点击/展示数据/动画/容器布局/输入)
         │    ├─ element_id    # 资源 ID
         │    └─ properties    # 附加属性
         └─ DialogInfo[]       # 弹窗信息
              ├─ name          # 弹窗名称
              ├─ dialog_type   # 弹窗类型
              ├─ scenario      # 推断的场景
              └─ message_hint  # 消息提示内容
```

## 示例输出

扫描完成后，终端输出：

```
Report saved to: report.html
  Pages: 45 | Elements: 312 | Dialogs: 28
  Scan time: 2.35s
```

打开生成的 HTML 报告即可查看交互式扫描结果。

## 技术实现说明

- **静态分析**：不依赖编译或运行时，直接扫描源码文件和 XML 资源文件
- **正则匹配**：使用正则表达式识别类定义、UI 控件、API 调用等
- **XML 解析**：使用标准库 `xml.etree.ElementTree` 解析 Android 布局文件和 iOS Storyboard/XIB 文件
- **零依赖设计**：整个工具仅使用 Python 标准库，无需安装任何第三方包
- **自包含报告**：HTML 报告将 CSS、JS 和数据全部内联到单个文件中，可直接在浏览器中打开

## License

MIT
