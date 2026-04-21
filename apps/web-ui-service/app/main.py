from contextlib import asynccontextmanager
import logging
import time
import uuid
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from fastapi import Depends as _Depends, FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from app.core.config import get_settings
from app.core.database import Base, engine
from app.core.redis_client import ping_redis
from app.core.security import get_current_user
from app.routers.auth import router as auth_router
from app.routers.dashboard import router as dashboard_router
from app.routers.health import router as health_router
from app.routers.page_objects import router as page_objects_router
from app.routers.page_objects_recorder import router as page_objects_recorder_router
from app.routers.test_cases import router as test_cases_router
from app.routers.test_projects import router as test_projects_router
from app.routers.workbench_assets import router as workbench_assets_router
from app.routers.workbench_gate import router as workbench_gate_router
from app.routers.workbench_generation import router as workbench_generation_router
from app.routers.workbench_reporting import router as workbench_reporting_router
from app.routers.workbench_reviews import router as workbench_reviews_router
from app.routers.workbench_runs import router as workbench_runs_router
from app.routers.workbench_scheduler import router as workbench_scheduler_router
from app.routers.workbench_tasks import router as workbench_tasks_router
from app.routers.ui import router as ui_router
from shared_backend.observability import configure_logging, set_request_id

settings = get_settings()
configure_logging(service_name="web-ui-service")
access_logger = logging.getLogger("web.access")
STATIC_DIR = Path(__file__).resolve().parent / "static"
DEVLIKE_APP_ENVS = {"dev", "development", "local", "test", "testing"}


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
    app.mount("/allure", StaticFiles(directory=str(ALLURE_DIR)), name="allure")
app.mount("/allure-snapshots", StaticFiles(directory=str(ALLURE_SNAPSHOTS_DIR)), name="allure-snapshots")

app.include_router(ui_router)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(dashboard_router, dependencies=_jwt_required)
app.include_router(workbench_assets_router, dependencies=_jwt_required)
app.include_router(workbench_gate_router, dependencies=_jwt_required)
app.include_router(workbench_generation_router, dependencies=_jwt_required)
app.include_router(workbench_reporting_router, dependencies=_jwt_required)
app.include_router(workbench_reviews_router, dependencies=_jwt_required)
app.include_router(workbench_runs_router, dependencies=_jwt_required)
app.include_router(workbench_scheduler_router, dependencies=_jwt_required)
app.include_router(workbench_tasks_router, dependencies=_jwt_required)
app.include_router(test_cases_router, dependencies=_jwt_required)
app.include_router(test_projects_router, dependencies=_jwt_required)
app.include_router(page_objects_router, dependencies=_jwt_required)
app.include_router(page_objects_recorder_router, dependencies=_jwt_required)


@app.middleware("http")
async def _disable_allure_cache(request: Request, call_next):  # type: ignore[no-untyped-def]
    request_id = str(request.headers.get("x-request-id", "")).strip() or str(uuid.uuid4())
    start = time.perf_counter()
    set_request_id(request_id)
    response: Response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers["X-Request-Id"] = request_id
    access_logger.info(
        "http_request method=%s path=%s status=%s duration_ms=%.2f client=%s",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        request.client.host if request.client else "-",
    )
    if request.url.path.startswith("/allure"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response
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

