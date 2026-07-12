"""Prompt 模板管理器：DB 优先，内置默认兜底。

架构：DB → 用户自定义覆盖(is_default=False) → 内置默认(代码常量)
惰性初始化：首次访问时种子内置模板到 DB(ensure_builtins)
"""
from __future__ import annotations

import logging

import jinja2
from jinja2 import meta as jinja2_meta
from sqlalchemy.orm import Session

from app.repositories.prompt_template_repository import PromptTemplateRepository

_LOGGER = logging.getLogger(__name__)

# 内置默认模板：code → {name, scene_type, system_prompt, user_prompt_template, variables, version}
_BUILTIN_TEMPLATES: dict[str, dict] = {
    "requirement_parse": {
        "name": "需求解析",
        "scene_type": "requirement_parse",
        "description": "从需求文本提取功能点、约束和验收条件",
        "system_prompt": "你是一个资深 QA 工程师。从给定的需求文本中提取测试意图。",
        "user_prompt_template": (
            "根据以下需求文本，提取所有功能点、边界条件、异常场景和安全约束:\n\n"
            "需求文本:\n{{ requirement }}\n\n"
            "页面: {{ page }}\n\n"
            "请以 JSON 数组格式返回，每项包含 intent_id/title/intent_type/priority/summary/steps/expected 字段。"
        ),
        "variables": {"requirement": {"required": True}, "page": {"required": False, "default": ""}},
        "version": 1,
    },
    "requirement_doc_to_test_points": {
        "name": "文档生成测试点",
        "scene_type": "requirement_parse",
        "description": "从结构化 Markdown 文档提取测试点",
        "system_prompt": "你是一个资深 QA 工程师。从给定的结构化需求文档中提取测试点。",
        "user_prompt_template": (
            "根据以下需求文档，提取所有测试点:\n\n"
            "{{ scoped_content }}\n\n"
            "页面: {{ page }}\n\n"
            "请以 JSON 数组格式返回，每项包含 intent_id/title/intent_type/priority/summary/steps/expected 字段。"
        ),
        "variables": {"scoped_content": {"required": True}, "page": {"required": False, "default": ""}},
        "version": 1,
    },
    "case_generation": {
        "name": "测试意图编译用例",
        "scene_type": "case_generation",
        "description": "从测试意图编译可执行用例步骤",
        "system_prompt": "你是一个自动化测试工程师。将测试意图编译为可执行的 DSL 步骤。",
        "user_prompt_template": (
            "将以下测试意图编译为可执行的测试用例:\n\n"
            "测试意图:\n{{ intent }}\n\n"
            "页面对象: {{ page_object }}\n\n"
            "请返回包含 steps/expected/priority 的 JSON 对象。"
        ),
        "variables": {"intent": {"required": True}, "page_object": {"required": False, "default": "{}"}},
        "version": 1,
    },
    "test_point_to_case": {
        "name": "测试点转用例",
        "scene_type": "case_generation",
        "description": "从测试点编译完整用例 YAML",
        "system_prompt": "你是一个测试用例编译器。将测试点转换为完整的可执行用例。",
        "user_prompt_template": (
            "将以下测试点转换为完整的可执行用例:\n\n"
            "测试点:\n{{ test_point }}\n\n"
            "请返回包含 case_id/steps/assertions/precondition 的 JSON 对象。"
        ),
        "variables": {"test_point": {"required": True}},
        "version": 1,
    },
    "failure_analysis": {
        "name": "失败原因分析",
        "scene_type": "failure_analysis",
        "description": "分析测试执行失败原因",
        "system_prompt": "你是一个测试故障分析专家。分析测试失败的可能原因。",
        "user_prompt_template": (
            "分析以下测试失败:\n\n"
            "用例: {{ case_title }}\n"
            "错误: {{ error_message }}\n"
            "日志: {{ logs }}\n\n"
            "请返回包含 root_cause/likely_fix/confidence 的 JSON 对象。"
        ),
        "variables": {"case_title": {"required": True}, "error_message": {"required": True}, "logs": {"required": False, "default": ""}},
        "version": 1,
    },
}


class PromptManager:
    """Prompt 模板管理器。DB 优先,内置默认兜底。"""

    @classmethod
    def get_template(cls, db: Session, code: str) -> dict | None:
        """DB 优先:查用户自定义(is_default=False, is_enabled=True) → 内置默认兜底。"""
        repo = PromptTemplateRepository(db)
        custom = repo.get_enabled_custom(code)
        if custom is not None:
            return _to_template_dict(custom)
        return _BUILTIN_TEMPLATES.get(code)

    @classmethod
    def render(cls, template: dict, context: dict) -> tuple[str, str]:
        """渲染 system_prompt + user_prompt_template → (system, user)。"""
        env = jinja2.Environment(undefined=jinja2.StrictUndefined)
        system = str(template.get("system_prompt", ""))
        user_tpl = env.from_string(str(template.get("user_prompt_template", "")))
        return system, user_tpl.render(**context)

    @classmethod
    def extract_variables(cls, template_text: str) -> list[str]:
        """从 Jinja2 模板文本提取变量名。"""
        env = jinja2.Environment()
        ast = env.parse(template_text)
        return sorted(jinja2_meta.find_undeclared_variables(ast))

    @classmethod
    def ensure_builtins(cls, db: Session):
        """惰性种子：确保所有内置模板已在 DB 中(is_default=True)。如 code 已存在但 version 更高,则升级。"""
        repo = PromptTemplateRepository(db)
        for code, data in _BUILTIN_TEMPLATES.items():
            repo.create_or_update_builtin(code=code, **data)
        db.commit()


def _to_template_dict(tmpl) -> dict:
    return {
        "id": tmpl.id,
        "code": tmpl.code,
        "name": tmpl.name,
        "scene_type": tmpl.scene_type,
        "system_prompt": tmpl.system_prompt,
        "user_prompt_template": tmpl.user_prompt_template,
        "variables": tmpl.variables,
        "is_default": tmpl.is_default,
        "is_enabled": tmpl.is_enabled,
        "version": tmpl.version,
        "created_by": tmpl.created_by,
        "updated_by": tmpl.updated_by,
        "created_at": tmpl.created_at.isoformat() if tmpl.created_at else None,
        "updated_at": tmpl.updated_at.isoformat() if tmpl.updated_at else None,
    }
