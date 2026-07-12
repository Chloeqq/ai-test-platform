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
    parse_status = ParseStatus.PARSED
    parse_error: str | None = None
    try:
        parsed_text = document_parser.parse_document(content, filename)
        if not parsed_text.strip():
            parse_status = ParseStatus.PARTIAL
            parse_error = "解析未提取到任何文本内容"
    except _PARSE_ERRORS as exc:
        _LOGGER.warning("requirement parse failed doc_id=%s: %s", doc.id, exc)
        parse_status = ParseStatus.FAILED
        parse_error = str(exc)

    repo.update_parse_result(doc.id, parse_status, parse_error)
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