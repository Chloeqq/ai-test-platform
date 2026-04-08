from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.services import ui_shell_service, ui_static_management_page_service

router = APIRouter(tags=["ui"])


@router.get("/cases", response_class=HTMLResponse)
@router.get("/assets/cases", include_in_schema=False, response_class=HTMLResponse)
def asset_cases_page(request: Request) -> HTMLResponse:
    return ui_shell_service.render_template(
        request,
        "cases.html",
        current_key="cases",
        context={
            "page_title": "用例中心",
            "page_description": "围绕用例列表、审核、版本和标签治理，统一管理平台内的测试用例资产。",
            "breadcrumbs": ["首页", "用例中心", "用例列表"],
        },
    )


@router.get("/cases/review", response_class=HTMLResponse)
@router.get("/assets/cases/review", include_in_schema=False, response_class=HTMLResponse)
def asset_cases_review_page(request: Request) -> HTMLResponse:
    return ui_shell_service.render_management_console(
        request,
        current_key="case_reviews",
        page_title="待审核用例",
        page_description="集中处理需要人工复核的新增、变更和 AI 生成用例，避免审核入口散落在多个页面中。",
        page_responsibility="本页唯一职责：查看待审核用例队列，并在右侧完成审核判断与下一步动作选择。",
        breadcrumbs=["首页", "用例中心", "待审核用例"],
        left_heading="待审核队列",
        left_items=[
            {"title": "商品列表筛选基础回归", "meta": "状态：Draft · 来源：AI 生成", "badge": "待初审"},
            {"title": "退货申请必填校验", "meta": "状态：Review · 来源：人工编辑", "badge": "待复核"},
            {"title": "订单查询异常提示", "meta": "状态：Review · 来源：历史迁移", "badge": "需补说明"},
        ],
        detail_panels=[
            {
                "title": "审核职责",
                "description": "审核页不承载生成和执行，只负责判断当前版本是否进入下一状态。",
                "bullets": ["查看版本差异和上下文", "补充审核意见与责任人", "决定继续 Draft、提交 Review 或转入 Ready"],
            },
            {
                "title": "后续接入",
                "description": "下一步会接入真实待审核队列、版本摘要和审计日志。",
                "bullets": ["按页面、模块、来源筛选", "展示标题与脚本差异", "保留 trace_id 与审计链路"],
            },
        ],
        primary_action={"label": "进入用例列表", "href": "/cases"},
        secondary_action={"label": "查看用例版本", "href": "/cases/versions"},
    )


@router.get("/cases/versions", response_class=HTMLResponse)
@router.get("/assets/cases/versions", include_in_schema=False, response_class=HTMLResponse)
def asset_cases_versions_page(request: Request) -> HTMLResponse:
    return ui_shell_service.render_management_console(
        request,
        current_key="case_versions",
        page_title="用例版本",
        page_description="聚焦用例版本演进、变更摘要与回滚入口，避免把版本治理混入日常编辑页。",
        page_responsibility="本页唯一职责：查看版本链路和选中版本的变更摘要，并进入对比与回滚判断。",
        breadcrumbs=["首页", "用例中心", "用例版本"],
        left_heading="版本链路",
        left_items=[
            {"title": "atp-web-prodlist-list-sm-ai-0001", "meta": "v3 · 最近变更：筛选断言增强", "badge": "最新"},
            {"title": "atp-web-ret-query-rg-ai-0001", "meta": "v2 · 最近变更：标题规范化", "badge": "可对比"},
            {"title": "atp-web-ord-list-rg-imp-0001", "meta": "v5 · 最近变更：迁移导入", "badge": "历史"},
        ],
        detail_panels=[
            {
                "title": "版本治理",
                "description": "Ready 版本不可直接覆盖，所有修改都应形成新版本并保留审计。",
                "bullets": ["查看版本号、变更人和变更摘要", "进入版本对比与差异查看", "在明确风险后执行回滚或继续演进"],
            }
        ],
        primary_action={"label": "返回用例列表", "href": "/cases"},
    )


@router.get("/assets/test-points", response_class=HTMLResponse)
def test_point_assets_page(request: Request) -> HTMLResponse:
    return ui_shell_service.render_template(
        request,
        "test_point_assets.html",
        current_key="test_point_assets",
        context={
            "page_title": "测试点资产",
            "page_description": "把测试点资产、覆盖状态、追溯矩阵和门禁准备度真正可视化，方便治理与回归决策。",
            "breadcrumbs": ["首页", "资产与配置", "测试点资产"],
            "active_filters": ui_shell_service.build_active_filters(
                request,
                {
                    "page": "页面",
                    "keyword": "关键词",
                    "source_type": "来源类型",
                    "coverage_status": "覆盖状态",
                    "review_status": "评审状态",
                    "gate_decision": "门禁决策",
                    "selection_state": "选择状态",
                },
            ),
        },
    )


@router.get("/cases/tags", response_class=HTMLResponse)
@router.get("/assets/tags", include_in_schema=False, response_class=HTMLResponse)
def asset_tags_page(request: Request) -> HTMLResponse:
    return ui_shell_service.render_management_console(
        request,
        current_key="tag_management",
        **ui_static_management_page_service.get_console_payload("tag_management"),
    )


@router.get("/cases/{case_id}", response_class=HTMLResponse)
@router.get("/assets/cases/{case_id}", include_in_schema=False, response_class=HTMLResponse)
def asset_case_detail_page(request: Request, case_id: str) -> HTMLResponse:
    return ui_shell_service.render_template(
        request,
        "case_detail.html",
        current_key="cases",
        context={
            "page_title": f"用例详情 · {case_id}",
            "page_description": "查看与编辑脚本代码、关联缺陷、执行历史和版本对比。",
            "breadcrumbs": ["首页", "用例中心", "用例列表", f"用例 {case_id}"],
            "case_id": case_id,
        },
    )


@router.get("/assets/test-points/{asset_id}", response_class=HTMLResponse)
def test_point_asset_detail_page(request: Request, asset_id: str) -> HTMLResponse:
    return ui_shell_service.render_template(
        request,
        "test_point_asset_detail.html",
        current_key="test_point_assets",
        context={
            "page_title": f"测试点资产详情 · {asset_id}",
            "page_description": "查看单个测试点资产的语义、评审、门禁、运行和追溯状态，帮助团队快速判断是否可直接纳入回归。",
            "breadcrumbs": ["首页", "资产与配置", "测试点资产", asset_id],
            "asset_id": asset_id,
        },
    )


@router.get("/assets/test-points/{asset_id}/matrix", response_class=HTMLResponse)
def test_point_coverage_matrix_page(request: Request, asset_id: str) -> HTMLResponse:
    return ui_shell_service.render_template(
        request,
        "test_point_coverage_matrix.html",
        current_key="test_point_assets",
        context={
            "page_title": f"覆盖矩阵 · {asset_id}",
            "page_description": "从 source ids、intent ids 到 point keys 和 gap/orphan 状态，直接检查测试点追溯是否完整。",
            "breadcrumbs": ["首页", "资产与配置", "测试点资产", asset_id, "覆盖矩阵"],
            "asset_id": asset_id,
            "active_filters": ui_shell_service.build_active_filters(
                request,
                {
                    "traceability_status": "追溯状态",
                    "changed_area": "变更域",
                    "orphan_only": "仅孤儿点位",
                },
            ),
        },
    )


@router.get("/assets/page-objects", response_class=HTMLResponse)
def asset_page_objects_page(request: Request) -> HTMLResponse:
    return ui_shell_service.render_template(
        request,
        "page_objects.html",
        current_key="page_objects",
        context={
            "page_title": "页面对象",
            "page_description": "统一维护页面对象与元素，保障执行链路可复用。",
            "breadcrumbs": ["首页", "资产与配置", "页面对象"],
        },
    )


@router.get("/assets/page-objects/recorder", response_class=HTMLResponse)
def asset_page_objects_recorder_page(request: Request) -> HTMLResponse:
    return ui_shell_service.render_template(
        request,
        "page_object_recorder.html",
        current_key="page_objects_recorder",
        context={
            "page_title": "页面对象录制",
            "page_description": "前端发起录制会话，后端托管 Playwright codegen，停止后自动解析并入库 page + element。",
            "breadcrumbs": ["首页", "资产与配置", "页面对象", "页面录制"],
        },
    )


@router.get("/assets/api-contracts", response_class=HTMLResponse)
def asset_api_contracts_page(request: Request) -> HTMLResponse:
    return ui_shell_service.render_management_console(
        request,
        current_key="api_contracts",
        **ui_static_management_page_service.get_console_payload("api_contracts"),
    )


@router.get("/assets/data-templates", response_class=HTMLResponse)
def asset_data_templates_page(request: Request) -> HTMLResponse:
    return ui_shell_service.render_management_console(
        request,
        current_key="data_templates",
        **ui_static_management_page_service.get_console_payload("data_templates"),
    )
