import json
import logging
import stat
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends as _Depends
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.database import Base, engine
from app.core.security import get_current_user
from app.routers.auth import router as auth_router
from app.routers.dashboard import router as dashboard_router
from app.routers.health import router as health_router
from app.routers.page_objects import router as page_objects_router
from app.routers.page_objects_candidates import router as page_objects_candidates_router
from app.routers.page_objects_elements import router as page_objects_elements_router
from app.routers.page_objects_recorder import router as page_objects_recorder_router
from app.routers.quality_dashboard_api import router as quality_dashboard_router
from app.routers.quality_eval_api import router as quality_eval_router
from app.routers.test_cases import router as test_cases_router
from app.routers.test_data_pools import router as test_data_pools_router
from app.routers.test_projects import router as test_projects_router
from app.routers.ui import router as ui_router
from app.routers.workbench_assets import router as workbench_assets_router
from app.routers.workbench_assets_cases import router as workbench_assets_cases_router
from app.routers.workbench_gate import router as workbench_gate_router
from app.routers.workbench_generation import router as workbench_generation_router
from app.routers.workbench_reporting import router as workbench_reporting_router
from app.routers.workbench_reviews import router as workbench_reviews_router
from app.routers.workbench_runs import router as workbench_runs_router
from app.routers.workbench_scheduler import router as workbench_scheduler_router
from app.routers.atp_api import router as atp_api_router
from app.routers.workbench_tasks import router as workbench_tasks_router
from app.services.workbench_reporting_service import inject_allure_branding
from shared_backend.observability import (
    configure_logging,
    set_request_id,
    summarize_http_context,
    summarize_log_value,
)

settings = get_settings()
configure_logging(service_name="web-ui-service")
access_logger = logging.getLogger("web.access")
STATIC_DIR = Path(__file__).resolve().parent / "static"
DEVLIKE_APP_ENVS = {"dev", "development", "local", "test", "testing"}


class BrandedAllureStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):  # type: ignore[no-untyped-def]
        if str(path or "").endswith(".html"):
            full_path, stat_result = self.lookup_path(path)
            if stat_result is not None and stat.S_ISREG(stat_result.st_mode):
                html = Path(full_path).read_text(encoding="utf-8")
                return HTMLResponse(inject_allure_branding(html))
        return await super().get_response(path, scope)


def _preview_request_payload(body: bytes, content_type: str) -> str:
    if not body:
        return ""
    text = body.decode("utf-8", errors="ignore").strip()
    if not text:
        return ""
    if "application/json" in str(content_type or "").lower():
        try:
            return summarize_log_value(json.loads(text))
        except Exception:
            return text[:2000]
    return text[:2000]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _assert_safe_startup_config()
    if _is_dev_like_env() and settings.database_auto_create_tables:
        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="FastAPI backend skeleton with SQLite and JWT authentication.",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
ALLURE_DIR = Path(__file__).resolve().parents[3] / "runners" / "web-playwright-python" / "allure-report"
ALLURE_SNAPSHOTS_DIR = Path(__file__).resolve().parents[3] / "runners" / "web-playwright-python" / "allure-report-snapshots"
ALLURE_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
_jwt_required = [_Depends(get_current_user)]

if ALLURE_DIR.exists():
    app.mount("/allure", BrandedAllureStaticFiles(directory=str(ALLURE_DIR)), name="allure")
app.mount("/allure-snapshots", BrandedAllureStaticFiles(directory=str(ALLURE_SNAPSHOTS_DIR)), name="allure-snapshots")

app.include_router(ui_router)
app.include_router(health_router)
app.include_router(atp_api_router)  # no JWT: public analysis endpoint
app.include_router(auth_router)
app.include_router(dashboard_router, dependencies=_jwt_required)
app.include_router(workbench_assets_router, dependencies=_jwt_required)
app.include_router(workbench_assets_cases_router, dependencies=_jwt_required)
app.include_router(workbench_gate_router, dependencies=_jwt_required)
app.include_router(workbench_generation_router, dependencies=_jwt_required)
app.include_router(workbench_reporting_router, dependencies=_jwt_required)
app.include_router(workbench_reviews_router, dependencies=_jwt_required)
app.include_router(workbench_runs_router, dependencies=_jwt_required)
app.include_router(workbench_scheduler_router, dependencies=_jwt_required)
app.include_router(workbench_tasks_router, dependencies=_jwt_required)
app.include_router(quality_dashboard_router, dependencies=_jwt_required)
app.include_router(quality_eval_router, dependencies=_jwt_required)
app.include_router(test_cases_router, dependencies=_jwt_required)
app.include_router(test_data_pools_router, dependencies=_jwt_required)
app.include_router(test_projects_router, dependencies=_jwt_required)
app.include_router(page_objects_router, dependencies=_jwt_required)
app.include_router(page_objects_candidates_router, dependencies=_jwt_required)
app.include_router(page_objects_elements_router, dependencies=_jwt_required)
app.include_router(page_objects_recorder_router, dependencies=_jwt_required)


@app.middleware("http")
async def _disable_allure_cache(request: Request, call_next):  # type: ignore[no-untyped-def]
    request_id = str(request.headers.get("x-request-id", "")).strip() or str(uuid.uuid4())
    start = time.perf_counter()
    set_request_id(request_id)
    body = await request.body()
    payload_preview = _preview_request_payload(body, request.headers.get("content-type", ""))

    async def _receive() -> dict[str, object]:
        return {"type": "http.request", "body": body, "more_body": False}

    request._receive = _receive  # type: ignore[attr-defined]
    access_logger.info(
        "http_request_start %s",
        summarize_http_context(
            method=request.method,
            path=request.url.path,
            query=request.url.query,
            client=request.client.host if request.client else "-",
            request_id=request_id,
            payload=payload_preview,
        ),
    )
    try:
        response: Response = await call_next(request)
    except Exception:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        access_logger.exception(
            "http_request_error %s",
            summarize_http_context(
                method=request.method,
                path=request.url.path,
                query=request.url.query,
                client=request.client.host if request.client else "-",
                request_id=request_id,
                duration_ms=duration_ms,
            ),
        )
        raise
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers["X-Request-Id"] = request_id
    access_logger.info(
        "http_request_end %s",
        summarize_http_context(
            method=request.method,
            path=request.url.path,
            query=request.url.query,
            client=request.client.host if request.client else "-",
            request_id=request_id,
            status_code=response.status_code,
            duration_ms=duration_ms,
        ),
    )
    if request.url.path.startswith("/allure"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.exception_handler(RequestValidationError)
async def _handle_request_validation_error(request: Request, exc: RequestValidationError):
    access_logger.warning(
        "http_request_validation_error %s",
        summarize_http_context(
            method=request.method,
            path=request.url.path,
            query=request.url.query,
            client=request.client.host if request.client else "-",
            request_id=str(request.headers.get("x-request-id", "")).strip() or "-",
            status_code=422,
            error=exc.errors(),
        ),
    )
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(HTTPException)
async def _handle_http_exception(request: Request, exc: HTTPException):
    level = logging.WARNING if exc.status_code < 500 else logging.ERROR
    access_logger.log(
        level,
        "http_request_http_exception %s",
        summarize_http_context(
            method=request.method,
            path=request.url.path,
            query=request.url.query,
            client=request.client.host if request.client else "-",
            request_id=str(request.headers.get("x-request-id", "")).strip() or "-",
            status_code=exc.status_code,
            error=exc.detail,
        ),
    )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def _handle_unexpected_exception(request: Request, exc: Exception):
    request_id = str(request.headers.get("x-request-id", "")).strip() or "-"
    access_logger.exception(
        "http_request_unhandled_exception %s",
        summarize_http_context(
            method=request.method,
            path=request.url.path,
            query=request.url.query,
            client=request.client.host if request.client else "-",
            request_id=request_id,
            status_code=500,
            error=exc,
        ),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error", "request_id": request_id},
    )
def _is_dev_like_env() -> bool:
    return str(settings.app_env).strip().lower() in DEVLIKE_APP_ENVS


def _assert_safe_startup_config() -> None:
    if _is_dev_like_env():
        return

    problems: list[str] = []
    jwt_secret_key = str(settings.jwt_secret_key or "").strip()
    if not jwt_secret_key or jwt_secret_key == "dev-jwt-secret-change-me":
        problems.append("JWT_SECRET_KEY")
    if bool(settings.database_auto_create_tables):
        problems.append("DATABASE_AUTO_CREATE_TABLES")
    if not str(settings.page_surface_login_url or "").strip():
        problems.append("PAGE_SURFACE_LOGIN_URL")

    if problems:
        raise RuntimeError(
            "unsafe bootstrap configuration for non-development environment: "
            + ", ".join(problems)
        )
