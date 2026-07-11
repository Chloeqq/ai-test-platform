"""需求文档解析：docx / pdf / md → 结构化 Markdown（纯逻辑，无 DB/IO 依赖）。

设计要点：
- docx 用 stdlib zipfile + ElementTree 解析 word/document.xml（零重依赖），
  标题层级优先 w:outlineLvl，fallback 到 w:pStyle 的 basedOn 样式继承链
  （参考 BrickCore document_structure.py，但补齐 outlineLvl 更可靠来源）。
- pdf 用 PyMuPDF(fitz) 逐页 get_text()。注意：fitz 按 PDF 内部流顺序输出，
  不保证多栏视觉阅读顺序（PRD 多为单栏，风险低）。
- 每个顶层 block 独立捕获具体异常，单段失败不阻断其余内容。
"""
from __future__ import annotations

import io
import logging
import os
import re
import zipfile
from typing import Any
from xml.etree import ElementTree as ET

_LOGGER = logging.getLogger(__name__)

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_W = f"{{{_W_NS}}}"

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
# 从样式名/ID 中解析标题层级：Heading 1 / 标题 1 等
_STYLE_HEADING_RE = re.compile(r"(?:heading|标题)\s*(\d+)", re.IGNORECASE)

_SUPPORTED_EXTS = {".docx", ".pdf", ".md", ".markdown", ".txt"}


def parse_document(content: bytes, filename: str) -> str:
    """按扩展名分发解析，返回结构化 Markdown。

    不支持的扩展名抛 ValueError；.doc(旧版二进制) 明确不支持。
    """
    ext = os.path.splitext(filename or "")[1].lower()
    if ext == ".docx":
        blocks = _parse_docx_to_blocks(content)
    elif ext == ".pdf":
        blocks = _parse_pdf_to_blocks(content)
    elif ext in (".md", ".markdown", ".txt"):
        blocks = _parse_md_to_blocks(content)
    elif ext == ".doc":
        raise ValueError("暂不支持旧版 .doc，请另存为 .docx 后上传")
    else:
        raise ValueError(f"不支持的文档格式: {ext or '(无扩展名)'}")
    return _blocks_to_markdown(blocks)


# ---------------------------------------------------------------------------
# docx
# ---------------------------------------------------------------------------
def _parse_docx_style_index(zf: zipfile.ZipFile) -> dict[str, dict[str, str]]:
    """解析 word/styles.xml → {styleId: {name, basedOn}}，供标题层级 fallback。"""
    index: dict[str, dict[str, str]] = {}
    if "word/styles.xml" not in zf.namelist():
        return index
    try:
        styles_root = ET.fromstring(zf.read("word/styles.xml"))
    except (ET.ParseError, KeyError) as exc:
        _LOGGER.debug("document_parser: styles.xml 解析失败: %s", exc)
        return index
    for style in styles_root.findall(f"{_W}style"):
        style_id = style.get(f"{_W}styleId")
        if not style_id:
            continue
        name_el = style.find(f"{_W}name")
        based_el = style.find(f"{_W}basedOn")
        index[style_id] = {
            "name": (name_el.get(f"{_W}val", "") if name_el is not None else "").strip(),
            "basedOn": (based_el.get(f"{_W}val", "") if based_el is not None else "").strip(),
        }
    return index


def _heading_level_from_label(label: str) -> int:
    """从样式名/ID 文本解析标题层级号；非标题返回 0。"""
    match = _STYLE_HEADING_RE.search(label or "")
    if match:
        try:
            return max(1, min(6, int(match.group(1))))
        except ValueError:
            return 0
    if label and ("标题" in label or label.lower().startswith("heading")):
        return 1
    return 0


def _heading_level_from_style(style_id: str, style_index: dict[str, dict[str, str]]) -> int:
    """沿 basedOn 链查找样式对应的标题层级；防环，命中即返回。"""
    if not style_id:
        return 0
    visited: set[str] = set()
    current = style_id.strip()
    while current and current not in visited:
        visited.add(current)
        info = style_index.get(current) or {}
        level = _heading_level_from_label(info.get("name", "") or current)
        if level:
            return level
        current = (info.get("basedOn") or "").strip()
    return _heading_level_from_label(style_id)


def _paragraph_heading_level(paragraph: ET.Element, style_index: dict[str, dict[str, str]]) -> int:
    """标题层级：优先 w:outlineLvl（0=一级，+1），fallback w:pStyle 样式链。"""
    p_pr = paragraph.find(f"{_W}pPr")
    if p_pr is None:
        return 0
    outline = p_pr.find(f"{_W}outlineLvl")
    if outline is not None:
        raw = outline.get(f"{_W}val")
        if raw is not None:
            try:
                return max(1, min(6, int(raw) + 1))
            except ValueError:
                pass
    p_style = p_pr.find(f"{_W}pStyle")
    if p_style is not None:
        return _heading_level_from_style(p_style.get(f"{_W}val", "") or "", style_index)
    return 0


def _paragraph_text(paragraph: ET.Element) -> str:
    return "".join(node.text or "" for node in paragraph.iter(f"{_W}t")).strip()


def _table_to_block(table: ET.Element) -> dict[str, Any] | None:
    """把 w:tbl 抽成 rows（每行 cell 文本列表）；空表返回 None。"""
    rows: list[list[str]] = []
    for row in table.findall(f".//{_W}tr"):
        cells: list[str] = []
        for cell in row.findall(f".//{_W}tc"):
            text = "".join(node.text or "" for node in cell.iter(f"{_W}t")).strip().replace("\n", " ")
            cells.append(text)
        if any(cells):
            rows.append(cells)
    if not rows:
        return None
    return {"type": "table", "rows": rows}


def _parse_docx_to_blocks(content: bytes) -> list[dict[str, Any]]:
    """解析 docx 为有序 blocks；每个顶层节点独立 try，单节点失败不阻断。"""
    blocks: list[dict[str, Any]] = []
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            style_index = _parse_docx_style_index(zf)
            if "word/document.xml" not in zf.namelist():
                raise ValueError("docx 缺少 word/document.xml")
            doc_root = ET.fromstring(zf.read("word/document.xml"))
            body = doc_root.find(f"{_W}body")
            if body is None:
                raise ValueError("docx 缺少 body")
            for child in body:
                try:
                    if child.tag == f"{_W}p":
                        text = _paragraph_text(child)
                        if not text:
                            continue
                        level = _paragraph_heading_level(child, style_index)
                        if level:
                            blocks.append({"type": "heading", "level": level, "text": text})
                        else:
                            blocks.append({"type": "paragraph", "text": text})
                    elif child.tag == f"{_W}tbl":
                        table_block = _table_to_block(child)
                        if table_block:
                            blocks.append(table_block)
                except (ET.ParseError, ValueError, AttributeError) as exc:
                    _LOGGER.warning("document_parser: 跳过无法解析的 docx 节点: %s", exc)
                    continue
    except zipfile.BadZipFile as exc:
        raise ValueError(f"docx 文件损坏或格式非法: {exc}") from exc
    except ET.ParseError as exc:
        raise ValueError(f"docx XML 解析失败: {exc}") from exc
    return blocks


# ---------------------------------------------------------------------------
# pdf
# ---------------------------------------------------------------------------
def _parse_pdf_to_blocks(content: bytes) -> list[dict[str, Any]]:
    """PyMuPDF 逐页抽文本为 paragraph blocks（每页一段，按内部流顺序）。"""
    import fitz  # 延迟导入：仅上传 pdf 时才需要该重依赖

    blocks: list[dict[str, Any]] = []
    try:
        doc = fitz.open(stream=content, filetype="pdf")
    except (fitz.FileDataError, ValueError, RuntimeError) as exc:
        raise ValueError(f"pdf 文件损坏或无法读取: {exc}") from exc
    try:
        for page_index in range(doc.page_count):
            try:
                page_text = doc[page_index].get_text().strip()
            except (RuntimeError, ValueError) as exc:
                _LOGGER.warning("document_parser: 跳过 pdf 第 %d 页: %s", page_index + 1, exc)
                continue
            if page_text:
                blocks.append({"type": "paragraph", "text": page_text})
    finally:
        doc.close()
    return blocks


# ---------------------------------------------------------------------------
# md / txt
# ---------------------------------------------------------------------------
def _parse_md_to_blocks(content: bytes) -> list[dict[str, Any]]:
    """按行解析 Markdown/纯文本：ATX 标题行 → heading，其余非空行 → paragraph。"""
    text = content.decode("utf-8", errors="replace")
    blocks: list[dict[str, Any]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = _HEADING_RE.match(line)
        if match:
            blocks.append({"type": "heading", "level": len(match.group(1)), "text": match.group(2).strip()})
        else:
            blocks.append({"type": "paragraph", "text": line})
    return blocks


# ---------------------------------------------------------------------------
# blocks → Markdown
# ---------------------------------------------------------------------------
def _table_block_to_markdown(rows: list[list[str]]) -> str:
    """rows → GFM 表格；首行作表头，补分隔行 | --- | --- |，按最宽行对齐列数。"""
    col_count = max(len(row) for row in rows)
    normalized = [row + [""] * (col_count - len(row)) for row in rows]

    def _fmt(cells: list[str]) -> str:
        return "| " + " | ".join(cell.replace("|", "\\|") for cell in cells) + " |"

    lines = [_fmt(normalized[0]), "| " + " | ".join(["---"] * col_count) + " |"]
    lines.extend(_fmt(row) for row in normalized[1:])
    return "\n".join(lines)


def _blocks_to_markdown(blocks: list[dict[str, Any]]) -> str:
    """有序 blocks → 规范 Markdown（标题 #、GFM 表格、段落空行分隔）。"""
    parts: list[str] = []
    for block in blocks:
        btype = block.get("type")
        if btype == "heading":
            level = max(1, min(6, int(block.get("level") or 1)))
            text = str(block.get("text") or "").strip()
            if text:
                parts.append(f"{'#' * level} {text}")
        elif btype == "table":
            rows = block.get("rows") or []
            if rows:
                parts.append(_table_block_to_markdown(rows))
        else:  # paragraph / 其他
            text = str(block.get("text") or "").strip()
            if text:
                parts.append(text)
    return "\n\n".join(parts).strip()
