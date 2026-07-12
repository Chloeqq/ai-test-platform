"""Prompt 模板管理路由：列表/详情/编辑/测试/恢复默认。"""
from __future__ import annotations

from typing import Any

import jinja2
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.repositories.prompt_template_repository import PromptTemplateRepository
from app.services.prompt_manager import _to_template_dict, PromptManager

router = APIRouter(prefix="/api/workbench/prompt-templates", tags=["prompt-templates"])


class PromptTemplateUpdate(BaseModel):
    system_prompt: str | None = Field(default=None)
    user_prompt_template: str | None = Field(default=None)
    is_enabled: bool | None = Field(default=None)
    updated_by: str | None = Field(default=None)


class PromptTemplateTest(BaseModel):
    variables: dict[str, str] = Field(default_factory=dict)


@router.get("")
def list_prompt_templates(
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> dict[str, object]:
    PromptManager.ensure_builtins(db)
    repo = PromptTemplateRepository(db)
    items = [_to_template_dict(t) for t in repo.list_all()]
    return {"items": items}


@router.get("/{template_id}")
def get_prompt_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> dict[str, object]:
    repo = PromptTemplateRepository(db)
    tmpl = repo.get_by_id(template_id)
    if tmpl is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模板不存在")
    return {"item": _to_template_dict(tmpl)}


@router.put("/{template_id}")
def update_prompt_template(
    template_id: int,
    payload: PromptTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> dict[str, object]:
    repo = PromptTemplateRepository(db)
    kwargs = {k: v for k, v in payload.model_dump().items() if v is not None}
    tmpl = repo.update(template_id, **kwargs)
    if tmpl is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模板不存在")
    db.commit()
    return {"item": _to_template_dict(tmpl)}


@router.post("/{template_id}/test")
def test_prompt_template(
    template_id: int,
    payload: PromptTemplateTest,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> dict[str, object]:
    repo = PromptTemplateRepository(db)
    tmpl = repo.get_by_id(template_id)
    if tmpl is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模板不存在")
    template_dict = _to_template_dict(tmpl)
    try:
        system, user = PromptManager.render(template_dict, payload.variables)
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
    repo = PromptTemplateRepository(db)
    repo.reset_to_default(template_id)
    db.commit()
    # 重新种子该模板
    tmpl = repo.get_by_id(template_id)
    code = tmpl.code if tmpl else ""
    PromptManager.ensure_builtins(db)
    new_tmpl = repo.get_by_code(code) if code else None
    if new_tmpl is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="恢复默认失败")
    return {"item": _to_template_dict(new_tmpl)}
