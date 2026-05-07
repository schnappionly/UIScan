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
    find_files,
)


class IDFixer:
    """ID 自动修复器。"""

    def __init__(
        self,
        project_dir: str,
        id_mappings: dict[str, str],
        dry_run: bool = True,
        only_xml: bool = False,
    ):
        self.project_dir = os.path.abspath(project_dir)
        self.id_mappings = id_mappings  # {old_id: new_id}
        self.dry_run = dry_run
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

        # 预编译：一次性构建全部正则和查找表
        self._compile_kt_java_patterns()
        self._compile_xml_patterns()

        # 统计（含幂等计数）
        self.stats = {
            "files_scanned": 0,
            "files_modified": 0,
            "files_skipped": 0,
            "replacements": 0,
            "already_replaced": 0,
            "errors": 0,
        }

        # 修改日志
        self.changes = []

    def _compile_xml_patterns(self):
        """预编译 XML 文件替换所需的全部正则，与 Java 同理。"""
        if not self.id_mappings:
            self._xml_old_ids_set = set()
            self._xml_declare_re = None
            self._xml_ref_re = None
            self._xml_map = {}
            return

        self._xml_old_ids_set = set(self.id_mappings.keys())
        self._xml_map = dict(self.id_mappings)

        sorted_ids = sorted(self._xml_old_ids_set, key=len, reverse=True)
        alts = '|'.join(re.escape(oid) for oid in sorted_ids)

        # @+id/old 和 @id/old 各一个预编译正则
        self._xml_declare_re = re.compile(rf'@\+id/({alts})(?![a-zA-Z0-9_])')
        self._xml_ref_re = re.compile(rf'@id/({alts})(?![a-zA-Z0-9_])')

    def _compile_kt_java_patterns(self):
        """预编译 Java 文件替换所需的全部正则，避免逐文件重复编译。

        同时构建幂等检测所需的 new_id 查找表，用于重复执行时快速跳过已替换的文件。
        """
        if not self.id_mappings:
            self._kj_rid_re = None
            self._kj_binding_re = None
            self._kj_synthetic_re = None
            self._kj_rid_map = {}
            self._kj_binding_map = {}
            self._kj_id_to_new = {}
            self._kj_new_ids = set()
            self._kj_new_id_set_re = None
            self._kj_new_camel_set = set()
            self._kj_new_camel_re = None
            return

        # --- R.id.xxx 匹配 ---
        sorted_ids = sorted(self.id_mappings.keys(), key=len, reverse=True)
        rid_alts = '|'.join(re.escape(oid) for oid in sorted_ids)
        self._kj_rid_re = re.compile(rf'R\.id\.({rid_alts})\b')
        self._kj_rid_map = dict(self.id_mappings)

        # --- 幂等检测: 快速判断文件中的 new_id 是否已全部替换完毕 ---
        self._kj_new_ids = set(self.id_mappings.values())
        new_ids_sorted = sorted(self._kj_new_ids, key=len, reverse=True)
        new_alts = '|'.join(re.escape(nid) for nid in new_ids_sorted)
        self._kj_new_id_set_re = re.compile(rf'R\.id\.({new_alts})\b')

        # --- binding.xxxCamel 匹配 ---
        if self.camel_mappings:
            sorted_camel = sorted(self.camel_mappings.keys(), key=len, reverse=True)
            camel_alts = '|'.join(re.escape(c) for c in sorted_camel)
            self._kj_binding_re = re.compile(rf'\bbinding\.\s*({camel_alts})\b')
            self._kj_new_camel_set = set(self.camel_mappings.values())
            new_camel_sorted = sorted(self._kj_new_camel_set, key=len, reverse=True)
            new_camel_alts = '|'.join(re.escape(c) for c in new_camel_sorted)
            self._kj_new_camel_re = re.compile(rf'\bbinding\.\s*({new_camel_alts})\b')
        else:
            self._kj_binding_re = None
            self._kj_new_camel_set = set()
            self._kj_new_camel_re = None
        self._kj_binding_map = dict(self.camel_mappings)

        # --- synthetic import 匹配 ---
        id_alts_dot = '|'.join(re.escape(oid) for oid in sorted_ids)
        self._kj_synthetic_re = re.compile(
            rf'import\s+kotlinx\.android\.synthetic\.main\.[\w.]+\.({id_alts_dot})\b'
        )
        self._kj_id_to_new = dict(self.id_mappings)

        # --- 幂等检测: 构建快速子串探测集合（用于 early-return） ---
        self._kj_old_ids_set = set(self.id_mappings.keys())
        self._kj_old_camels_set = set(self.camel_mappings.keys()) if self.camel_mappings else set()

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
        """修复 XML 文件中的 ID 引用。返回替换次数。

        预编译正则 + 回调查表 + 幂等早退，与 Java 优化同思路。
        """
        try:
            content = read_file(filepath)
        except Exception as e:
            print_error(f"读取文件失败 {filepath}: {e}")
            self.stats["errors"] += 1
            return 0

        if not self._xml_declare_re:
            return 0

        # ── 早退：不含任何 old_id 子串 ──
        _has_old = False
        for old_id in self._xml_old_ids_set:
            if old_id in content:
                _has_old = True
                break
        if not _has_old:
            return 0

        # ── 幂等检测：有子串命中但正则不匹配 → 已替换完毕 ──
        _has_declare = self._xml_declare_re.search(content) is not None
        _has_ref = self._xml_ref_re.search(content) is not None
        if not _has_declare and not _has_ref:
            self.stats["files_skipped"] += 1
            self.stats["already_replaced"] += 1
            return 0

        original = content
        count = 0
        _local_log = self.changes.append
        _rid_map = self._xml_map
        _project = self.project_dir

        if _has_declare:
            def _replace_declare(m):
                nonlocal count
                old = m.group(1)
                new = _rid_map[old]
                count += 1
                _local_log({
                    "file": os.path.relpath(filepath, _project),
                    "old": f"@+id/{old}", "new": f"@+id/{new}",
                    "context": "XML id 声明",
                })
                return f'@+id/{new}'
            content = self._xml_declare_re.sub(_replace_declare, content)

        if _has_ref:
            def _replace_ref(m):
                nonlocal count
                old = m.group(1)
                new = _rid_map[old]
                count += 1
                _local_log({
                    "file": os.path.relpath(filepath, _project),
                    "old": f"@id/{old}", "new": f"@id/{new}",
                    "context": "XML id 引用",
                })
                return f'@id/{new}'
            content = self._xml_ref_re.sub(_replace_ref, content)

        if content != original:
            if not self.dry_run:
                write_file(filepath, content)
            self.stats["files_modified"] += 1
            self.stats["replacements"] += count

        return count

    # ================================================================
    # Kotlin / Java 文件替换
    # ================================================================

    def fix_kotlin_java_file(self, filepath: str) -> int:
        """修复 Java 文件中的 ID 引用。返回替换次数。

        性能优化 + 幂等安全：
        1. 预编译正则：所有 old_id 合并为一个大 alternation，一次扫描。
        2. 回调查表替换：O(1) 查 dict，避免反复扫描。
        3. 快速子串探测早退：不含任何 old_id 的文件直接跳过。
        4. 幂等检测：文件只含 new_id 不含 old_id → 已替换完毕，标记跳过。
        """
        try:
            content = read_file(filepath)
        except Exception as e:
            print_error(f"读取文件失败 {filepath}: {e}")
            self.stats["errors"] += 1
            return 0

        if not self._kj_rid_re:
            return 0

        # ── 第一层早退：不含任何 old_id 子串 → 完全无关文件 ──
        _has_old = False
        for old_id in self._kj_old_ids_set:
            if old_id in content:
                _has_old = True
                break
        if not _has_old:
            # 检查是否含有 old camel（binding 场景）
            for old_camel in self._kj_old_camels_set:
                if old_camel in content:
                    _has_old = True
                    break
        if not _has_old:
            return 0

        # ── 幂等检测：不含 old_id 但含 new_id → 已替换完毕 ──
        _has_old_rid = self._kj_rid_re.search(content) is not None
        _has_old_binding = (self._kj_binding_re is not None
                           and self._kj_binding_re.search(content) is not None)
        _has_old_synthetic = (self._kj_synthetic_re is not None
                             and self._kj_synthetic_re.search(content) is not None)

        if not _has_old_rid and not _has_old_binding and not _has_old_synthetic:
            # 全部是 new_id，没有 old_id 残留 → 文件已替换，快速跳过
            self.stats["files_skipped"] += 1
            self.stats["already_replaced"] += 1
            rel = os.path.relpath(filepath, self.project_dir)
            cprint(f"    {rel}: 已替换，跳过", Colors.CYAN)
            return 0

        original = content
        count = 0
        _local_log = self.changes.append

        # ── 1. R.id.xxx 一次性替换 ──
        if _has_old_rid:
            def _replace_rid(m):
                nonlocal count
                old = m.group(1)
                new = self._kj_rid_map[old]
                count += 1
                _local_log({
                    "file": os.path.relpath(filepath, self.project_dir),
                    "old": f"R.id.{old}",
                    "new": f"R.id.{new}",
                    "context": "R.id 引用",
                })
                return f'R.id.{new}'

            content = self._kj_rid_re.sub(_replace_rid, content)

        # ── 2. binding.xxxCamel 一次性替换 ──
        if _has_old_binding:
            def _replace_binding(m):
                nonlocal count
                old_camel = m.group(1)
                new_camel = self._kj_binding_map[old_camel]
                count += 1
                _local_log({
                    "file": os.path.relpath(filepath, self.project_dir),
                    "old": f"binding.{old_camel}",
                    "new": f"binding.{new_camel}",
                    "context": "ViewBinding",
                })
                return f'binding.{new_camel}'

            content = self._kj_binding_re.sub(_replace_binding, content)

        # ── 3. synthetic import 行级替换 ──
        if _has_old_synthetic:
            lines = content.split("\n")
            new_lines = None
            for i, line in enumerate(lines):
                m = self._kj_synthetic_re.search(line)
                if m:
                    if new_lines is None:
                        new_lines = list(lines)
                    old_id = m.group(1)
                    new_id = self._kj_id_to_new[old_id]
                    new_line = line.replace(old_id, new_id)
                    count += 1
                    _local_log({
                        "file": os.path.relpath(filepath, self.project_dir),
                        "old": line.strip(),
                        "new": new_line.strip(),
                        "context": "synthetic import",
                    })
                    new_lines[i] = new_line
            if new_lines is not None:
                content = "\n".join(new_lines)

        if content != original:
            if not self.dry_run:
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
            self._fix_java_files()
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
            # 直接遍历 layout*/ 开头的子目录，避免收集全部 XML 再过滤
            try:
                entries = os.listdir(res_dir)
            except OSError:
                continue
            for entry in entries:
                entry_path = os.path.join(res_dir, entry)
                if not os.path.isdir(entry_path) or not entry.startswith("layout"):
                    continue
                for fp in find_files(entry_path, extensions=[".xml"]):
                    self.stats["files_scanned"] += 1
                    count = self.fix_xml_file(fp)
                    if count > 0:
                        rel = os.path.relpath(fp, self.project_dir)
                        cprint(f"    {rel}: {count} 处替换", Colors.GREEN)

    def _fix_java_files(self):
        """修复所有模块中的 Java 源文件。"""
        cprint("\n  [2/5] 扫描 Java 源文件...", Colors.BOLD)
        for src_main in self._source_roots:
            base = os.path.join(src_main, "java")
            if not os.path.isdir(base):
                continue
            for fp in find_files(base, extensions=[".java"]):
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
                            if not self.dry_run:
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
        cprint(f"  已替换跳过:     {self.stats['files_skipped']}", Colors.CYAN)
        cprint(f"  替换总数:       {self.stats['replacements']}", Colors.GREEN)
        cprint(f"  已替换 ID 数:   {self.stats['already_replaced']}", Colors.CYAN)
        cprint(f"  错误数:         {self.stats['errors']}", Colors.RED)

        if self.stats['files_skipped'] > 0:
            cprint(f"\n  提示: {self.stats['files_skipped']} 个文件已替换完毕，本次跳过", Colors.CYAN)

        if self.dry_run:
            cprint(f"\n  这是预览模式，未实际修改任何文件", Colors.YELLOW)
            cprint(f"  要执行实际修改，去掉 --dry-run 参数", Colors.YELLOW)
        else:
            cprint(f"\n  修改已完成！", Colors.GREEN)
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
        only_xml=args.only_xml,
    )
    fixer.fix_all()

    if dry_run:
        cprint("\n提示：这是预览模式。确认无误后使用 --execute 参数执行实际修改：", Colors.YELLOW)
        cprint(f"  python fixer.py {args.project_dir} --report {args.report} --execute", Colors.YELLOW)


if __name__ == "__main__":
    main()
