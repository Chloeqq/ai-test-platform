#!/usr/bin/env python3
"""架构护栏——CI 中运行，拦截违反架构规则的代码。

检测项:
  1. 文件大小上限（按层设阈值）
  2. 函数大小上限
  3. Repository 强制（非 repository 层不能有 db.execute(select(...))）
  4. Session 边界（service/repository 不能 SessionLocal()）
  5. 分层导入违规
  6. 重复函数定义（type_utils 已有）

用法: python scripts/ci/check_architecture.py
退出码 0 = 全通过，1 = 有违规
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APPS = ROOT / "apps" / "web-ui-service" / "app"
SRC = ROOT / "apps" / "ai-orchestrator" / "src"

# ---- 配置 ----

FILE_SIZE_LIMITS = {
    "facade": 2500,    # app/api/workbench/facade.py
    "service": 1000,
    "repository": 400,
    "router": 200,
    "model": 200,
}

FUNC_SIZE_WARN = 100
FUNC_SIZE_FAIL = 200

# type_utils 中已有的公共函数，不允许在其他文件重复定义
SHARED_FUNCS = {
    "dict_value", "list_value", "int_value", "float_value", "str_value",
    "dedup_keep_order", "bounded_score", "json_dict", "json_list",
    "now_iso", "normalize_project_code", "normalize_project_code_strict",
}

# 分层导入黑名单（模块名 → 禁止导入的模式列表）
LAYER_IMPORT_BLACKLIST = {
    "facade": [],  # facade 可以导入任何东西
    "repository": ["app.services.", "app.api."],
}

violations = 0
warnings = 0


def report(level: str, path: str, msg: str, line: int = 0) -> None:
    global violations, warnings
    prefix = {"error": "❌", "warn": "⚠️ "}[level]
    loc = f"L{line}: " if line else ""
    print(f"  {prefix} {path}: {loc}{msg}")
    if level == "error":
        violations += 1
    else:
        warnings += 1


# ---- 1. 文件大小 + 函数大小 ----

def _classify_file(filepath: Path) -> str:
    name = filepath.name
    if "facade" in name:
        return "facade"
    if "repository" in str(filepath) or filepath.suffix == ".py" and "repository" in str(filepath.parent):
        return "repository"
    if "router" in str(filepath):
        return "router"
    if "model" in str(filepath):
        return "model"
    if "/services/" in str(filepath):
        return "service"
    return "other"


def _parse_functions(source: str) -> list[tuple[str, int, int]]:
    """返回 [(函数名, 起始行, 结束行), ...]"""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    funcs = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs.append((node.name, node.lineno, node.end_lineno or node.lineno))
    return funcs


def check_sizes(filepath: Path) -> None:
    rel = str(filepath.relative_to(ROOT))
    category = _classify_file(filepath)
    limit = FILE_SIZE_LIMITS.get(category)
    lines = filepath.read_text().splitlines()
    total = len(lines)

    if limit and total > limit:
        report("error", rel, f"文件 {total} 行，超过 {category} 上限 {limit} 行", 0)

    for name, start, end in _parse_functions("\n".join(lines)):
        size = end - start + 1
        if size > FUNC_SIZE_FAIL:
            report("error", rel, f"函数 {name}() {size} 行，超过上限 {FUNC_SIZE_FAIL}", start)
        elif size > FUNC_SIZE_WARN:
            report("warn", rel, f"函数 {name}() {size} 行，建议拆分", start)


# ---- 2. Repository 强制 ----

def check_repository_enforcement(filepath: Path) -> None:
    rel = str(filepath.relative_to(ROOT))
    if "/repositories/" in rel:
        return
    content = filepath.read_text()
    if "db.execute(select(" in content:
        report("error", rel, "禁止直接写 db.execute(select(...))，请使用 Repository 方法")


# ---- 3. Session 边界 ----

_SESSION_ALLOWED = {
    "app/core/database.py",
    "app/services/workbench_state_store.py",
}

def check_session_boundary(filepath: Path) -> None:
    rel = str(filepath.relative_to(ROOT))
    if any(allowed in rel for allowed in _SESSION_ALLOWED):
        return
    # 允许 facade 的后台线程闭包
    if "facade" in rel:
        return
    content = filepath.read_text()
    if "SessionLocal()" in content:
        report("error", rel, "禁止 SessionLocal()，请通过参数接收 db: Session")


# ---- 4. 分层导入违规 ----

def check_layer_imports(filepath: Path) -> None:
    rel = str(filepath.relative_to(ROOT))
    content = filepath.read_text()
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return

    if "sqlite3" in content:
        report("error", rel, "禁止 import sqlite3，请使用 shared_backend.db.get_db_session()")

    if "/repositories/" not in rel and "/services/" in rel:
        if "from app.api.workbench.store import" in content or "from app.api.workbench import" in content:
            report("warn", rel, "service 层不应直接 import store(API层)，请接收 db 参数")


# ---- 5. 重复函数 ----

def check_duplicate_funcs(filepath: Path) -> None:
    rel = str(filepath.relative_to(ROOT))
    if "type_utils" in rel:
        return
    content = filepath.read_text()
    for func in SHARED_FUNCS:
        if f"def {func}(" in content or f"def _{func}(" in content:
            report("error", rel, f"函数 _{func} 已在 shared_backend/type_utils.py 中定义，请改为 import")


# ---- 6. 禁止 import * ----

def check_import_star(filepath: Path) -> None:
    rel = str(filepath.relative_to(ROOT))
    if filepath.name == "__init__.py":
        return
    for line in filepath.read_text().splitlines():
        if "import *" in line and not line.strip().startswith("#"):
            report("warn", rel, "禁止非 __init__.py 中使用 import *")
            return


# ---- 主流程 ----

def main() -> int:
    print("\n🔍 架构护栏检查\n")
    py_files = list(APPS.rglob("*.py")) + list(SRC.rglob("*.py"))
    py_files = [f for f in py_files if "__pycache__" not in str(f) and "node_modules" not in str(f)]
    py_files = [f for f in py_files if "test_" not in f.name and "/tests/" not in str(f)]

    for f in sorted(py_files):
        check_sizes(f)
        check_repository_enforcement(f)
        check_session_boundary(f)
        check_layer_imports(f)
        check_duplicate_funcs(f)
        check_import_star(f)

    # Baseline: 已知的历史遗留违规(44 violations, 61 warnings)
    # CI 只拦截新增违规。降低 baseline 会导致 CI 失败。
    BASELINE_VIOLATIONS = 44
    BASELINE_WARNINGS = 61

    print(f"\n{'='*40}")
    print(f"  {violations} violations, {warnings} warnings")
    print(f"  baseline: {BASELINE_VIOLATIONS} violations, {BASELINE_WARNINGS} warnings")
    if violations > BASELINE_VIOLATIONS:
        print(f"  ❌ {violations - BASELINE_VIOLATIONS} new violation(s) since baseline")
        return 1
    elif warnings > BASELINE_WARNINGS:
        print(f"  ⚠️  {warnings - BASELINE_WARNINGS} new warning(s) since baseline")
    print(f"  ✅ no new violations")
    print(f"{'='*40}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
