from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.routers.ui_assets_pages import router as ui_assets_pages_router
from app.routers.ui_governance_pages import router as ui_governance_pages_router
from app.routers.ui_operations_pages import router as ui_operations_pages_router
from app.services import ui_shell_service

router = APIRouter(tags=["ui"])
router.include_router(ui_assets_pages_router)
router.include_router(ui_operations_pages_router)
router.include_router(ui_governance_pages_router)


@router.get("/", response_class=HTMLResponse)
@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request) -> HTMLResponse:
    return ui_shell_service.render_template(
        request,
        "dashboard.html",
        current_key="dashboard",
        context={
            "page_title": "仪表盘",
            "page_description": "聚焦平台概览、本周重点和待处理事项，把当前最值得团队先处理的问题放在同一个首页里。",
            "breadcrumbs": ["首页", "仪表盘"],
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
