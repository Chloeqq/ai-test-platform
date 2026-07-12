"""需求文档上传解析路由：POST /api/workbench/requirement-documents/upload。

校验（扩展名白名单 / 大小上限）参数化自 settings，不硬编码；编排委托 Service。
"""
from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.services import requirement_document_service

router = APIRouter(prefix="/api/workbench/requirement-documents", tags=["requirement-documents"])


def _allowed_exts(settings: Settings) -> set[str]:
    """解析逗号分隔的扩展名白名单（.docx,.pdf,.md）为规范化集合。"""
    return {
        item.strip().lower()
        for item in (settings.requirement_upload_allowed_exts or "").split(",")
        if item.strip()
    }


@router.post("/upload")
async def upload_requirement_document(
    project_code: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: Any = Depends(get_current_user),
) -> dict[str, object]:
    project_code = (project_code or "").strip()
    if not project_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="project_code 不能为空")

    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()
    allowed = _allowed_exts(settings)
    if ext not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文档格式: {ext or '(无扩展名)'}，仅允许 {sorted(allowed)}",
        )

    max_bytes = settings.requirement_upload_max_bytes
    if file.size is not None and file.size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"文件超过大小上限 {max_bytes} 字节",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件内容为空")
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"文件超过大小上限 {max_bytes} 字节",
        )

    try:
        result = requirement_document_service.upload_and_parse(
            db,
            project_code=project_code,
            filename=filename,
            content=content,
            content_type=file.content_type or "",
            username=getattr(current_user, "username", None),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    return {"item": result}


@router.get("")
def list_requirement_documents(
    project_code: str = Query(...),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> dict[str, object]:
    if not (project_code or "").strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="project_code 不能为空")
    items = requirement_document_service.list_documents(
        db, project_code=project_code.strip(), status_filter=status,
    )
    return {"items": items}


@router.get("/{doc_id}")
def get_requirement_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return {"item": requirement_document_service.get_document_detail(db, doc_id=doc_id)}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{doc_id}/download")
def download_requirement_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    try:
        data, filename, content_type = requirement_document_service.download_document(db, doc_id=doc_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return Response(
        content=data,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )