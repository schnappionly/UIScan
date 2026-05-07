#!/usr/bin/env python3
"""
Android 组件 ID 规范化扫描工具

扫描 Android 项目中所有布局 XML 文件，
检查组件 ID 是否符合命名规范，生成 CSV 报告。

用法：
  python scanner.py <项目路径> [选项]

示例：
  python scanner.py /path/to/android/project
  python scanner.py /path/to/android/project --config config.yaml
  python scanner.py /path/to/android/project --output report.csv
  python scanner.py /path/to/android/project --whitelist "content,nav_host"
"""

import argparse
import csv
import os
import sys
from datetime import datetime

# 添加当前目录到 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from id_rules import (
    COMPONENT_ABBR,
    extract_page_name,
    get_component_abbr,
    is_id_compliant,
    generate_suggested_id,
    snake_to_camel,
)
from utils import (
    Colors,
    cprint,
    print_success,
    print_error,
    print_warning,
    print_info,
    find_layout_files,
    parse_layout_xml,
)


def load_config(config_path: str) -> dict:
    """加载配置文件（简单 YAML 解析，不依赖第三方库）。"""
    config = {
        "layout_patterns": ["**/src/main/res/layout*/*.xml"],
        "source_dirs": [
            "app/src/main/java",
            "app/src/main/kotlin",
            "app/src/main/res/navigation",
            "app/src/main/res/menu",
            "app/src/main/res/values",
        ],
        "whitelist_ids": [],
        "whitelist_files": [],
        "output_dir": ".",
        "report_filename": "id_report.csv",
    }

    if not config_path or not os.path.exists(config_path):
        return config

    try:
        import yaml
        with open(config_path, "r", encoding="utf-8") as f:
            user_config = yaml.safe_load(f)
        if user_config:
            # 映射配置键
            if "layout_paths" in user_config:
                config["layout_patterns"] = user_config["layout_paths"]
            if "source_paths" in user_config:
                config["source_dirs"] = user_config["source_paths"]
            if "whitelist_ids" in user_config:
                config["whitelist_ids"] = user_config["whitelist_ids"]
            if "whitelist_files" in user_config:
                config["whitelist_files"] = user_config["whitelist_files"]
            if "output" in user_config:
                out = user_config["output"]
                if isinstance(out, dict):
                    config["output_dir"] = out.get("report_dir", ".")
                    config["report_filename"] = out.get("report_filename", "id_report.csv")
    except ImportError:
        # 没有 yaml 模块时用简单解析
        print_warning("未安装 PyYAML，使用默认配置")
    except Exception as e:
        print_warning(f"配置文件加载失败: {e}，使用默认配置")

    return config


def is_whitelisted_file(filename: str, patterns: list[str]) -> bool:
    """检查文件是否在白名单中。"""
    import fnmatch
    for pattern in patterns:
        if fnmatch.fnmatch(filename, pattern):
            return True
    return False


def scan_project(
    project_dir: str,
    config: dict,
) -> list[dict]:
    """扫描项目，返回所有 ID 检查结果。"""
    results = []
    layout_patterns = config.get("layout_patterns", [])
    whitelist_ids = config.get("whitelist_ids", [])
    whitelist_files = config.get("whitelist_files", [])

    # 查找布局文件
    layout_files = find_layout_files(project_dir, layout_patterns)

    if not layout_files:
        print_warning(f"未找到布局文件，请检查路径和模式：{layout_patterns}")
        return results

    cprint(f"\n{'='*70}", Colors.BLUE)
    cprint(f"  扫描项目: {os.path.abspath(project_dir)}", Colors.BOLD)
    cprint(f"  布局文件数: {len(layout_files)}", Colors.BOLD)
    cprint(f"{'='*70}\n", Colors.BLUE)

    total_ids = 0
    compliant_count = 0
    non_compliant_count = 0
    whitelisted_count = 0

    for layout_file in layout_files:
        filename = os.path.basename(layout_file)

        # 白名单文件跳过
        if is_whitelisted_file(filename, whitelist_files):
            print_info(f"跳过白名单文件: {filename}")
            continue

        # 提取页面名
        page_name = extract_page_name(filename)

        # 解析 XML
        elements = parse_layout_xml(layout_file)
        if not elements:
            continue

        file_has_issues = False
        file_ids = []

        for elem in elements:
            if not elem.get("has_id") or not elem.get("id"):
                continue

            id_name = elem["id"]
            tag = elem["tag"]

            # 白名单 ID 跳过
            if id_name in whitelist_ids:
                whitelisted_count += 1
                continue

            total_ids += 1

            # 合规检查
            is_ok, reasons = is_id_compliant(id_name, page_name, tag)

            if is_ok:
                compliant_count += 1
                result = {
                    "file_path": os.path.relpath(layout_file, project_dir),
                    "file_name": filename,
                    "page_name": page_name,
                    "component_tag": tag,
                    "component_abbr": get_component_abbr(tag) or "unknown",
                    "original_id": id_name,
                    "is_compliant": True,
                    "reasons": "",
                    "suggested_id": id_name,
                    "suggested_camel": snake_to_camel(id_name),
                }
            else:
                non_compliant_count += 1
                suggested = generate_suggested_id(id_name, page_name, tag)
                reason_str = "; ".join(reasons)
                file_has_issues = True

                result = {
                    "file_path": os.path.relpath(layout_file, project_dir),
                    "file_name": filename,
                    "page_name": page_name,
                    "component_tag": tag,
                    "component_abbr": get_component_abbr(tag) or "unknown",
                    "original_id": id_name,
                    "is_compliant": False,
                    "reasons": reason_str,
                    "suggested_id": suggested,
                    "suggested_camel": snake_to_camel(suggested),
                }

                cprint(
                    f"    {Colors.RED}✗{Colors.RESET} {id_name} "
                    f"→ {Colors.GREEN}{suggested}{Colors.RESET}  ({reason_str})",
                    Colors.RESET,
                )

            file_ids.append(result)

        if file_ids:
            status = f"{Colors.RED}有 {sum(1 for r in file_ids if not r['is_compliant'])} 个问题{Colors.RESET}" if file_has_issues else f"{Colors.GREEN}全部合规{Colors.RESET}"
            cprint(f"  [{filename}] 页面: {page_name} | {len(file_ids)} 个 ID | {status}", Colors.BOLD)

        results.extend(file_ids)

    # 打印统计摘要
    cprint(f"\n{'='*70}", Colors.BLUE)
    cprint("  扫描结果摘要", Colors.BOLD)
    cprint(f"{'='*70}", Colors.BLUE)
    cprint(f"  布局文件数:   {len(layout_files)}", Colors.CYAN)
    cprint(f"  ID 总数:      {total_ids + whitelisted_count}", Colors.CYAN)
    cprint(f"  合规 ID:      {compliant_count}", Colors.GREEN)
    cprint(f"  不合规 ID:    {non_compliant_count}", Colors.RED)
    cprint(f"  白名单跳过:   {whitelisted_count}", Colors.YELLOW)
    if total_ids > 0:
        rate = compliant_count / total_ids * 100
        color = Colors.GREEN if rate >= 80 else Colors.YELLOW if rate >= 50 else Colors.RED
        cprint(f"  合规率:       {rate:.1f}%", color)
    cprint(f"{'='*70}\n", Colors.BLUE)

    return results


def save_report(results: list[dict], output_path: str) -> None:
    """保存 CSV 报告。"""
    if not results:
        print_warning("没有扫描结果，不生成报告")
        return

    fieldnames = [
        "file_path",
        "file_name",
        "page_name",
        "component_tag",
        "component_abbr",
        "original_id",
        "is_compliant",
        "reasons",
        "suggested_id",
        "suggested_camel",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    # 只统计不合规数量
    non_compliant = sum(1 for r in results if not r["is_compliant"])
    cprint(f"  报告已保存: {output_path}", Colors.GREEN)
    cprint(f"  不合规 ID 数: {non_compliant}", Colors.RED if non_compliant > 0 else Colors.GREEN)


def main():
    parser = argparse.ArgumentParser(
        description="Android 组件 ID 规范化扫描工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "project_dir",
        help="Android 项目根目录路径",
    )
    parser.add_argument(
        "--config", "-c",
        help="配置文件路径 (YAML)",
        default=None,
    )
    parser.add_argument(
        "--output", "-o",
        help="报告输出文件路径 (CSV)",
        default=None,
    )
    parser.add_argument(
        "--whitelist",
        help="白名单 ID，逗号分隔",
        default=None,
    )

    args = parser.parse_args()

    # 验证项目路径
    if not os.path.isdir(args.project_dir):
        print_error(f"项目目录不存在: {args.project_dir}")
        sys.exit(1)

    # 加载配置
    config = load_config(args.config)

    # 命令行白名单覆盖
    if args.whitelist:
        config["whitelist_ids"].extend(args.whitelist.split(","))

    # 扫描
    results = scan_project(args.project_dir, config)

    # 保存报告
    output_path = args.output
    if not output_path:
        output_dir = config.get("output_dir", ".")
        report_name = config.get("report_filename", "id_report.csv")
        output_path = os.path.join(output_dir, report_name)

    save_report(results, output_path)

    # 返回退出码：有不合规 ID 时返回 1
    has_non_compliant = any(not r["is_compliant"] for r in results)
    sys.exit(1 if has_non_compliant else 0)


if __name__ == "__main__":
    main()
