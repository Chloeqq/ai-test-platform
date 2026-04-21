from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

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


@router.get("/", response_class=RedirectResponse)
@router.get("/dashboard", response_class=RedirectResponse)
def dashboard_page(request: Request) -> RedirectResponse:
    query = str(request.url.query or "").strip()
    suffix = f"?{query}" if query else ""
    return RedirectResponse(url=f"/react/dashboard{suffix}", status_code=307)


@router.get("/login", response_class=RedirectResponse)
def login_page(next: str = "/ai-generation") -> RedirectResponse:
    safe_next = ui_shell_service.safe_next_path(next)
    query = urlencode({"next": safe_next})
    return RedirectResponse(url=f"/react/login?{query}", status_code=307)


if ui_assets_pages_router is not None:
    router.include_router(ui_assets_pages_router)
if ui_operations_pages_router is not None:
    router.include_router(ui_operations_pages_router)
if ui_governance_pages_router is not None:
    router.include_router(ui_governance_pages_router)
