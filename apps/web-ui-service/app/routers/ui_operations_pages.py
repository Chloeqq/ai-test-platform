from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.test_case import TestCase, TestCaseExecution
from app.services import ui_shell_service

router = APIRouter(tags=["ui"])


@router.get("/ai-orchestration", response_class=HTMLResponse)
def ai_orchestration_page() -> RedirectResponse:
    return RedirectResponse(url="/ai-generation", status_code=307)


@router.get("/execution/workbench", response_class=HTMLResponse)
@router.get("/workbench", include_in_schema=False, response_class=HTMLResponse)
def workbench_page(request: Request) -> HTMLResponse:
    return ui_shell_service.render_template(
        request,
        "workbench.html",
        current_key="workbench",
        context={
            "page_title": "调试工作台",
            "page_description": "用于高级调试、YAML 精修、失败复现和快速重跑，不再作为默认新手入口。",
            "breadcrumbs": ["首页", "执行中心", "调试工作台"],
        },
    )


@router.get("/execution/workbench/{case_id}", include_in_schema=False, response_class=HTMLResponse)
def execution_workbench_case_page(case_id: str) -> RedirectResponse:
    return RedirectResponse(url=f"/execution/workbench?case_id={case_id}", status_code=307)


@router.get("/ai-generation", response_class=HTMLResponse)
@router.get("/workbench/generate", include_in_schema=False, response_class=HTMLResponse)
def workbench_generate_page(request: Request) -> HTMLResponse:
    return ui_shell_service.render_template(
        request,
        "workbench_generate.html",
        current_key="workbench_generate",
        context={
            "page_title": "AI生成 - 生成用例",
            "page_description": "通过分步式向导输入来源、确认范围和高级参数，再统一预览与提交生成结果。",
            "breadcrumbs": ["首页", "AI生成", "生成用例"],
        },
    )


@router.get("/ai-generation/preview", response_class=RedirectResponse)
@router.get("/workbench/preview", include_in_schema=False, response_class=RedirectResponse)
def workbench_preview_page() -> RedirectResponse:
    return RedirectResponse(url="/ai-generation?step=3", status_code=307)


@router.get("/ai-generation/history", response_class=HTMLResponse)
@router.get("/workbench/history", include_in_schema=False, response_class=HTMLResponse)
def workbench_history_page(request: Request) -> HTMLResponse:
    return ui_shell_service.render_template(
        request,
        "workbench_history.html",
        current_key="workbench_history",
        context={
            "page_title": "AI生成 - 生成历史",
            "page_description": "查看生成、预览、保存、自愈与重跑等动作时间线，帮助我们回放生成链路。",
            "breadcrumbs": ["首页", "AI生成", "生成历史"],
            "active_filters": ui_shell_service.build_active_filters(
                request,
                {
                    "project_code": "项目",
                    "keyword": "关键词",
                    "action": "动作",
                    "status": "状态",
                    "risk_gate_decision": "风险门禁",
                    "self_healing_status": "自愈状态",
                    "actor": "确认人",
                    "sort": "排序",
                },
            ),
        },
    )


@router.get("/ai-generation/prompts", response_class=HTMLResponse)
@router.get("/ai/prompt-management", include_in_schema=False, response_class=HTMLResponse)
def prompt_management_page(request: Request) -> HTMLResponse:
    return ui_shell_service.render_management_console(
        request,
        current_key="prompt_management",
        page_title="Prompt 管理",
        page_description="集中查看提示词版本、模型配置和 fallback 说明，把高级 AI 参数从生成主流程中折叠出来。",
        page_responsibility="本页唯一职责：管理 Prompt 版本与模型配置；它是高级入口，不承担直接生成动作。",
        breadcrumbs=["首页", "AI生成", "Prompt 管理"],
        left_heading="Prompt 列表",
        left_items=[
            {"title": "requirement-parser.prompt.v3", "meta": "适用：需求解析 · 模型：主模型", "badge": "默认"},
            {"title": "test-design.prompt.v2", "meta": "适用：测试设计 · 模型：主模型", "badge": "已发布"},
            {"title": "fallback.generate.v1", "meta": "适用：生成兜底 · 模型：fallback", "badge": "备用"},
        ],
        detail_panels=[
            {
                "title": "高级参数默认折叠",
                "description": "Prompt、model 和 fallback 都属于高级治理参数，不应直接铺在生成主入口里。",
                "bullets": ["查看 prompt_version、model、fallback", "关联 trace_id 与审计链路", "后续接入版本发布与回滚"],
            }
        ],
        primary_action={"label": "返回生成用例", "href": "/ai-generation"},
    )


@router.get("/execution/plans", response_class=HTMLResponse)
@router.get("/executions/plans", include_in_schema=False, response_class=HTMLResponse)
def execution_plans_page(request: Request) -> HTMLResponse:
    return ui_shell_service.render_management_console(
        request,
        current_key="execution_plans",
        page_title="测试计划",
        page_description="围绕回归范围、执行计划和依赖关系安排执行，而不是把计划与运行结果混在一个页面里。",
        page_responsibility="本页唯一职责：查看测试计划列表和选中计划的范围、依赖、排队与调度建议。",
        breadcrumbs=["首页", "执行中心", "测试计划"],
        left_heading="计划列表",
        left_items=[
            {"title": "发布前回归计划 - 订单链路", "meta": "范围：订单 / 退货 / 支付", "badge": "待执行"},
            {"title": "日常烟测计划 - 商品中心", "meta": "范围：商品列表 / 新增商品", "badge": "循环任务"},
            {"title": "缺陷回归计划 - 搜索筛选", "meta": "范围：搜索 / 筛选 / 排序", "badge": "需确认"},
        ],
        detail_panels=[
            {
                "title": "计划详情",
                "description": "计划页只负责定义与查看计划，不直接承载运行详情。",
                "bullets": ["展示计划范围、目标环境和执行策略", "查看依赖任务与幂等键", "跳转执行任务与执行结果"],
            }
        ],
        primary_action={"label": "查看执行任务", "href": "/execution/runs"},
        secondary_action={"label": "查看执行结果", "href": "/execution/results"},
    )


@router.get("/execution/runs", response_class=HTMLResponse)
@router.get("/executions", include_in_schema=False, response_class=HTMLResponse)
def execution_records_page(request: Request) -> HTMLResponse:
    return ui_shell_service.render_template(
        request,
        "execution_runs.html",
        current_key="execution_records",
        context={
            "page_title": "执行中心 - 执行任务",
            "page_description": "查看任务执行过程、状态流转、证据健康与治理风险，并围绕当前筛选条件继续排查。",
            "breadcrumbs": ["首页", "执行中心", "执行任务"],
            "active_filters": ui_shell_service.build_active_filters(
                request,
                {
                    "project_code": "项目",
                    "keyword": "关键词",
                    "risk_levels": "风险级别",
                    "traceability_gap": "追溯缺口",
                    "changed_area": "变更影响",
                    "status": "状态",
                    "queue_status": "队列状态",
                    "source": "来源",
                    "evidence_health_status": "证据健康",
                    "strict_mode_status": "Strict-mode",
                    "retry_enabled": "重试能力",
                    "has_dependencies": "依赖关系",
                    "sort": "排序",
                },
            ),
        },
    )


@router.get("/execution/results", response_class=HTMLResponse)
@router.get("/report", include_in_schema=False, response_class=HTMLResponse)
def report_overview_page(request: Request) -> HTMLResponse:
    return ui_shell_service.render_template(
        request,
        "report_overview.html",
        current_key="report_overview",
        context={
            "page_title": "执行中心 - 执行结果",
            "page_description": "聚合执行摘要、通过率、健康度与高风险失败，帮助我们从任务进入结果分析。",
            "breadcrumbs": ["首页", "执行中心", "执行结果"],
        },
    )


@router.get("/execution/results/failures", response_class=HTMLResponse)
@router.get("/report/failures", include_in_schema=False, response_class=HTMLResponse)
def report_failures_page(request: Request) -> HTMLResponse:
    return ui_shell_service.render_template(
        request,
        "report_failures.html",
        current_key="report_overview",
        context={
            "page_title": "测试报告 - 失败详情",
            "page_description": "查看失败用例、证据与 AI 分析，并完成缺陷关联。",
            "breadcrumbs": ["首页", "执行中心", "执行结果", "失败详情"],
        },
    )


@router.get("/execution/results/context", response_class=HTMLResponse)
@router.get("/report/context", include_in_schema=False, response_class=HTMLResponse)
def report_context_page(request: Request) -> HTMLResponse:
    return ui_shell_service.render_template(
        request,
        "report_context.html",
        current_key="report_overview",
        context={
            "page_title": "测试报告 - 资产与集成",
            "page_description": "展示运行环境、版本信息与执行上下文。",
            "breadcrumbs": ["首页", "执行中心", "执行结果", "资产与集成"],
        },
    )


@router.get("/execution/results/performance", response_class=HTMLResponse)
@router.get("/report/performance", include_in_schema=False, response_class=HTMLResponse)
def report_performance_page(request: Request) -> HTMLResponse:
    return ui_shell_service.render_template(
        request,
        "report_performance.html",
        current_key="report_overview",
        context={
            "page_title": "测试报告 - 性能耗时",
            "page_description": "关注平均耗时、最大耗时与慢用例 Top10。",
            "breadcrumbs": ["首页", "执行中心", "执行结果", "性能耗时"],
        },
    )


@router.get("/execution/results/allure", response_class=HTMLResponse)
@router.get("/report/allure", include_in_schema=False, response_class=HTMLResponse)
def report_allure_page(request: Request) -> HTMLResponse:
    return ui_shell_service.render_template(
        request,
        "report_allure.html",
        current_key="report_overview",
        context={
            "page_title": "测试报告 - Allure",
            "page_description": "查看完整 Allure 报告趋势和附件。",
            "breadcrumbs": ["首页", "执行中心", "执行结果", "Allure 报告"],
        },
    )


@router.get("/execution/results/{execution_id}", response_class=HTMLResponse)
@router.get("/reports/{execution_id}", include_in_schema=False, response_class=HTMLResponse)
def execution_report_page(
    request: Request,
    execution_id: int,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    execution = db.execute(
        select(TestCaseExecution).where(TestCaseExecution.id == execution_id)
    ).scalar_one_or_none()
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

    case = db.execute(
        select(TestCase).where(TestCase.id == execution.case_id)
    ).scalar_one_or_none()
    return ui_shell_service.render_template(
        request,
        "report_execution.html",
        current_key="execution_records",
        context={
            "page_title": f"执行报告 #{execution.id}",
            "page_description": "展示执行留痕、结果摘要和快速排障入口。",
            "breadcrumbs": ["首页", "执行记录", f"报告 #{execution.id}"],
            "report": {
                "execution_id": execution.id,
                "case_id": execution.case_id,
                "case_name": case.name if case else f"用例 ID {execution.case_id}",
                "status": execution.status,
                "duration_ms": execution.duration_ms,
                "executed_at": execution.executed_at,
            },
        },
    )


@router.get("/report/{execution_id}", include_in_schema=False, response_class=HTMLResponse)
def legacy_report_redirect(execution_id: int) -> RedirectResponse:
    return RedirectResponse(url=f"/reports/{execution_id}", status_code=307)
