"""Prompt 模板管理路由：列表/详情/编辑/测试/恢复默认（全部通过 PromptManager）。"""
from __future__ import annotations

from typing import Any

import jinja2
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.services.prompt_manager import PromptManager

router = APIRouter(prefix="/api/workbench/prompt-templates", tags=["prompt-templates"])


class PromptTemplateUpdate(BaseModel):
    system_prompt: str | None = Field(default=None)
    user_prompt_template: str | None = Field(default=None)
    description: str | None = Field(default=None)
    is_enabled: bool | None = Field(default=None)
    updated_by: str | None = Field(default=None)


class PromptTemplateTest(BaseModel):
    variables: dict[str, str] = Field(default_factory=dict)


@router.get("")
def list_prompt_templates(
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> dict[str, object]:
    items = PromptManager.list_all(db)
    return {"items": items}


@router.get("/{template_id}")
def get_prompt_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> dict[str, object]:
    item = PromptManager.get_by_id(db, template_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模板不存在")
    return {"item": item}


@router.put("/{template_id}")
def update_prompt_template(
    template_id: int,
    payload: PromptTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> dict[str, object]:
    kwargs = {k: v for k, v in payload.model_dump().items() if v is not None}
    item = PromptManager.update(db, template_id, **kwargs)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模板不存在")
    return {"item": item}


@router.post("/{template_id}/test")
def test_prompt_template(
    template_id: int,
    payload: PromptTemplateTest,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> dict[str, object]:
    template = PromptManager.get_by_id(db, template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模板不存在")
    try:
        system, user = PromptManager.render(template, payload.variables)
    except jinja2.UndefinedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"模板变量缺失: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"渲染失败: {exc}") from exc
    return {"system_prompt": system, "user_prompt": user}


@router.post("/{template_id}/reset")
def reset_prompt_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> dict[str, object]:
    item = PromptManager.reset_to_default(db, template_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模板不存在或已是默认")
    return {"item": item}
