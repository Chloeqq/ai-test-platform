from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.security import decode_access_token

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

PLATFORM_NAME = "企业AI测试平台"
DEFAULT_USER_NAME = "访客"
DEFAULT_USER_INITIAL = "访"


def _initial_for_name(name: str) -> str:
    value = str(name or "").strip()
    if not value:
        return DEFAULT_USER_INITIAL
    return value[:1].upper()


def _resolve_request_user(request: Request) -> dict[str, str]:
    auth_header = str(request.headers.get("authorization", "")).strip()
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        if token:
            try:
                payload = decode_access_token(token)
                username = str(payload.get("username", "")).strip()
                if username:
                    return {
                        "user_name": username,
                        "user_initial": _initial_for_name(username),
                    }
            except HTTPException:
                pass

    for header_name in ("x-user-name", "x-forwarded-user"):
        username = str(request.headers.get(header_name, "")).strip()
        if username:
            return {
                "user_name": username,
                "user_initial": _initial_for_name(username),
            }

    return {
        "user_name": DEFAULT_USER_NAME,
        "user_initial": DEFAULT_USER_INITIAL,
    }


def _navigation(current_key: str) -> list[dict[str, Any]]:
    nav_items: list[dict[str, Any]] = [
        {"key": "dashboard", "label": "仪表盘", "icon": "dashboard", "href": "/dashboard"},
        {
            "key": "case_center",
            "label": "用例中心",
            "icon": "assets",
            "children": [
                {"key": "cases", "label": "用例列表", "href": "/cases"},
                {"key": "case_reviews", "label": "待审核用例", "href": "/cases/review"},
                {"key": "case_versions", "label": "用例版本", "href": "/cases/versions"},
                {"key": "tag_management", "label": "标签管理", "href": "/cases/tags"},
            ],
        },
        {
            "key": "ai_generation",
            "label": "AI生成",
            "icon": "ai_orchestration",
            "children": [
                {"key": "workbench_generate", "label": "生成用例", "href": "/ai-generation"},
                {"key": "workbench_history", "label": "生成历史", "href": "/ai-generation/history"},
                {"key": "prompt_management", "label": "Prompt 管理", "href": "/ai-generation/prompts"},
            ],
        },
        {
            "key": "execution_center",
            "label": "执行中心",
            "icon": "execution_records",
            "children": [
                {"key": "execution_plans", "label": "测试计划", "href": "/execution/plans"},
                {"key": "execution_records", "label": "执行任务", "href": "/execution/runs"},
                {"key": "report_overview", "label": "执行结果", "href": "/execution/results"},
                {"key": "workbench", "label": "调试工作台", "href": "/execution/workbench"},
            ],
        },
        {
            "key": "quality_analysis",
            "label": "质量分析",
            "icon": "quality_analysis",
            "children": [
                {"key": "flaky", "label": "Flaky分析", "href": "/quality/flaky"},
                {"key": "failure_clusters", "label": "失败聚类", "href": "/quality/failure-clusters"},
                {"key": "trend_analysis", "label": "趋势分析", "href": "/quality/trends"},
                {"key": "defects", "label": "缺陷管理", "href": "/defects"},
                {"key": "gate_config", "label": "质量门禁", "href": "/quality/gates"},
            ],
        },
        {
            "key": "asset_config",
            "label": "资产与配置",
            "icon": "assets",
            "children": [
                {"key": "page_objects", "label": "页面对象", "href": "/assets/page-objects"},
                {"key": "page_objects_recorder", "label": "页面录制", "href": "/assets/page-objects/recorder"},
                {"key": "api_contracts", "label": "API契约", "href": "/assets/api-contracts"},
                {"key": "test_point_assets", "label": "测试点资产", "href": "/assets/test-points"},
                {"key": "data_templates", "label": "数据模板", "href": "/assets/data-templates"},
            ],
        },
        {
            "key": "system_management",
            "label": "系统管理",
            "icon": "system_settings",
            "children": [
                {"key": "env_management", "label": "环境管理", "href": "/system/environments"},
                {"key": "node_management", "label": "节点管理", "href": "/system/nodes"},
                {"key": "integration_config", "label": "集成配置", "href": "/system/integrations"},
                {"key": "role_permissions", "label": "权限与角色", "href": "/system/roles"},
            ],
        },
    ]

    always_open_keys = {
        "case_center",
        "ai_generation",
        "execution_center",
        "quality_analysis",
        "asset_config",
        "system_management",
    }
    for section in nav_items:
        children = section.get("children")
        child_items: list[dict[str, Any]] = children if isinstance(children, list) else []
        section["active"] = section["key"] == current_key
        if child_items:
            child_active = False
            for child in child_items:
                child["active"] = child["key"] == current_key
                child_active = child_active or child["active"]
            section["active"] = section["active"] or child_active
            section["open"] = child_active or section["key"] in always_open_keys
        else:
            section["open"] = False
    return nav_items


def build_base_context(request: Request, current_key: str) -> dict[str, Any]:
    user_context = _resolve_request_user(request)
    return {
        "request": request,
        "platform_name": PLATFORM_NAME,
        "user_name": user_context["user_name"],
        "user_initial": user_context["user_initial"],
        "nav_sections": _navigation(current_key),
    }


def safe_next_path(value: str) -> str:
    candidate = str(value or "").strip()
    if not candidate.startswith("/"):
        return "/ai-generation"
    if candidate.startswith("//"):
        return "/ai-generation"
    return candidate


def render_template(
    request: Request,
    template_name: str,
    *,
    current_key: str,
    context: dict[str, Any] | None = None,
) -> HTMLResponse:
    template_context = build_base_context(request, current_key)
    if context:
        template_context.update(context)
    return templates.TemplateResponse(request, template_name, template_context)
