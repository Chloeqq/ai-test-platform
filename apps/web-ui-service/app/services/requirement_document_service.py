"""需求文档上传解析编排 Service（不直接访问 DB，DB 操作全部委托 Repository）。

编排链路：MinIO 存档 → 落库(pending) → 解析 → 回写 parse_status。
存储失败向上抛 RuntimeError（Router 映射 503）；解析失败降级为 failed/partial
状态（原始文件已存档，可后续重试），不丢失上传。
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.constants.requirement_document import ParseStatus
from app.core.minio_client import StorageError, download_bytes, get_minio_client, upload_bytes
from app.repositories.requirement_document_repository import RequirementDocumentRepository
from app.services import document_parser

_LOGGER = logging.getLogger(__name__)

# 扩展名 → 规范 MIME 类型（浏览器上报的 content_type 不可靠，以此为准）。
_EXT_CONTENT_TYPE: dict[str, str] = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pdf": "application/pdf",
    ".md": "text/markdown",
}
_DEFAULT_CONTENT_TYPE = "application/octet-stream"
# 文件名净化：非 [\w.-] 一律替换为下划线，避免 object_key 注入/路径穿越。
_UNSAFE_FILENAME_RE = re.compile(r"[^\w.-]")

# 解析阶段可预期的失败类型（编排降级，不使用裸 except）。
_PARSE_ERRORS = (ValueError, RuntimeError, ImportError, OSError)


def _parse_blocks(content: bytes, filename: str) -> list[dict[str, Any]] | None:
    """按扩展名分发到块级解析器，返回 blocks 列表。解析失败返回 None。"""
    ext = os.path.splitext(filename or "")[1].lower()
    try:
        if ext == ".docx":
            return document_parser._parse_docx_to_blocks(content)
        elif ext == ".pdf":
            return document_parser._parse_pdf_to_blocks(content)
        elif ext in (".md", ".markdown", ".txt"):
            return document_parser._parse_md_to_blocks(content)
    except _PARSE_ERRORS:
        pass
    return None


def _ext_of(filename: str) -> str:
    return os.path.splitext(filename or "")[1].lower()


def _sanitize_filename(filename: str) -> str:
    cleaned = _UNSAFE_FILENAME_RE.sub("_", filename or "").strip("._")
    return cleaned or "document"


def _build_object_key(project_code: str, filename: str, *, now: datetime) -> str:
    """{project_code}/{YYYYMMDD}_{HHMMSS}_{净化后文件名}。"""
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    return f"{project_code}/{timestamp}_{_sanitize_filename(filename)}"


def upload_and_parse(
    db: Session,
    *,
    project_code: str,
    filename: str,
    content: bytes,
    content_type: str,
    username: str | None,
) -> dict[str, Any]:
    """上传原始文件到 MinIO 并解析，返回记录信息。

    返回 shape: {
        document_id: int, parsed_text: str, parse_status: str,
        object_key: str, filename: str, source_type: str,
    }
    """
    client = get_minio_client()
    if client is None:
        raise RuntimeError("MinIO 未启用")

    ext = _ext_of(filename)
    source_type = ext.lstrip(".")
    resolved_content_type = _EXT_CONTENT_TYPE.get(ext) or content_type or _DEFAULT_CONTENT_TYPE
    object_key = _build_object_key(project_code, filename, now=datetime.now())

    try:
        upload_bytes(client, object_key, content, resolved_content_type)
    except StorageError as exc:
        _LOGGER.warning("requirement upload storage failed: %s", exc)
        raise RuntimeError("存储不可用") from exc

    repo = RequirementDocumentRepository(db)
    doc = repo.create(
        project_code=project_code,
        filename=filename,
        source_type=source_type,
        object_key=object_key,
        file_size=len(content),
        parse_status=ParseStatus.PENDING,
        created_by=username,
    )

    parsed_text = ""
    parsed_blocks: list[dict[str, Any]] | None = None
    parse_status = ParseStatus.PARSED
    parse_error: str | None = None
    try:
        parsed_text = document_parser.parse_document(content, filename)
        parsed_blocks = _parse_blocks(content, filename)
        if not parsed_text.strip():
            parse_status = ParseStatus.PARTIAL
            parse_error = "解析未提取到任何文本内容"
    except _PARSE_ERRORS as exc:
        _LOGGER.warning("requirement parse failed doc_id=%s: %s", doc.id, exc)
        parse_status = ParseStatus.FAILED
        parse_error = str(exc)

    repo.update_parse_result(doc.id, parse_status, parse_error)
    # persist parsed_blocks for chapter selection
    if parsed_blocks is not None:
        from app.repositories.requirement_document_repository import RequirementDocumentRepository as _R
        _R(db).get_by_id(doc.id)
        doc.parsed_blocks = {"blocks": parsed_blocks, "source_type": source_type}
        db.flush()
    document_id = doc.id
    # get_db() 不自动 commit（仅 close），写路径须显式提交，否则行只 flush 不落库。
    db.commit()

    return {
        "document_id": document_id,
        "parsed_text": parsed_text,
        "parse_status": parse_status,
        "object_key": object_key,
        "filename": filename,
        "source_type": source_type,
    }


def list_documents(
    db: Session,
    *,
    project_code: str,
    status_filter: str | None = None,
    keyword: str | None = None,
) -> list[dict[str, Any]]:
    """返回指定项目下的文档列表,支持状态筛选和关键字搜索(前端过滤,数据量小)。"""
    repo = RequirementDocumentRepository(db)
    rows = repo.list_by_project(project_code)
    results: list[dict[str, Any]] = []
    for doc in rows:
        if status_filter and status_filter != "all" and doc.parse_status != status_filter:
            continue
        if keyword and keyword.lower() not in (doc.filename or "").lower():
            continue
        results.append({
            "id": doc.id,
            "filename": doc.filename,
            "source_type": doc.source_type,
            "object_key": doc.object_key,
            "file_size": doc.file_size,
            "parse_status": doc.parse_status,
            "parse_error": doc.parse_error,
            "created_by": doc.created_by,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
        })
    return results


def get_document_detail(db: Session, *, doc_id: int) -> dict[str, Any]:
    """返回单个文档详情,含解析文本前 500 字符预览。"""
    repo = RequirementDocumentRepository(db)
    doc = repo.get_by_id(doc_id)
    if doc is None:
        raise ValueError(f"文档不存在: id={doc_id}")
    # 从 MinIO 下载源文件获取 parsed_text 预览
    parsed_preview = ""
    try:
        client = get_minio_client()
        if client and doc.object_key:
            raw = download_bytes(client, doc.object_key)
            text = raw.decode("utf-8", errors="replace")
            parsed_preview = text[:500]
    except StorageError:
        parsed_preview = ""
    return {
        "id": doc.id,
        "filename": doc.filename,
        "source_type": doc.source_type,
        "object_key": doc.object_key,
        "file_size": doc.file_size,
        "parse_status": doc.parse_status,
        "parse_error": doc.parse_error,
        "is_deleted": doc.is_deleted,
        "created_by": doc.created_by,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "deleted_at": doc.deleted_at.isoformat() if doc.deleted_at else None,
        "parsed_preview": parsed_preview,
    }


def download_document(db: Session, *, doc_id: int) -> tuple[bytes, str, str]:
    """返回 (file_bytes, filename, content_type)。MinIO 不可用时 raise RuntimeError。"""
    repo = RequirementDocumentRepository(db)
    doc = repo.get_by_id(doc_id)
    if doc is None:
        raise ValueError(f"文档不存在: id={doc_id}")
    if not doc.object_key:
        raise ValueError(f"文档存储对象不存在: id={doc_id}")
    client = get_minio_client()
    if client is None:
        raise RuntimeError("MinIO 未启用")
    try:
        raw = download_bytes(client, doc.object_key)
    except StorageError as exc:
        raise RuntimeError("文件下载失败") from exc
    ext_map = {".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
               ".pdf": "application/pdf", ".md": "text/markdown"}
    content_type = ext_map.get(f".{doc.source_type}", "application/octet-stream")
    return raw, doc.filename, content_type


# ---------------------------------------------------------------------------
# 章节选择 support
# ---------------------------------------------------------------------------

def blocks_to_sections(blocks: list[dict[str, Any]], source_type: str) -> list[dict[str, Any]]:
    """将解析 blocks 转为章节树。借鉴 BrickCore requirement_document.py:blocks_to_sections。"""
    if not blocks:
        return []
    # pdf 按页面分节
    if source_type == "pdf":
        return _sections_from_pdf(blocks)
    return _sections_from_headings(blocks)


def _sections_from_pdf(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for i, b in enumerate(blocks):
        sections.append({
            "id": f"page-{i + 1}",
            "title": f"第 {i + 1} 页",
            "level": 1,
            "block_ids": [b.get("id", f"b{i}")],
            "char_count": len(str(b.get("text", ""))),
            "children": [],
        })
    return sections


def _sections_from_headings(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # 给每个 block 分配 id
    indexed: list[dict[str, Any]] = []
    for i, b in enumerate(blocks):
        indexed.append({**b, "_idx": i, "_id": f"b{i}"})

    # 找第一个标题的层级作为文档根级
    first_heading_level = None
    for b in indexed:
        if b.get("type") == "heading":
            first_heading_level = b["level"]
            break

    if first_heading_level is None:
        # 无标题 → 全文作为一个 section
        total_chars = sum(len(str(b.get("text", ""))) for b in indexed)
        return [{
            "id": "sec-full",
            "title": "全文",
            "level": 1,
            "block_ids": [b["_id"] for b in indexed],
            "char_count": total_chars,
            "children": [],
        }]

    # 构建 section 树
    sections: list[dict[str, Any]] = []
    stack: list[dict[str, Any]] = []  # 按 (level, section) 入栈
    current_section: dict[str, Any] | None = None

    for b in indexed:
        if b.get("type") == "heading" and b["level"] >= first_heading_level:
            sec = {
                "id": f"sec-{len(sections) + 1}",
                "title": str(b.get("text", "")).strip(),
                "level": b["level"],
                "block_ids": [b["_id"]],
                "char_count": len(str(b.get("text", ""))),
                "children": [],
            }
            # 找父节点: 栈中 level < 当前 level 的最大者
            while stack and stack[-1]["level"] >= b["level"]:
                stack.pop()
            if stack:
                stack[-1]["children"].append(sec)
            else:
                sections.append(sec)
            stack.append(sec)
            current_section = sec
        elif current_section is not None and b.get("type") in ("paragraph", "table"):
            current_section["block_ids"].append(b["_id"])
            text = str(b.get("text", ""))
            if b.get("type") == "table" and b.get("rows"):
                text = "\n".join(" | ".join(r) for r in b["rows"])
            current_section["char_count"] += len(text)

    # 如果最终没有构建出任何 section（只有 paragraph，没有 heading），退回全文模式
    if not sections and indexed:
        total_chars = sum(len(str(b.get("text", ""))) for b in indexed)
        return [{
            "id": "sec-full",
            "title": "全文",
            "level": 1,
            "block_ids": [b["_id"] for b in indexed],
            "char_count": total_chars,
            "children": [],
        }]
    return sections


def get_document_sections(db: Session, *, doc_id: int) -> list[dict[str, Any]]:
    """返回文档的章节树。"""
    repo = RequirementDocumentRepository(db)
    doc = repo.get_by_id(doc_id)
    if doc is None:
        raise ValueError(f"文档不存在: id={doc_id}")
    blocks_data = doc.parsed_blocks
    if not blocks_data or not isinstance(blocks_data, dict):
        return []
    blocks = blocks_data.get("blocks")
    if not isinstance(blocks, list) or len(blocks) == 0:
        return []
    source_type = str(blocks_data.get("source_type", doc.source_type or ""))
    return blocks_to_sections(list(blocks), source_type)


def build_scoped_content(db: Session, *, doc_id: int, section_ids: list[str]) -> dict[str, Any]:
    """根据勾选的 section_ids 组装范围文本,返回 {scoped_text, char_count, estimated_tokens, level}。"""
    sections = get_document_sections(db, doc_id=doc_id)
    if not sections or not section_ids:
        return {"scoped_text": "", "char_count": 0, "estimated_tokens": 0, "level": "ok"}

    # flatten all sections reachable from selected ids
    selected_ids = set(section_ids)
    all_sections: list[dict[str, Any]] = []

    def collect(secs: list[dict[str, Any]]):
        for s in secs:
            if s["id"] in selected_ids:
                all_sections.append(s)
            collect(s.get("children", []))

    collect(sections)

    # build text from blocks of selected sections
    repo = RequirementDocumentRepository(db)
    doc = repo.get_by_id(doc_id)
    if doc is None or not doc.parsed_blocks:
        return {"scoped_text": "", "char_count": 0, "estimated_tokens": 0, "level": "ok"}

    blocks_data = doc.parsed_blocks
    raw_blocks: list[dict[str, Any]] = list(blocks_data.get("blocks", []))
    all_selected_block_ids: set[str] = set()
    for sec in all_sections:
        for bid in sec.get("block_ids", []):
            all_selected_block_ids.add(bid)

    parts: list[str] = []
    for i, b in enumerate(raw_blocks):
        bid = b.get("_id", f"b{i}")
        if bid not in all_selected_block_ids:
            continue
        if b.get("type") == "heading":
            parts.append(f"{'#' * b.get('level', 1)} {b.get('text', '')}")
        elif b.get("type") == "table" and b.get("rows"):
            rows = b["rows"]
            parts.append("| " + " | ".join(rows[0]) + " |")
            parts.append("| " + " | ".join(["---"] * len(rows[0])) + " |")
            for row in rows[1:]:
                parts.append("| " + " | ".join(row) + " |")
        else:
            parts.append(str(b.get("text", "")))

    scoped_text = "\n\n".join(parts)
    char_count = len(scoped_text)
    # token estimate: CJK ~1.6 chars/token, others ~4
    cjk = sum(1 for c in scoped_text if "一" <= c <= "鿿")
    other = char_count - cjk
    estimated_tokens = int(round(cjk / 1.6 + other / 4.0))
    level = "ok"
    if estimated_tokens >= 16000:
        level = "block"
    elif estimated_tokens >= 8000:
        level = "warn"

    return {
        "scoped_text": scoped_text,
        "char_count": char_count,
        "estimated_tokens": estimated_tokens,
        "level": level,
    }