from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.test_case import TestCase, TestCaseExecution

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(tags=["ui"])

PLATFORM_NAME = "企业AI测试平台"
DEFAULT_USER_NAME = "Admin"
DEFAULT_USER_INITIAL = "A"


def _navigation(current_key: str) -> list[dict[str, Any]]:
    nav_items = [
        {"key": "dashboard", "label": "仪表盘", "icon": "dashboard", "href": "/"},
        {
            "key": "assets",
            "label": "测试资产",
            "icon": "assets",
            "children": [
                {"key": "cases", "label": "用例库", "href": "/assets/cases"},
                {"key": "page_objects", "label": "页面对象", "href": "/assets/page-objects"},
                {"key": "api_contracts", "label": "API契约", "href": "/assets/api-contracts"},
                {"key": "data_templates", "label": "数据模板", "href": "/assets/data-templates"},
                {"key": "tag_management", "label": "标签管理", "href": "/assets/tags"},
            ],
        },
        {
            "key": "ai_orchestration",
            "label": "AI编排",
            "icon": "ai_orchestration",
            "children": [
                {"key": "workbench", "label": "工作台", "href": "/workbench"},
                {"key": "workbench_generate", "label": "生成用例", "href": "/workbench/generate"},
                {"key": "workbench_history", "label": "操作历史", "href": "/workbench/history"},
            ],
        },
        {"key": "execution_records", "label": "执行记录", "icon": "execution_records", "href": "/executions"},
        {
            "key": "quality_analysis",
            "label": "质量分析",
            "icon": "quality_analysis",
            "children": [
                {"key": "flaky", "label": "Flaky分析", "href": "/quality/flaky"},
                {"key": "failure_clusters", "label": "失败聚类", "href": "/quality/clusters"},
                {"key": "trend_analysis", "label": "趋势分析", "href": "/quality/trends"},
            ],
        },
        {"key": "gate_config", "label": "门禁配置", "icon": "gate_config", "href": "/gate"},
        {
            "key": "system_settings",
            "label": "系统设置",
            "icon": "system_settings",
            "children": [
                {"key": "env_management", "label": "环境管理", "href": "/settings/environments"},
                {"key": "node_management", "label": "节点管理", "href": "/settings/nodes"},
                {"key": "integration_config", "label": "集成配置", "href": "/settings/integrations"},
            ],
        },
    ]

    for section in nav_items:
        children = section.get("children") or []
        section["active"] = section["key"] == current_key
        if children:
            child_active = False
            for child in children:
                child["active"] = child["key"] == current_key
                child_active = child_active or child["active"]
            section["active"] = section["active"] or child_active
            section["open"] = child_active or section["key"] in {"assets", "quality_analysis", "system_settings", "ai_orchestration"}
        else:
            section["open"] = False
    return nav_items


def _base_context(request: Request, current_key: str) -> dict[str, Any]:
    return {
        "request": request,
        "platform_name": PLATFORM_NAME,
        "user_name": DEFAULT_USER_NAME,
        "user_initial": DEFAULT_USER_INITIAL,
        "nav_sections": _navigation(current_key),
    }


def _render_page(
    request: Request,
    *,
    current_key: str,
    page_title: str,
    page_description: str,
    breadcrumbs: list[str],
) -> HTMLResponse:
    context = _base_context(request, current_key)
    context.update(
        {
            "page_title": page_title,
            "page_description": page_description,
            "breadcrumbs": breadcrumbs,
        }
    )
    return templates.TemplateResponse("page.html", context)


@router.get("/", response_class=HTMLResponse)
def dashboard_page(request: Request) -> HTMLResponse:
    context = _base_context(request, current_key="dashboard")
    context.update(
        {
            "page_title": "仪表盘",
            "page_description": "聚焦主分支质量风险、执行趋势、门禁状态与待处理问题。",
            "breadcrumbs": ["首页", "仪表盘"],
        }
    )
    return templates.TemplateResponse("dashboard.html", context)


@router.get("/assets/cases", response_class=HTMLResponse)
def asset_cases_page(request: Request) -> HTMLResponse:
    context = _base_context(request, current_key="cases")
    context.update(
        {
            "page_title": "测试资产 - 用例库",
            "page_description": "按产品线/模块管理测试用例，支持筛选、批量操作与引导式新建。",
            "breadcrumbs": ["首页", "测试资产", "用例库"],
        }
    )
    return templates.TemplateResponse("cases.html", context)


@router.get("/assets/cases/{case_id}", response_class=HTMLResponse)
def asset_case_detail_page(request: Request, case_id: int) -> HTMLResponse:
    context = _base_context(request, current_key="cases")
    context.update(
        {
            "page_title": f"用例详情 #{case_id}",
            "page_description": "查看与编辑脚本代码、关联缺陷、执行历史和版本对比。",
            "breadcrumbs": ["首页", "测试资产", "用例库", f"用例 #{case_id}"],
            "case_id": case_id,
        }
    )
    return templates.TemplateResponse("case_detail.html", context)


@router.get("/assets/page-objects", response_class=HTMLResponse)
def asset_page_objects_page(request: Request) -> HTMLResponse:
    return _render_page(
        request,
        current_key="page_objects",
        page_title="页面对象",
        page_description="维护页面元素映射和可复用动作，支撑稳定自动化执行。",
        breadcrumbs=["首页", "测试资产", "页面对象"],
    )


@router.get("/assets/api-contracts", response_class=HTMLResponse)
def asset_api_contracts_page(request: Request) -> HTMLResponse:
    return _render_page(
        request,
        current_key="api_contracts",
        page_title="API契约",
        page_description="统一管理 OpenAPI 与接口契约资产，支持变更追踪。",
        breadcrumbs=["首页", "测试资产", "API契约"],
    )


@router.get("/assets/data-templates", response_class=HTMLResponse)
def asset_data_templates_page(request: Request) -> HTMLResponse:
    return _render_page(
        request,
        current_key="data_templates",
        page_title="数据模板",
        page_description="维护稳定可复用的数据模板，支撑多场景回归生成。",
        breadcrumbs=["首页", "测试资产", "数据模板"],
    )


@router.get("/assets/tags", response_class=HTMLResponse)
def asset_tags_page(request: Request) -> HTMLResponse:
    return _render_page(
        request,
        current_key="tag_management",
        page_title="标签管理",
        page_description="统一标签体系，用于用例分层、治理和覆盖率分析。",
        breadcrumbs=["首页", "测试资产", "标签管理"],
    )


@router.get("/ai-orchestration", response_class=HTMLResponse)
def ai_orchestration_page() -> RedirectResponse:
    return RedirectResponse(url="/workbench", status_code=307)


@router.get("/workbench", response_class=HTMLResponse)
def workbench_page(request: Request) -> HTMLResponse:
    context = _base_context(request, current_key="workbench")
    context.update(
        {
            "page_title": "AI编排 - 工作台",
            "page_description": "选择项目、生成/编辑 YAML、触发执行并在同页完成失败诊断。",
            "breadcrumbs": ["首页", "AI编排", "工作台"],
        }
    )
    return templates.TemplateResponse("workbench.html", context)


@router.get("/workbench/generate", response_class=HTMLResponse)
def workbench_generate_page(request: Request) -> HTMLResponse:
    context = _base_context(request, current_key="workbench_generate")
    context.update(
        {
            "page_title": "AI编排 - 生成用例",
            "page_description": "从需求生成 YAML 用例草稿，并可直接进入预览与编辑。",
            "breadcrumbs": ["首页", "AI编排", "生成用例"],
        }
    )
    return templates.TemplateResponse("workbench_generate.html", context)


@router.get("/workbench/preview", response_class=HTMLResponse)
def workbench_preview_page(request: Request) -> HTMLResponse:
    context = _base_context(request, current_key="workbench")
    context.update(
        {
            "page_title": "AI编排 - 用例预览",
            "page_description": "查看生成的 YAML 内容、调整关键字段并保存到资产库。",
            "breadcrumbs": ["首页", "AI编排", "用例预览"],
        }
    )
    return templates.TemplateResponse("workbench_preview.html", context)


@router.get("/workbench/history", response_class=HTMLResponse)
def workbench_history_page(request: Request) -> HTMLResponse:
    context = _base_context(request, current_key="workbench_history")
    context.update(
        {
            "page_title": "AI编排 - 操作历史",
            "page_description": "查看生成、运行、自愈与重跑等动作的时间线。",
            "breadcrumbs": ["首页", "AI编排", "操作历史"],
        }
    )
    return templates.TemplateResponse("workbench_history.html", context)


@router.get("/executions", response_class=HTMLResponse)
def execution_records_page(request: Request) -> HTMLResponse:
    return _render_page(
        request,
        current_key="execution_records",
        page_title="执行记录",
        page_description="查看任务执行过程、状态流转、日志与证据留痕。",
        breadcrumbs=["首页", "执行记录"],
    )


@router.get("/report", response_class=HTMLResponse)
def report_overview_page(request: Request) -> HTMLResponse:
    context = _base_context(request, current_key="execution_records")
    context.update(
        {
            "page_title": "测试报告 - 总览",
            "page_description": "聚合执行摘要、通过率、健康度与高风险失败。",
            "breadcrumbs": ["首页", "执行记录", "报告总览"],
        }
    )
    return templates.TemplateResponse("report_overview.html", context)


@router.get("/report/failures", response_class=HTMLResponse)
def report_failures_page(request: Request) -> HTMLResponse:
    context = _base_context(request, current_key="execution_records")
    context.update(
        {
            "page_title": "测试报告 - 失败详情",
            "page_description": "查看失败用例、证据与 AI 分析，并完成缺陷关联。",
            "breadcrumbs": ["首页", "执行记录", "失败详情"],
        }
    )
    return templates.TemplateResponse("report_failures.html", context)


@router.get("/report/context", response_class=HTMLResponse)
def report_context_page(request: Request) -> HTMLResponse:
    context = _base_context(request, current_key="execution_records")
    context.update(
        {
            "page_title": "测试报告 - 资产与集成",
            "page_description": "展示运行环境、版本信息与执行上下文。",
            "breadcrumbs": ["首页", "执行记录", "资产与集成"],
        }
    )
    return templates.TemplateResponse("report_context.html", context)


@router.get("/report/performance", response_class=HTMLResponse)
def report_performance_page(request: Request) -> HTMLResponse:
    context = _base_context(request, current_key="execution_records")
    context.update(
        {
            "page_title": "测试报告 - 性能耗时",
            "page_description": "关注平均耗时、最大耗时与慢用例 Top10。",
            "breadcrumbs": ["首页", "执行记录", "性能耗时"],
        }
    )
    return templates.TemplateResponse("report_performance.html", context)


@router.get("/report/allure", response_class=HTMLResponse)
def report_allure_page(request: Request) -> HTMLResponse:
    context = _base_context(request, current_key="execution_records")
    context.update(
        {
            "page_title": "测试报告 - Allure",
            "page_description": "查看完整 Allure 报告趋势和附件。",
            "breadcrumbs": ["首页", "执行记录", "Allure 报告"],
        }
    )
    return templates.TemplateResponse("report_allure.html", context)


@router.get("/quality/flaky", response_class=HTMLResponse)
def quality_flaky_page(request: Request) -> HTMLResponse:
    return _render_page(
        request,
        current_key="flaky",
        page_title="Flaky分析",
        page_description="识别不稳定用例，定位随机失败模式并评估治理优先级。",
        breadcrumbs=["首页", "质量分析", "Flaky分析"],
    )


@router.get("/quality/clusters", response_class=HTMLResponse)
def quality_clusters_page(request: Request) -> HTMLResponse:
    return _render_page(
        request,
        current_key="failure_clusters",
        page_title="失败聚类",
        page_description="按故障模式聚合失败结果，提升问题定位和修复效率。",
        breadcrumbs=["首页", "质量分析", "失败聚类"],
    )


@router.get("/quality/trends", response_class=HTMLResponse)
def quality_trends_page(request: Request) -> HTMLResponse:
    return _render_page(
        request,
        current_key="trend_analysis",
        page_title="趋势分析",
        page_description="持续观察质量趋势、发布风险与治理效果变化。",
        breadcrumbs=["首页", "质量分析", "趋势分析"],
    )


@router.get("/gate", response_class=HTMLResponse)
def gate_config_page(request: Request) -> HTMLResponse:
    return _render_page(
        request,
        current_key="gate_config",
        page_title="门禁配置",
        page_description="配置发布门禁规则和风险阈值，保障交付质量基线。",
        breadcrumbs=["首页", "门禁配置"],
    )


@router.get("/settings/environments", response_class=HTMLResponse)
def settings_environments_page(request: Request) -> HTMLResponse:
    return _render_page(
        request,
        current_key="env_management",
        page_title="环境管理",
        page_description="统一管理测试环境、基础地址和运行参数。",
        breadcrumbs=["首页", "系统设置", "环境管理"],
    )


@router.get("/settings/nodes", response_class=HTMLResponse)
def settings_nodes_page(request: Request) -> HTMLResponse:
    return _render_page(
        request,
        current_key="node_management",
        page_title="节点管理",
        page_description="管理执行节点状态与资源容量，提升调度稳定性。",
        breadcrumbs=["首页", "系统设置", "节点管理"],
    )


@router.get("/settings/integrations", response_class=HTMLResponse)
def settings_integrations_page(request: Request) -> HTMLResponse:
    return _render_page(
        request,
        current_key="integration_config",
        page_title="集成配置",
        page_description="对接代码仓、缺陷系统、通知渠道与外部测试服务。",
        breadcrumbs=["首页", "系统设置", "集成配置"],
    )


@router.get("/reports/{execution_id}", response_class=HTMLResponse)
def execution_report_page(request: Request, execution_id: int, db: Session = Depends(get_db)) -> HTMLResponse:
    execution = db.execute(select(TestCaseExecution).where(TestCaseExecution.id == execution_id)).scalar_one_or_none()
    if not execution:
        execution = db.execute(
            select(TestCaseExecution).where(
                or_(
                    TestCaseExecution.report_url == f"/reports/{execution_id}",
                    TestCaseExecution.report_url == f"/report/{execution_id}",
                    TestCaseExecution.report_url == f"report/{execution_id}",
                )
            )
        ).scalar_one_or_none()
    if not execution:
        raise HTTPException(status_code=404, detail="execution report not found")
    case = db.execute(select(TestCase).where(TestCase.id == execution.case_id)).scalar_one_or_none()
    context = _base_context(request, current_key="execution_records")
    context.update(
        {
            "page_title": f"执行报告 #{execution.id}",
            "page_description": "展示执行留痕、结果摘要和快速排障入口。",
            "breadcrumbs": ["首页", "执行记录", f"报告 #{execution.id}"],
            "report": {
                "execution_id": execution.id,
                "case_id": execution.case_id,
                "case_name": case.name if case else f"用例 #{execution.case_id}",
                "status": execution.status,
                "duration_ms": execution.duration_ms,
                "executed_at": execution.executed_at,
            },
        }
    )
    return templates.TemplateResponse("report_execution.html", context)


@router.get("/report/{execution_id}", include_in_schema=False, response_class=HTMLResponse)
def legacy_report_redirect(execution_id: int) -> RedirectResponse:
    return RedirectResponse(url=f"/reports/{execution_id}", status_code=307)

