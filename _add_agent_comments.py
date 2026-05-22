#!/usr/bin/env python3
"""一次性脚本：为 agents/ 下 Python 文件补充中文注释（仅注释，不改逻辑）。"""
from __future__ import annotations

import ast
from pathlib import Path

AGENTS_ROOT = Path(__file__).resolve().parent / "agents"

NAME_HINTS: dict[str, str] = {
    "main": "CLI 入口",
    "generate": "生成主流程",
    "parse": "解析需求并输出结构化规格",
    "design_bundle": "生成企业级设计包（用例、测试点与追溯信息）",
    "to_dict": "序列化为字典",
    "load_page_object": "从 DB API 加载页面对象",
    "list_page_elements": "列出页面对象中的元素编码",
    "build_test_point_plan": "根据步骤构建测试点计划",
    "build_test_point_plan_from_openapi": "从 OpenAPI 规范构建 API 测试点计划",
    "render_steps_from_test_point_plan": "将测试点计划还原为执行步骤",
}


def _describe_node(node: ast.AST, name: str) -> str:
    if isinstance(node, ast.ClassDef):
        return f"{name}：核心类型定义"
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        if name.startswith("_") and not name.startswith("__"):
            hint = NAME_HINTS.get(name.lstrip("_"))
            return hint if hint else f"内部辅助逻辑（{name}）"
        return NAME_HINTS.get(name, f"{name} 业务方法")
    return name


def _has_docstring(node: ast.AST) -> bool:
    body = getattr(node, "body", None)
    if not body:
        return False
    first = body[0]
    return (
        isinstance(first, ast.Expr)
        and isinstance(getattr(first, "value", None), ast.Constant)
        and isinstance(first.value.value, str)
    )


def _module_comment(path: Path) -> str | None:
    rel = path.relative_to(AGENTS_ROOT)
    parts = rel.parts
    agent = parts[0] if parts else "agent"
    if "tests" in parts or parts[-2:] == ("tests", path.name):
        return f"# 测试：{agent} 单元/集成测试"
    if path.name.startswith("test_") and "tests" in str(rel):
        return f"# 测试：{agent} 单元/集成测试"
    if path.name == "schema.py":
        return f"# 数据模型：{agent} 输入输出与中间结构"
    if path.name in {"prompt.py", "instructions.py"}:
        return f"# 提示词：{agent} LLM 系统提示与版本元数据"
    if path.name == "index.py":
        return f"# CLI：{agent} 命令行入口"
    if path.name == "agent.py":
        return f"# 核心 Agent：{agent} 业务实现"
    return f"# 模块：{agent} / {'/'.join(parts[1:])}"


def _has_chinese_module_header(lines: list[str]) -> bool:
    for line in lines[:10]:
        s = line.strip()
        if not s or s.startswith("# mypy") or s.startswith("# ruff") or s.startswith("# type:"):
            continue
        if s.startswith("from __future__"):
            continue
        if any("\u4e00" <= ch <= "\u9fff" for ch in s):
            return True
        break
    return False


def _body_indent(line: str) -> str:
    base = line[: len(line) - len(line.lstrip())]
    return f"{base}    "


def _signature_end_line(lines: list[str], node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> int:
    """定位 def/class 签名结束行（勿用 end_lineno，其为整个函数体末行）。"""
    start = node.lineno - 1
    depth = 0
    for i in range(start, min(len(lines), start + 80)):
        line = lines[i]
        for ch in line:
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth = max(0, depth - 1)
        if line.rstrip().endswith(":") and depth == 0:
            return i + 1
    return node.lineno


def process_file(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    plain_lines = original.splitlines()
    lines = original.splitlines(keepends=True)
    if not lines:
        return False

    try:
        tree = ast.parse(original)
    except SyntaxError:
        return False

    # (0-based index to insert AFTER, text to insert)
    insertions: list[tuple[int, str]] = []

    if isinstance(tree, ast.Module) and not _has_chinese_module_header(plain_lines):
        header = _module_comment(path)
        if header:
            insert_at = 0
            for i, ln in enumerate(plain_lines[:6]):
                stripped = ln.strip()
                if stripped.startswith("# mypy") or stripped.startswith("# ruff") or stripped.startswith("# type:"):
                    insert_at = i + 1
                    continue
                if stripped.startswith("from __future__"):
                    insert_at = i + 1
                    continue
                break
            insertions.append((insert_at, header + "\n"))

    for node in ast.walk(tree):
        if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if _has_docstring(node):
            continue
        sig_end = _signature_end_line(plain_lines, node)
        sig_line = plain_lines[sig_end - 1]
        indent = _body_indent(sig_line)
        desc = _describe_node(node, node.name)
        doc = f'{indent}"""{desc}。"""\n'
        insertions.append((sig_end, doc))

    if not insertions:
        return False

    insertions.sort(key=lambda x: x[0], reverse=True)
    for idx, text in insertions:
        lines.insert(idx, text)

    new_content = "".join(lines)
    if new_content == original:
        return False
    path.write_text(new_content, encoding="utf-8")
    return True


def main() -> None:
    modified: list[str] = []
    for path in sorted(AGENTS_ROOT.rglob("*.py")):
        if process_file(path):
            modified.append(str(path.relative_to(AGENTS_ROOT.parent)))
    for item in modified:
        print(item)


if __name__ == "__main__":
    main()
