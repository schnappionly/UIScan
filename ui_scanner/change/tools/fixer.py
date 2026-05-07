#!/usr/bin/env python3
"""
Android 组件 ID 规范化自动修复工具

根据扫描报告（CSV），自动将不合规 ID 替换为规范 ID，
全项目同步修改：XML 布局、Kotlin/Java 代码、Navigation、Menu、DataBinding 等。

用法：
  python fixer.py <项目路径> --report id_report.csv [选项]

示例：
  # 预览模式（不实际修改）
  python fixer.py /path/to/project --report id_report.csv --dry-run

  # 执行修复
  python fixer.py /path/to/project --report id_report.csv

  # 只修改特定文件
  python fixer.py /path/to/project --report id_report.csv --only-xml
"""

import argparse
import csv
import os
import re
import sys
import shutil
from datetime import datetime
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from id_rules import snake_to_camel, camel_to_snake
from utils import (
    Colors,
    cprint,
    print_success,
    print_error,
    print_warning,
    print_info,
    read_file,
    write_file,
    backup_file,
    find_files,
)


class IDFixer:
    """ID 自动修复器。"""

    def __init__(
        self,
        project_dir: str,
        id_mappings: dict[str, str],
        dry_run: bool = True,
        backup: bool = True,
        only_xml: bool = False,
    ):
        self.project_dir = os.path.abspath(project_dir)
        self.id_mappings = id_mappings  # {old_id: new_id}
        self.dry_run = dry_run
        self.backup = backup
        self.only_xml = only_xml

        # 自动发现所有模块的 src/main 目录
        self._source_roots = self._discover_source_roots()

        # 同时维护驼峰形式的映射（用于 ViewBinding）
        self.camel_mappings = {}
        for old_id, new_id in id_mappings.items():
            old_camel = snake_to_camel(old_id)
            new_camel = snake_to_camel(new_id)
            if old_camel != new_camel:
                self.camel_mappings[old_camel] = new_camel

        # 统计
        self.stats = {
            "files_scanned": 0,
            "files_modified": 0,
            "replacements": 0,
            "backups_created": 0,
            "errors": 0,
        }

        # 修改日志
        self.changes = []

    def log_change(self, filepath: str, old: str, new: str, context: str = ""):
        self.changes.append({
            "file": os.path.relpath(filepath, self.project_dir),
            "old": old,
            "new": new,
            "context": context,
        })

    def load_report(self, report_path: str) -> dict[str, str]:
        """从 CSV 报告加载 ID 映射（只取不合规的）。"""
        mappings = {}
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("is_compliant") == "False":
                        old_id = row["original_id"]
                        new_id = row["suggested_id"]
                        if old_id != new_id:
                            mappings[old_id] = new_id
        except Exception as e:
            print_error(f"报告加载失败: {e}")
        return mappings

    # ================================================================
    # XML 文件替换
    # ================================================================

    def fix_xml_file(self, filepath: str) -> int:
        """修复 XML 文件中的 ID 引用。返回替换次数。"""
        try:
            content = read_file(filepath)
        except Exception as e:
            print_error(f"读取文件失败 {filepath}: {e}")
            self.stats["errors"] += 1
            return 0

        original = content
        count = 0

        # 1. 替换 android:id="@+id/xxx" 声明
        for old_id, new_id in self.id_mappings.items():
            # @+id/old -> @+id/new
            pattern = r'@\+id/' + re.escape(old_id) + r'(?![a-zA-Z0-9_])'
            replacement = f'@+id/{new_id}'
            new_content = re.sub(pattern, replacement, content)
            if new_content != content:
                matches = len(re.findall(pattern, content))
                count += matches
                self.log_change(filepath, f"@+id/{old_id}", f"@+id/{new_id}", "XML id 声明")
                content = new_content

            # 2. 替换 @id/xxx 引用（约束布局等）
            pattern = f'@id/{re.escape(old_id)}(?![a-zA-Z0-9_])'
            replacement = f'@id/{new_id}'
            new_content = re.sub(pattern, replacement, content)
            if new_content != content:
                matches = len(re.findall(pattern, content))
                count += matches
                self.log_change(filepath, f"@id/{old_id}", f"@id/{new_id}", "XML id 引用")
                content = new_content

        if content != original:
            if not self.dry_run:
                if self.backup:
                    backup_file(filepath)
                    self.stats["backups_created"] += 1
                write_file(filepath, content)
            self.stats["files_modified"] += 1
            self.stats["replacements"] += count

        return count

    # ================================================================
    # Kotlin / Java 文件替换
    # ================================================================

    def fix_kotlin_java_file(self, filepath: str) -> int:
        """修复 Kotlin/Java 文件中的 ID 引用。返回替换次数。"""
        try:
            content = read_file(filepath)
        except Exception as e:
            print_error(f"读取文件失败 {filepath}: {e}")
            self.stats["errors"] += 1
            return 0

        original = content
        count = 0

        for old_id, new_id in self.id_mappings.items():
            old_camel = snake_to_camel(old_id)
            new_camel = snake_to_camel(new_id)

            # 1. R.id.xxx 引用（最常见）
            pattern = rf'R\.id\.{re.escape(old_id)}\b'
            replacement = f'R.id.{new_id}'
            new_content = re.sub(pattern, replacement, content)
            if new_content != content:
                matches = len(re.findall(pattern, content))
                count += matches
                self.log_change(filepath, f"R.id.{old_id}", f"R.id.{new_id}", "R.id 引用")
                content = new_content

            # 2. findViewById<R.type.old> 或 findViewById(R.id.old)
            pattern = rf'findViewById[<(]\s*R\.id\.{re.escape(old_id)}\s*[>)]'
            replacement = f'findViewById(R.id.{new_id})'
            new_content = re.sub(pattern, replacement, content)
            if new_content != content:
                matches = len(re.findall(pattern, content))
                count += matches
                self.log_change(filepath, "findViewById", f"findViewById(R.id.{new_id})", "findViewById")
                content = new_content

            # 3. ViewBinding 引用: binding.oldCamel -> binding.newCamel
            if old_camel != new_camel:
                pattern = rf'\b{re.escape(old_camel)}\b'
                # 只在看起来像 binding.field 的上下文中替换
                new_content = re.sub(
                    rf'(\bbinding\.\s*){re.escape(old_camel)}\b',
                    rf'\1{new_camel}',
                    content,
                )
                if new_content != content:
                    matches = len(re.findall(rf'(\bbinding\.\s*){re.escape(old_camel)}\b', content))
                    count += matches
                    self.log_change(filepath, f"binding.{old_camel}", f"binding.{new_camel}", "ViewBinding")
                    content = new_content

                # 4. synthetic imports: import kotlinx.android.synthetic.main.xxx.old
                pattern = rf'import\s+kotlinx\.android\.synthetic\.main\.[\w.]+\.{re.escape(old_id)}\b'
                replacement_content = content  # 需要整行替换
                lines = content.split("\n")
                new_lines = []
                for line in lines:
                    if re.search(pattern, line):
                        new_line = line.replace(old_id, new_id)
                        if new_line != line:
                            count += 1
                            self.log_change(filepath, line.strip(), new_line.strip(), "synthetic import")
                        new_lines.append(new_line)
                    else:
                        new_lines.append(line)
                content = "\n".join(new_lines)

            # 5. @IdRes 注解的参数
            pattern = rf'@IdRes[^)]*?{re.escape(old_id)}\b'
            new_content = content  # rare, handled by R.id pattern above

        if content != original:
            if not self.dry_run:
                if self.backup:
                    backup_file(filepath)
                    self.stats["backups_created"] += 1
                write_file(filepath, content)
            self.stats["files_modified"] += 1
            self.stats["replacements"] += count

        return count

    # ================================================================
    # Navigation XML 替换
    # ================================================================

    def fix_navigation_file(self, filepath: str) -> int:
        """修复 Navigation XML 文件中的 ID 引用。"""
        return self.fix_xml_file(filepath)

    # ================================================================
    # Menu XML 替换
    # ================================================================

    def fix_menu_file(self, filepath: str) -> int:
        """修复 Menu XML 文件中的 ID 引用。"""
        return self.fix_xml_file(filepath)

    # ================================================================
    # DataBinding 布局替换
    # ================================================================

    def fix_databinding_file(self, filepath: str) -> int:
        """修复 DataBinding 表达式中的 ID 引用。"""
        try:
            content = read_file(filepath)
        except Exception as e:
            self.stats["errors"] += 1
            return 0

        original = content
        count = 0

        for old_id, new_id in self.id_mappings.items():
            # DataBinding: @{...} 表达式中可能引用 view id
            # 如 android:text="@{viewModel.text}" 不是 id 引用
            # 但 onClick 等可能引用 @id/xxx
            pattern = f'@id/{re.escape(old_id)}(?![a-zA-Z0-9_])'
            replacement = f'@id/{new_id}'
            new_content = re.sub(pattern, replacement, content)
            if new_content != content:
                matches = len(re.findall(pattern, content))
                count += matches
                content = new_content

        if content != original:
            if not self.dry_run:
                if self.backup:
                    backup_file(filepath)
                    self.stats["backups_created"] += 1
                write_file(filepath, content)
            self.stats["files_modified"] += 1
            self.stats["replacements"] += count

        return count

    # ================================================================
    # 全项目修复
    # ================================================================

    def fix_all(self) -> None:
        """全项目扫描并修复。"""
        cprint(f"\n{'='*70}", Colors.BLUE)
        cprint(f"  Android ID 规范化修复工具", Colors.BOLD)
        cprint(f"  项目: {self.project_dir}", Colors.BOLD)
        cprint(f"  ID 映射数: {len(self.id_mappings)}", Colors.BOLD)
        mode = "预览模式 (dry-run)" if self.dry_run else "执行模式"
        cprint(f"  模式: {mode}", Colors.YELLOW if self.dry_run else Colors.GREEN)
        cprint(f"  发现模块数: {len(self._source_roots)}", Colors.BOLD)
        for root in self._source_roots:
            rel = os.path.relpath(root, self.project_dir)
            cprint(f"    - {rel}", Colors.CYAN)
        cprint(f"{'='*70}\n", Colors.BLUE)

        if not self.id_mappings:
            print_warning("没有需要修复的 ID 映射")
            return

        # 打印映射表
        cprint("  ID 映射表:", Colors.BOLD)
        cprint(f"  {'原 ID':<30} → {'新 ID':<30}", Colors.CYAN)
        cprint(f"  {'-'*30}   {'-'*30}", Colors.CYAN)
        for old_id, new_id in sorted(self.id_mappings.items()):
            cprint(f"  {Colors.RED}{old_id:<30}{Colors.RESET} → {Colors.GREEN}{new_id:<30}{Colors.RESET}", Colors.RESET)

        # 扫描并修复文件
        self._fix_layout_files()
        if not self.only_xml:
            self._fix_kotlin_java_files()
            self._fix_navigation_files()
            self._fix_menu_files()
            self._fix_values_files()

        # 打印结果
        self._print_summary()
        self._save_changelog()

    def _discover_source_roots(self) -> list[str]:
        """自动发现项目中所有模块的 src/main 目录。

        支持多模块项目结构：
          project/app/src/main/
          project/module1/src/main/
          project/feature/login/src/main/
        同时也覆盖 src/main 直接在项目根目录下的情况。
        """
        roots = []
        seen = set()
        for dirpath, dirnames, filenames in os.walk(self.project_dir):
            # 跳过 build、.gradle、.idea 等目录
            dirnames[:] = [d for d in dirnames if d not in (
                "build", ".gradle", ".idea", ".git", "gradle", "tools",
            )]
            if os.path.basename(dirpath) == "main" and "src" in dirpath:
                # 确认父目录是 src
                parent = os.path.dirname(dirpath)
                if os.path.basename(parent) == "src":
                    if dirpath not in seen:
                        seen.add(dirpath)
                        roots.append(dirpath)
                        # 不再深入这个 main 目录内部找子 main
                        dirnames.clear()
        return roots

    def _fix_layout_files(self):
        """修复所有模块中的布局 XML 文件。"""
        cprint("\n  [1/5] 扫描布局 XML 文件...", Colors.BOLD)
        for src_main in self._source_roots:
            res_dir = os.path.join(src_main, "res")
            if not os.path.isdir(res_dir):
                continue
            layout_files = list(find_files(res_dir, extensions=[".xml"]))
            layout_files = [
                f for f in layout_files
                if "/layout" in f or os.sep + "layout" in f
            ]
            for fp in layout_files:
                self.stats["files_scanned"] += 1
                count = self.fix_xml_file(fp)
                if count > 0:
                    rel = os.path.relpath(fp, self.project_dir)
                    cprint(f"    {rel}: {count} 处替换", Colors.GREEN)

    def _fix_kotlin_java_files(self):
        """修复所有模块中的 Kotlin/Java 源文件。"""
        cprint("\n  [2/5] 扫描 Kotlin/Java 源文件...", Colors.BOLD)
        for src_main in self._source_roots:
            for src_dir in ["java", "kotlin"]:
                base = os.path.join(src_main, src_dir)
                if not os.path.isdir(base):
                    continue
                for fp in find_files(base, extensions=[".kt", ".java", ".kts"]):
                    self.stats["files_scanned"] += 1
                    count = self.fix_kotlin_java_file(fp)
                    if count > 0:
                        rel = os.path.relpath(fp, self.project_dir)
                        cprint(f"    {rel}: {count} 处替换", Colors.GREEN)

    def _fix_navigation_files(self):
        """修复所有模块中的 Navigation XML。"""
        cprint("\n  [3/5] 扫描 Navigation XML...", Colors.BOLD)
        for src_main in self._source_roots:
            nav_dir = os.path.join(src_main, "res", "navigation")
            if not os.path.isdir(nav_dir):
                continue
            for fp in find_files(nav_dir, extensions=[".xml"]):
                self.stats["files_scanned"] += 1
                count = self.fix_navigation_file(fp)
                if count > 0:
                    rel = os.path.relpath(fp, self.project_dir)
                    cprint(f"    {rel}: {count} 处替换", Colors.GREEN)

    def _fix_menu_files(self):
        """修复所有模块中的 Menu XML。"""
        cprint("\n  [4/5] 扫描 Menu XML...", Colors.BOLD)
        for src_main in self._source_roots:
            menu_dir = os.path.join(src_main, "res", "menu")
            if not os.path.isdir(menu_dir):
                continue
            for fp in find_files(menu_dir, extensions=[".xml"]):
                self.stats["files_scanned"] += 1
                count = self.fix_menu_file(fp)
                if count > 0:
                    rel = os.path.relpath(fp, self.project_dir)
                    cprint(f"    {rel}: {count} 处替换", Colors.GREEN)

    def _fix_values_files(self):
        """修复所有模块中的 values/ids.xml 等文件。"""
        cprint("\n  [5/5] 扫描 values XML...", Colors.BOLD)
        for src_main in self._source_roots:
            values_dir = os.path.join(src_main, "res", "values")
            if not os.path.isdir(values_dir):
                continue
            for fp in find_files(values_dir, extensions=[".xml"]):
                self.stats["files_scanned"] += 1
                try:
                    content = read_file(fp)
                    original = content
                    count = 0
                    for old_id, new_id in self.id_mappings.items():
                        pattern = rf'name\s*=\s*"{re.escape(old_id)}"'
                        if re.search(pattern, content):
                            content = re.sub(pattern, f'name="{new_id}"', content)
                            count += 1
                            self.log_change(fp, old_id, new_id, "values XML")
                    if content != original:
                        if not self.dry_run:
                            if self.backup:
                                backup_file(fp)
                            write_file(fp, content)
                        self.stats["files_modified"] += 1
                        self.stats["replacements"] += count
                        rel = os.path.relpath(fp, self.project_dir)
                        cprint(f"    {rel}: {count} 处替换", Colors.GREEN)
                except Exception:
                    pass

    def _print_summary(self):
        """打印修复摘要。"""
        cprint(f"\n{'='*70}", Colors.BLUE)
        cprint("  修复摘要", Colors.BOLD)
        cprint(f"{'='*70}", Colors.BLUE)
        cprint(f"  扫描文件数:     {self.stats['files_scanned']}", Colors.CYAN)
        cprint(f"  修改文件数:     {self.stats['files_modified']}", Colors.GREEN)
        cprint(f"  替换总数:       {self.stats['replacements']}", Colors.GREEN)
        cprint(f"  备份数:         {self.stats['backups_created']}", Colors.YELLOW)
        cprint(f"  错误数:         {self.stats['errors']}", Colors.RED)

        if self.dry_run:
            cprint(f"\n  这是预览模式，未实际修改任何文件", Colors.YELLOW)
            cprint(f"  要执行实际修改，去掉 --dry-run 参数", Colors.YELLOW)
        else:
            cprint(f"\n  修改已完成！所有原文件已备份为 .bak", Colors.GREEN)
            rollback_cmd = 'find . -name "*.bak" -exec bash -c \'mv "$0" "${0%.bak}"\' {} \\;'
            cprint(f"  如需回滚：{rollback_cmd}", Colors.CYAN)
        cprint(f"{'='*70}\n", Colors.BLUE)

    def _save_changelog(self):
        """保存修改日志。"""
        if not self.changes:
            return

        log_path = os.path.join(self.project_dir, "id_changes.log")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"# Android ID 规范化修改日志\n")
            f.write(f"# 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# 模式: {'预览(dry-run)' if self.dry_run else '实际修改'}\n\n")
            for change in self.changes:
                f.write(f"[{change['context']}] {change['file']}\n")
                f.write(f"  {change['old']} -> {change['new']}\n\n")

        cprint(f"  修改日志已保存: {log_path}", Colors.GREEN)


def _resolve_duplicates(id_mappings: dict[str, str]) -> dict[str, str]:
    """检测 suggested_id 重复，自动追加数字后缀消歧。

    例：两个 old_id 都映射到 login_btn_submit，
    则第二个自动变为 login_btn_submit_2，第三个 login_btn_submit_3。
    """
    from collections import Counter

    new_id_counts = Counter(id_mappings.values())
    duplicates = {nid for nid, cnt in new_id_counts.items() if cnt > 1}

    if not duplicates:
        return id_mappings

    resolved = {}
    # 记录每个重复 new_id 当前已分配的序号
    seq_map = {}

    for old_id, new_id in id_mappings.items():
        if new_id in duplicates:
            seq_map.setdefault(new_id, 0)
            seq_map[new_id] += 1
            if seq_map[new_id] == 1:
                # 第一个保持不变
                resolved[old_id] = new_id
            else:
                resolved_id = f"{new_id}_{seq_map[new_id]}"
                print_warning(f"重复 ID '{new_id}' → 自动重命名为 '{resolved_id}' (原 ID: {old_id})")
                resolved[old_id] = resolved_id
        else:
            resolved[old_id] = new_id

    return resolved


def main():
    parser = argparse.ArgumentParser(
        description="Android 组件 ID 规范化自动修复工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "project_dir",
        help="Android 项目根目录路径",
    )
    parser.add_argument(
        "--report", "-r",
        required=True,
        help="Scanner 生成的 CSV 报告路径",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="预览模式，不实际修改文件（默认开启）",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="实际执行修改（关闭 dry-run）",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="不创建备份文件",
    )
    parser.add_argument(
        "--only-xml",
        action="store_true",
        help="只修改 XML 布局文件，不修改 Kotlin/Java 代码",
    )
    parser.add_argument(
        "--mapping",
        help="手动指定映射 old_id:new_id，逗号分隔。如: add_btn:home_btn_add",
        default=None,
    )

    args = parser.parse_args()

    # 验证项目路径
    if not os.path.isdir(args.project_dir):
        print_error(f"项目目录不存在: {args.project_dir}")
        sys.exit(1)

    # 构建 ID 映射
    id_mappings = {}

    # 从报告加载
    if args.report and os.path.exists(args.report):
        try:
            with open(args.report, "r", encoding="utf-8-sig") as f:
                raw_lines = f.readlines()
            # 跳过 Excel sep= 声明行，避免 DictReader 误解析
            clean_lines = [line for line in raw_lines if not line.strip().startswith("sep=")]
            import io
            reader = csv.DictReader(io.StringIO("".join(clean_lines)))
            for row in reader:
                # 兼容各种 Excel 保存格式：False/FALSE/false/0 等
                is_compliant = str(row.get("is_compliant", "")).strip().lower()
                if is_compliant in ("false", "0", "no", ""):
                    old_id = row.get("original_id", "").strip()
                    new_id = row.get("suggested_id", "").strip()
                    # 去掉 Excel 可能加的引号
                    if new_id.startswith('"') and new_id.endswith('"'):
                        new_id = new_id[1:-1]
                    if old_id and new_id and old_id != new_id:
                        id_mappings[old_id] = new_id
        except Exception as e:
            print_error(f"报告加载失败: {e}")
            sys.exit(1)
    else:
        if not args.mapping:
            print_error(f"报告文件不存在: {args.report}，请使用 --mapping 手动指定映射")
            sys.exit(1)

    # 手动映射覆盖
    if args.mapping:
        for pair in args.mapping.split(","):
            if ":" in pair:
                old, new = pair.split(":", 1)
                id_mappings[old.strip()] = new.strip()

    if not id_mappings:
        print_warning("没有需要修复的 ID")
        sys.exit(0)

    # 冲突检测：检查新 ID 是否重复，自动加数字后缀消歧
    print_info("检查 ID 冲突...")
    id_mappings = _resolve_duplicates(id_mappings)

    # 执行修复
    dry_run = not args.execute
    fixer = IDFixer(
        project_dir=args.project_dir,
        id_mappings=id_mappings,
        dry_run=dry_run,
        backup=not args.no_backup,
        only_xml=args.only_xml,
    )
    fixer.fix_all()

    if dry_run:
        cprint("\n提示：这是预览模式。确认无误后使用 --execute 参数执行实际修改：", Colors.YELLOW)
        cprint(f"  python fixer.py {args.project_dir} --report {args.report} --execute", Colors.YELLOW)


if __name__ == "__main__":
    main()
