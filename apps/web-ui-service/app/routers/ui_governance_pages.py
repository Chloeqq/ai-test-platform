from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.services import ui_shell_service, ui_static_management_page_service

router = APIRouter(tags=["ui"])


@router.get("/quality/flaky", response_class=HTMLResponse)
def quality_flaky_page(request: Request) -> HTMLResponse:
    return ui_shell_service.render_template(
        request,
        "quality_flaky.html",
        current_key="flaky",
        context={
            "page_title": "Flaky分析",
            "page_description": "识别不稳定任务、风险重叠和建议动作，把治理注意力集中到最容易反复波动的区域。",
            "breadcrumbs": ["首页", "质量分析", "Flaky分析"],
            "active_filters": ui_shell_service.build_active_filters(
                request,
                {
                    "page": "页面",
                    "module": "模块",
                    "source_type": "来源类型",
                    "changed_area": "变更域",
                },
            ),
        },
    )


@router.get("/quality/failure-clusters", response_class=HTMLResponse)
@router.get("/quality/clusters", include_in_schema=False, response_class=HTMLResponse)
def quality_clusters_page(request: Request) -> HTMLResponse:
    return ui_shell_service.render_template(
        request,
        "quality_clusters.html",
        current_key="failure_clusters",
        context={
            "page_title": "失败聚类",
            "page_description": "按故障模式聚合失败结果，提升问题定位和修复效率。",
            "breadcrumbs": ["首页", "质量分析", "失败聚类"],
            "active_filters": ui_shell_service.build_active_filters(
                request,
                {
                    "keyword": "关键词",
                    "alert_code": "门禁告警码",
                    "page": "门禁页面",
                    "queue": "队列",
                    "failure_class": "故障类",
                    "severity": "严重级别",
                    "manual_review": "仅人工复核",
                    "cluster_id": "聚类",
                    "sort": "排序",
                },
            ),
        },
    )


@router.get("/quality/trends", response_class=HTMLResponse)
def quality_trends_page(request: Request) -> HTMLResponse:
    return ui_shell_service.render_template(
        request,
        "quality_trends.html",
        current_key="trend_analysis",
        context={
            "page_title": "趋势分析",
            "page_description": "持续观察质量趋势、发布风险、strict manifest 状态和治理压力变化，让团队知道接下来该先处理什么。",
            "breadcrumbs": ["首页", "质量分析", "趋势分析"],
            "active_filters": ui_shell_service.build_active_filters(
                request,
                {
                    "view": "视图",
                    "direction": "趋势方向",
                    "window": "时间窗口",
                    "alert_code": "门禁告警码",
                },
            ),
        },
    )


@router.get("/quality/gates", response_class=HTMLResponse)
@router.get("/gate", include_in_schema=False, response_class=HTMLResponse)
def gate_config_page(request: Request) -> HTMLResponse:
    return ui_shell_service.render_template(
        request,
        "gate_console.html",
        current_key="gate_config",
        context={
            "page_title": "执行门禁管理",
            "page_description": "把执行门禁配置、最近阻断、人工决策和审批历史放到同一个治理工作台里。",
            "breadcrumbs": ["首页", "质量分析", "质量门禁"],
        },
    )


@router.get("/defects", response_class=HTMLResponse)
def defects_page(request: Request) -> HTMLResponse:
    return ui_shell_service.render_template(
        request,
        "defects.html",
        current_key="defects",
        context={
            "page_title": "缺陷管理",
            "page_description": "统一查看缺陷关联、最近执行和失败上下文，把平台内的质量问题闭环真正串起来。",
            "breadcrumbs": ["首页", "质量分析", "缺陷管理"],
            "active_filters": ui_shell_service.build_active_filters(
                request,
                {
                    "case_id": "用例",
                    "defect_id": "缺陷编号",
                    "system": "缺陷系统",
                },
            ),
        },
    )


@router.get("/settings/scheduler", response_class=HTMLResponse)
def scheduler_page(request: Request) -> HTMLResponse:
    return ui_shell_service.render_template(
        request,
        "scheduler.html",
        current_key="scheduler",
        context={
            "page_title": "调度中心",
            "page_description": "从 queue pressure、环境池、资源画像到 dispatch lane，统一观察平台当前调度状态和推荐动作。",
            "breadcrumbs": ["首页", "系统管理", "调度中心"],
        },
    )


@router.get("/system/environments", response_class=HTMLResponse)
@router.get("/settings/environments", include_in_schema=False, response_class=HTMLResponse)
def settings_environments_page(request: Request) -> HTMLResponse:
    return ui_shell_service.render_management_console(
        request,
        current_key="env_management",
        **ui_static_management_page_service.get_console_payload("env_management"),
    )


@router.get("/system/nodes", response_class=HTMLResponse)
@router.get("/settings/nodes", include_in_schema=False, response_class=HTMLResponse)
def settings_nodes_page(request: Request) -> HTMLResponse:
    return ui_shell_service.render_management_console(
        request,
        current_key="node_management",
        **ui_static_management_page_service.get_console_payload("node_management"),
    )


@router.get("/system/integrations", response_class=HTMLResponse)
@router.get("/settings/integrations", include_in_schema=False, response_class=HTMLResponse)
def settings_integrations_page(request: Request) -> HTMLResponse:
    return ui_shell_service.render_management_console(
        request,
        current_key="integration_config",
        **ui_static_management_page_service.get_console_payload("integration_config"),
    )


@router.get("/system/roles", response_class=HTMLResponse)
@router.get("/settings/roles", include_in_schema=False, response_class=HTMLResponse)
def settings_roles_page(request: Request) -> HTMLResponse:
    return ui_shell_service.render_management_console(
        request,
        current_key="role_permissions",
        page_title="权限与角色",
        page_description="集中管理平台角色、页面权限和操作范围，让治理动作与执行动作的边界更清晰。",
        page_responsibility="本页唯一职责：查看角色列表和选中角色的权限明细，不承担用户目录或登录流程的复杂操作。",
        breadcrumbs=["首页", "系统管理", "权限与角色"],
        left_heading="角色列表",
        left_items=[
            {"title": "平台管理员", "meta": "拥有系统配置与治理全量权限", "badge": "Admin"},
            {"title": "QA 负责人", "meta": "拥有审核、门禁、计划治理权限", "badge": "Lead"},
            {"title": "执行工程师", "meta": "拥有执行与调试权限", "badge": "Engineer"},
        ],
        detail_panels=[
            {
                "title": "权限边界",
                "description": "角色页只负责权限查看与配置，不与执行、生成或资产编辑混在一起。",
                "bullets": ["区分查看、编辑、审核、发布权限", "保留角色修改审计日志", "后续接入成员与角色绑定"],
            }
        ],
        primary_action={"label": "查看环境管理", "href": "/system/environments"},
    )
