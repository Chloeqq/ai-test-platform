#!/usr/bin/env python3
"""
Generate per-module Markdown docs under docs/python-modules/ mirroring source tree.

Usage (from repo root):
  python scripts/tools/generate_python_module_docs.py

Caller hints use a one-pass Python index (no external ripgrep required).
"""
from __future__ import annotations

import argparse
import ast
import builtins
import re
import shutil
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


SKIP_DIR_NAMES = frozenset({
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".eggs",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "actions-runner",
})

DOC_ROOT_NAME = "python-modules"

SKIP_CALL_IDS = frozenset(name for name in dir(builtins) if name.isidentifier())

CALL_SITE_PATTERN = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")


@dataclass
class FuncInfo:
    name: str
    lineno: int
    end_lineno: int | None
    is_async: bool
    qualname: str
    args: list[str]
    arg_defaults_count: int
    decorators: list[str]
    doc_summary: str
    returns: str | None
    internal_calls: list[str] = field(default_factory=list)


def _safe_summary(doc: str | None, max_len: int = 280) -> str:
    if not doc:
        return ""
    line = doc.strip().splitlines()[0].strip() if doc.strip() else ""
    if len(line) > max_len:
        return line[: max_len - 3] + "..."
    return line


def _annotation_str(node: ast.expr | None) -> str | None:
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:
        return None


def _decorator_name(d: ast.expr) -> str:
    if isinstance(d, ast.Call):
        return _decorator_name(d.func)
    if isinstance(d, ast.Attribute):
        base = _decorator_name(d.value)
        return f"{base}.{d.attr}" if base else d.attr
    if isinstance(d, ast.Name):
        return d.id
    try:
        return ast.unparse(d)
    except Exception:
        return type(d).__name__


def _collect_calls(body: Iterable[ast.stmt]) -> list[str]:
    names: list[str] = []

    class Visitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
            func = node.func
            if isinstance(func, ast.Name):
                names.append(func.id)
            elif isinstance(func, ast.Attribute):
                names.append(func.attr)
            self.generic_visit(node)

    for stmt in body:
        Visitor().visit(stmt)
    # stable unique preserving order
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _parse_google_args_returns(doc: str | None) -> tuple[dict[str, str], str | None]:
    if not doc:
        return {}, None
    lines = doc.expandtabs().splitlines()
    section: str | None = None
    args: dict[str, str] = {}
    returns: list[str] = []
    current_arg: str | None = None
    buf: list[str] = []

    def flush_arg() -> None:
        nonlocal current_arg, buf
        if current_arg is not None:
            args[current_arg] = " ".join(buf).strip()
        current_arg = None
        buf = []

    header_re = re.compile(r"^\s*(Args|Arguments|Returns|Yields):\s*$", re.I)
    arg_line_re = re.compile(r"^\s{0,3}([a-zA-Z_][a-zA-Z0-9_]*)\s*(\(.*?\))?\s*:\s*(.*)$")

    for raw in lines:
        line = raw.rstrip()
        mhdr = header_re.match(line)
        if mhdr:
            flush_arg()
            section = mhdr.group(1).split(":")[0].strip().lower()
            if section.startswith("arg"):
                section = "args"
            elif section.startswith("return"):
                section = "returns"
            continue
        if section == "args":
            m = arg_line_re.match(line)
            if m:
                flush_arg()
                current_arg = m.group(1)
                rest = m.group(3) or ""
                buf = [rest] if rest else []
            elif current_arg is not None and line.strip():
                buf.append(line.strip())
            continue
        if section == "returns" and line.strip():
            returns.append(line.strip())
            continue

    flush_arg()
    ret = " ".join(returns).strip() or None
    return args, ret


def extract_functions(tree: ast.Module) -> list[FuncInfo]:
    """Collect module-level functions, class methods, and nested functions."""
    out: list[FuncInfo] = []

    def handle_fn(fn: ast.AsyncFunctionDef | ast.FunctionDef, qual: str) -> None:
        posonly = getattr(fn.args, "posonlyargs", []) or []
        args = [a.arg for a in posonly + fn.args.args]
        kwonly = [a.arg for a in fn.args.kwonlyargs]
        if fn.args.vararg:
            args.append("*" + fn.args.vararg.arg)
        args.extend(kwonly)
        if fn.args.kwarg:
            args.append("**" + fn.args.kwarg.arg)
        deco = [_decorator_name(d) for d in fn.decorator_list]
        doc = ast.get_docstring(fn)
        g_args, g_ret = _parse_google_args_returns(doc)
        summary = _safe_summary(doc)
        ret_ann = _annotation_str(fn.returns)
        returns = ret_ann or g_ret
        calls = _collect_calls(fn.body)
        fi = FuncInfo(
            name=fn.name,
            lineno=fn.lineno,
            end_lineno=getattr(fn, "end_lineno", None),
            is_async=isinstance(fn, ast.AsyncFunctionDef),
            qualname=qual,
            args=args,
            arg_defaults_count=len(fn.args.defaults) + len(fn.args.kw_defaults),
            decorators=deco,
            doc_summary=summary,
            returns=returns,
            internal_calls=calls,
        )
        setattr(fi, "_google_args", g_args)
        out.append(fi)
        walk_function_body(fn.body, qual)

    def walk_function_body(body: list[ast.stmt], parent_qual: str) -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                handle_fn(node, f"{parent_qual}.{node.name}")

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            handle_fn(node, node.name)
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    handle_fn(child, f"{node.name}.{child.name}")
    return out


def iter_py_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for p in root.rglob("*.py"):
        parts = set(p.parts)
        if parts & SKIP_DIR_NAMES:
            continue
        rel = p.relative_to(root)
        if rel.parts[0] == "docs" and len(rel.parts) > 1 and rel.parts[1] == DOC_ROOT_NAME:
            continue
        files.append(p)
    files.sort()
    return files


def build_call_index(repo_root: Path, py_files: list[Path], per_name_cap: int = 800) -> dict[str, list[tuple[str, int, str]]]:
    """Map identifier -> list of (relative posix path, lineno, line text) for call-site hints."""
    index: dict[str, list[tuple[str, int, str]]] = defaultdict(list)
    doc_prefix = f"docs/{DOC_ROOT_NAME}/"
    for path in py_files:
        rel = path.relative_to(repo_root).as_posix()
        if rel.startswith(doc_prefix):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("def ") or stripped.startswith("async def "):
                continue
            for m in CALL_SITE_PATTERN.finditer(line):
                name = m.group(1)
                if name in SKIP_CALL_IDS:
                    continue
                bucket = index[name]
                if len(bucket) >= per_name_cap:
                    continue
                bucket.append((rel, lineno, line.rstrip()))
    return index


def format_call_site(rel: str, lineno: int, line: str) -> str:
    return f"`{rel}:{lineno}` — `{line.strip()[:160]}`"


def summarize_imports(tree: ast.Module) -> str:
    imports: list[str] = []
    for node in tree.body[:120]:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            names = ", ".join(a.name for a in node.names)
            imports.append(f"from {mod} import {names}")
    if not imports:
        return "_（无 import 或仅类型守卫之后的位置）_"
    return "\n".join(f"- `{imp}`" for imp in imports[:80])


def extract_module_constants(tree: ast.Module, limit: int = 40) -> list[str]:
    consts: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id.isupper():
                    consts.append(t.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id.isupper():
                consts.append(node.target.id)
    return consts[:limit]


def md_escape(s: str) -> str:
    return s.replace("|", "\\|")


def write_module_doc(
    repo_root: Path,
    py_path: Path,
    out_path: Path,
    call_index: dict[str, list[tuple[str, int, str]]],
    caller_limit: int,
) -> None:
    src = py_path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(src, filename=str(py_path))
    except SyntaxError as e:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            f"# `{py_path.relative_to(repo_root)}`\n\n"
            f"_AST 解析失败（语法错误）：{e}_\n",
            encoding="utf-8",
        )
        return

    assert isinstance(tree, ast.Module)
    mod_doc = ast.get_docstring(tree)
    rel = py_path.relative_to(repo_root)
    funcs = extract_functions(tree)

    exclude_rel = py_path.relative_to(repo_root).as_posix()
    callers_map: dict[str, list[str]] = defaultdict(list)
    if funcs:
        for fname in {f.name for f in funcs}:
            formatted: list[str] = []
            for site_rel, lineno, content in call_index.get(fname, []):
                if site_rel == exclude_rel:
                    continue
                formatted.append(format_call_site(site_rel, lineno, content))
                if len(formatted) >= caller_limit:
                    break
            callers_map[fname] = formatted

    lines: list[str] = []
    lines.append(f"# `{rel}`\n")
    lines.append("## 模块概述\n")
    if mod_doc:
        lines.append(mod_doc.strip())
        lines.append("")
    else:
        lines.append("_（模块级 docstring 缺失）_")
        lines.append("")
    lines.append(f"- **源文件行数**: {src.count(chr(10)) + 1}")
    lines.append("")
    lines.append("## 静态分析口径\n")
    lines.append(
        "- **调用方（上游）**：预先扫描全仓库 `*.py`，按 `标识符(` 建索引（跳过内置名、跳过 `def` / `async def` 定义行）；"
        "不包含字符串反射、`getattr`、部分框架注册入口。"
    )
    lines.append(
        "- **函数体内调用（下游）**：由 AST 静态提取的直接调用（`foo()` 记 `foo`；`obj.bar()` 记 `bar`）。"
    )
    lines.append("")
    lines.append("## 调用方索引说明\n")
    lines.append(
        "- _不同类中的同名方法共享同一索引键（例如多个 `run`）；请以路径与行内容甄别。_"
    )
    lines.append(
        "- _高频内置调用已从索引剔除；单标识符最多保留有限条引用以免文档体积膨胀。_"
    )
    lines.append("")
    lines.append("## 导入依赖（摘要）\n")
    lines.append(summarize_imports(tree))
    lines.append("")
    consts = extract_module_constants(tree)
    if consts:
        lines.append("## 顶层常量 / 配置名（大写标识符抽样）\n")
        lines.append(", ".join(f"`{c}`" for c in consts))
        lines.append("")

    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    if classes:
        lines.append("## 类概览\n")
        for c in classes:
            doc = _safe_summary(ast.get_docstring(c))
            bases = []
            for b in c.bases:
                try:
                    bases.append(ast.unparse(b))
                except Exception:
                    bases.append(type(b).__name__)
            lines.append(f"- **`{c.name}`**（L{c.lineno}）" + (f" — {doc}" if doc else ""))
            if bases:
                lines.append(f"  - 基类: {', '.join(f'`{b}`' for b in bases)}")
        lines.append("")

    lines.append("## 函数与方法\n")

    if not funcs:
        lines.append("_（本文件未定义顶层函数或类方法）_")
    else:
        for fn in sorted(funcs, key=lambda x: (x.lineno, x.qualname)):
            async_pfx = "async " if fn.is_async else ""
            args_sig = ", ".join(fn.args)
            deco = ", ".join(f"`@{d}`" for d in fn.decorators) if fn.decorators else ""
            header = f"### `{async_pfx}{fn.qualname}({args_sig})`"
            lines.append(header)
            lines.append(f"- **定义位置**: L{fn.lineno}" + (f"–L{fn.end_lineno}" if fn.end_lineno else ""))
            if deco:
                lines.append(f"- **装饰器**: {deco}")
            summary = fn.doc_summary or "_（无 docstring 摘要）_"
            lines.append(f"- **功能说明**: {summary}")

            g_args: dict[str, str] = getattr(fn, "_google_args", {})
            lines.append("- **参数（上游 → 本函数）**:")
            if not fn.args:
                lines.append("  - _无显式参数_")
            else:
                for a in fn.args:
                    extra = g_args.get(a.lstrip("*"))
                    if extra:
                        lines.append(f"  - `{a}`: {md_escape(extra)}")
                    else:
                        lines.append(
                            f"  - `{a}`: 由调用方传入；参见仓库内「调用方提示」。"
                        )

            ret = fn.returns
            lines.append(
                f"- **返回值（本函数 → 下游）**: {md_escape(ret) if ret else '_（未标注返回值 / docstring Returns）_'}"
            )

            internal = [n for n in fn.internal_calls if not n.startswith("_")]
            internal_private = [n for n in fn.internal_calls if n.startswith("_")]
            if internal or internal_private:
                shown = internal[:35]
                note = ", ".join(f"`{x}`" for x in shown)
                lines.append(f"- **函数体内的直接调用（下游静态线索）**: {note}")
                if len(internal) > 35:
                    lines.append(f"  - _… 另有 {len(internal) - 35} 个公开符号调用未列出_")
                if internal_private:
                    priv = ", ".join(f"`{x}`" for x in internal_private[:20])
                    lines.append(f"  - **私有/内部样式调用**: {priv}")

            caller_lines = callers_map.get(fn.name, [])
            lines.append("- **调用方提示（上游静态检索，排除本文件 `def` 行）**:")
            if caller_lines:
                for cl in caller_lines[:caller_limit]:
                    lines.append(f"  - {cl}")
            else:
                lines.append(
                    "  - _未在其它 `.py` 中匹配到 `name(` 形式调用；可能仅为内部递归、回调表、路由注册或动态调用。_"
                )
            lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate docs/python-modules/*.md from AST + call index.")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Repository root (default: ../../ from this script).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help=f"Output root under root/docs/{DOC_ROOT_NAME} (default).",
    )
    parser.add_argument("--caller-limit", type=int, default=12, help="Max caller hints per function.")
    args = parser.parse_args()
    repo_root = args.root.resolve()
    out_root = (args.out or (repo_root / "docs" / DOC_ROOT_NAME)).resolve()
    default_docs = (repo_root / "docs" / DOC_ROOT_NAME).resolve()
    if out_root == default_docs and out_root.is_dir():
        shutil.rmtree(out_root)

    py_files = iter_py_files(repo_root)
    call_index = build_call_index(repo_root, py_files)
    for py_path in py_files:
        rel = py_path.relative_to(repo_root)
        out_path = out_root / rel.with_suffix(".md")
        write_module_doc(repo_root, py_path, out_path, call_index, caller_limit=args.caller_limit)

    print(f"Wrote {len(py_files)} markdown files under {out_root}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
