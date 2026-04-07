from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.services import ui_shell_service

router = APIRouter(tags=["ui"])

try:
    from app.routers.ui_assets_pages import router as ui_assets_pages_router
except Exception:  # pragma: no cover - compatibility for source-pruned environments
    ui_assets_pages_router = None

try:
    from app.routers.ui_governance_pages import router as ui_governance_pages_router
except Exception:  # pragma: no cover - compatibility for source-pruned environments
    ui_governance_pages_router = None

try:
    from app.routers.ui_operations_pages import router as ui_operations_pages_router
except Exception:  # pragma: no cover - compatibility for source-pruned environments
    ui_operations_pages_router = None


def _render(
    request: Request,
    template_name: str,
    *,
    current_key: str,
    page_title: str,
    page_description: str,
    breadcrumbs: list[str],
    extra_context: dict[str, object] | None = None,
) -> HTMLResponse:
    context: dict[str, object] = {
        "page_title": page_title,
        "page_description": page_description,
        "breadcrumbs": breadcrumbs,
    }
    if extra_context:
        context.update(extra_context)
    return ui_shell_service.render_template(
        request,
        template_name,
        current_key=current_key,
        context=context,
    )


@router.get("/", response_class=HTMLResponse)
@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request) -> HTMLResponse:
    return _render(
        request,
        "dashboard.html",
        current_key="dashboard",
        page_title="仪表盘",
        page_description="聚焦平台概览、本周重点和待处理事项，把当前最值得团队先处理的问题放在同一个首页里。",
        breadcrumbs=["首页", "仪表盘"],
    )


@router.get("/cases", response_class=HTMLResponse)
@router.get("/assets/cases", response_class=HTMLResponse)
def cases_page(request: Request) -> HTMLResponse:
    return _render(
        request,
        "cases.html",
        current_key="assets_cases",
        page_title="用例中心",
        page_description="统一浏览、筛选、治理和导出测试用例。",
        breadcrumbs=["资产中心", "用例中心"],
    )


@router.get("/cases/review", response_class=HTMLResponse)
@router.get("/assets/cases/review", response_class=HTMLResponse)
def cases_review_page(request: Request) -> HTMLResponse:
    return _render(
        request,
        "cases.html",
        current_key="assets_cases_review",
        page_title="用例审核",
        page_description="聚焦 AI 生成草稿与待审核用例，请在列表中筛选后处理。",
        breadcrumbs=["资产中心", "用例审核"],
    )


@router.get("/assets/cases/{case_id}", response_class=HTMLResponse)
def case_detail_page(request: Request, case_id: str) -> HTMLResponse:
    return _render(
        request,
        "case_detail.html",
        current_key="assets_cases",
        page_title=f"用例详情 · {case_id}",
        page_description="查看用例详情、执行历史、版本差异与关联缺陷。",
        breadcrumbs=["资产中心", "用例中心", "用例详情"],
        extra_context={"case_id": case_id},
    )


@router.get("/execution/workbench", response_class=HTMLResponse)
@router.get("/workbench", response_class=HTMLResponse)
def workbench_page(request: Request) -> HTMLResponse:
    return _render(
        request,
        "workbench.html",
        current_key="execution_records",
        page_title="执行工作台",
        page_description="单用例调试、运行、日志追踪与失败复盘。",
        breadcrumbs=["执行中心", "执行工作台"],
    )


@router.get("/ai-generation", response_class=HTMLResponse)
@router.get("/workbench/generate", response_class=HTMLResponse)
def generation_page(request: Request) -> HTMLResponse:
    return _render(
        request,
        "workbench_generate.html",
        current_key="ai_orchestration",
        page_title="AI 生成",
        page_description="基于 URL/PRD/API/用户故事生成候选 Draft。",
        breadcrumbs=["AI 编排", "AI 生成"],
    )


@router.get("/ai-generation/history", response_class=HTMLResponse)
@router.get("/workbench/history", response_class=HTMLResponse)
@router.get("/execution/runs", response_class=HTMLResponse)
def generation_history_page(request: Request) -> HTMLResponse:
    return _render(
        request,
        "workbench_history.html",
        current_key="execution_records",
        page_title="操作历史",
        page_description="查看生成、审核、门禁和自愈等关键动作的历史记录。",
        breadcrumbs=["执行中心", "操作历史"],
    )


@router.get("/execution/results", response_class=HTMLResponse)
@router.get("/report", response_class=HTMLResponse)
def report_overview_page(request: Request) -> HTMLResponse:
    return _render(
        request,
        "report_overview.html",
        current_key="execution_records",
        page_title="执行结果总览",
        page_description="汇总最近执行结果、失败聚类与关键趋势。",
        breadcrumbs=["执行中心", "执行结果", "总览"],
    )


@router.get("/execution/results/failures", response_class=HTMLResponse)
@router.get("/report/failures", response_class=HTMLResponse)
def report_failures_page(request: Request) -> HTMLResponse:
    return _render(
        request,
        "report_failures.html",
        current_key="execution_records",
        page_title="失败详情",
        page_description="查看失败样本、证据状态和缺陷关联情况。",
        breadcrumbs=["执行中心", "执行结果", "失败详情"],
    )


@router.get("/execution/results/context", response_class=HTMLResponse)
@router.get("/report/context", response_class=HTMLResponse)
def report_context_page(request: Request) -> HTMLResponse:
    return _render(
        request,
        "report_context.html",
        current_key="execution_records",
        page_title="资产与集成上下文",
        page_description="展示执行环境、构建信息与上下文数据。",
        breadcrumbs=["执行中心", "执行结果", "资产与集成"],
    )


@router.get("/execution/results/performance", response_class=HTMLResponse)
@router.get("/report/performance", response_class=HTMLResponse)
def report_performance_page(request: Request) -> HTMLResponse:
    return _render(
        request,
        "report_performance.html",
        current_key="execution_records",
        page_title="性能耗时",
        page_description="查看执行耗时分布、慢用例与性能指标。",
        breadcrumbs=["执行中心", "执行结果", "性能耗时"],
    )


@router.get("/execution/results/allure", response_class=HTMLResponse)
@router.get("/report/allure", response_class=HTMLResponse)
def report_allure_page(request: Request) -> HTMLResponse:
    return _render(
        request,
        "report_allure.html",
        current_key="execution_records",
        page_title="Allure 报告",
        page_description="查看 Allure 报告入口和快照信息。",
        breadcrumbs=["执行中心", "执行结果", "Allure 报告"],
    )


@router.get("/quality/trends", response_class=HTMLResponse)
@router.get("/quality/flaky", response_class=HTMLResponse)
@router.get("/quality/failure-clusters", response_class=HTMLResponse)
@router.get("/quality/clusters", response_class=HTMLResponse)
@router.get("/quality/gates", response_class=HTMLResponse)
@router.get("/gate", response_class=HTMLResponse)
@router.get("/defects", response_class=HTMLResponse)
@router.get("/executions/plans", response_class=HTMLResponse)
@router.get("/assets/test-points", response_class=HTMLResponse)
@router.get("/assets/cases/versions", response_class=HTMLResponse)
@router.get("/settings/roles", response_class=HTMLResponse)
@router.get("/ai/prompt-management", response_class=HTMLResponse)
def placeholder_page(request: Request) -> HTMLResponse:
    path = request.url.path
    return _render(
        request,
        "page.html",
        current_key="dashboard",
        page_title="功能页建设中",
        page_description="当前环境已恢复主链路页面，复杂治理页面正在补齐后端契约与稳定性。",
        breadcrumbs=["平台", "功能页"],
        extra_context={
            "active_filters": [
                {"label": "当前路径", "value": path},
                {"label": "说明", "value": "可先从仪表盘、用例中心、AI 生成、执行工作台与报告页进入。"},
            ]
        },
    )


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str = "/ai-generation") -> HTMLResponse:
    return ui_shell_service.templates.TemplateResponse(
        request,
        "login.html",
        {
            "request": request,
            "platform_name": ui_shell_service.PLATFORM_NAME,
            "next_path": ui_shell_service.safe_next_path(next),
        },
    )


if ui_assets_pages_router is not None:
    router.include_router(ui_assets_pages_router)
if ui_operations_pages_router is not None:
    router.include_router(ui_operations_pages_router)
if ui_governance_pages_router is not None:
    router.include_router(ui_governance_pages_router)
